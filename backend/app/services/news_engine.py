"""
AlphaTerminal 实时新闻引擎 - Phase 5
全局缓存 + 后台异步刷新（API 只读缓存，<50ms 响应）
"""
import asyncio
import hashlib
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ── 代理由 proxy_config.py 统一管理，从环境变量读取 ──────────────

logger = logging.getLogger(__name__)

# ── 延迟导入akshare（减少启动内存）────────────────────────────────────
_akshare_module = None

def _get_ak():
    """延迟加载akshare"""
    global _akshare_module
    if _akshare_module is None:
        import akshare as ak
        _akshare_module = ak
    return _akshare_module

# ── 线程池执行器（用于异步并行获取新闻）────────────────────────────────────
_news_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="news_fetch_")

# ── 全局新闻缓存（进程内存，uvicorn 常驻）──────────────────────────────
# 结构: list[dict]，由后台刷新线程维护，API 只读不写
_NEWS_CACHE: list[dict] = []
_NEWS_CACHE_READY: bool = False
_CACHE_LOCK = threading.Lock()

# ── 轮询标的（20 只 A 股核心，覆盖主要行业）─────────────────────────
NEWS_SYMBOLS = [
    "000001", "399001", "399006", "000300",              # 核心指数
    "600036", "601318", "600030", "600016",              # 银行/券商
    "600519", "002594", "300750", "688981",              # 消费/新能源/半导体
    "601628", "000776",                                  # 保险
    "002230", "300059", "688111",                        # 科技
    "600028", "601899", "600050",                        # 周期
    "600887", "603288", "000858",                        # 消费
    "600009", "601888",                                  # 旅游/免税
]

# ── 缓存去重在 refresh_news_cache() 内部通过局部 seen 集合实现 ─────


# ─────────────────────────────────────────────────────────────────
def _tag_news(title: str, source: str) -> str:
    t = title + source
    if any(k in t for k in ["突发", "紧急", "暴跌", "大涨", "重磅", "制裁", "黑天鹅"]):
        return "🔴 突发"
    if any(k in t for k in ["央行", "美联储", "降息", "降准", "CPI", "PPI", "GDP", "LPR"]):
        return "💎 宏观"
    if any(k in t for k in ["A股", "沪指", "深指", "创业板", "科创", "涨跌"]):
        return "📈 A股"
    if any(k in t for k in ["港股", "恒生", "南向"]):
        return "🌏 港股"
    if any(k in t for k in ["美股", "纳斯达克", "道琼斯", "标普"]):
        return "🇺🇸 美股"
    if any(k in t for k in ["AI", "ChatGPT", "大模型", "特朗普", "科技"]):
        return "🖥️ AI"
    if any(k in t for k in ["黄金", "原油", "大宗", "能源"]):
        return "🛢️ 商品"
    if any(k in t for k in ["房地产", "楼市", "房价", "限购"]):
        return "🏠 地产"
    return "📰 其他"


