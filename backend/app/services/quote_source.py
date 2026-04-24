"""
财务数据源管理器 - 多源fallback机制
支持: A股(腾讯/新浪), 港股(腾讯港股), 美股(AlphaVantage), K线(新浪)

⚠️ 关键设计决策：
- 底层 _parse_* 函数保持同步（httpx.Client + timeout context manager）
- 上层 async 路由通过 asyncio.to_thread() 调用同步函数，避免阻塞事件循环
- 不混用 httpx.AsyncClient（避免连接池泄漏和调试困难）
"""
import asyncio
import logging
import os
import time
import httpx

logger = logging.getLogger(__name__)

# ========== 数据源配置 ==========
DATA_SOURCES = {
    "tencent": {
        "name": "腾讯财经(A股)",
        "name_cn": "腾讯A股",
        "type": "primary",
        "proxy": False,
        "timeout": 10,
        "weight": 100,
        "has_pepb": True,
        "has_realtime": True,
    },
    "sina_kline": {
        "name": "新浪60分K线",
        "name_cn": "新浪K线",
        "type": "backup",
        "proxy": False,
        "timeout": 15,
        "weight": 25,
        "has_pepb": False,
        "has_realtime": True,
    },
    "sina": {
        "name": "新浪财经(A股)",
        "name_cn": "新浪A股",
        "type": "backup",
        "proxy": False,
        "timeout": 10,
        "weight": 30,
        "has_pepb": False,
        "has_realtime": True,
    },
    "eastmoney": {
        "name": "东方财富",
        "name_cn": "东财",
        "type": "backup",
        "proxy": True,
        "proxy_url": None,   # 从 proxy_config.py 动态读取，永不硬编码
        "timeout": 10,
        "weight": 50,
        "has_pepb": True,
        "has_realtime": True,
    },
    "tencent_hk": {
        "name": "腾讯港股",
        "name_cn": "腾讯港股",
        "type": "backup",
        "proxy": False,
        "timeout": 10,
        "weight": 80,
        "has_pepb": True,
        "has_realtime": True,
    },
    "alpha_vantage": {
        "name": "Alpha Vantage (美股)",
        "name_cn": "AlphaV",
        "type": "backup",
        "proxy": False,
        "timeout": 30,
        "weight": 20,
        "api_key": os.environ.get("ALPHA_VANTAGE_API_KEY", ""),
        "has_pepb": True,
        "has_realtime": True,
    },
}

_current_source = "tencent"
_source_status = {k: {"status": "unknown", "latency": None, "fail_count": 0} for k in DATA_SOURCES}


def _get_proxy(source_name: str) -> dict | None:
    from app.services.proxy_config import get_proxy_url, build_httpx_proxies
    source = DATA_SOURCES.get(source_name, {})
    if source.get("proxy"):
        proxy_url = source.get("proxy_url") or get_proxy_url()
        return build_httpx_proxies(proxy_url)
    return None


# ========== 解析函数 ==========

def _parse_tencent_quote(symbol: str) -> dict | None:
    """腾讯A股（同步，抓取用完即弃连接池）"""
    url = f"https://qt.gtimg.cn/q={symbol}"
    try:
        start = time.time()
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url)
        latency = (time.time() - start) * 1000
        if r.status_code != 200 or '"' not in r.text:
            return None
        parts = r.text.split('"')[1].split('~')
        if len(parts) < 40:
            return None
        return {
            "source": "tencent",
            "latency_ms": round(latency, 1),
            "pe_static": float(parts[38]) if parts[38] not in ('0', '-', '') else None,
            "pe_ttm": float(parts[46]) if len(parts) > 46 and parts[46] not in ('0', '-', '') else None,
            "pb": float(parts[39]) if parts[39] not in ('0', '-', '') else None,
            "price": float(parts[3]) if parts[3] else None,
            "prev_close": float(parts[4]) if parts[4] else None,
            "open": float(parts[5]) if parts[5] else None,
            "high": float(parts[6]) if parts[6] else None,
            "low": float(parts[7]) if parts[7] else None,
        }
    except Exception as e:
        logger.warning(f"[Tencent] {symbol} fail: {e}")
        return None


def _parse_sina_quote(symbol: str) -> dict | None:
    """新浪A股（同步）"""
    url = f"https://hq.sinajs.cn/list={symbol}"
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn'}
    try:
        start = time.time()
        with httpx.Client(timeout=10.0, headers=headers) as client:
            r = client.get(url)
        latency = (time.time() - start) * 1000
        if '=' not in r.text:
            return None
        parts = r.text.split('=')[1].split(',')
        if len(parts) < 10:
            return None
        return {
            "source": "sina",
            "latency_ms": round(latency, 1),
            "price": float(parts[1]) if parts[1] else None,
            "prev_close": float(parts[2]) if parts[2] else None,
            "open": float(parts[3]) if parts[3] else None,
            "high": float(parts[4]) if parts[4] else None,
            "low": float(parts[5]) if parts[5] else None,
            "pe_static": None, "pe_ttm": None, "pb": None,
        }
    except Exception as e:
        logger.warning(f"[Sina] {symbol} fail: {e}")
        return None


