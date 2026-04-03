"""
市场数据接口 - Phase 7 + Phase 5
所有数据从 SQLite market_data_realtime 读取
宏观大宗商品（USD/CNH·黄金·WTI·VIX）由腾讯/Sina 实时接口抓取，10 分钟缓存
"""
import logging
import os
import re
import threading
import time
from datetime import datetime
from fastapi import APIRouter
import httpx
from app.db import get_latest_prices, get_price_history
from app.utils.market_status import is_market_open


logger = logging.getLogger(__name__)
router = APIRouter()

# ── Phase 7: 宏观大宗商品缓存（10 分钟 TTL）─────────────────────────────
os.environ.setdefault("HTTP_PROXY",  "http://192.168.1.50:7897")
os.environ.setdefault("HTTPS_PROXY", "http://192.168.1.50:7897")
os.environ.setdefault("http_proxy",  "http://192.168.1.50:7897")
os.environ.setdefault("https_proxy", "http://192.168.1.50:7897")

_MACRO_CACHE       = {}   # {symbol: {price, change_pct, name, unit, timestamp}}
_MACRO_CACHE_TTL  = 600  # 10 分钟（Phase 7 延长 TTL）
_MACRO_CACHE_LOCK  = threading.RLock()  # RLock 可重入
_LAST_FETCH_TIME   = 0   # 0 = immediately refresh on first call
_REFRESH_SEMAPHORE = threading.Semaphore(1)  # 防止并发刷新

SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (compatible; AlphaTerminal/1.0)",
}


def _fetch_from_sina(symbols: list[str]) -> dict[str, list]:
    """从 Sina HQ 和腾讯 qt 拉取多个标的，返回 {symbol: [fields...]}"""
    results = {}

    # 1) Sina HQ（外汇、黄金、原油）
    sina_syms = [s for s in symbols if s not in ("CNHUSD",)]
    if sina_syms:
        codes = ",".join(sina_syms)
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(
                    f"https://hq.sinajs.cn/list={codes}",
                    headers=SINA_HEADERS,
                )
                resp.raise_for_status()
                raw = resp.text
            for line in raw.splitlines():
                line = line.strip()
                if not line or "=" not in line:
                    continue
                try:
                    m = re.match(r'var hq_str_(\w+)="(.*?)"', line)
                    if m:
                        sym = m.group(1)
                        fields = [f.strip() for f in m.group(2).split(",")]
                        results[sym] = fields
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"[Macro] Sina fetch failed: {e}")

    # 2) 腾讯 qt（CNH/USD 汇率 + VHSI 恒指波指，不过代理）
    qt_syms = [s for s in symbols if s in ("CNHUSD", "hkVHSI")]
    if qt_syms:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(
                    f"https://qt.gtimg.cn/q={','.join(qt_syms)}",
                    headers={"Referer": "https://gu.qq.com", "User-Agent": "Mozilla/5.0"},
                )
                resp.raise_for_status()
                raw = resp.text
            for line in raw.splitlines():
                line = line.strip()
                if "none_match" in line or "=" not in line:
                    continue
                try:
                    sym = line.split("=")[0].replace("v_", "").strip('" \n')
                    # 腾讯 qt 格式: v_hkVHSI="100~港股~VHSI~27.850~29.220~..."
                    # 分隔符是 ~ 不是 ,
                    raw_val = line.split("=", 1)[1].strip('";\r\n ')
                    fields = raw_val.split("~")
                    results[sym] = [f.strip() for f in fields]
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"[Macro] Tencent qt fetch failed: {e}")

    return results


def _parse_cnyusd(data: dict) -> tuple[float, float, str]:
    """
    解析 CNYUSD，返回 (USDCNY, 涨跌幅%, 时间戳)
    Sina 格式: [时间, 中行汇买价, 钞买价, 汇卖价, ?, 汇买价2, 钞卖价2, 汇卖价2, 折算价, 货币名, 日期]
    中行汇买价 0.1452 ≈ 0.1452 USD per CNY → USDCNY = 1/0.1452 ≈ 6.887
    注意：Sina 数据可能有延迟，建议以央行中间价为准做参考
    """
    f = data.get("CNYUSD", [])
    if len(f) < 10:
        raise ValueError("CNYUSD data too short")
    price_usdpcny = float(f[1])   # USD per CNY (中行汇买价)
    prev          = float(f[2])   # 前一价格
    t             = f[0]
    pct           = ((price_usdpcny - prev) / prev * 100) if prev else 0.0
    usdcny        = round(1.0 / price_usdpcny, 4) if price_usdpcny else 7.25
    return usdcny, round(pct, 4), t


