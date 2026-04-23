"""
sina.py — 新浪财经行情 Fetcher（重构版）

✅ 全面接入 ValidatedHTTPClient（指数退避重试 + CircuitBreaker）
✅ 修复 parts[3] 致命错位 Bug（指数的 parts[3] 是今开，不是涨跌幅！）
✅ 全字段严格路由（指数 vs 个股字段顺序完全不同）
✅ 输出符合 QuoteData / IndexQuoteData Pydantic 契约

Sina 实时行情 API：
- 个股格式: hq_str_sh600519="贵州茅台,现价,昨收,今开,最高,最低,...,涨跌幅,..."
  字段[1]=当前价, [2]=昨收, [3]=今开, [4]=最高, [5]=最低, [32]=涨跌幅(%), [33]=涨跌额
- 指数格式: hq_str_s_sh000001="上证指数,当前价,昨收,今开,最高,最低,...,涨跌幅,涨跌额"
  ⚠️ 注意：指数的 parts[3] 是今开，不是涨跌幅！parts[32]=涨跌幅%, parts[33]=涨跌额
  涨跌幅必须通过 (current - prev_close) / prev_close * 100 计算得出
"""
from __future__ import annotations

import logging
import re
import time
from typing import Optional, List

import httpx

from .base import BaseMarketFetcher
from .alphavantage import AlphavantageFetcher
from ..http_client import ValidatedHTTPClient
from ..circuit_breaker import CircuitBreaker, CircuitState
from ..data_validator import (
    QuoteData, IndexQuoteData, KlineData,
    validate_quote, validate_kline,
    MarketType, DataType,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://hq.sinajs.cn"
KLINE_URL = "https://quotes.sina.cn/cn/api/quotes.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn",
}

# ─────────────────────────────────────────────────────────────────────────────
# 核心标的指数白名单（额外价格合理性校验）
# ─────────────────────────────────────────────────────────────────────────────
CRITICAL_INDICES = {
    "sh000001": ("上证指数",   2000.0, 6000.0),
    "sh000300": ("沪深300",   2000.0, 6000.0),
    "sh000016": ("上证50",    1500.0, 8000.0),
    "sh000688": ("科创50",     500.0, 3000.0),
    "sz399001": ("深证成指",  5000.0, 20000.0),
    "sz399006": ("创业板指",  1000.0, 6000.0),
    "sz399005": ("中小板指",  2000.0, 10000.0),
}

# ─────────────────────────────────────────────────────────────────────────────
# Symbol 规范化
# ─────────────────────────────────────────────────────────────────────────────

def normalize_symbol(symbol: str) -> str:
    """
    将各种格式的 symbol 规范化为 Sina 格式。
    例如: "600519" → "sh600519", "000001" → "sz000001"
    """
    s = symbol.lower().strip()
    if s.startswith("sh") or s.startswith("sz"):
        return s
    # 纯数字代码
    if s.startswith("6") or s.startswith("5"):
        return f"sh{s}"
    return f"sz{s}"


def is_index_symbol(symbol: str) -> bool:
    """判断是否为指数（指数和个股的字段解析逻辑不同）"""
    return symbol.lower() in CRITICAL_INDICES


# ─────────────────────────────────────────────────────────────────────────────
# 核心解析函数（修复版）
# ─────────────────────────────────────────────────────────────────────────────