def _parse_sina_kline_60min(symbol: str) -> dict | None:
    """新浪60分钟K线数据（同步）"""
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=60&ma=no&datalen=100"
    try:
        start = time.time()
        with httpx.Client(timeout=15.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            r = client.get(url)
        latency = (time.time() - start) * 1000
        if r.status_code != 200:
            return None
        import json
        data = json.loads(r.text)
        if not isinstance(data, list) or len(data) == 0:
            return None
        klines = data[-60:] if len(data) > 60 else data
        return {
            "source": "sina_kline",
            "latency_ms": round(latency, 1),
            "kline_type": "60min",
            "data": klines,
            "count": len(klines),
        }
    except Exception as e:
        logger.warning(f"[SinaKline] {symbol} fail: {e}")
        return None


def _parse_eastmoney_quote(symbol: str) -> dict | None:
    """东方财富（同步）"""
    if symbol.startswith('sh'):
        secid = '1.' + symbol[2:]
    elif symbol.startswith('sz'):
        secid = '0.' + symbol[2:]
    else:
        return None
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {'secid': secid, 'fields': 'f2,f3,f4,f5,f6,f7,f12,f14,f57,f58,f116,f117'}
    proxy = _get_proxy("eastmoney")
    try:
        start = time.time()
        with httpx.Client(timeout=10.0, proxies=proxy) as client:
            r = client.get(url, params=params)
        latency = (time.time() - start) * 1000
        d = r.json().get('data', {})
        return {
            "source": "eastmoney",
            "latency_ms": round(latency, 1),
            "price": d.get('f2'),
            "change_pct": d.get('f3'),
            "pe_static": d.get('f116'),
            "pe_ttm": d.get('f57'),
            "pb": d.get('f58') or d.get('f117'),
        }
    except Exception as e:
        logger.warning(f"[Eastmoney] {symbol} fail: {e}")
        return None


def _parse_tencent_hk_quote(symbol: str) -> dict | None:
    """腾讯港股（同步）"""
    url = f"https://qt.gtimg.cn/q={symbol}"
    try:
        start = time.time()
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url)
        latency = (time.time() - start) * 1000
        if r.status_code != 200 or '"' not in r.text:
            return None
        parts = r.text.split('"')[1].split('~')
        if len(parts) < 40:
            return None
        return {
            "source": "tencent_hk",
            "latency_ms": round(latency, 1),
            "price": float(parts[3]) if parts[3] else None,
            "prev_close": float(parts[4]) if parts[4] else None,
            "open": float(parts[5]) if parts[5] else None,
            "high": float(parts[6]) if parts[6] else None,
            "low": float(parts[7]) if parts[7] else None,
            "pe_static": float(parts[38]) if parts[38] not in ('0', '-', '') else None,
            "pb": float(parts[39]) if parts[39] not in ('0', '-', '') else None,
        }
    except Exception as e:
        logger.warning(f"[Tencent HK] {symbol} fail: {e}")
        return None