def _parse_hf_gold(data: dict) -> tuple[float, float, str]:
    """
    解析 hf_GC（上海金交易所 SGE 黄金现货，RMB/盎司）
    字段: [当前价, 涨跌%, 昨收, 开, 高, 低, 时间, 昨结算, ...]
    """
    f = data.get("hf_GC", [])
    if len(f) < 8:
        raise ValueError("hf_GC data too short")
    try:
        price = float(f[0])   # RMB/oz（SGE 现货金的报价单位）
        prev  = float(f[7])   # 昨结算 RMB/oz
        pct   = float(f[1]) if f[1] else (((price - prev) / prev * 100) if prev else 0.0)
        tick  = f[6] if len(f) > 6 else ""
    except Exception as e:
        raise ValueError(f"hf_GC parse error: {e}")
    return round(price, 2), round(pct, 2), tick


def _get_cnyusd_approx() -> float:
    """CNY/USD ≈ 7.25（固定估算，用于内部换算）"""
    return 7.25


def _parse_hkvhsi(data: dict) -> tuple[float, float, str]:
    """
    解析 hkVHSI（恒指波幅指数，腾讯 qt 格式，~分隔）
    f[3]=当前价, f[4]=昨收, f[30]=时间, f[31]=涨跌额, f[32]=涨跌幅%
    """
    f = data.get("hkVHSI", [])
    if len(f) < 33:
        raise ValueError("hkVHSI data too short")
    try:
        price = float(f[3])   # 当前 VHSI
        prev  = float(f[4])   # 昨收
        # f[32] = 涨跌幅%，f[31] = 涨跌额
        pct   = float(f[32]) if f[32] else (((price - prev) / prev * 100) if prev else 0.0)
        # f[30] = "2026/03/31 16:00:00"，提取时间部分
        tick  = f[30][-8:-3] if f[30] and len(f[30]) > 4 else ""  # "HH:MM"
    except Exception as e:
        raise ValueError(f"hkVHSI parse error: {e}")
    return round(price, 2), round(pct, 2), tick


def _parse_hf_cl(data: dict) -> tuple[float, float, str]:
    """
    解析 hf_CL（WTI 原油期货，USD/桶）
    字段: [当前价, 涨跌%, 昨收, 开, 高, 低, 时间, 昨结算, ...]
    """
    f = data.get("hf_CL", [])
    if len(f) < 8:
        raise ValueError("hf_CL data too short")
    try:
        price = float(f[0])   # USD/桶（WTI 期货报价）
        prev  = float(f[7])   # 昨结算
        pct   = float(f[1]) if f[1] else (((price - prev) / prev * 100) if prev else 0.0)
        tick  = f[6] if len(f) > 6 else ""
    except Exception as e:
        raise ValueError(f"hf_CL parse error: {e}")
    return round(price, 2), round(pct, 2), tick


