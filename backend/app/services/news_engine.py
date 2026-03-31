"""
AlphaTerminal 实时新闻引擎 - Phase 5
全局缓存 + 后台异步刷新（API 只读缓存，<50ms 响应）
"""
import hashlib
import logging
import threading
import time
from datetime import datetime

import akshare as ak

logger = logging.getLogger(__name__)

# ── 全局新闻缓存（进程内存，uvicorn 常驻）──────────────────────────────
# 结构: list[dict]，由后台刷新线程维护，API 只读不写
_NEWS_CACHE: list[dict] = []
_NEWS_CACHE_READY: bool = False
_CACHE_LOCK = threading.Lock()

# ── 轮询标的（30 只 A 股，覆盖多行业）────────────────────────────────
NEWS_SYMBOLS = [
    "000001", "399001", "399006", "000300", "000016",   # 核心指数
    "600036", "601318", "600000", "601166", "600016",   # 银行
    "601628", "600030", "601688", "000776",              # 保险/券商
    "600585", "002594", "300750", "688981",              # 科技/新能源
    "600519", "000858", "603288", "600887",              # 消费
    "601899", "600028", "600050", "601888",              # 周期
    "002230", "300059", "688111", "300760",              # 更多中小盘
    "002475", "300015", "002352", "300122",              # 医药/电子
    "600009", "600031", "300274", "601012",              # 地产/制造
    "600150", "601668", "600276", "600900",              # 建筑/电力
]

# ── 全局去重哈希集合 ────────────────────────────────────────────────
_SEEN_URL_HASHES: set[str] = set()
_MAX_CACHE_SIZE  = 500


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
        df = ak.stock_news_em(symbol=symbol)
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
        df = ak.news_economic_baidu()
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


def refresh_news_cache(background: bool = True):
    """
    刷新全局新闻缓存池（后台线程调用，或启动时一次性填充）
    策略：
      1. 30 只个股新闻（东方财富 eastmoney）
      2. 7×24 快讯兜底（AkShare 宏观资讯，一次 100+ 条）
    两个来源合并去重，确保 >150 条
    """
    global _NEWS_CACHE, _NEWS_CACHE_READY

    def _do_fetch():
        global _NEWS_CACHE, _NEWS_CACHE_READY
        all_news: list[dict] = []

        try:
            # ① 个股新闻（30 标的，限速）
            for sym in NEWS_SYMBOLS:
                try:
                    items = _fetch_news_for_symbol(sym)
                    all_news.extend(items)
                except Exception as e:
                    logger.warning(f"[NewsEngine] 个股 {sym} 失败: {e}")
                time.sleep(0.1)

            # ② 7×24 快讯兜底
            try:
                items_7x24 = _fetch_7x24_news()
                all_news.extend(items_7x24)
            except Exception as e:
                logger.warning(f"[NewsEngine] 7x24 失败: {e}")

        except Exception as e:
            logger.error(f"[NewsEngine] 整体拉取失败: {e}", exc_info=True)
            return

        # 合并去重（MD5 URL）
        unique_news: list[dict] = []
        seen: set[str] = set()
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

        # 更新全局缓存
        with _CACHE_LOCK:
            _NEWS_CACHE = final
            _NEWS_CACHE_READY = True

        logger.info(f"[NewsEngine] 缓存刷新完成: 共 {len(final)} 条")

        logger.info(
            f"[HEARTBEAT] News pool refreshed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, "
            f"total={len(final)} items"
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
