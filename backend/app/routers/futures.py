"""
期货行情路由 - Phase 7
数据源：akshare futures_zh_realtime（国内期货） + Sina hf_（国际商品）
缓存策略：3 分钟 TTL，后台异步刷新

Phase B: 统一 API 响应格式
"""
import logging
import asyncio
import re
import threading
import time
from datetime import datetime
from fastapi import APIRouter
import httpx
from app.utils.response import success_response, error_response, ErrorCode
from app.services.data_cache import get_cache

logger = logging.getLogger(__name__)
router = APIRouter()

_cache = get_cache()
NAMESPACE = "futures:"
TTL = 180  # 3 minutes
_CACHE_LOCK = threading.RLock()
_LAST_FETCH_TIME = 0
_REFRESH_SEM = threading.Semaphore(1)

# Module-level cache for test compatibility (initialized by _init_mock_cache)
_FUTURES_CACHE = {}

# 重点监控的国内商品期货合约
WATCHED_COMMODITIES = {
    # (symbol, name, unit)
    "RB0": ("螺纹钢",   "元/吨"),
    "HC0": ("热卷",     "元/吨"),
    "I0":  ("铁矿石",   "元/吨"),
    "JM0": ("焦煤",     "元/吨"),
    "J0":  ("焦炭",     "元/吨"),
    "SC0": ("原油",     "元/桶"),
    "FU0": ("燃油",     "元/吨"),
    "TA0": ("PTA",      "元/吨"),
    "MA0": ("甲醇",     "元/吨"),
    "V0":  ("PVC",      "元/吨"),
    "UR0": ("尿素",     "元/吨"),
    "EG0": ("乙二醇",   "元/吨"),
    "PP0": ("聚丙烯",   "元/吨"),
    "LC0": ("碳酸锂",   "元/吨"),
    "SA0": ("纯碱",     "元/吨"),
}

# 板块映射：symbol → (板块名, emoji)
COMMODITY_SECTORS = {
    "RB0": ("黑色建材", "🔨"),
    "HC0": ("黑色建材", "🔨"),
    "I0":  ("黑色建材", "🔨"),
    "JM0": ("黑色建材", "🔨"),
    "J0":  ("黑色建材", "🔨"),
    "SC0": ("能源化工", "⚡"),
    "FU0": ("能源化工", "⚡"),
    "TA0": ("能源化工", "⚡"),
    "MA0": ("能源化工", "⚡"),
    "V0":  ("能源化工", "⚡"),
    "UR0": ("能源化工", "⚡"),
    "EG0": ("能源化工", "⚡"),
    "PP0": ("能源化工", "⚡"),
    "LC0": ("新能源",   "🔋"),
    "SA0": ("新能源",   "🔋"),
}

SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (compatible; AlphaTerminal/1.0)",
}


async def _fetch_index_futures_realtime():
    """
    Fetch real-time index futures data from akshare.
    Returns tuple: (index_futures_list, source_str)
    """
    import akshare as ak
    import warnings
    warnings.filterwarnings("ignore")
    
    index_futures = []
    source = "mock"
    
    # Define contracts to fetch: (symbol, name, akshare_symbol_name)
    contracts = [
        ("IF", "IF 沪深300", "沪深300指数期货"),
        ("IC", "IC 中证500", "中证500指数期货"),
        ("IM", "IM 中证1000", "中证1000"),
    ]
    
    for symbol, name, ak_symbol_name in contracts:
        try:
            # Use asyncio.wait_for for 5 second timeout
            df = await asyncio.wait_for(
                asyncio.to_thread(ak.futures_zh_realtime, symbol=ak_symbol_name),
                timeout=5.0
            )
            
            if df is not None and len(df) > 0:
                # Get the main contract (first row, symbol ends with 0)
                main_row = df[df['symbol'].str.endswith('0')].iloc[0] if len(df[df['symbol'].str.endswith('0')]) > 0 else df.iloc[0]
                
                price = main_row.get("trade", 0)
                change_pct = main_row.get("changepercent", 0)
                position = main_row.get("position", 0)
                
                # Format position
                if position:
                    pos_val = float(position)
                    if pos_val >= 10000:
                        pos_str = f"{pos_val/10000:.1f}万手"
                    else:
                        pos_str = f"{int(pos_val)}手"
                else:
                    pos_str = "N/A"
                
                index_futures.append({
                    "symbol": symbol,
                    "name": name,
                    "price": round(float(price), 2) if price else 0,
                    "change_pct": round(float(change_pct), 2) if change_pct else 0,
                    "position": pos_str,
                    "note": f"IM{symbol}",
                })
                source = "real"
                logger.info(f"[Futures] Fetched real data for {symbol}: price={price}")
        except asyncio.TimeoutError:
            logger.warning(f"[Futures] Timeout fetching {symbol}")
        except Exception as e:
            logger.warning(f"[Futures] Failed to fetch {symbol}: {e}")
    
    # Fallback to mock if all failed
    if not index_futures:
        logger.warning("[Futures] All index futures fetch failed, using mock data")
        index_futures = _MOCK_INDEX_FUTURES
        source = "mock"
    elif len(index_futures) < 3:
        # If we got some but not all, add mock data for missing ones
        logger.warning(f"[Futures] Only fetched {len(index_futures)} futures, adding mock for missing")
        fetched_symbols = [f["symbol"] for f in index_futures]
        for mock in _MOCK_INDEX_FUTURES:
            if mock["symbol"] not in fetched_symbols:
                index_futures.append(mock)
    
    return index_futures, source