def _fetch_macro_data():
    """
    Phase 7: 真实数据抓取（腾讯/Sina HQ）
    - USD/CNY: CNYUSD → 换算（Sina）
    - SGE黄金: Sina hf_GC → RMB/oz（上海金现货）
    - WTI原油: Sina hf_CL → USD/桶
    - VHSI: 恒指波幅指数（腾讯 qt hkVHSI）
    """
    global _MACRO_CACHE, _LAST_FETCH_TIME
    now_str = datetime.now().strftime("%H:%M")

    # 初始化默认值（静态兜底）
    usdcny_price = 6.8871; usdcny_pct = 0.0
    gold_price = 4720.0; gold_pct = 0.0
    wti_price = 101.0; wti_pct = 0.0
    vhsi_price = 20.0; vhsi_pct = 0.0

    try:
        # 一次性拉取所有需要的数据
        raw = _fetch_from_sina(["CNYUSD", "hf_GC", "hf_CL", "hkVHSI"])

        usdcnh_price = 7.2531
        usdcnh_pct   = 0.0
        gold_price   = 3318.40
        gold_pct     = 0.0
        wti_price    = 68.92
        wti_pct      = 0.0
        fetched = False

        if "CNYUSD" in raw and raw["CNYUSD"]:
            try:
                usdcny_price, usdcny_pct, _ = _parse_cnyusd(raw)
                fetched = True
            except Exception as e:
                logger.warning(f"[Macro] CNYUSD parse error: {e}")

        if "hf_GC" in raw and raw["hf_GC"]:
            try:
                gold_price, gold_pct, _ = _parse_hf_gold(raw)
                fetched = True
            except Exception as e:
                logger.warning(f"[Macro] GOLD parse error: {e}")

        if "hf_CL" in raw and raw["hf_CL"]:
            try:
                wti_price, wti_pct, _ = _parse_hf_cl(raw)
                fetched = True
            except Exception as e:
                logger.warning(f"[Macro] WTI parse error: {e}")

        if "hkVHSI" in raw and raw["hkVHSI"]:
            try:
                vhsi_price, vhsi_pct, _ = _parse_hkvhsi(raw)
                logger.info(f"[Macro] VHSI fetched: {vhsi_price} ({vhsi_pct}%)")
            except Exception as e:
                logger.warning(f"[Macro] VHSI parse error: {e}")

        results = {
            "USD/CNY": {"name": "美元/离岸人民币", "price": round(usdcny_price, 4), "unit": "",    "change_pct": round(usdcny_pct, 4),  "timestamp": now_str},
            "GOLD":    {"name": "SGE黄金(人民币)",  "price": round(gold_price, 2),   "unit": "¥/oz","change_pct": round(gold_pct, 2),  "timestamp": now_str},
            "WTI":     {"name": "WTI原油(美元)",    "price": round(wti_price, 2),    "unit": "$/桶","change_pct": round(wti_pct, 2),   "timestamp": now_str},
            "VHSI":    {"name": "恒指波幅(VHSI)",   "price": round(vhsi_price, 2),    "unit": "",     "change_pct": round(vhsi_pct, 2),  "timestamp": now_str},
        }

        with _MACRO_CACHE_LOCK:
            _MACRO_CACHE = results
            _LAST_FETCH_TIME = time.time()
        logger.info(f"[Macro] Fetched: USD={usdcny_price} GOLD={gold_price}¥ WTI={wti_price} VHSI={vhsi_price}({vhsi_pct}%)")

    except Exception as e:
        logger.warning(f"[Macro] Fetch failed, keeping old cache: {e}")
        # 保持旧缓存不变，不抛异常


def _get_macro_data() -> dict:
    """
    返回宏观缓存（TTL 10 分钟）。
    缓存空或过期时：立即返回旧缓存，同时后台触发一次异步刷新（绝不阻塞 API）。
    """
    global _MACRO_CACHE, _LAST_FETCH_TIME
    stale = not _MACRO_CACHE or (time.time() - _LAST_FETCH_TIME) > _MACRO_CACHE_TTL

    if stale and _REFRESH_SEMAPHORE.acquire(blocking=False):
        # 立即返回旧缓存（避免阻塞），后台刷新
        def bg():
            try:
                _fetch_macro_data()
            finally:
                _REFRESH_SEMAPHORE.release()
        t = threading.Thread(target=bg, daemon=True, name="macro-refresh")
        t.start()

    with _MACRO_CACHE_LOCK:
        return dict(_MACRO_CACHE) if _MACRO_CACHE else {}


