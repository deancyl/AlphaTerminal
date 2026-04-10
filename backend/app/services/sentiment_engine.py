"""
市场情绪引擎 v6 - Phase 3 稳定版
策略：启动即填充 china_all + 后台 Sina HQ 增量刷新
"""
import logging
import os
import threading
from datetime import datetime

import numpy as np

# ── 确保代理环境变量生效 ───────────────────────────────────────
os.environ.setdefault("HTTP_PROXY",  "http://192.168.1.50:7897")
os.environ.setdefault("HTTPS_PROXY", "http://192.168.1.50:7897")
os.environ.setdefault("http_proxy",  "http://192.168.1.50:7897")
os.environ.setdefault("https_proxy", "http://192.168.1.50:7897")

logger = logging.getLogger(__name__)

# ── 新闻情感缓存（Phase 4：快讯 → 情绪联动）─────────────────────────
_NEWS_SENTIMENT = {
    "score": 0.0,       # -1.0 (极度利空) ~ +1.0 (极度利好)
    "label": "中性",
    "bullish_count": 0,
    "bearish_count": 0,
    "total_count": 0,
    "keywords": [],
    "timestamp": "",
}
_NEWS_SENTIMENT_LOCK = threading.Lock()

# 利好/利空关键词字典
_BULLISH_KEYWORDS = [
    "暴涨", "大涨", "涨停", "牛市", "利好", "重磅", "突破",
    "创新高", "超预期", "业绩", "增长", "分红", "回购",
    "增持", "买入", "强烈推荐", "政策支持", "逆势上涨",
    "宁德时代", "强势", "护盘", "资金流入",
]
_BEARISH_KEYWORDS = [
    "暴跌", "大跌", "跌停", "熊市", "利空", "黑天鹅", "危机",
    "亏损", "债务", "违约", "减持", "卖出", "风险",
    "调查", "制裁", "破裂", "业绩下滑", "裁员", "破产",
    "腥风血雨", "恐慌", "踩踏", "资金出逃",
]


