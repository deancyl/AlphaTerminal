"""
市场数据模块共享依赖

本模块从 market.py 拆分，包含：
- 缓存变量与锁（宏观/实时行情）
- 符号规范化工具（_normalize_symbol, _unprefix, _clean_symbol）
- 序列化辅助函数（_serialize_price_row, _serialize_price_rows）
- 历史数据注入函数（_inject_change_pct, _apply_adjustment）
- 常量定义（风向标指数、全球指数、利率符号等）
- 宏观数据抓取函数（Sina/Tencent 实时接口）
- 实时行情缓存函数

设计原则：
- 所有函数保持原有签名，确保向后兼容
- 使用线程安全的锁（RLock）保护共享缓存
- 懒加载全市场A股名称（避免阻塞后端启动）
"""
import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

# 日志器（供其他模块导入）
logger = logging.getLogger(__name__)

# ── Phase 7: 宏观大宗商品缓存（10 分钟 TTL）─────────────────────────────
# 代理由 proxy_config.py 统一管理，从环境变量读取
# 用户需在启动前设置 HTTP_PROXY/HTTPS_PROXY 环境变量

_MACRO_CACHE       = {}   # {symbol: {price, change_pct, name, unit, timestamp}}
_MACRO_CACHE_TTL  = 600  # 10 分钟（Phase 7 延长 TTL）
_MACRO_CACHE_LOCK  = threading.RLock()  # RLock 可重入
_LAST_FETCH_TIME   = 0   # 0 = immediately refresh on first call
_REFRESH_SEMAPHORE = threading.Semaphore(1)  # 防止并发刷新

SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (compatible; AlphaTerminal/1.0)",
}

# K线支持的白名单（仅这些标的支持分钟级别K线）
MIN_KLINE_SUPPORTED = {"000001", "000300", "399001", "399006", "000688"}

# 周期映射（中文period → 分钟数）
FREQUENCY_MAP = {"1min": 1, "5min": 5, "15min": 15, "30min": 30, "60min": 60}

# 期货周期映射
FUTURES_FREQ_MAP = {"1min": 1, "5min": 5, "15min": 15, "30min": 30, "60min": 60}


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

    # 3) 腾讯 qt（CNH/USD 汇率 + VHSI 恒指波指 + 恒生指数HSI，不过代理）
    qt_syms = [s for s in symbols if s in ("CNHUSD", "hkVHSI", "hkHSI")]
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
                    # 腾讯 qt 格式: v_hkHSI="51~恒生指数~HSI~25357.23~..."
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


def _parse_hkhsi(data: dict) -> tuple[float, float, str]:
    """
    解析 hkHSI（恒生指数，腾讯 qt 格式，~分隔）
    f[3]=当前价, f[4]=昨收, f[31]=涨跌额, f[32]=涨跌幅%
    """
    f = data.get("hkHSI", [])
    if len(f) < 33:
        raise ValueError("hkHSI data too short")
    try:
        price = float(f[3])   # 当前 HSI
        prev  = float(f[4])   # 昨收
        pct   = float(f[32]) if f[32] else (((price - prev) / prev * 100) if prev else 0.0)
        # f[30] = "2026/04/02 18:31:21"
        tick  = f[30][-8:-3] if f[30] and len(f[30]) > 4 else ""
    except Exception as e:
        raise ValueError(f"hkHSI parse error: {e}")
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