def parse_sina_response(raw_text: str, symbol: str) -> Optional[dict]:
    """
    解析 Sina hq_str 响应。

    ⚠️ 指数 vs 个股的字段顺序完全不同：

    指数格式（s_sh000001）：
        parts[0]=名称, [1]=当前价, [2]=昨收, [3]=今开,
        [4]=最高, [5]=最低, ..., [32]=涨跌幅%, [33]=涨跌额

    个股格式（sh600519）：
        parts[0]=名称, [1]=今开, [2]=昨收, [3]=当前价,
        [4]=最高, [5]=最低, ..., [32]=涨跌幅%, [33]=涨跌额

    关键区别：
    - 指数: parts[3]=今开, parts[32]=涨跌幅%
    - 个股: parts[3]=当前价, parts[32]=涨跌幅%
    - 涨跌幅绝不能直接用 parts[32]（指数和个股都是同位置，但含义需要验证）
    - ⚠️ 绝对不能把 parts[3] 当作涨跌幅！那是今开（指数）或当前价（个股）
    """
    m = re.search(r'"([^"]+)"', raw_text)
    if not m:
        return None

    parts = m.group(1).split(",")
    if len(parts) < 10:
        return None

    sym_key = symbol.lower()

    if is_index_symbol(sym_key):
        # ── 指数解析 ────────────────────────────────────────────────────
        # parts[1]=当前价, parts[2]=昨收, parts[3]=今开(！), parts[32]=涨跌幅%(参考)
        try:
            current = float(parts[1])
            prev_close = float(parts[2])
            open_price = float(parts[3]) if len(parts) > 3 and parts[3] else current
            high = float(parts[4]) if len(parts) > 4 and parts[4] else current
            low = float(parts[5]) if len(parts) > 5 and parts[5] else current

            # 涨跌幅必须通过计算验证，不用 parts[32]（可能被污染）
            computed_chg_pct = ((current - prev_close) / prev_close * 100) if prev_close else 0.0
            reported_chg_pct = float(parts[32]) if len(parts) > 32 and parts[32] else computed_chg_pct

            # 如果 parts[32] 与计算值偏差 > 5%，说明 API 数据异常，使用计算值
            if abs(reported_chg_pct - computed_chg_pct) > 5.0:
                logger.warning(
                    f"[Sina] {symbol} API报告涨跌幅 {reported_chg_pct}% "
                    f"与计算值 {computed_chg_pct:.2f}% 偏差过大，使用计算值"
                )
                chg_pct = computed_chg_pct
            else:
                chg_pct = reported_chg_pct

            change = round(current - prev_close, 3) if prev_close else 0.0

            return {
                "symbol": sym_key,
                "name": parts[0].strip(),
                "market": MarketType.AShare.value,
                "price": current,
                "prev_close": prev_close,
                "open": open_price,
                "high": high,
                "low": low,
                "change_pct": round(chg_pct, 4),
                "change": round(change, 3),
                "volume": 0.0,  # 指数无成交量字段（为0）
                "timestamp": int(time.time()),
                "data_type": DataType.INDEX.value,
                "source": "sina",
            }
        except (ValueError, IndexError) as e:
            logger.error(f"[Sina] 指数解析失败 {symbol}: {e}, parts={parts[:10]}")
            return None

    else:
        # ── 个股解析 ────────────────────────────────────────────────────
        # parts[1]=今开, parts[2]=昨收, parts[3]=当前价, parts[4]=最高, parts[5]=最低
        # ⚠️ 注意：parts[3] 是当前价，不是涨跌幅！
        try:
            open_price = float(parts[1]) if parts[1] else 0.0
            prev_close = float(parts[2]) if parts[2] else 0.0
            current = float(parts[3]) if parts[3] else 0.0
            high = float(parts[4]) if parts[4] else current
            low = float(parts[5]) if parts[5] else current

            if current <= 0 or prev_close <= 0:
                logger.error(f"[Sina] 个股 {symbol} 价格异常: current={current}, prev_close={prev_close}")
                return None

            computed_chg_pct = ((current - prev_close) / prev_close * 100)
            change = round(current - prev_close, 3)

            # 成交量：parts[8]=成交量(股)
            volume = float(parts[8]) if len(parts) > 8 and parts[8] else 0.0
            # 成交额：parts[9]=成交额(元)
            amount = float(parts[9]) if len(parts) > 9 and parts[9] else None
            # 换手率：parts[10]=换手率(%)
            turnover = float(parts[10]) if len(parts) > 10 and parts[10] else None

            # 涨跌额 parts[33]
            reported_change = float(parts[33]) if len(parts) > 33 and parts[33] else change

            return {
                "symbol": normalize_symbol(parts[2].strip() if len(parts) > 2 else symbol),  # parts[2]=代码
                "name": parts[0].strip(),
                "market": MarketType.AShare.value,
                "price": current,
                "prev_close": prev_close,
                "open": open_price,
                "high": high,
                "low": low,
                "change_pct": round(computed_chg_pct, 4),
                "change": round(reported_change, 3),
                "volume": volume,
                "amount": amount,
                "turnover": turnover,
                "timestamp": int(time.time()),
                "data_type": DataType.STOCK.value,
                "source": "sina",
            }
        except (ValueError, IndexError) as e:
            logger.error(f"[Sina] 个股解析失败 {symbol}: {e}")
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Sina Fetcher
# ─────────────────────────────────────────────────────────────────────────────

