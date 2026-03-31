"""
市场情绪引擎 v5 - Phase 3
数据源：Sina HQ (qt.gtimg.cn) 批量接口 + AkShare 备用
- Stocks 表：50只重点股票（Sina HQ）
- Histogram：基于 Sina HQ 数据的 11 桶涨跌分布
- 绝不依赖被封的 Sina / Eastmoney 个股接口
"""
import logging
import threading
import time as time_module
from datetime import datetime
from typing import Optional

import akshare as ak
import numpy as np

from app.services.sina_hq_fetcher import fetch_hq_batch, build_histogram_from_rows, FOCUS_STOCKS

logger = logging.getLogger(__name__)

# ── 全局缓存 ────────────────────────────────────────────────────
class SpotCache:
    _stocks  = []    # list[dict]  实时股票数据
    _ready   = False
    _lock    = threading.Lock()
    _ts      = ""

    @classmethod
    def update(cls, stocks, ts):
        with cls._lock:
            cls._stocks = stocks
            cls._ts     = ts
            cls._ready   = True
        logger.info(f"[SpotCache] {len(stocks)} 只股票已缓存 @ {ts}")

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

        COL_MAP = {
            "chg_pct":  lambda r: r["chg_pct"],
            "turnover":  lambda r: r["turnover"],
            "amount":    lambda r: r.get("volume", 0),
            "price":     lambda r: r["price"],
            "code":      lambda r: r["code"],
            "name":      lambda r: r["name"],
        }
        key_fn = COL_MAP.get(sort_by, COL_MAP["chg_pct"])
        sorted_s = sorted(stocks, key=key_fn, reverse=not asc)

        total = len(sorted_s)
        pages = max(1, (total + page_size - 1) // page_size)
        page  = max(1, min(page, pages))
        start = (page - 1) * page_size
        end   = start + page_size
        page_stocks = sorted_s[start:end]

        result = []
        seq = start + 1
        for s in page_stocks:
            result.append({
                "seq":      seq,
                "code":     s["code"],
                "name":     s["name"],
                "price":    s["price"],
                "chg":      s["chg"],
                "chg_pct":  s["chg_pct"],
                "turnover": s["turnover"],
                "volume":   s["volume"],
                "amount":   s.get("volume", 0),
                "market":   s["market"],
            })
            seq += 1

        return {
            "total":    total,
            "page":     page,
            "pages":    pages,
            "sort_by":  sort_by,
            "asc":      asc,
            "stocks":   result,
            "timestamp": cls.get_ts(),
        }

    @classmethod
    def get_histogram(cls) -> dict:
        stocks = cls.get_stocks()
        if not stocks:
            return {"buckets": [], "total": 0, "advance": 0, "decline": 0,
                    "unchanged": 0, "limit_up": 0, "limit_down": 0,
                    "up_ratio": 0.0, "timestamp": ""}
        return build_histogram_from_rows(stocks)


# ── 新闻多源轮询 ──────────────────────────────────────────────
_NEWS_LAST_SUCCESS = None

def _fetch_news_with_fallback():
    """
    主从备份新闻抓取（不阻塞 API）
    1. 优先：AkShare stock_news_em (30只股票)
    2. 兜底：AkShare news_economic_baidu (宏观快讯)
    """
    global _NEWS_LAST_SUCCESS
    from app.services.news_engine import _NEWS_CACHE, _NEWS_CACHE_READY, _CACHE_LOCK

    all_news = []
    sources_used = []

    # ① 主源：AkShare stock_news_em（东方财富，30只股票）
    from app.services.news_engine import NEWS_SYMBOLS, _fetch_news_for_symbol, _tag_news, _url_md5
    try:
        for sym in NEWS_SYMBOLS:
            try:
                items = _fetch_news_for_symbol(sym)
                all_news.extend(items)
                time_module.sleep(0.1)
            except Exception as e:
                logger.warning(f"[News] {sym} 失败: {e}")
        if all_news:
            sources_used.append("akshare_news")
    except Exception as e:
        logger.warning(f"[News] 主源失败: {e}")

    # ② 从源：AkShare news_economic_baidu（宏观快讯，兜底）
    try:
        df = ak.news_economic_baidu()
        if df is not None and not df.empty:
            from app.services.news_engine import get_mock_news as _gm
            for _, row in df.iterrows():
                try:
                    url   = str(row.get("新闻链接", "") or "")
                    title = str(row.get("新闻标题", "") or "")
                    time_ = str(row.get("发布时间", "")[:16])
                    src   = str(row.get("来源", "百度财经") or "百度财经")
                    if title and url and url != "nan":
                        all_news.append({
                            "title": title.strip(),
                            "time":  time_,
                            "source": src,
                            "url":   url,
                        })
                except Exception:
                    continue
            sources_used.append("baidu_economic")
    except Exception as e:
        logger.warning(f"[News] 百度宏观快讯失败: {e}")

    if not all_news:
        logger.warning("[News] 所有来源均失败，跳过本次刷新")
        return

    # 去重（MD5 URL）
    seen = set()
    unique = []
    for item in all_news:
        h = _url_md5(item["url"])
        if h not in seen:
            seen.add(h)
            item["tag"] = _tag_news(item["title"], item["source"])
            item["id"]   = h[:12]
            unique.append(item)

    unique.sort(key=lambda x: x.get("time", ""), reverse=True)
    final = unique[:200]

    with _CACHE_LOCK:
        _NEWS_CACHE      = final
        _NEWS_CACHE_READY = True

    _NEWS_LAST_SUCCESS = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        f"[HEARTBEAT] News refreshed at {_NEWS_LAST_SUCCESS}, "
        f"sources={sources_used}, total={len(final)} items"
    )


# ── 全量股票拉取 ──────────────────────────────────────────────
def _fetch_spot_cache():
    """使用 Sina HQ 批量接口拉取 50 只重点股票"""
    try:
        ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = fetch_hq_batch(FOCUS_STOCKS)
        if rows:
            SpotCache.update(rows, ts)
            logger.info(f"[HEARTBEAT] Spot cache refreshed: {len(rows)} stocks at {ts}")
        else:
            logger.warning("[SpotCache] Sina HQ 返回空，保留旧缓存")
    except Exception as e:
        logger.error(f"[SpotCache] 拉取失败: {type(e).__name__}: {e}", exc_info=True)


# ── 调度器用函数 ──────────────────────────────────────────────
def trigger_spot_fetch():
    t = threading.Thread(target=_fetch_spot_cache, daemon=True, name="spot-hq-fetch")
    t.start()
    logger.info("[SpotCache] 后台 Sina HQ 拉取已触发")

def trigger_news_fetch():
    t = threading.Thread(target=_fetch_news_with_fallback, daemon=True, name="news-multi-source")
    t.start()
    logger.info("[News] 多源新闻刷新已触发")

def get_last_news_time() -> Optional[str]:
    return _NEWS_LAST_SUCCESS


# ── 外部 API ────────────────────────────────────────────────────
def get_histogram():
    return SpotCache.get_histogram()

def query_stocks(page=1, page_size=20, sort_by="chg_pct", asc=False):
    return SpotCache.query(page, page_size, sort_by, asc)

def is_spot_ready():
    return SpotCache.is_ready()