def _parse_hkvhsi(data: dict) -> tuple[float, float, str]:
    """
    解析 hkVHSI（恒指波幅指数，腾讯 qt 格式）
    _fetch_from_sina 返回 list：f[3]=当前 VHSI 值, f[4]=昨收, f[32]=涨跌幅%
    若解析失败（格式不符），返回 (20.0, 0.0, "") 而不崩溃
    """
    f = data.get("hkVHSI", [])
    if len(f) < 5:
        raise ValueError("hkVHSI data too short")
    try:
        price = float(f[3])   # VHSI 当前值
        prev  = float(f[4]) if f[4] else price
        # f[32] 是涨跌幅%，若为空则用 (price-prev)/prev 推算
        pct = 0.0
        if len(f) > 32 and f[32]:
            try:
                pct = float(f[32])
            except (ValueError, TypeError):
                pct = (price - prev) / prev * 100 if prev else 0.0
        else:
            pct = (price - prev) / prev * 100 if prev else 0.0
        tick = f[30][-8:-3] if len(f) > 30 and f[30] and len(f[30]) > 4 else ""
    except (ValueError, IndexError, TypeError) as e:
        raise ValueError(f"hkVHSI parse error: {e}")
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

    # 初始化默认值（静态兜底，网络失败时使用）
    usdcny_price = 6.8871; usdcny_pct = 0.0
    gold_price = 3318.40; gold_pct = 0.0
    wti_price = 68.92; wti_pct = 0.0
    vhsi_price = 20.0; vhsi_pct = 0.0

    try:
        raw = _fetch_from_sina(["CNYUSD", "hf_GC", "hf_CL", "hkVHSI"])

        if "CNYUSD" in raw and raw["CNYUSD"]:
            try:
                usdcny_price, usdcny_pct, _ = _parse_cnyusd(raw)
            except Exception as e:
                logger.warning(f"[Macro] CNYUSD parse error: {e}")

        if "hf_GC" in raw and raw["hf_GC"]:
            try:
                gold_price, gold_pct, _ = _parse_hf_gold(raw)
            except Exception as e:
                logger.warning(f"[Macro] GOLD parse error: {e}")

        if "hf_CL" in raw and raw["hf_CL"]:
            try:
                wti_price, wti_pct, _ = _parse_hf_cl(raw)
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


# ══════════════════════════════════════════════════════════════════════════
# 符号规范化工具
# ══════════════════════════════════════════════════════════════════════════

def _normalize_symbol(raw: str) -> str:
    """
    将各种前端传入格式统一为带市场前缀的规范 symbol。
    例如: '000001' → 'sh000001', 'sh000001' → 'sh000001', 'NDX' → 'usNDX'
    """
    s = raw.strip()
    # 已知美股（无前缀形式，如 'ndx'）
    if s.upper() in ('NDX', 'SPX', 'DJI'):
        return 'us' + s.upper()
    # 已知日经
    if s.upper() in ('N225', 'NI225', 'NIKKEI'):
        return 'jpN225'
    # 已知港股
    if s.upper() in ('HSI',):
        return 'hkHSI'
    # 已知宏观（无前缀）
    if s.upper() in ('GOLD', 'WTI', 'VIX'):
        return s.upper()
    # CNH/USD 特殊处理
    upper_s = s.upper()
    if upper_s == 'CNHUSD':
        return 'CNHUSD'
    if upper_s.startswith('CNH'):
        suffix = upper_s[len('CNH'):]
        if suffix.isdigit() or suffix.startswith('USD'):
            return 'CNHUSD'
    # 去掉 sh/sz/hk/us/jp 前缀
    clean = s.lower()
    for pfx in ('sh', 'sz', 'hk', 'us', 'jp'):
        if clean.startswith(pfx):
            clean = clean[len(pfx):]
            break
    # A股数字段判断
    if clean.isdigit():
        if clean.startswith('6') or clean in ('000001', '000300', '000688'):
            return 'sh' + clean
        if clean.startswith(('0', '2', '3')):
            return 'sz' + clean
        return 'sz' + clean
    return s


def _unprefix(raw: str) -> str:
    """去掉 sh/sz/hk/us/jp 前缀，用于查询 market_data_realtime（该表存无前缀 symbol）。"""
    s = str(raw).strip()
    for p in ('sh', 'sz', 'hk', 'us', 'jp', 'SH', 'SZ', 'HK', 'US', 'JP'):
        if s.startswith(p):
            return s[len(p):]
    return s


def _clean_symbol(raw: str) -> str:
    """
    规范化 symbol：
    - A 股 sh/sz 前缀：去掉（DB 存纯数字如 '000001'）
    - 美股/港股/日经前缀：统一去掉（DB 存 'ixic'/'hsi' 等，不带 us/hk/jp 前缀）
    - macro 前缀：去掉
    - 返回纯数字/字母（用于 DB 查询），全部小写
    """
    s = raw.strip()
    # macro 前缀
    if s.lower().startswith("macro"):
        s = s[len("macro"):].lstrip('_')
    # 去掉 us/hk/jp 前缀
    s = re.sub(r"^(us|hk|jp)", "", s, flags=re.IGNORECASE)
    # 去掉 A 股前缀
    for pfx in ("sh", "sz", "SH", "SZ"):
        if s.startswith(pfx):
            s = s[len(pfx):]
            break
    return s.lower()