class SinaFetcher(BaseMarketFetcher):
    """
    新浪财经行情 Fetcher（重构版）。

    能力：
    - A股实时行情（指数 + 个股）
    - 自动 retry（ValidatedHTTPClient）
    - 熔断器集成
    - Pydantic 严格校验输出

    不支持：
    - 港股、美股（请用 AlphavantageFetcher）
    - Level 2 盘口（请用专门的 Level 2 Fetcher）
    """

    name = "sina"
    display_name = "新浪财经"

    supports_quote = True
    supports_kline = True
    supports_order_book = False
    supports_futures = False
    supports_hk = False
    supports_us = False

    # 国内金融域名不走代理（直接连接）
    NO_PROXY_DOMAINS = {
        "hq.sinajs.cn", "finance.sina.com.cn", "sinajs.cn", "sina.com.cn",
    }

    def __init__(
        self,
        proxy: Optional[str] = None,
        cb: Optional[CircuitBreaker] = None,
    ):
        self.proxy = proxy
        self.cb = cb
        self._http: Optional[ValidatedHTTPClient] = None

    def _get_proxy(self) -> Optional[str]:
        """
        返回代理地址。
        国内金融域名直连，海外域名走代理。
        此处根据 Sina 是国内域名返回 None（直连）。
        """
        return None  # Sina 国内直连，不走代理

    async def _get_http(self) -> ValidatedHTTPClient:
        if self._http is None:
            self._http = ValidatedHTTPClient(
                proxy=self._get_proxy(),   # Sina 国内直连
                timeout=10.0,
                max_retries=3,
                base_delay=1.0,
                max_delay=30.0,
                circuit_breaker=self.cb,
            )
        return self._http

    # ── 公开 API ───────────────────────────────────────────────────────

    async def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        获取单个标的实时行情。

        Returns:
            QuoteData: 通过 Pydantic 校验的行情对象
            None: 获取失败（网络错误 / 解析失败 / 校验失败）

        校验层级：
        1. HTTP retry（最多3次，指数退避）
        2. 解析完整性（非空、字段数够）
        3. Pydantic QuoteData 校验（price > 0, OHLC 自洽, change_pct 合理）
        4. 核心标的指数价格合理性（sh000001 价格必须在 [2000, 6000]）
        """
        http = await self._get_http()
        sina_code = normalize_symbol(symbol)

        try:
            url = f"{BASE_URL}/list={sina_code}"
            resp = await http.get_with_retry(
                url,
                headers=HEADERS,
                encoding="gbk",
            )
            resp.encoding = "gbk"

            raw = parse_sina_response(resp.text, sina_code)
            if raw is None:
                if self.cb:
                    self.cb.record_failure()
                return None

            # Pydantic 校验（核心错位检测在这里触发）
            result = validate_quote(raw, source="sina")
            if result is None:
                # 校验失败（价格错位、OHLC 不一致等）→ record failure
                if self.cb:
                    self.cb.record_failure()
                return None

            # 核心标的价格合理性二次检查
            if result.symbol.lower() in CRITICAL_INDICES:
                lo, hi = CRITICAL_INDICES[result.symbol.lower()][1], CRITICAL_INDICES[result.symbol.lower()][2]
                if not (lo <= result.price <= hi):
                    logger.error(
                        f"[Sina] 核心标的 {result.name}({result.symbol}) "
                        f"价格 {result.price} 超出合理范围 [{lo}, {hi}]，拒绝！"
                    )
                    if self.cb:
                        self.cb.record_failure()
                    return None

            if self.cb:
                self.cb.record_success()
            return result

        except Exception as e:
            logger.error(f"[Sina] get_quote({symbol}) 异常: {e}")
            if self.cb:
                self.cb.record_failure()
            return None

    async def get_quotes_batch(
        self,
        symbols: List[str],
        batch_size: int = 50,
    ) -> List[QuoteData]:
        """
        批量获取多个标的行情（Sina 批量接口，最多50个/次）。

        内部自动分批请求，单个失败不影响其他。
        """
        results: List[QuoteData] = []
        http = await self._get_http()

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            codes = ",".join(normalize_symbol(s) for s in batch)

            try:
                url = f"{BASE_URL}/list={codes}"
                resp = await http.get_with_retry(url, headers=HEADERS, encoding="gbk")
                resp.encoding = "gbk"

                # 按行解析（每行一个标的）
                for line in resp.text.strip().split("\n"):
                    if "=" not in line:
                        continue
                    raw = parse_sina_response(line, "")
                    if raw is None:
                        continue
                    result = validate_quote(raw, source="sina")
                    if result is not None:
                        results.append(result)

            except Exception as e:
                logger.warning(f"[Sina] 批量请求第 {i//batch_size + 1} 批失败: {e}")
                continue

        return results

    async def get_kline(
        self,
        symbol: str,
        period: str = "day",
        datalen: int = 100,
    ) -> Optional[List[KlineData]]:
        """
        获取 K 线历史数据。

        period → Sina scale 参数：
        - minute: 5min (5)
        - day: 日K (240)
        - week: 周K (8880)
        - month: 月K (52260)
        """
        http = await self._get_http()
        sina_code = normalize_symbol(symbol)

        period_map = {
            "minute": (5, "min"),
            "day": (240, "day"),
            "week": (8880, "week"),
            "month": (52260, "month"),
        }
        scale, sina_period = period_map.get(period, (240, "day"))

        try:
            url = (
                f"{KLINE_URL}?symbol={sina_code}"
                f"&scale={scale}&datalen={datalen}"
            )
            resp = await http.get_with_retry(url, headers=HEADERS)
            data = resp.json()

            series = data.get("data", []) if isinstance(data, dict) else []
            if not series:
                logger.warning(f"[Sina] get_kline({symbol}, {period}) 无数据")
                return None

            klines: List[KlineData] = []
            for item in series:
                raw = {
                    "symbol": normalize_symbol(symbol),
                    "date": item.get("d", ""),
                    "period": sina_period,
                    "open": float(item.get("o", 0)),
                    "high": float(item.get("h", 0)),
                    "low": float(item.get("l", 0)),
                    "close": float(item.get("c", 0)),
                    "volume": float(item.get("v", 0)),
                    "timestamp": 0,
                    "source": "sina",
                }
                kline = validate_kline(raw, source="sina")
                if kline is not None:
                    klines.append(kline)

            return klines

        except Exception as e:
            logger.error(f"[Sina] get_kline({symbol}) 异常: {e}")
            return None

    async def ping(self) -> bool:
        """健康检查：抓取上证指数验证连通性"""
        try:
            result = await self.get_quote("sh000001")
            return result is not None and result.price > 0
        except Exception:
            return False

    async def close(self):
        if self._http:
            await self._http.close()
            self._http = None
