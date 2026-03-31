"""
市场情绪引擎 - Phase 2
涨跌家数温度计（A股全市场实时情绪）
数据源：新浪 A股实时行情（stock_zh_a_spot）
缓存刷新：后台每 3 分钟，不阻塞 API
"""
import logging
import threading
import time
from datetime import datetime

import akshare as ak

logger = logging.getLogger(__name__)

# ── 全局缓存 ────────────────────────────────────────────────────
_SENTIMENT_CACHE = {
    "advance":    0,
    "decline":    0,
    "unchanged":  0,
    "limit_up":   0,
    "limit_down": 0,
    "total":      0,
    "up_ratio":   0.0,    # 0.0 ~ 1.0
    "timestamp":  "",
}
_SENTIMENT_READY = False
_SENTIMENT_LOCK  = threading.Lock()


def _fetch_sentiment(background: bool = True):
    """后台拉取新浪 A股全市场实时行情，计算涨跌家数"""
    def _do():
        global _SENTIMENT_CACHE, _SENTIMENT_READY
        try:
            logger.info("[Sentiment] 开始拉取全市场行情...")
            df = ak.stock_zh_a_spot()
            if df is None or df.empty:
                logger.warning("[Sentiment] 全市场数据为空")
                return

            # 新浪字段：['代码','名称','最新价','涨跌额','涨跌幅','买入','卖出','昨收','今开','最高','最低','成交量']
            pct_col = '涨跌幅'
            if pct_col not in df.columns:
                logger.warning(f"[Sentiment] 无涨跌幅列，可用列: {list(df.columns)}")
                return

            pct = df[pct_col].astype(float)
            now = datetime.now().strftime("%H:%M")

            advance   = int((pct > 0).sum())
            decline   = int((pct < 0).sum())
            unchanged = int((pct == 0).sum())
            total     = len(df)
            up_ratio  = round(advance / total, 4) if total > 0 else 0.0

            # 涨停 ≈ 涨跌幅 >= 9.9%（ST 股 5%），跌停 ≈ <= -9.9%
            limit_up   = int((pct >= 9.9).sum())
            limit_down = int((pct <= -9.9).sum())

            with _SENTIMENT_LOCK:
                _SENTIMENT_CACHE = {
                    "advance":    advance,
                    "decline":    decline,
                    "unchanged":  unchanged,
                    "limit_up":   limit_up,
                    "limit_down": limit_down,
                    "total":      total,
                    "up_ratio":   up_ratio,   # 0.0 ~ 1.0
                    "timestamp":  now,
                }
                _SENTIMENT_READY = True

            logger.info(
                f"[Sentiment] 涨跌家数完成: 涨 {advance}/{total} ({up_ratio:.1%}) "
                f"| 涨停 {limit_up} 跌停 {limit_down}"
            )
        except Exception as e:
            logger.error(f"[Sentiment] 拉取失败: {type(e).__name__}: {e}", exc_info=True)

    if background:
        t = threading.Thread(target=_do, daemon=True, name="sentiment-fetch")
        t.start()
    else:
        _do()


def get_sentiment() -> dict:
    """API 调用：返回当前缓存的情绪数据"""
    with _SENTIMENT_LOCK:
        return dict(_SENTIMENT_CACHE)


def is_sentiment_ready() -> bool:
    return _SENTIMENT_READY