def _fetch_futures_data():
    """后台抓取期货数据（腾讯 qt.gtimg.cn + akshare，5秒超时兜底Mock）"""
    global _LAST_FETCH_TIME
    now_str = datetime.now().strftime("%H:%M")
    spot_data = {}
    fetch_success = False
    index_source = "mock"

    try:
        # 腾讯 qt.gtimg.cn 国内期货现货（直连不过代理）
        codes = ",".join(WATCHED_COMMODITIES.keys())
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"https://qt.gtimg.cn/q={codes}")
                resp.raise_for_status()
                raw = resp.text
            for line in raw.splitlines():
                line = line.strip()
                if "=" not in line or "none_match" in line:
                    continue
                try:
                    sym = line.split("=")[0].replace("v_qt_", "").replace("v_", "").strip('" ')
                    fields = line.split("=")[1].strip('";\n')
                    f = [x.strip() for x in fields.split(",")]
                    if len(f) > 10:
                        price  = float(f[1]) if f[1] else None
                        change = float(f[32]) if f[32] else 0.0  # 涨跌幅%
                        spot_data[sym] = {
                            "price": round(price, 2) if price else 0,
                            "change_pct": round(change, 2),
                            "tick": f[30] if len(f) > 30 else "",
                        }
                except Exception:
                    continue
            logger.info(f"[Futures] Tencent qt data: {len(spot_data)} items")
            if len(spot_data) > 0:
                fetch_success = True
        except Exception as e:
            logger.warning(f"[Futures] Tencent fetch failed: {e}")

    except Exception as e:
        logger.warning(f"[Futures] overall fetch failed: {e}")

    # 如果腾讯数据获取失败，使用 Mock 数据作为 fallback
    if not fetch_success or len(spot_data) == 0:
        logger.warning("[Futures] Using mock commodity data as fallback")
        # 使用 Mock 商品数据的 price/change_pct
        for mock_item in _MOCK_COMMODITIES:
            spot_data[mock_item["symbol"]] = {
                "price": mock_item.get("price", 0),
                "change_pct": mock_item.get("change_pct", 0),
                "tick": mock_item.get("tick", ""),
            }

    # 整理商品期货列表
    commodities = []
    for sym, (name, unit) in WATCHED_COMMODITIES.items():
        d = spot_data.get(sym, {})
        sector_key = COMMODITY_SECTORS.get(sym, ("其他", "📦"))
        commodities.append({
            "symbol":     sym,
            "name":       name,
            "unit":       unit,
            "price":      d.get("price", 0),
            "change_pct": d.get("change_pct", 0),
            "tick":       d.get("tick", ""),
            "sector":     sector_key[0],
            "sector_emoji": sector_key[1],
        })

    # Fetch real index futures data (synchronously in thread)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            index_futures, index_source = loop.run_until_complete(_fetch_index_futures_realtime())
        finally:
            loop.close()
    except Exception as e:
        logger.warning(f"[Futures] Index futures fetch failed: {e}, using mock")
        index_futures = _MOCK_INDEX_FUTURES
        index_source = "mock"

    cache_data = {
        "index_futures": index_futures,
        "commodities":   commodities,
        "update_time":   now_str,
        "index_source":  index_source,
    }
    _cache.set(f"{NAMESPACE}main", cache_data, ttl=TTL)
    with _CACHE_LOCK:
        _LAST_FETCH_TIME = time.time()
    logger.info(f"[Futures] cached {len(commodities)} commodities + {len(index_futures)} index futures (source: {index_source})")