def _analyze_news_sentiment(news_items: list[dict]):
    """
    Phase 4：分析最新快讯的情感倾向，更新全局 _NEWS_SENTIMENT
    返回 (score, label, bullish_count, bearish_count)
    """
    global _NEWS_SENTIMENT
    bullish = 0
    bearish = 0
    hit_keywords = []

    for item in news_items[:50]:   # 只分析最新50条
        text = (item.get("title", "") + item.get("source", "")).lower()
        b_hit = [k for k in _BULLISH_KEYWORDS if k in text]
        e_hit = [k for k in _BEARISH_KEYWORDS if k in text]
        if b_hit:
            bullish += 1
            hit_keywords.extend(b_hit)
        if e_hit:
            bearish += 1
            hit_keywords.extend(e_hit)

    total = len(news_items[:50])
    score = round((bullish - bearish) / max(total, 1), 3)  # -1 ~ +1
    label = (
        "极度利好" if score > 0.6 else
        "偏利好"   if score > 0.2 else
        "中性偏多" if score > 0.05 else
        "中性"    if score > -0.05 else
        "中性偏空" if score > -0.2 else
        "偏利空"   if score > -0.6 else
        "极度利空"
    )

    with _NEWS_SENTIMENT_LOCK:
        _NEWS_SENTIMENT = {
            "score": score,
            "label": label,
            "bullish_count": bullish,
            "bearish_count": bearish,
            "total_count": total,
            "keywords": list(set(hit_keywords))[:10],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    logger.info(
        f"[NewsSentiment] score={score} label={label} "
        f"bullish={bullish} bearish={bearish} keywords={hit_keywords[:5]}"
    )
    return score, label, bullish, bearish


def get_news_sentiment() -> dict:
    """供 router 调用的只读接口"""
    with _NEWS_SENTIMENT_LOCK:
        return dict(_NEWS_SENTIMENT)


# ── 全局缓存 ────────────────────────────────────────────────────
class SpotCache:
    _stocks = []
    _ready  = False
    _lock   = threading.Lock()
    _ts     = ""

    BUCKET_THRESHOLDS = [
        ("跌停",      -1e9,  -9.9),
        ("<-7%",     -9.9,   -7.0),
        ("-7%~-5%",  -7.0,   -5.0),
        ("-5%~-2%",  -5.0,   -2.0),
        ("-2%~0%",   -2.0,    0.0),
        ("平盘(0%)",   0.0,    0.0),
        ("0%~2%",     0.0,    2.0),
        ("2%~5%",     2.0,    5.0),
        ("5%~7%",     5.0,    7.0),
        (">7%",       7.0,    9.9),
        ("涨停",       9.9,  1e9),
    ]

    @classmethod
    def update(cls, stocks, ts=""):
        with cls._lock:
            cls._stocks = stocks
            cls._ts     = ts or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cls._ready  = True
        logger.info(f"[SpotCache] {len(stocks)} 条已缓存 @ {cls._ts}")

    @classmethod
    def get_stocks(cls):
        with cls._lock:
            return list(cls._stocks)

    @classmethod
    def is_ready(cls):
        return cls._ready

    @classmethod
    def get_ts(cls):
        with cls._lock:
            return cls._ts

    @classmethod
    def query(cls, page=1, page_size=20, sort_by="chg_pct", asc=False) -> dict:
        stocks = cls.get_stocks()
        if not stocks:
            return {"total": 0, "page": page, "pages": 0, "stocks": []}

        COL_KEYS = {
            "chg_pct":  lambda r: r["chg_pct"],
            "turnover":  lambda r: r["turnover"],
            "amount":    lambda r: r.get("volume", 0),
            "price":     lambda r: r["price"],
            "code":      lambda r: r["code"],
            "name":      lambda r: r["name"],
        }
        key_fn = COL_KEYS.get(sort_by, COL_KEYS["chg_pct"])
        sorted_s = sorted(stocks, key=key_fn, reverse=not asc)

        total = len(sorted_s)
        pages = max(1, (total + page_size - 1) // page_size)
        page  = max(1, min(page, pages))
        start = (page - 1) * page_size
        result = []
        for i, s in enumerate(sorted_s[start:start + page_size]):
            result.append({
                "seq":      start + i + 1,
                "code":     s["code"],
                "name":     s["name"],
                "price":    s["price"],
                "chg":      s["chg"],
                "chg_pct":  s["chg_pct"],
                "turnover": s["turnover"],
                "amount":   s.get("amount", 0),    # 成交额（元）
                "volume":   s["volume"],
                "market":   s.get("market", "SH"),
            })
        return {
            "total": total, "page": page, "pages": pages,
            "sort_by": sort_by, "asc": asc,
            "stocks": result,
            "timestamp": cls.get_ts(),
        }

    @classmethod
    def get_histogram(cls) -> dict:
        stocks = cls.get_stocks()
        # 若缓存数据不足500只，尝试从全市场表读取真实A股数据
        if not stocks or len(stocks) < 500:
            try:
                from app.db.database import get_all_stocks
                _, db_rows = get_all_stocks(limit=6000)
                if db_rows:
                    stocks = []
                    for r in db_rows:
                        price = float(r.get('price') or 0)
                        change_pct = float(r.get('change_pct') or 0)
                        prev = price / (1 + change_pct / 100) if change_pct != -100 else price
                        change = round(price - prev, 3)
                        code = str(r.get('code', ''))
                        stocks.append({
                            "code": code,
                            "name": r.get('name', ''),
                            "price": price,
                            "chg": change,
                            "chg_pct": change_pct,
                            "turnover": float(r.get('turnover') or 0),
                            "volume": float(r.get('volume') or 0),
                            "market": code[:2] in ('60','68','90') and "SH" or "SZ",
                        })
            except Exception as e:
                logger.warning(f"[SpotCache] DB fallback failed: {e}")

        if not stocks:
            return {"buckets": [], "total": 0, "advance": 0, "decline": 0,
                    "unchanged": 0, "limit_up": 0, "limit_down": 0,
                    "up_ratio": 0.0, "timestamp": ""}
        pcts   = np.array([s["chg_pct"] for s in stocks], dtype=float)
        total  = len(stocks)
        advance   = int((pcts > 0).sum())
        decline   = int((pcts < 0).sum())
        unchanged = int((pcts == 0).sum())
        limit_up   = int((pcts >= 9.9).sum())
        limit_down = int((pcts <= -9.9).sum())
        buckets = []
        for label, lo, hi in cls.BUCKET_THRESHOLDS:
            if label == "平盘(0%)":
                count = int((pcts == 0.0).sum())
            else:
                count = int(((pcts > lo) & (pcts <= hi)).sum())
            color = "#14b143" if lo < 0 else "#ef232a" if lo >= 0 else "#6b7280"
            buckets.append({
                "label": label, "count": count,
                "pct":   round(count / total * 100, 2) if total > 0 else 0,
                "color": color,
            })
        return {
            "buckets": buckets, "total": total,
            "advance": advance, "decline": decline, "unchanged": unchanged,
            "limit_up": limit_up, "limit_down": limit_down,
            "up_ratio": round(advance / total, 4) if total > 0 else 0,
            "timestamp": cls.get_ts(),
        }


# ── 后台拉取（先立即同步填充，再后台刷新）─────────────────────
def _immediate_fill():
    """启动时同步：用 china_all 指数立即填充（秒级）"""
    try:
        from app.db import get_latest_prices
        rows = get_latest_prices(["000001","000300","399001","399006","000688","000016","000905","000852","000510","399100"])
        if not rows:
            return
        stocks = []
        for r in rows:
            pct = float(r.get("change_pct") or 0)
            code = str(r.get("symbol") or "")
            stocks.append({
                "code":     code,
                "name":     r.get("name", ""),
                "price":    float(r.get("price") or 0),
                "chg":      float(r.get("change_pct", 0) or 0) * float(r.get("price") or 0) / 100,
                "chg_pct":  pct,
                "turnover": float(r.get("turnover") or 0),
                "volume":   float(r.get("volume") or 0),
                "amount":   float(r.get("amount") or 0),
                "market":   "SH" if code.startswith("000") else "SZ",
                "timestamp": r.get("time", "") or "",
            })
        SpotCache.update(stocks, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logger.info(f"[SpotCache] 立即填充: {len(stocks)} 条（来自 china_all）")
    except Exception as e:
        logger.error(f"[SpotCache] 立即填充失败: {e}", exc_info=True)


def _bg_sina_refresh():
    """后台：用 Sina HQ 抓取真实股票，失败时从 market_all_stocks 兜底"""
    try:
        from app.services.sina_hq_fetcher import fetch_hq_batch, get_stock_pool
        pool = get_stock_pool()
        rows = fetch_hq_batch(pool)
        if rows and len(rows) >= 5:
            SpotCache.update(rows, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            logger.info(f"[HEARTBEAT] Spot cache (Sina HQ): {len(rows)} stocks from pool of {len(pool)}")
            return
        logger.warning("[SpotCache] Sina HQ 返回不足，尝试从数据库兜底")
    except Exception as e:
        logger.warning(f"[SpotCache] Sina HQ 失败，尝试从数据库兜底: {type(e).__name__}: {e}")
    
    # 兜底：从 market_all_stocks 读取全市场数据
    try:
        from app.db.database import get_all_stocks
        total, db_rows = get_all_stocks(limit=6000)
        if db_rows:
            rows = []
            for r in db_rows:
                price = float(r.get('price') or 0)
                change_pct = float(r.get('change_pct') or 0)
                # 计算 change
                prev = price / (1 + change_pct / 100) if change_pct != -100 else price
                change = round(price - prev, 3)
                rows.append({
                    "code": r.get('code', ''),
                    "name": r.get('name', ''),
                    "price": price,
                    "chg": change,
                    "chg_pct": change_pct,
                    "turnover": float(r.get('turnover') or 0),
                    "volume": float(r.get('volume') or 0),
                    "market": r.get('code', '')[:2] in ('60','68','90') and "SH" or "SZ",
                })
            SpotCache.update(rows, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            logger.info(f"[HEARTBEAT] Spot cache (DB fallback): {len(rows)} stocks")
    except Exception as e:
        logger.error(f"[SpotCache] 数据库兜底也失败: {e}")


def trigger_spot_fetch():
    t = threading.Thread(target=_bg_sina_refresh, daemon=True, name="spot-sina-fetch")
    t.start()
    logger.info("[SpotCache] 后台 Sina HQ 刷新已触发")


# ── 新闻多源轮询（stock_news_em 主源，真实发布时间）──────────────
_NEWS_LAST_SUCCESS = None

# 宏观新闻标的（akshare stock_news_em，返回真实 发布时间 字段）
_MACRO_NEWS_SYMBOLS = [
    "000001", "399001", "399006", "000300",   # 主要指数
    "600036", "601318", "600000",              # 金融
    "600519", "000858", "600028",              # 消费/能源
    "002230", "300750", "688981",              # 科技
]


def trigger_news_fetch():
    t = threading.Thread(target=_do_news_fetch, daemon=True, name="news-multi-source")
    t.start()
    logger.info("[News] 多源新闻刷新已触发")


def _do_news_fetch():
    global _NEWS_LAST_SUCCESS
    try:
        import akshare as ak
        import time as time_module

        all_news = []
        sources = []

        # 主源：akshare stock_news_em（东方财富，每只股票返回真实 发布时间）
        for sym in _MACRO_NEWS_SYMBOLS:
            try:
                df = ak.stock_news_em(symbol=sym)
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        try:
                            title  = str(row.get("新闻标题", "") or "")
                            time_  = str(row.get("发布时间", "") or "")[:16]
                            source = str(row.get("文章来源", "东财") or "东财")
                            url    = str(row.get("新闻链接", "") or "")
                            if title and len(title) > 5:
                                all_news.append({
                                    "title":  title.strip(),
                                    "time":   time_,
                                    "publish_time": time_,
                                    "source": source,
                                    "url":    url,
                                })
                        except Exception:
                            continue
                    sources.append(f"em:{sym}")
            except Exception as e:
                logger.warning(f"[News] stock_news_em({sym}) failed: {e}")
            time_module.sleep(0.05)

        # 补充：从源 Sina 个股新闻（东方财富 stock_news_em）
        try:
            from app.services.sina_hq_fetcher import get_stock_pool
            pool = get_stock_pool()
            for sym in pool[:15]:  # 最多15只
                try:
                    df2 = ak.stock_news_em(symbol=sym)
                    if df2 is not None and not df2.empty:
                        for _, row in df2.iterrows():
                            try:
                                url     = str(row.get("新闻链接", "") or "")
                                title   = str(row.get("新闻标题", "") or "")
                                time_   = str(row.get("发布时间", "") or "")[:16]
                                source2 = str(row.get("文章来源", "东方财富") or "东方财富")
                                if title and url and len(title) > 5:
                                    all_news.append({"title": title.strip(), "time": time_, "publish_time": time_,
                                                     "source": source2, "url": url})
                            except Exception:
                                continue
                except Exception:
                    pass
                time_module.sleep(0.15)
        except Exception as e:
            logger.warning(f"[News] Sina 个股失败: {e}")

        if not all_news:
            logger.warning("[News] 所有来源无数据")
            return

        # 去重
        seen = set()
        unique = []
        for item in all_news:
            import hashlib
            h = hashlib.md5(item["url"].encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                item["tag"] = _tag_news_fallback(item["title"], item["source"])
                item["id"]  = h[:12]
                unique.append(item)

        unique.sort(key=lambda x: x.get("time", ""), reverse=True)
        final = unique[:200]

        from app.services.news_engine import _NEWS_CACHE, _NEWS_CACHE_READY, _CACHE_LOCK
        with _CACHE_LOCK:
            _NEWS_CACHE.clear()
            _NEWS_CACHE.extend(final)
            _NEWS_CACHE_READY = True

        _NEWS_LAST_SUCCESS = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[HEARTBEAT] News refreshed: {len(final)} items, sources={sources}")

        # Phase 4: 抓取完成后，异步分析情感倾向并联动情绪面板
        _analyze_news_sentiment(final)
    except Exception as e:
        logger.error(f"[News] 多源刷新失败: {type(e).__name__}: {e}", exc_info=True)


def _tag_news_fallback(title, source):
    t = title + source
    if any(k in t for k in ["突发", "紧急", "暴跌", "大涨", "重磅", "制裁", "黑天鹅"]):
        return "🔴 突发"
    if any(k in t for k in ["央行", "美联储", "降息", "降准", "CPI", "GDP", "LPR"]):
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
    return "📰 其他"


# ── 外部 API ────────────────────────────────────────────────────
def get_histogram():
    return SpotCache.get_histogram()

def query_stocks(page=1, page_size=20, sort_by="chg_pct", asc=False):
    return SpotCache.query(page, page_size, sort_by, asc)

def is_spot_ready():
    return SpotCache.is_ready()

def get_last_news_time():
    return _NEWS_LAST_SUCCESS