# ══════════════════════════════════════════════════════════════════════════
# 序列化辅助函数
# ══════════════════════════════════════════════════════════════════════════

def _serialize_price_row(row: dict, include_status: bool = False, status: str = None) -> dict:
    """
    统一序列化价格数据行

    Args:
        row: 数据库原始行数据
        include_status: 是否包含市场状态字段
        status: 市场状态值（仅当 include_status=True 时有效）

    Returns:
        标准化后的数据字典
    """
    result = {
        "symbol": row["symbol"],
        "name": row["name"],
        "price": row["price"],
        "change_pct": row["change_pct"],
        "volume": row["volume"],
        "market": row["market"],
    }
    if include_status and status:
        result["status"] = status
    return result


def _serialize_price_rows(rows: list, include_status: bool = False, status: str = None) -> list:
    """批量序列化价格数据行"""
    return [_serialize_price_row(r, include_status, status) for r in rows]


# ── 风向标指数（Task 2: 精简 overview，只保留核心风向标）─────────────────
WIND_SYMBOLS = ["000001", "000300", "399001", "399006", "HSI", "IXIC"]
INDEX_SYMBOLS = ["000001", "000300", "399001", "399006"]
CHINA_ALL_SYMBOLS = [
    "000001", "000300", "399001", "399006",
    "000688", "000905", "000852", "000016",
    "000510", "399100",
]
RATE_SYMBOLS = ["shibor_1d", "shibor_1w", "shibor_1m", "shibor_3m", "shibor_1y"]
GLOBAL_SYMBOLS = ["HSI", "DJI", "IXIC", "SPX", "N225"]
DERIVATIVE_SYMBOLS = ["GC", "CL"]

# ── 实时行情缓存（10秒 TTL，避免频繁调 Sina）─────────────────────────
_REALTIME_CACHE = {"wind": None, "china_all": None, "_ts": 0}
_CACHE_TTL = 10  # 秒


def _get_cached_wind(force=False):
    """获取风向标实时数据，10秒内复用缓存"""
    now = time.time()
    if not force and _REALTIME_CACHE["wind"] and (now - _REALTIME_CACHE["_ts"]) < _CACHE_TTL:
        return _REALTIME_CACHE["wind"]
    try:
        from app.services.data_fetcher import fetch_china_indices, fetch_global_indices
        # A股4大指数（实时）+ 全球指数（港美）
        rows_cn  = fetch_china_indices()           # 新浪实时
        rows_int = fetch_global_indices()           # 腾讯/Sina 实时
        rows = rows_cn + rows_int
        wind_data = {}
        for r in rows:
            sym = r.get("symbol", "")
            wind_data[sym] = {
                "name":       r.get("name", sym),
                "price":      r.get("price", 0),
                "change_pct": r.get("change_pct", 0),
                "volume":     r.get("volume", 0),
                "market":     r.get("market", ""),
            }
        _REALTIME_CACHE["wind"] = wind_data
        _REALTIME_CACHE["_ts"]  = now
        return wind_data
    except Exception as e:
        logger.warning(f"[market_overview] 实时拉取失败，回退缓存: {e}")
        return _REALTIME_CACHE["wind"] or {}


# ══════════════════════════════════════════════════════════════════════════
# 历史数据注入函数
# ══════════════════════════════════════════════════════════════════════════