def _get_futures_cache() -> dict:
    """TTL 3分钟；过期则后台刷新，返回旧缓存（绝不阻塞）"""
    global _LAST_FETCH_TIME
    stale = (time.time() - _LAST_FETCH_TIME) > TTL

    if stale and _REFRESH_SEM.acquire(blocking=False):
        def bg():
            try:
                _fetch_futures_data()
            finally:
                _REFRESH_SEM.release()
        t = threading.Thread(target=bg, daemon=True, name="futures-refresh")
        t.start()

    cached = _cache.get(f"{NAMESPACE}main")
    return cached if cached else {}


@router.get("/futures/index_history")
async def futures_index_history(symbol: str = "IF", period: str = "daily", limit: int = 200):
    """
    股指期货历史K线数据
    
    参数:
      symbol: 品种代码 (IF/IC/IM)
      period: 周期 (daily/1min/5min/15min/30min/60min)
      limit: 返回条数 (默认200)
    
    返回:
      symbol: 品种代码
      history: K线数据 [{date, open, close, high, low, volume, hold}]
    """
    # 验证品种代码
    valid_symbols = ["IF", "IC", "IM"]
    if symbol.upper() not in valid_symbols:
        logger.warning(f"[futures_index_history] Invalid symbol: {symbol}")
        return success_response({
            "symbol": symbol.upper(),
            "history": [],
            "message": f"暂不支持品种: {symbol}，支持: {', '.join(valid_symbols)}"
        })
    
    symbol = symbol.upper()
    
    try:
        import akshare as ak
        import warnings
        warnings.filterwarnings("ignore")
        
        # 主力合约代码（加0后缀）
        contract_symbol = f"{symbol}0"
        
        # 根据周期选择API
        if period == "daily":
            # 日线数据
            df = await asyncio.wait_for(
                asyncio.to_thread(ak.futures_zh_daily_sina, symbol=contract_symbol),
                timeout=10.0
            )
        else:
            # 分钟数据
            df = await asyncio.wait_for(
                asyncio.to_thread(ak.futures_zh_minute_sina, symbol=contract_symbol),
                timeout=10.0
            )
        
        # 处理数据
        history = []
        if df is not None and not df.empty:
            # 重命名列（akshare返回的列名可能不同）
            df = df.rename(columns={
                'date': 'date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume',
                'hold': 'hold',
                'open_interest': 'hold',
                '持仓量': 'hold',
            })
            
            # 取最后 limit 条
            df = df.tail(limit)
            
            for _, row in df.iterrows():
                try:
                    item = {
                        "date": str(row.get("date", "")),
                        "open": float(row.get("open", 0)) if row.get("open") else 0,
                        "close": float(row.get("close", 0)) if row.get("close") else 0,
                        "high": float(row.get("high", 0)) if row.get("high") else 0,
                        "low": float(row.get("low", 0)) if row.get("low") else 0,
                        "volume": int(row.get("volume", 0)) if row.get("volume") else 0,
                        "hold": int(row.get("hold", 0)) if row.get("hold") else 0,
                    }
                    history.append(item)
                except Exception as e:
                    logger.debug(f"[futures_index_history] Skip row: {e}")
                    continue
        
        logger.info(f"[futures_index_history] {symbol}({period}): {len(history)} bars")
        return success_response({
            "symbol": symbol,
            "period": period,
            "history": history,
        })
        
    except asyncio.TimeoutError:
        logger.warning(f"[futures_index_history] Timeout for {symbol}")
        return success_response({
            "symbol": symbol,
            "period": period,
            "history": [],
            "message": "数据获取超时，请稍后重试"
        })
    except Exception as e:
        logger.warning(f"[futures_index_history] Failed for {symbol}: {type(e).__name__}: {e}")
        return success_response({
            "symbol": symbol,
            "period": period,
            "history": [],
            "message": f"获取数据失败: {str(e)}"
        })


