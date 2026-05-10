"""
数据源管理接口

Extracted from market.py for better code organization.
Provides endpoints for:
- Source status monitoring
- Circuit breaker status
- Source switching
- Connectivity testing
- Proxy configuration
- API key management
"""
import asyncio
import logging

from fastapi import APIRouter

from app.utils.response import success_response, error_response, ErrorCode
from app.services.quote_source import get_source_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/source", tags=["source"])


# ── 代理设置（模块级状态）───────────────────────────────────────────────
_proxy_config = {"proxy_url": "", "enabled": False}


# ── 数据源状态管理 ───────────────────────────────────────────────────────
@router.get("/status")
async def source_status():
    """获取数据源状态"""
    return success_response(get_source_status())


@router.get("/circuit-breaker")
async def circuit_breaker_status():
    """获取所有数据源的熔断器状态"""
    from app.services.quote_source import get_circuit_breaker_status
    return success_response(get_circuit_breaker_status())


@router.post("/switch")
async def switch_source(source: str):
    """手动切换主源"""
    from app.services.quote_source import set_primary_source
    ok = set_primary_source(source)
    if ok:
        return success_response({"message": f"主源已切换为: {source}"})
    return error_response(ErrorCode.BAD_REQUEST, f"无效的数据源: {source}")


@router.get("/test")
async def test_all_sources_api(symbol: str = "sh000001"):
    """测试所有数据源连通性"""
    from app.services.quote_source import test_all_sources
    results = test_all_sources(symbol)
    return success_response(results)


@router.get("/config")
async def source_config():
    """获取数据源完整配置"""
    from app.services.quote_source import DATA_SOURCES
    return success_response({
        k: {
            "name": v["name"],
            "name_cn": v.get("name_cn"),
            "type": v["type"],
            "proxy": v.get("proxy"),
            "has_pepb": v.get("has_pepb"),
            "has_realtime": v.get("has_realtime"),
            "api_key": "***" if v.get("api_key") else None,
        } for k, v in DATA_SOURCES.items()
    })


# ── 代理设置 ───────────────────────────────────────────────────────────
@router.get("/proxy")
async def get_proxy():
    """获取当前代理设置"""
    return success_response(_proxy_config)


@router.post("/proxy")
async def set_proxy(config: dict):
    """设置代理"""
    global _proxy_config
    proxy = config.get("proxy", "")
    _proxy_config = {
        "proxy_url": proxy,
        "enabled": bool(proxy)
    }
    # 更新所有需要代理的数据源
    from app.services import quote_source
    if proxy:
        for k, v in quote_source.DATA_SOURCES.items():
            if v.get("proxy"):
                v["proxy_url"] = proxy
    return success_response({"message": "代理设置已更新", "proxy": proxy})


# ── 探测所有源状态 ───────────────────────────────────────────────────
@router.get("/ping")
async def ping_all_sources():
    """主动探测所有数据源状态（并发异步，不阻塞事件循环）"""
    from app.services import quote_source

    # 测试符号映射
    test_map = {
        "tencent": "sh000001",
        "sina": "sh000001",
        "eastmoney": "sh000001",
        "sina_kline": "sh000001",
        "tencent_hk": "hk00700",
        "alpha_vantage": "AAPL",
    }

    # 并发探测所有源
    async def probe(name: str):
        sym = test_map.get(name, "sh000001")
        return name, await quote_source.test_source_async(name, sym)

    probes = [probe(name) for name in quote_source.DATA_SOURCES.keys()]
    probe_results = await asyncio.gather(*probes, return_exceptions=True)

    results = {}
    for item in probe_results:
        if isinstance(item, Exception):
            continue
        name, result = item
        results[name] = result

    return success_response(results)


# ── AlphaVantage API Key 设置 ─────────────────────────────────────────
@router.get("/alpha_vantage_key")
async def get_alpha_vantage_key():
    """获取AlphaVantage API Key"""
    from app.services.quote_source import DATA_SOURCES
    key = DATA_SOURCES.get("alpha_vantage", {}).get("api_key", "")
    return success_response({"api_key": key})


@router.post("/alpha_vantage_key")
async def set_alpha_vantage_key(config: dict):
    """设置AlphaVantage API Key"""
    from app.services.quote_source import DATA_SOURCES
    new_key = config.get("api_key", "").strip()
    if new_key:
        DATA_SOURCES["alpha_vantage"]["api_key"] = new_key
        return success_response({"message": "API Key已更新", "api_key": new_key})
    return error_response(ErrorCode.BAD_REQUEST, "API Key不能为空")


# ── 导出符号 ──────────────────────────────────────────────────────
__all__ = ["router"]