def _url_md5(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _fetch_news_for_symbol(symbol: str) -> list[dict]:
    """针对单个标的拉取新闻"""
    try:
        df = _get_ak().stock_news_em(symbol=symbol)
        if df is None or df.empty:
            return []
        rows = []
        for _, row in df.iterrows():
            try:
                raw_url = str(row.get("新闻链接", "")) or ""
                title   = str(row.get("新闻标题", "")) or ""
                if not title or not raw_url or raw_url == "nan":
                    continue
                rows.append({
                    "title":  title.strip(),
                    "time":   str(row.get("发布时间", ""))[:16],
                    "source": str(row.get("文章来源", "")) or "未知",
                    "url":    raw_url,   # ← 绝对路径，例: http://finance.eastmoney.com/a/202603313690418549.html
                })
            except Exception:
                continue
        return rows
    except Exception as e:
        logger.warning(f"[NewsEngine] stock_news_em({symbol}) 失败: {type(e).__name__}: {e}")
        return []


def _fetch_7x24_news() -> list[dict]:
    """
    东方财富 7×24 实时全球资讯（AkShare 宏观接口，一次性拉取 150+ 条）
    这是兜底数据源，不受个股新闻数量限制
    """
    try:
        df = _get_ak().news_economic_baidu()
        if df is None or df.empty:
            return []
        rows = []
        for _, row in df.iterrows():
            try:
                raw_url = str(row.get("新闻链接", "")) or ""
                title   = str(row.get("新闻标题", "")) or ""
                time_   = str(row.get("发布时间", ""))[:16]
                source  = str(row.get("来源", "")) or "百度财经"
                if not title or not raw_url or raw_url == "nan":
                    continue
                rows.append({
                    "title":  title.strip(),
                    "time":   time_,
                    "source": source,
                    "url":    raw_url,
                })
            except Exception:
                continue
        logger.info(f"[NewsEngine] 7x24 快讯: {len(rows)} 条")
        return rows
    except Exception as e:
        logger.warning(f"[NewsEngine] 7x24 拉取失败: {type(e).__name__}: {e}")
        return []


async def fetch_news_parallel(symbols: list[str]) -> list[dict]:
    """并行获取多个股票的新闻（最多4个并发）"""
    loop = asyncio.get_event_loop()

    async def fetch_one(sym):
        try:
            df = await loop.run_in_executor(
                _news_executor,
                lambda s=sym: _get_ak().stock_news_em(symbol=s)
            )
            if df is None or df.empty:
                return []
            rows = []
            for _, row in df.iterrows():
                try:
                    raw_url = str(row.get("新闻链接", "")) or ""
                    title   = str(row.get("新闻标题", "")) or ""
                    if not title or not raw_url or raw_url == "nan":
                        continue
                    rows.append({
                        "title":  title.strip(),
                        "time":   str(row.get("发布时间", ""))[:16],
                        "source": str(row.get("文章来源", "")) or "未知",
                        "url":    raw_url,
                    })
                except Exception:
                    continue
            return rows
        except Exception as e:
            logger.warning(f"[NewsEngine] parallel fetch failed for {sym}: {type(e).__name__}: {e}")
            return []

    results = await asyncio.gather(*[fetch_one(s) for s in symbols])

    all_news = []
    seen = set()
    for items in results:
        for item in items:
            h = _url_md5(item["url"])
            if h not in seen:
                seen.add(h)
                all_news.append(item)

    return all_news


def refresh_news_cache(background: bool = True):
    """
    刷新全局新闻缓存池（后台线程调用）
    策略：
      1. 宏观快讯：stock_news_main_cx（财新，100条，走代理，稳定可靠）
      2. 个股新闻：akshare stock_news_em（东方财富，20只）
      所有来源均包含真实发布时间（发布时间 字段），无时间戳造假
    """
    global _NEWS_CACHE, _NEWS_CACHE_READY

    # ── 宏观快讯专用标的（从 stock_news_em 拉，真实时间戳）──────────────
    _MACRO_SYMBOLS = [
        "000001", "399001", "399006", "000300",   # 主要指数
        "600036", "601318", "600000",              # 金融
        "600519", "000858", "600028",              # 消费/能源
        "002230", "300750", "688981",              # 科技
    ]

    def _do_fetch():
        global _NEWS_CACHE, _NEWS_CACHE_READY
        all_news: list[dict] = []
        sources_used = []

        try:
            macro_news = asyncio.run(fetch_news_parallel(_MACRO_SYMBOLS))
            all_news.extend(macro_news)
            sources_used.append(f"parallel:{len(_MACRO_SYMBOLS)}")
            logger.info(f"[SCHEDULER] 宏观快讯并行获取: {len(macro_news)} 条")

            stock_news = asyncio.run(fetch_news_parallel(NEWS_SYMBOLS))
            all_news.extend(stock_news)
            sources_used.append(f"parallel:{len(NEWS_SYMBOLS)}")
            logger.info(f"[SCHEDULER] 个股新闻并行获取: {len(stock_news)} 条")

        except Exception as e:
            logger.error(f"[SCHEDULER] Overall news fetch failed: {e}", exc_info=True)
            logger.info(f"[HEARTBEAT] News fetch failed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {e}")
            return

        if not all_news:
            logger.warning("[SCHEDULER] All sources returned empty, skipping cache update.")
            return

        # 合并去重（MD5 URL）
        seen = set()
        unique_news = []
        for item in all_news:
            h = _url_md5(item["url"])
            if h not in seen:
                seen.add(h)
                item["tag"] = _tag_news(item["title"], item["source"])
                item["id"]  = h[:12]
                unique_news.append(item)

        # 全量覆盖缓存（去重后最新 200 条）
        unique_news.sort(key=lambda x: x.get("time", ""), reverse=True)
        final = unique_news[:200]

        with _CACHE_LOCK:
            _NEWS_CACHE.clear()
            _NEWS_CACHE.extend(final)
            _NEWS_CACHE_READY = True

        # ── 审计日志：记录最新一条新闻 ────────────────────────────────
        if final:
            latest = final[0]
            logger.info(
                f"[News Fetch] 抓取完成，共 {len(final)} 条。"
                f"最新新闻时间：{latest['time']}，标题：{latest['title'][:40]}"
            )
        else:
            logger.info("[News Fetch] 抓取完成，缓存为空。")

        logger.info(
            f"[SCHEDULER] Successfully pushed {len(final)} items to cache. "
            f"(sources: {sources_used}, total_raw={len(all_news)}, total_unique={len(unique_news)})"
        )
        logger.info(
            f"[HEARTBEAT] News refreshed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, "
            f"total={len(final)} items (sources: {sources_used})"
        )

    if background:
        t = threading.Thread(target=_do_fetch, daemon=True, name="news-cache-refresh")
        t.start()
        logger.info("[NewsEngine] 后台刷新线程已启动")
    else:
        _do_fetch()


# ── 外部调用：返回缓存数据（<50ms）─────────────────────────────────
def get_cached_news(limit: int = 150) -> list[dict]:
    """API 调用专用：直接读缓存，毫秒级返回"""
    with _CACHE_LOCK:
        return list(_NEWS_CACHE[:limit])


def is_cache_ready() -> bool:
    return _NEWS_CACHE_READY


def get_mock_news() -> list[dict]:
    return [
        {"id": "mock001", "tag": "🔴 突发", "title": "央行宣布定向降准 0.25 个百分点，释放长期资金约 5000 亿元",
         "time": datetime.now().strftime("%H:%M"), "source": "央行官网", "url": "#"},
        {"id": "mock002", "tag": "📈 A股",  "title": "上证指数重返 3900 点，券商板块掀起涨停潮",
         "time": datetime.now().strftime("%H:%M"), "source": "东方财富", "url": "#"},
        {"id": "mock003", "tag": "🌏 港股", "title": "恒生科技指数大涨 3.8%，南向资金净买入超 100 亿",
         "time": datetime.now().strftime("%H:%M"), "source": "经济通", "url": "#"},
        {"id": "mock004", "tag": "💎 宏观", "title": "美国 2 月 CPI 超预期回落，市场押注美联储 6 月降息概率突破 70%",
         "time": datetime.now().strftime("%H:%M"), "source": "Bloomberg", "url": "#"},
        {"id": "mock005", "tag": "🖥️ AI",  "title": "OpenAI 发布 GPT-5 Turbo，上下文窗口扩展至 100 万 token",
         "time": datetime.now().strftime("%H:%M"), "source": "The Verge", "url": "#"},
    ]