@router.get("/futures/main_indexes")
async def futures_main_indexes():
    """
    股指期货主力（IF · IC · IM）
    """
    try:
        cache = _get_futures_cache()
        return success_response({
            "index_futures": cache.get("index_futures", []),
            "update_time":  cache.get("update_time", ""),
            "source":       cache.get("index_source", "mock"),
        })
    except Exception as e:
        logger.error(f"[futures_main_indexes] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取股指期货失败: {str(e)}")


@router.get("/futures/commodities")
async def futures_commodities():
    """
    国内大宗商品期货实时行情
    """
    try:
        cache = _get_futures_cache()
        return success_response({
            "commodities": cache.get("commodities", []),
            "update_time": cache.get("update_time", ""),
        })
    except Exception as e:
        logger.error(f"[futures_commodities] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取大宗商品失败: {str(e)}")


@router.get("/futures/term_structure")
async def futures_term_structure(symbol: str = "RB"):
    """
    大宗商品期货期限结构（Forward Curve）

    参数:
      symbol: 品种代码，如 RB（螺纹钢）、I（铁矿石）、SC（原油）

    返回:
      symbol:         品种代码
      name:           中文名称
      term_structure:  各交割月合约列表，按月份升序
        - contract:  合约代码（如 RB2405）
        - month:     交割月（如 2405）
        - price:     最新价
        - oi:        持仓量（Open Interest）

    用途：
      - Contango（升水）：远月 > 近月，向上倾斜曲线 → 现货充足
      - Backwardation（贴水）：近月 > 远月，向下倾斜曲线 → 现货紧缺
    """
    # 去除数字和特殊字符，提取字母前缀
    prefix = re.sub(r'[^A-Za-z]', '', symbol).upper()
    if not prefix:
        return success_response(None, f"无效品种代码: {symbol}")

    # 从 WATCHED_COMMODITIES 反查中文名
    zh_name = None
    for sym_key, (name, _unit) in WATCHED_COMMODITIES.items():
        key_prefix = re.sub(r'[^A-Za-z]', '', sym_key).upper()
        if key_prefix == prefix:
            zh_name = name
            break

    if not zh_name:
        return error_response(ErrorCode.BAD_REQUEST, f"暂不支持品种: {prefix}，支持的品种见 /futures/commodities", {"symbol": prefix, "name": None, "term_structure": []})

    try:
        import akshare as ak, warnings
        warnings.filterwarnings("ignore")
        # 同步 IO 放入线程池，避免阻塞 FastAPI 事件循环
        # 添加 10 秒超时保护
        try:
            df = await asyncio.wait_for(
                asyncio.to_thread(ak.futures_zh_realtime, symbol=zh_name),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"[Futures] term_structure timeout for {prefix}")
            return error_response(ErrorCode.INTERNAL_ERROR, "数据源响应超时，请稍后重试", {
                "symbol": prefix,
                "name": zh_name,
                "term_structure": []
            })

        curves = []
        for _, row in df.iterrows():
            contract_sym = str(row.get("symbol", "")).strip()
            price = row.get("trade") if row.get("trade") is not None else row.get("最新价")
            vol   = row.get("volume") if row.get("volume") is not None else row.get("成交量")
            oi    = row.get("position") if row.get("position") is not None else row.get("持仓量", 0)

            try: price = float(price)
            except (TypeError, ValueError): price = None
            try: vol = float(vol)
            except (TypeError, ValueError): vol = None
            try: oi = float(oi) if oi is not None else 0.0
            except (TypeError, ValueError): oi = 0.0

            # 过滤僵尸合约（无成交量或无价格）
            if (vol is None or vol == 0) and (price is None or price == 0):
                continue
            if price is None or price <= 0:
                continue

            # 提取交割月数字：RB2405 → 2405
            try:
                month_match = re.search(r'\d+$', contract_sym)
                if not month_match:
                    continue
                month_code = month_match.group()
            except Exception:
                # AkShare 上游接口字段规则变动时，fail-safe 跳过该行
                continue

            curves.append({
                "contract": contract_sym.upper(),
                "month":    month_code,
                "price":    round(price, 2),
                "oi":       int(oi) if oi else 0,
            })

        if not curves:
            return error_response(ErrorCode.NOT_FOUND, f"品种 {prefix}({zh_name}) 暂无可用合约数据", {"symbol": prefix, "name": zh_name, "term_structure": []})

        # 按交割月升序排列
        curves = sorted(curves, key=lambda x: x["month"])

        logger.info(f"[Futures] term_structure {prefix}({zh_name}): {len(curves)} contracts")
        return success_response({
            "symbol": prefix,
            "name":   zh_name,
            "term_structure": curves,
        })

    except Exception as e:
        logger.warning(f"[Futures] term_structure failed for {prefix}: {type(e).__name__}: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取期限结构失败: {type(e).__name__}: {str(e)}", {"symbol": prefix, "name": zh_name, "term_structure": []})


