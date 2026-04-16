"""
proxy_config.py — 统一代理配置
所有 HTTP/HTTPS 代理统一从环境变量读取，禁止硬编码 IP。
"""
import os
import logging

logger = logging.getLogger(__name__)

# 优先级：HTTP_PROXY / http_proxy（兼容大小写）
def get_proxy_url() -> str | None:
    """读取代理地址，优先从环境变量，返回 None 表示直连。"""
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if proxy:
        logger.info(f"[ProxyConfig] 使用代理: {proxy}")
    else:
        logger.info("[ProxyConfig] 无代理配置，使用直连")
    return proxy


def build_httpx_proxies(proxy_url: str | None = None) -> dict | None:
    """
    构造 httpx 兼容的 proxies 字典。
    proxy_url 为 None 或空字符串时返回 None（直连）。
    """
    if not proxy_url:
        return None
    return {
        "http://": proxy_url,
        "https://": proxy_url,
    }


def get_proxies() -> dict | None:
    """快捷方法：读取环境变量并构造 httpx proxies。"""
    return build_httpx_proxies(get_proxy_url())


def setup_environ() -> None:
    """
    将代理地址同步到 os.environ（供 akshare / httpx / requests 等库读取）。
    只有在代理地址非空时才写入，绝不覆盖用户已设置的值。
    """
    proxy = get_proxy_url()
    if proxy:
        os.environ.setdefault("HTTP_PROXY",  proxy)
        os.environ.setdefault("HTTPS_PROXY", proxy)
        os.environ.setdefault("http_proxy",  proxy)
        os.environ.setdefault("https_proxy", proxy)
