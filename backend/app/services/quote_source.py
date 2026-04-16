"""
财务数据源管理器 - 多源fallback机制
支持: A股(腾讯/新浪), 港股(腾讯港股), 美股(AlphaVantage), K线(新浪)
"""
import logging
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
        "api_key": "NTPKY2RBGQ2ZS8IU",
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
    """腾讯A股"""
    url = f"https://qt.gtimg.cn/q={symbol}"
    try:
        start = time.time()
        r = httpx.get(url, timeout=10)
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
    """新浪A股"""
    url = f"https://hq.sinajs.cn/list={symbol}"
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn'}
    try:
        start = time.time()
        r = httpx.get(url, timeout=10, headers=headers)
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
    """新浪60分钟K线数据"""
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=60&ma=no&datalen=100"
    try:
        start = time.time()
        r = httpx.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
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
    """东方财富"""
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
        r = httpx.get(url, params=params, timeout=10, proxies=proxy)
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
    """腾讯港股"""
    url = f"https://qt.gtimg.cn/q={symbol}"
    try:
        start = time.time()
        r = httpx.get(url, timeout=10)
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
    """Alpha Vantage - 美股数据（带重试，短超时）"""
    api_key = DATA_SOURCES.get("alpha_vantage", {}).get("api_key", "demo")
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
    
    # 重试1次，超时缩短到5秒（避免阻塞ping）
    r = None
    latency = 0
    for attempt in range(2):
        try:
            start = time.time()
            r = httpx.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
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


# ========== 主接口 ==========

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