def _inject_change_pct(rows: list[dict]) -> list[dict]:
    """
    对 ASC 排列的历史 K 线内联注入 change_pct（利用相邻 close 计算）。
    market_data_daily 表无 change_pct 列，需在此层内联计算。
    同时注入 amplitude（历史旧数据可能缺失）。
    """
    if not rows:
        return rows
    result = []
    prev_close = None
    for r in rows:
        close = float(r.get("close") or 0)
        high  = float(r.get("high") or 0)
        low   = float(r.get("low") or 0)
        if prev_close is not None and prev_close != 0:
            pct       = (close - prev_close) / prev_close * 100
            amplitude = round((high - low) / prev_close * 100, 4)
        else:
            pct       = 0.0
            amplitude = 0.0
        # 只注入缺失的字段，保留已有值
        item = {**r}
        if item.get("change_pct") is None:
            item["change_pct"] = round(pct, 4)
        if item.get("amplitude") is None:
            item["amplitude"] = amplitude
        result.append(item)
        prev_close = close
    return result


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
    if method == 'hfq':
        factor = latest_close
        return [{
            **r,
            'open':   round(float(r.get('open')  or 0) * factor, 3),
            'high':   round(float(r.get('high')  or 0) * factor, 3),
            'low':    round(float(r.get('low')   or 0) * factor, 3),
            'close':  round(float(r.get('close') or 0) * factor, 3),
        } for r in rows]

    return rows


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

# ── 全市场A股名称懒加载（不阻塞后端启动）───────────────────────────────
_ALL_STOCK_NAMES: list[dict] = []      # 全量个股注册表
_STOCK_NAMES_LOADED: bool = False
_STOCK_LOAD_LOCK = threading.Lock()      # 防止并发多次加载

# 快速 lookup 表（动态 + 静态分开，market_lookup 合并查询）
_SYMBOL_LOOKUP_STATIC = { item['symbol']: item for item in _SYMBOL_REGISTRY }


def _get_combined_lookup() -> dict:
    """返回完整 lookup：静态注册表 + 已加载的动态全市场A股（线程安全）"""
    base = dict(_SYMBOL_LOOKUP_STATIC)
    if _STOCK_NAMES_LOADED:
        for s in _ALL_STOCK_NAMES:
            base[s['symbol']] = s
    return base

def _pinyin_fallback(name: str) -> str:
    """获取名称首字拼音（无 pypinyin 时回退到名称前4字）"""
    try:
        from pypinyin import lazy_pinyin
        py = lazy_pinyin(name)
        return ''.join(py) if py else name[:4]
    except Exception:
        return name[:4]  # 无 pypinyin 时用名称前4字做近似


def _load_all_stock_names() -> list[dict]:
    """
    调用 akshare stock_info_a_code_name() 获取全市场A股代码+名称，
    懒加载一次，线程安全，结果缓存于 _ALL_STOCK_NAMES。
    """
    global _ALL_STOCK_NAMES, _STOCK_NAMES_LOADED
    if _STOCK_NAMES_LOADED:
        return _ALL_STOCK_NAMES

    with _STOCK_LOAD_LOCK:
        if _STOCK_NAMES_LOADED:   # double-check（其他线程已加载）
            return _ALL_STOCK_NAMES

        try:
            import akshare as ak
            logger.info("[SymbolRegistry] 开始加载全市场A股名称...")
            df = ak.stock_info_a_code_name()
            df_work = df.copy()
            df_work['code'] = df_work['code'].astype(str).str.strip()
            df_work['name'] = df_work['name'].astype(str).str.strip()
            df_work = df_work[(df_work['code'].str.len() == 6) & (df_work['code'] != '') & (df_work['name'] != '')]
            df_work['prefix'] = df_work['code'].apply(lambda x: 'sh' if x[0] in ('6', '9') else ('bj' if x[0] == '8' else 'sz'))
            df_work['symbol'] = df_work['prefix'] + df_work['code']
            df_work['pinyin'] = df_work['name'].apply(_pinyin_fallback)
            df_work['market'] = 'AShare'
            df_work['type'] = 'stock'
            _ALL_STOCK_NAMES = df_work[['symbol', 'code', 'name', 'pinyin', 'market', 'type']].to_dict('records')
            _STOCK_NAMES_LOADED = True
            logger.info(f"[SymbolRegistry] 全市场A股加载完成: {len(_ALL_STOCK_NAMES)} 只")
        except Exception as e:
            logger.warning(f"[SymbolRegistry] 加载全市场A股失败，使用兜底数据: {e}")
            _ALL_STOCK_NAMES = []
            _STOCK_NAMES_LOADED = True

    return _ALL_STOCK_NAMES


def _parse_timestamp(dt_str: str) -> int:
    """将日期时间字符串转为 Unix timestamp（毫秒）"""
    try:
        from datetime import datetime
        dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return int(dt_obj.timestamp() * 1000)
    except Exception:
        return 0
