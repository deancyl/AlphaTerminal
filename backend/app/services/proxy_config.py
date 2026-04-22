"""
proxy_config.py — 统一代理配置 + 智能分流
所有 HTTP/HTTPS 代理统一从环境变量读取，禁止硬编码 IP。
国内数据源直连，海外数据源走代理。
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── 国内数据源（直连，不走代理）───────────────────────────────────────
DOMESTIC_HOSTS = frozenset([
    # 东方财富
    "eastmoney.com", "emoney.cn", "followfund.cn",
    "18.push2.eastmoney.com", "80.push2.eastmoney.com",
    "push2.eastmoney.com", "push3.eastmoney.com",
    # 新浪财经
    "sina.com.cn", "sinajs.cn", "hq.sinajs.cn", "finance.sina.com.cn",
    # 腾讯财经
    "gtimg.cn", "qt.gtimg.cn", "web.ifzq.gtimg.cn",
    # 网易财经
    "126.com", "money.126.com", "quotes.money.163.com",
    # 百度/Alibaba/京东财经
    "baidu.com", "alibaba.com", "jd.com",
    # 上海黄金交易所
    "sge.com", "sge.com.cn",
    # 中国外汇交易中心
    "chinamoney.com", "chinamoney.com.cn",
    # 财新
    "caixin.com",
    # 同花顺
    "10jqka.com", "data.10jqka.com",
    # 雪球
    "xueqiu.com",
    # Wind
    "wind.com", "wind.com.cn",
    # 北向数据
    "hbstock.com",
    # 其他国内金融节点
    "legulegu.com",
    "morningstar.com",
    # AkShare 常用域名（备用）
    "akshare.com",
])

# ── 海外数据源（走代理）───────────────────────────────────────────────
OVERSEAS_HOSTS = frozenset([
    "alphavantage.co", "alphavantage.com",
    "finnhub.com",
    "twelvedata.com",
    "polygon.io",
    "yahoo.com", "yahooapis.com",
    "fRED.stlouisfed.org", "fred.stlouisfed.org",
    "api.nasdaq.com",
    "stooq.com",
])


def _is_domestic(url: str) -> bool:
    """判断 URL 是否为国内数据源（直连）"""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
        # 去掉端口
        host = host.split(":")[0]
        # 精确匹配或域名后缀匹配
        if host in DOMESTIC_HOSTS:
            return True
        # *.eastmoney.com 类后缀匹配
        for domestic in DOMESTIC_HOSTS:
            if host == domestic or host.endswith("." + domestic):
                return True
        return False
    except Exception:
        return False


def _is_overseas(url: str) -> bool:
    """判断 URL 是否为海外数据源（走代理）"""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower().split(":")[0]
        for overseas in OVERSEAS_HOSTS:
            if host == overseas or host.endswith("." + overseas):
                return True
        return False
    except Exception:
        return False


# ── 代理配置 ────────────────────────────────────────────────────────────

PROXY_URL = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")


def get_proxy_url() -> str | None:
    """读取代理地址。"""
    return PROXY_URL


def smart_proxy_for(url: str) -> str | None:
    """
    根据目标 URL 智能返回代理配置。
    - 国内数据源 → 直连（返回 None）
    - 海外数据源 → 走代理 PROXY_URL
    - 无法判断 → 直连（保守策略，避免代理撞墙）
    """
    if _is_domestic(url):
        return None
    if _is_overseas(url):
        return PROXY_URL
    # 未知域名 → 直连（保守策略）
    return None


def smart_proxies(url: str) -> dict | None:
    """快捷方法：根据 URL 返回对应 httpx proxies（直连或代理）。"""
    proxy = smart_proxy_for(url)
    return build_httpx_proxies(proxy)


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


def get_proxies(url: str | None = None) -> dict | None:
    """
    快捷方法：构造 httpx proxies。
    传入 url 时使用智能分流（国内直连/海外代理），
    不传 url 时返回全局代理（向后兼容）。
    """
    if url:
        return smart_proxies(url)
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