@router.get("/market/macro")
async def market_macro():
    """
    Phase 5: 宏观核心数据（USD/CNH · COMEX黄金 · WTI原油 · VIX恐慌指数）
    5 分钟 TTL 缓存，不阻塞 API 响应
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "macro": list(_get_macro_data().values()),
    }

# ── 风向标指数（Task 2: 精简 overview，只保留核心风向标）─────────────────
WIND_SYMBOLS = ["000001", "000300", "399001", "399006", "HSI", "IXIC"]  # 上证 · 沪深300 · 深证 · 创业板 · 恒生 · 纳斯达克
INDEX_SYMBOLS = ["000001", "000300", "399001", "399006"]  # A股四大指数
CHINA_ALL_SYMBOLS = [   # Task 2: 国内10+核心指数
    "000001", "000300", "399001", "399006",  # 基础四大
    "000688", "000905", "000852", "000016",  # 科创50·中证500·中证1000·上证50
    "000510", "399100",                         # 上证380·深证A指
]
RATE_SYMBOLS  = ["shibor_1d", "shibor_1w", "shibor_1m", "shibor_3m", "shibor_1y"]
GLOBAL_SYMBOLS = ["HSI", "DJI", "IXIC", "SPX", "N225"]  # Task 2: 扩容全球
DERIVATIVE_SYMBOLS = ["IF", "GC", "CL"]


# ── Task 2: 修复后的 market/overview ─────────────────────────────────────
@router.get("/market/overview")
async def market_overview():
    """
    市场概览 — 风向标视图
    包含：上证、沪深300、恒生、纳斯达克（动态交易状态）
    SHIBOR 已移除（单独卡片）
    """
    is_open_cn, status_cn = is_market_open("A_SHARE")
    is_open_hk, status_hk  = is_market_open("HK")
    is_open_us, status_us  = is_market_open("US")

    wind_labels = {
        "000001": ("上证指数",  "AShare", status_cn),
        "000300": ("沪深300",  "AShare", status_cn),
        "399001": ("深证成指",  "AShare", status_cn),
        "399006": ("创业板指",  "AShare", status_cn),
        "HSI":    ("恒生指数",  "HK",     status_hk),
        "IXIC":   ("纳斯达克",  "US",     status_us),
    }

    rows = get_latest_prices(WIND_SYMBOLS)
    wind_data = {}
    for r in rows:
        sym = r["symbol"]
        label = wind_labels.get(sym, (sym, r["market"], "已休市"))
        wind_data[sym] = {
            "name":       r["name"] or label[0],
            "index":      r["price"],
            "change_pct": r["change_pct"],
            "volume":     r["volume"],
            "status":     label[2],
            "market":     r["market"],
        }

    return {
        "timestamp": datetime.now().isoformat(),
        "wind": wind_data,
    }


# ── Task 2: 国内10+核心指数 ──────────────────────────────────────────────
@router.get("/market/china_all")
async def market_china_all():
    """国内10+核心指数（上证、沪深300、深证、创业板、科创50…）"""
    is_open, status = is_market_open("A_SHARE")
    rows = get_latest_prices(CHINA_ALL_SYMBOLS)
    return {
        "timestamp": datetime.now().isoformat(),
        "china_all": [
            {
                "symbol":     r["symbol"],
                "name":       r["name"],
                "price":      r["price"],
                "change_pct": r["change_pct"],
                "volume":     r["volume"],
                "status":     status,
                "market":     r["market"],
            }
            for r in rows
        ],
    }


@router.get("/market/indices")
async def market_indices():
    """A股四大指数列表"""
    rows = get_latest_prices(INDEX_SYMBOLS)
    return {
        "timestamp": datetime.now().isoformat(),
        "indices": [
            {
                "symbol":     r["symbol"],
                "name":       r["name"],
                "price":      r["price"],
                "change_pct": r["change_pct"],
                "volume":     r["volume"],
                "timestamp":  r["timestamp"],
            }
            for r in rows
        ],
    }


# ── Phase 10: 符号注册表（供前端搜索索引）───────────────────────────────
# 规范化 Symbol 前缀规则：sh=上证 sz=深证 us=美股 hk=港股 JP=日股
_MARKET_PREFIX = {
    '000001': 'sh', '000300': 'sh', '000688': 'sh',  # 上证体系
    '399001': 'sz', '399006': 'sz',                   # 深证体系
}
_SYMBOL_REGISTRY = [
    # A股指数
    { 'symbol': 'sh000001', 'code': '000001', 'name': '上证指数',   'pinyin': 'SCZS',  'market': 'AShare', 'type': 'index' },
    { 'symbol': 'sh000300', 'code': '000300', 'name': '沪深300',   'pinyin': 'HS300',  'market': 'AShare', 'type': 'index' },
    { 'symbol': 'sz399001', 'code': '399001', 'name': '深证成指',   'pinyin': 'SZCZS',  'market': 'AShare', 'type': 'index' },
    { 'symbol': 'sz399006', 'code': '399006', 'name': '创业板指',   'pinyin': 'CYBZZ',  'market': 'AShare', 'type': 'index' },
    { 'symbol': 'sh000688', 'code': '000688', 'name': '科创50',     'pinyin': 'KC50',   'market': 'AShare', 'type': 'index' },
    # 全球指数
    { 'symbol': 'usNDX',    'code': 'NDX',    'name': '纳斯达克100', 'pinyin': 'NDX',   'market': 'US',     'type': 'index' },
    { 'symbol': 'usSPX',    'code': 'SPX',    'name': '标普500',     'pinyin': 'SPX',   'market': 'US',     'type': 'index' },
    { 'symbol': 'usDJI',    'code': 'DJI',    'name': '道琼斯',      'pinyin': 'DJS',   'market': 'US',     'type': 'index' },
    { 'symbol': 'hkHSI',    'code': 'HSI',    'name': '恒生指数',    'pinyin': 'HSZS',  'market': 'HK',     'type': 'index' },
    { 'symbol': 'jpN225',   'code': 'N225',   'name': '日经225',     'pinyin': 'RJB',   'market': 'JP',     'type': 'index' },
    # A股个股（示例，实际可扩展到全市场）
    { 'symbol': 'sh600519', 'code': '600519', 'name': '贵州茅台',    'pinyin': 'GZMJ',  'market': 'AShare', 'type': 'stock' },
    { 'symbol': 'sh601318', 'code': '601318', 'name': '中国平安',    'pinyin': 'ZGPA',  'market': 'AShare', 'type': 'stock' },
    { 'symbol': 'sz000858', 'code': '000858', 'name': '五粮液',      'pinyin': 'WLY',   'market': 'AShare', 'type': 'stock' },
    { 'symbol': 'sh600036', 'code': '600036', 'name': '招商银行',    'pinyin': 'ZSYH',  'market': 'AShare', 'type': 'stock' },
    { 'symbol': 'sz002594', 'code': '002594', 'name': '比亚迪',      'pinyin': 'BYD',   'market': 'AShare', 'type': 'stock' },
    # 宏观
    { 'symbol': 'GOLD',     'code': 'GOLD',   'name': '黄金(USD)',   'pinyin': 'JH',    'market': 'Macro',   'type': 'commodity' },
    { 'symbol': 'WTI',      'code': 'WTI',    'name': 'WTI原油',     'pinyin': 'YSCY',  'market': 'Macro',   'type': 'commodity' },
    { 'symbol': 'CNHUSD',   'code': 'CNHUSD', 'name': '美元/人民币',  'pinyin': 'MYRMB', 'market': 'Macro',   'type': 'forex' },
    { 'symbol': 'VIX',      'code': 'VIX',    'name': 'VIX恐慌指数',  'pinyin': 'VIX',  'market': 'Macro',   'type': 'index' },
]

# 快速 lookup 表
_SYMBOL_LOOKUP = { item['symbol']: item for item in _SYMBOL_REGISTRY }


def _normalize_symbol(raw: str) -> str:
    """
    将各种前端传入格式统一为带市场前缀的规范 symbol。
    例如: '000001' → 'sh000001', 'sh000001' → 'sh000001', 'NDX' → 'usNDX'
    """
    s = raw.strip().lower()
    # 已知美股
    if s.upper() in ('NDX', 'SPX', 'DJI'):
        return 'us' + s.upper()
    # 已知日经
    if s.upper() in ('N225', 'NI225', 'NIKKEI'):
        return 'jpN225'
    # 已知港股
    if s.upper() in ('HSI',):
        return 'hkHSI'
    # 已知宏观（无前缀）
    if s.upper() in ('GOLD', 'WTI', 'VIX', 'CNHUSD'):
        return s.upper()
    # 去掉 sh/sz/hk 前缀后判断
    clean = s.replace('sh', '').replace('sz', '').replace('hk', '').replace('us', '').replace('jp', '')
    # 判断是否 A 股（纯数字）
    if clean.isdigit():
        if clean.startswith(('0', '3', '6')):
            # 根据规则判断交易所
            if clean.startswith('6') or (len(clean) == 6 and clean[0:2] in ('00', '30')):
                return 'sh' + clean
            return 'sz' + clean
    return s


@router.get("/market/symbols")
async def market_symbols():
    """返回全量符号注册表，供前端搜索索引构建"""
    return {
        'symbols': _SYMBOL_REGISTRY,
        'timestamp': datetime.now().isoformat(),
    }


@router.get("/market/lookup/{symbol}")
async def market_lookup(symbol: str):
    """单个 symbol 的元信息查询"""
    norm = _normalize_symbol(symbol)
    item = _SYMBOL_LOOKUP.get(norm)
    if not item:
        return { 'error': 'symbol not found', 'raw': symbol, 'normalized': norm }
    return item


@router.get("/market/quote/{symbol}")
async def market_quote(symbol: str):
    """
    轻量实时行情（专用于高频轮询，不含历史数据）
    返回：最新价、涨跌额、涨跌幅、成交量、成交额、振幅、换手率
    """
    norm = _normalize_symbol(symbol)
    from app.db import get_price_history
    rows = get_price_history(norm, limit=2)  # 最新+昨日
    if not rows:
        return { 'error': 'no data', 'symbol': norm }
    latest = rows[0]  # DESC，最新在前
    prev   = rows[1] if len(rows) > 1 else latest
    close  = float(latest.get('close') or 0)
    prev_c = float(prev.get('close') or close)
    chg    = close - prev_c
    chg_pct = (chg / prev_c * 100) if prev_c else 0
    return {
        'symbol':       norm,
        'price':        close,
        'change':       round(chg, 3),
        'change_pct':   round(chg_pct, 2),
        'volume':       float(latest.get('volume') or 0),
        'amount':       float(latest.get('amount') or 0),
        'amplitude':    round((float(latest.get('high') or 0) / float(latest.get('low') or 1) - 1) * 100, 2) if latest.get('high') and latest.get('low') else 0,
        'turnover_rate': float(latest.get('turnover_rate') or 0),
        'timestamp':     datetime.now().isoformat(),
    }


# ── Phase 9: 历史K线（多周期路由）────────────────────────────────────────
def _clean_symbol(raw: str) -> str:
    """Strip sh/sz/SH/SZ/前缀，容忍前端各种格式传入"""
    return raw.lower().replace("sh", "").replace("sz", "").strip()

@router.get("/market/history/{symbol}")
async def market_history(
    symbol: str,
    limit: int = 300,
    period: str = "daily",
    offset: int = 0,
    trade_date: str = None,
    adjustment: str = "none",
):
    """
    获取某标的历史行情，支持多周期切换 + 懒加载分页。

    若本地数据库无该标的数据，立即触发 AkShare 穿透拉取
    （全量历史写入 SQLite），再返回给前端。

    周期与数据深度：
      daily   : 日K线，默认拉取上限 5000 条（约 20 年），可分页
      weekly : 周K线，默认上限 500 条（约 10 年），可分页
      monthly: 月K线，默认上限 300 条（约 25 年），可分页
      分钟系  : 分时/1/5/15/30/60 分钟，仅支持白名单 A 股指数

    offset : 分页偏移量（每次向后翻页 offset += limit）
    """
    clean_sym = _clean_symbol(symbol)
    from app.db import get_daily_history, get_periodic_history, get_daily_count, get_periodic_count

    chart_type = "candlestick"
    history     = []
    has_more    = False
    fetching    = False   # 正在穿透拉取中

    _MIN_KLINE_SUPPORTED = {"000001", "000300", "399001", "399006", "000688"}
    _FREQUENCY_MAP = {"1min": 1, "5min": 5, "15min": 15, "30min": 30, "60min": 60}

    # ── 分钟K线（Eastmoney N分钟接口，仅支持部分 A 股指数）───────────────
    if period in _FREQUENCY_MAP:
        freq = _FREQUENCY_MAP[period]
        if clean_sym.upper() in _MIN_KLINE_SUPPORTED or clean_sym in _MIN_KLINE_SUPPORTED:
            from app.services.data_fetcher import fetch_index_minute_history
            all_data = fetch_index_minute_history(clean_sym, limit=limit, frequency=freq, offset=offset, trade_date=trade_date)
            history  = all_data
            has_more = len(all_data) >= min(limit, 300)
        else:
            history = []
        chart_type = "candlestick"

    elif period == "minutely":
        if clean_sym.upper() in _MIN_KLINE_SUPPORTED or clean_sym in _MIN_KLINE_SUPPORTED:
            from app.services.data_fetcher import fetch_index_minute_history
            history  = fetch_index_minute_history(clean_sym, limit=min(limit, 300), frequency=5, offset=offset)
            has_more = len(history) >= min(limit, 300)
        else:
            history = []
        chart_type = "line"

    # ── 日K线（支持个股 + 指数，自动按需穿透）───────────────────────────
    elif period == "daily":
        raw_rows = get_daily_history(clean_sym, limit=limit, offset=offset)
        total    = get_daily_count(clean_sym)

        # 本地无数据 → 触发 AkShare 按需穿透（仅首次，limit=max 一次性拉足）
        if not raw_rows and offset == 0:
            logger.info(f"[Market History] 本地无 {clean_sym} 日K，触发穿透拉取…")
            fetching = True
            try:
                from app.services.data_fetcher import fetch_stock_history
                rows = fetch_stock_history(clean_sym)
                if rows:
                    # 穿透完成后再查（此时 SQLite 已有数据）
                    raw_rows = get_daily_history(clean_sym, limit=limit, offset=offset)
                    total    = get_daily_count(clean_sym)
            except Exception as e:
                logger.error(f"[Market History] 穿透失败: {e}")

        history  = _apply_adjustment(list(reversed(raw_rows)), adjustment)
        has_more = (offset + len(raw_rows)) < total
        chart_type = "candlestick"

    # ── 周/月K线（支持个股 + 指数，自动按需穿透）────────────────────────
    elif period in ("weekly", "monthly"):
        raw_rows = get_periodic_history(clean_sym, period=period, limit=limit, offset=offset)
        total    = get_periodic_count(clean_sym, period)

        # 本地无数据 → 触发穿透（先把日K拉足，再由 fetch_stock_history 内聚合并写入 periodic 表）
        if not raw_rows and offset == 0:
            logger.info(f"[Market History] 本地无 {clean_sym} {period}K，触发穿透…")
            fetching = True
            try:
                from app.services.data_fetcher import fetch_stock_history
                fetch_stock_history(clean_sym)   # 日K写入后自动生成 periodic
                raw_rows = get_periodic_history(clean_sym, period=period, limit=limit, offset=offset)
                total    = get_periodic_count(clean_sym, period)
            except Exception as e:
                logger.error(f"[Market History] 穿透失败: {e}")

        history  = _apply_adjustment(list(reversed(raw_rows)), adjustment)
        has_more = (offset + len(raw_rows)) < total
        chart_type = "candlestick"

    else:
        from app.db import get_price_history
        history    = get_price_history(clean_sym, limit=limit)
        chart_type = "candlestick"

    return {
        "symbol":     clean_sym,
        "period":     period,
        "chart_type": chart_type,
        "has_more":   has_more,
        "offset":     offset,
        "fetching":   fetching,    # 前端据此显示"穿透拉取中"状态
        "timestamp":  datetime.now().isoformat(),
        "history":    history,
    }


@router.get("/market/rates")
async def market_rates():
    """利率数据"""
    rows = get_latest_prices(RATE_SYMBOLS)
    return {
        "timestamp": datetime.now().isoformat(),
        "rates": [
            {
                "symbol":  r["symbol"],
                "name":    r["name"],
                "rate":    r["price"],
                "timestamp": r["timestamp"],
            }
            for r in rows
        ],
    }


# ── 复权因子计算（QFQ/HFQ）────────────────────────────────────────
def _apply_adjustment(rows, method):
    """
    对 OHLCV 历史数据应用复权因子。
    method: 'qfq' 前复权 | 'hfq' 后复权 | 'none' 不复权
    """
    if not rows or method == 'none':
        return rows

    # 取最新一根（最近交易日）的收盘价作为基准
    latest = rows[-1]  # 按 date ASC 排列时最后一条是最新
    latest_close = float(latest.get('close') or 0)
    if latest_close <= 0:
        return rows

    # 前复权：最新价为基准，向前倒推
    # qfq_factor_t = latest_close / close_t
    if method == 'qfq':
        result = []
        for r in rows:
            t_close = float(r.get('close') or 0)
            if t_close > 0:
                factor = latest_close / t_close
                result.append({
                    **r,
                    'open':   round(float(r.get('open')   or 0) * factor, 3),
                    'high':   round(float(r.get('high')   or 0) * factor, 3),
                    'low':    round(float(r.get('low')    or 0) * factor, 3),
                    'close':  round(t_close * factor, 3),
                })
            else:
                result.append({**r})
        return result

    # 后复权：简化版，以最新收盘价为基准等比放大
    # hfq_factor = latest_close（假设基准为1，前复权后价格 × 最新收盘价）
    if method == 'hfq':
        factor = latest_close  # 简化：恒定因子 = 最新收盘价
        return [{
            **r,
            'open':   round(float(r.get('open')  or 0) * factor, 3),
            'high':   round(float(r.get('high')  or 0) * factor, 3),
            'low':    round(float(r.get('low')   or 0) * factor, 3),
            'close':  round(float(r.get('close') or 0) * factor, 3),
        } for r in rows]

    return rows


# ── Task 2: 全球市场（扩容至5个指数）────────────────────────────────────
@router.get("/market/global")
async def market_global():
    """全球核心市场指数（恒生、道琼斯、纳斯达克、标普500、日经）"""
    is_open_hk, status_hk = is_market_open("HK")
    is_open_us, status_us = is_market_open("US")
    is_open_jp, status_jp = is_market_open("JP")

    status_map = {"HSI": status_hk, "DJI": status_us, "IXIC": status_us, "SPX": status_us, "N225": status_jp}

    rows = get_latest_prices(GLOBAL_SYMBOLS)
    return {
        "timestamp": datetime.now().isoformat(),
        "global": [
            {
                "symbol":     r["symbol"],
                "name":       r["name"],
                "price":      r["price"],
                "change_pct": r["change_pct"],
                "volume":     r["volume"],
                "status":     status_map.get(r["symbol"], "已休市"),
                "market":     r["market"],
            }
            for r in rows
        ],
    }


# ── Task 1: 行业板块（只读缓存，后台Job填充，路由绝不阻塞）──────────────
@router.get("/market/sectors")
async def market_sectors():
    """
    真实行业板块数据 — Task 1: 毫秒级响应
    所有 akshare 调用全部移到后台 Job，API 只读 _SECTORS_CACHE
    """
    from app.services.sectors_cache import get_sectors
    sectors = get_sectors()
    return {
        "timestamp": datetime.now().isoformat(),
        "sectors": sectors,
    }


# ── Phase 6: 期货与大宗商品 ──────────────────────────────────────────────
@router.get("/market/derivatives")
async def market_derivatives():
    """期货与大宗商品（IF期指主力、SGE黄金、WTI原油）"""
    rows = get_latest_prices(DERIVATIVE_SYMBOLS)
    return {
        "timestamp": datetime.now().isoformat(),
        "derivatives": [
            {
                "symbol":     r["symbol"],
                "name":       r["name"],
                "price":      r["price"],
                "change_pct": r["change_pct"],
                "volume":     r["volume"],
                "status":     "日内更新",
                "market":     r["market"],
            }
            for r in rows
        ],
    }