def _parse_alpha_vantage_quote(symbol: str) -> dict | None:
    """Alpha Vantage - 美股数据（同步，带重试）"""
    api_key = DATA_SOURCES.get("alpha_vantage", {}).get("api_key", "demo")
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"

    # 重试1次，超时缩短到5秒（避免阻塞ping）
    r = None
    latency = 0
    for attempt in range(2):
        try:
            start = time.time()
            with httpx.Client(timeout=5.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
                r = client.get(url)
            latency = (time.time() - start) * 1000
            break
        except Exception as e:
            if attempt == 1:
                logger.warning(f"[AlphaVantage] {symbol} failed after 2 attempts: {e}")
                return None
            time.sleep(0.5)

    if not r or r.status_code != 200:
        return None

    import json
    data = r.json()
    quote = data.get("Global Quote", {})

    if not quote:
        return None

    return {
        "source": "alpha_vantage",
        "latency_ms": round(latency, 1),
        "price": float(quote.get("05. price")) if quote.get("05. price") else None,
        "prev_close": float(quote.get("08. previous close")) if quote.get("08. previous close") else None,
        "open": float(quote.get("02. open")) if quote.get("02. open") else None,
        "high": float(quote.get("03. high")) if quote.get("03. high") else None,
        "low": float(quote.get("04. low")) if quote.get("04. low") else None,
        "volume": int(quote.get("06. volume")) if quote.get("06. volume") else None,
    }


# ========== 主接口（同步版，给 ping 等同步上下文用）============

def get_quote_with_fallback(symbol: str) -> dict:
    global _current_source
    
    if symbol.startswith('sh') or symbol.startswith('sz'):
        sources_order = ["tencent", "eastmoney", "sina"]
    elif symbol.startswith('hk'):
        sources_order = ["tencent_hk"]
    else:
        sources_order = ["tencent"]
    
    for source_name in sources_order:
        logger.debug(f"[Quote] 尝试: {source_name}")
        
        if source_name == "tencent":
            result = _parse_tencent_quote(symbol)
        elif source_name == "sina":
            result = _parse_sina_quote(symbol)
        elif source_name == "eastmoney":
            result = _parse_eastmoney_quote(symbol)
        elif source_name == "tencent_hk":
            result = _parse_tencent_hk_quote(symbol)
        else:
            continue
        
        if result:
            _current_source = source_name
            _source_status[source_name] = {"status": "ok", "latency": result.get("latency_ms"), "fail_count": 0}
            logger.info(f"[Quote] {symbol} -> {source_name}, {result.get('latency_ms')}ms")
            return result
    
    return {"source": "none", "error": "所有数据源均失败", "pe_static": None, "pe_ttm": None, "pb": None}


# ========== 主接口（异步版，给 FastAPI async 路由用）============
# 策略：底层解析函数保持同步（httpx.Client context manager），避免连接池泄漏；
#       async 路由通过 asyncio.to_thread() 调用同步解析器，不阻塞事件循环。

async def _thread_parse(parser_fn, symbol: str):
    """在线程池中执行同步解析函数，避免阻塞事件循环。"""
    return parser_fn(symbol)

async def get_quote_with_fallback_async(symbol: str) -> dict:
    """
    异步版行情获取——内部调用同步 _parse_* 函数，
    用 asyncio.to_thread() 隔离网络阻塞，不卡 FastAPI 事件循环。
    """
    global _current_source

    if symbol.startswith('sh') or symbol.startswith('sz'):
        sources_order = [("tencent", _parse_tencent_quote),
                         ("eastmoney", _parse_eastmoney_quote),
                         ("sina", _parse_sina_quote)]
    elif symbol.startswith('hk'):
        sources_order = [("tencent_hk", _parse_tencent_hk_quote)]
    else:
        sources_order = [("tencent", _parse_tencent_quote)]

    for source_name, parser in sources_order:
        logger.debug(f"[Quote/async] 尝试: {source_name}")
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(parser, symbol),
                timeout=15.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"[Quote/async] {source_name} 超时 15s")
            _source_status[source_name] = {"status": "timeout", "latency": None, "fail_count": _source_status[source_name]["fail_count"] + 1}
            continue
        except Exception as e:
            logger.warning(f"[Quote/async] {source_name} 异常: {e}")
            _source_status[source_name] = {"status": "error", "latency": None, "fail_count": _source_status[source_name]["fail_count"] + 1}
            continue

        if result:
            _current_source = source_name
            _source_status[source_name] = {"status": "ok", "latency": result.get("latency_ms"), "fail_count": 0}
            logger.info(f"[Quote/async] {symbol} -> {source_name}, {result.get('latency_ms')}ms")
            return result

    return {"source": "none", "error": "所有数据源均失败", "pe_static": None, "pe_ttm": None, "pb": None}


async def test_source_async(source_name: str, symbol: str = "sh000001") -> dict:
    """异步探测单个数据源（用于 /source/ping）"""
    parsers = {
        "tencent": _parse_tencent_quote,
        "sina": _parse_sina_quote,
        "eastmoney": _parse_eastmoney_quote,
        "sina_kline": _parse_sina_kline_60min,
        "tencent_hk": _parse_tencent_hk_quote,
        "alpha_vantage": _parse_alpha_vantage_quote,
    }
    parser = parsers.get(source_name)
    if not parser:
        return {"status": "unknown", "latency": None}
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(parser, symbol),
            timeout=10.0
        )
        if result:
            return {"status": "ok", "latency": result.get("latency_ms")}
        return {"status": "fail", "latency": None}
    except asyncio.TimeoutError:
        return {"status": "timeout", "latency": None}
    except Exception as e:
        return {"status": "error", "latency": None}


def get_source_status() -> dict:
    return {
        "current": _current_source,
        "sources": _source_status,
        "config": {k: {"name": v["name"], "name_cn": v.get("name_cn"), "type": v["type"], "proxy": v.get("proxy"), "has_pepb": v.get("has_pepb", False), "has_realtime": v.get("has_realtime", False)} for k, v in DATA_SOURCES.items()},
    }


def set_primary_source(source_name: str) -> bool:
    global _current_source
    if source_name in DATA_SOURCES:
        _current_source = source_name
        return True
    return False