# ── Mock 数据（仅作为 Fallback，确保服务稳定性）────────────────
# ⚠️ 注意：Mock 数据是备用数据源，不是主数据源
# 主数据源：akshare futures_zh_realtime（实时数据）
# 当主数据源失败时，Mock 数据确保 API 不返回空结果
# 请勿删除：用于启动初始化和网络异常时的降级处理
_MOCK_COMMODITIES = [
    {"symbol": "RB0", "name": "螺纹钢",   "unit": "元/吨", "price": 3850, "change_pct": +1.28, "tick": ""},
    {"symbol": "HC0", "name": "热卷",     "unit": "元/吨", "price": 3920, "change_pct": -0.54, "tick": ""},
    {"symbol": "SA0", "name": "纯碱",     "unit": "元/吨", "price": 1580, "change_pct": +3.21, "tick": ""},
    {"symbol": "LC0", "name": "碳酸锂",   "unit": "元/吨", "price": 78000, "change_pct": -2.17, "tick": ""},
    {"symbol": "I0",  "name": "铁矿石",   "unit": "元/吨", "price": 920,  "change_pct": +0.83, "tick": ""},
    {"symbol": "JM0", "name": "焦煤",     "unit": "元/吨", "price": 1380, "change_pct": +1.45, "tick": ""},
    {"symbol": "SC0", "name": "原油",     "unit": "元/桶", "price": 580,  "change_pct": -1.32, "tick": ""},
    {"symbol": "FU0", "name": "燃油",     "unit": "元/吨", "price": 3100, "change_pct": -0.78, "tick": ""},
    {"symbol": "TA0", "name": "PTA",      "unit": "元/吨", "price": 6810, "change_pct": +0.29, "tick": ""},
    {"symbol": "MA0", "name": "甲醇",     "unit": "元/吨", "price": 2580, "change_pct": +1.08, "tick": ""},
    {"symbol": "V0",  "name": "PVC",      "unit": "元/吨", "price": 6350, "change_pct": -0.21, "tick": ""},
    {"symbol": "UR0", "name": "尿素",     "unit": "元/吨", "price": 2180, "change_pct": +2.44, "tick": ""},
]

# 股指期货 Mock 数据（Fallback 用，请勿删除）
_MOCK_INDEX_FUTURES = [
    {"symbol": "IF",  "name": "IF 沪深300",   "price": 4448.2,  "change_pct": -0.93, "position": "8.2万手", "note": "IMIF"},
    {"symbol": "IC",  "name": "IC 中证500",   "price": 6102.4,  "change_pct": +0.31, "position": "6.5万手", "note": "IMIC"},
    {"symbol": "IM",  "name": "IM 中证1000",  "price": 6438.8,  "change_pct": +0.72, "position": "5.1万手", "note": "IMIM"},
]


def _init_mock_cache():
    global _LAST_FETCH_TIME, _FUTURES_CACHE
    now_str = datetime.now().strftime("%H:%M")
    cache_data = {
        "index_futures": _MOCK_INDEX_FUTURES,
        "commodities":   _MOCK_COMMODITIES,
        "update_time":   now_str,
        "index_source":  "mock",
    }
    _cache.set(f"{NAMESPACE}main", cache_data, ttl=TTL)
    _FUTURES_CACHE = cache_data
    with _CACHE_LOCK:
        _LAST_FETCH_TIME = time.time()
    logger.info("[Futures] Mock cache initialized")

_init_mock_cache()
