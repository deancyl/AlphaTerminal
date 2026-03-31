"""
AlphaTerminal 实时新闻引擎
- 数据源：东方财富 A股个股新闻（akshare stock_news_em）
- 轮询多个核心标的，合并去重，按时间倒序
- 去重策略：MD5(news_url) 哈希集合，内存常驻（uvicorn 进程生命周期）
"""
import hashlib
import logging
import time
from datetime import datetime, timedelta

import akshare as ak

logger = logging.getLogger(__name__)

# ── 新闻去重集合（进程内存，uvicorn 常驻）──────────────────────────────────
_SEEN_URL_HASHES: set[str] = set()
_MAX_CACHE = 500   # 超过此条数自动清理旧哈希

# ── 轮询标的（覆盖 A股主要指数 + 宏观）────────────────────────────────────
NEWS_SYMBOLS = ["000001", "399001", "399006", "000300", "000016"]


def _tag_news(title: str, source: str) -> str:
    """根据标题/来源关键词打标签"""
    t = title + source
    if any(k in t for k in ["突发", "紧急", "暴跌", "大涨", "重磅", "制裁", "黑天鹅"]):
        return "🔴 突发"
    if any(k in t for k in ["央行", "美联储", "降息", "降准", "CPI", "PPI", "GDP", "LPR"]):
        return "💎 宏观"
    if any(k in t for k in ["A股", "沪指", "深指", "创业板", "科创", "涨跌"]):
        return "📈 A股"
    if any(k in t for k in ["港股", "恒生", "南向"]):
        return "🌏 港股"
    if any(k in t for k in ["美股", "纳斯达克", "道琼斯", "标普", "美联储"]):
        return "🇺🇸 美股"
    if any(k in t for k in ["AI", "ChatGPT", "大模型", "特朗普", "科技"]):
        return "🖥️ AI"
    if any(k in t for k in ["黄金", "原油", "大宗", "能源", "铜"]):
        return "🛢️ 商品"
    if any(k in t for k in ["房地产", "楼市", "房价", "限购"]):
        return "🏠 地产"
    return "📰 其他"


def _url_md5(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _fetch_news_for_symbol(symbol: str) -> list[dict]:
    """针对单个标的拉取新闻"""
    try:
        df = ak.stock_news_em(symbol=symbol)
        if df is None or df.empty:
            return []
        rows = []
        for _, row in df.iterrows():
            try:
                url = str(row.get("新闻链接", "")) or ""
                title = str(row.get("新闻标题", "")) or ""
                if not title or not url or url == "nan":
                    continue
                rows.append({
                    "title":   title.strip(),
                    "time":    str(row.get("发布时间", ""))[:16],
                    "source":  str(row.get("文章来源", "")) or "未知",
                    "url":     url,
                })
            except Exception:
                continue
        return rows
    except Exception as e:
        logger.warning(f"[NewsEngine] stock_news_em({symbol}) 失败: {type(e).__name__}: {e}")
        return []


def fetch_latest_news(limit: int = 150) -> list[dict]:
    """
    聚合多个标的新闻，去重，返回最新 N 条
    去重机制：MD5(news_url) 哈希集合，内存常驻
    """
    global _SEEN_URL_HASHES

    all_news: list[dict] = []

    for sym in NEWS_SYMBOLS:
        items = _fetch_news_for_symbol(sym)
        all_news.extend(items)
        time.sleep(0.3)   # 礼貌性延迟，避免触发东财频率限制

    # 去重（URL 哈希）
    unique_news = []
    for item in all_news:
        h = _url_md5(item["url"])
        if h not in _SEEN_URL_HASHES:
            _SEEN_URL_HASHES.add(h)
            unique_news.append(item)

    # 内存清理（超过上限，删除最老的 100 条）
    if len(_SEEN_URL_HASHES) > _MAX_CACHE:
        # 保留最新 300 条
        _SEEN_URL_HASHES = set(list(_SEEN_URL_HASHES)[-300:])
        logger.info(f"[NewsEngine] 去重缓存已压缩，当前 {len(_SEEN_URL_HASHES)} 条")

    # 排序（时间倒序）
    unique_news.sort(key=lambda x: x.get("time", ""), reverse=True)

    # 打标签
    for item in unique_news:
        item["tag"] = _tag_news(item["title"], item["source"])
        item["id"]  = _url_md5(item["url"])[:12]   # 前12位作为唯一 ID

    logger.info(f"[NewsEngine] 本次返回 {len(unique_news[:limit])} 条新新闻（累计去重 {len(_SEEN_URL_HASHES)} 条）")
    return unique_news[:limit]


def get_mock_news() -> list[dict]:
    """降级：API 全部失败时返回内置静态数据"""
    return [
        {"id": "mock001", "tag": "🔴 突发",  "title": "央行宣布定向降准 0.25 个百分点，释放长期资金约 5000 亿元", "time": datetime.now().strftime("%H:%M"), "source": "央行官网",    "url": "#"},
        {"id": "mock002", "tag": "📈 A股",   "title": "上证指数重返 3900 点，券商板块掀起涨停潮",                           "time": datetime.now().strftime("%H:%M"), "source": "东方财富",   "url": "#"},
        {"id": "mock003", "tag": "🌏 港股",  "title": "恒生科技指数大涨 3.8%，南向资金净买入超 100 亿",                   "time": datetime.now().strftime("%H:%M"), "source": "经济通",     "url": "#"},
        {"id": "mock004", "tag": "💎 宏观",  "title": "美国 2 月 CPI 超预期回落，市场押注美联储 6 月降息概率突破 70%",     "time": datetime.now().strftime("%H:%M"), "source": "Bloomberg", "url": "#"},
        {"id": "mock005", "tag": "🖥️ AI",   "title": "OpenAI 发布 GPT-5 Turbo，上下文窗口扩展至 100 万 token",           "time": datetime.now().strftime("%H:%M"), "source": "The Verge",  "url": "#"},
    ]
