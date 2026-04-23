#!/usr/bin/env python3
"""
test_sina_fetcher.py — Sina Fetcher 重构后单元测试
测试框架：pytest（按 test-runner skill 规范）

覆盖：
1. Symbol 规范化（normalize_symbol）
2. 指数 vs 个股 路由区分（is_index_symbol）
3. 指数解析 parts[3] Bug 修复（上证指数 3948.55 正确解析）
4. 个股解析字段顺序正确性
5. 核心标的 sh000001 价格白名单拒绝（price=3.94 拒绝）
6. HTTP retry + CB 联动（mock）
7. get_quote 端到端（mock HTTP 200，返回正确价格）
"""
import asyncio
import sys
import os
import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.fetchers.sina import (
    SinaFetcher,
    normalize_symbol,
    is_index_symbol,
    parse_sina_response,
    CRITICAL_INDICES,
)
from app.services.data_validator import QuoteData, IndexQuoteData, MarketType, DataType
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Symbol Normalization
# ─────────────────────────────────────────────────────────────────────────────
class TestSymbolNormalization:
    def test_numeric_to_sh(self):
        assert normalize_symbol("600519") == "sh600519"
        assert normalize_symbol("000001") == "sz000001"
        assert normalize_symbol("000300") == "sz000300"

    def test_already_normalized(self):
        assert normalize_symbol("sh600519") == "sh600519"
        assert normalize_symbol("sz000001") == "sz000001"

    def test_case_insensitive(self):
        assert normalize_symbol("SH000001") == "sh000001"  # SH prefix preserved, lowercased
        assert normalize_symbol("Sz000001") == "sz000001"  # SZ prefix preserved, lowercased


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Index vs Stock Routing
# ─────────────────────────────────────────────────────────────────────────────
class TestIndexRouting:
    def test_index_symbols(self):
        indices = ["sh000001", "sh000300", "sh000016", "sh000688",
                   "sz399001", "sz399006", "sz399005"]
        for s in indices:
            assert is_index_symbol(s) is True, f"{s} should be index"

    def test_stock_symbols(self):
        stocks = ["sh600519", "sz000858", "sh601318", "sz002594"]
        for s in stocks:
            assert is_index_symbol(s) is False, f"{s} should be stock"

    def test_international_symbols(self):
        assert is_index_symbol("usIBM") is False
        assert is_index_symbol("usAAPL") is False


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: 核心 Bug 修复 — 上证指数 parts[3] 错位
# ─────────────────────────────────────────────────────────────────────────────
class TestSinaIndexParsingBug:
    """
    修复前：parts[3] 被当作涨跌幅（那是今开价！）
    修复后：涨跌幅必须通过 (current - prev_close) / prev_close * 100 计算

    真实 Sina API 返回（2026-04-21 上证指数）：
    parts[0]="上证指数", parts[1]="3923.286", parts[2]="3913.723", parts[3]="3918.621"
    （parts[3]=今开，parts[32]="0.24"=涨跌幅%，parts[33]="9.563"=涨跌额）
    """

    def test_index_3948_price_parsed_correctly(self):
        """上证指数真实场景：价格应为 3948.55，今开应为独立字段"""
        # 模拟真实 Sina API 返回（与历史数据格式一致）
        raw = (
            'var hq_str_s_sh000001="上证指数,3948.555,3948.555,3923.280,'
            '3950.123,3910.456,,,,,,,,,,,,,,,,,,,,,,,,0.64,25.275,,,,,,";'
        )
        result = parse_sina_response(raw, "sh000001")

        assert result is not None, "解析结果不能为 None"
        assert result["price"] == 3948.555, f"价格应为 3948.555，实际 {result['price']}"
        assert result["name"] == "上证指数"
        assert result["source"] == "sina"
        # 今开不应该等于当前价（parts[3] 不是涨跌幅）
        assert result["open"] == 3923.280, f"今开应为 3923.280，实际 {result['open']}"

    def test_index_change_pct_calculated_not_from_parts32(self):
        """
        验证 parts[3] 错位修复：涨跌幅必须通过计算得出
        parts[3]=今开（3923.28），不是涨跌幅！
        正确的 change_pct = (3948.555 - 3948.555) / 3948.555 * 100 ≈ 0%
        但若 parts[32]=0.64 被直接采用（错位场景），则为另一值
        """
        raw = (
            'var hq_str_s_sh000001="上证指数,3948.555,3948.555,3923.280,'
            '3950.123,3910.456,,,,,,,,,,,,,,,,,,,,,,,,0.00,0.000,,,,,,";'
        )
        result = parse_sina_response(raw, "sh000001")
        assert result is not None
        # (3948.555 - 3948.555) / 3948.555 * 100 = 0.0
        assert abs(result["change_pct"]) < 0.01, \
            f"change_pct 应接近 0（平盘），实际 {result['change_pct']}"

    def test_index_with_reported_chg_pct_deviation(self):
        """
        parts[32] 与计算值偏差 > 5% 时，应使用计算值而非 API 报告值
        这是防止 API 数据污染的最终安全网
        """
        # parts[32] 报告 10%，但计算应为 0.64%（明显异常）
        raw = (
            'var hq_str_s_sh000001="上证指数,3948.555,3948.555,3923.280,'
            '3950.123,3910.456,,,,,,,,,,,,,,,,,,,,,,,,10.00,390.000,,,,,,";'
        )
        result = parse_sina_response(raw, "sh000001")
        assert result is not None
        # 系统应拒绝 parts[32]=10%，使用计算值
        # (3948.555-3948.555)/3948.555*100 = 0%
        assert abs(result["change_pct"]) < 1.0, \
            f"偏差超过5%时应使用计算值，change_pct={result['change_pct']}，期望接近0"


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: 个股解析字段顺序正确性
# ─────────────────────────────────────────────────────────────────────────────
class TestSinaStockParsing:
    """验证个股字段顺序：parts[3]=当前价（非涨跌幅）"""

    def test_stock_guizhou_maotai(self):
        """贵州茅台：parts[3]=当前价，parts[1]=今开，parts[2]=昨收"""
        raw = (
            'var hq_str_sh600519="贵州茅台,1800.00,1948.55,1795.00,1810.00,1780.00,,,'
            ',,,,,,,,,,,,,,,,,,,,,,,,,-7.62,-148.55,";'
        )
        result = parse_sina_response(raw, "sh600519")
        assert result is not None
        # parts[3] = 当前价 = 1795.00（不是 parts[32] 涨跌幅 -7.62）
        assert result["price"] == 1795.00, f"当前价应为 1795.00，实际 {result['price']}"
        assert result["name"] == "贵州茅台"
        assert result["open"] == 1800.00, f"今开应为 1800.00，实际 {result['open']}"
        assert result["prev_close"] == 1948.55, f"昨收应为 1948.55，实际 {result['prev_close']}"

    def test_stock_change_pct_consistency(self):
        """个股涨跌幅必须与 (price - prev_close) / prev_close * 100 一致"""
        raw = (
            'var hq_str_sh600519="贵州茅台,1800.00,1948.55,1795.00,1810.00,1780.00,,,'
            ',,,,,,,,,,,,,,,,,,,,,,,,,-7.62,-148.55, ";'
        )
        result = parse_sina_response(raw, "sh600519")
        assert result is not None
        expected_chg_pct = round((1795.00 - 1948.55) / 1948.55 * 100, 4)
        assert abs(result["change_pct"] - expected_chg_pct) < 0.02, \
            f"change_pct={result['change_pct']} 与计算值 {expected_chg_pct} 不符"


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: 核心标的指数价格白名单拒绝
# ─────────────────────────────────────────────────────────────────────────────
class TestCriticalIndexWhitelist:
    """sh000001 价格 3.94（疑似小数点错位）→ 必须拒绝"""

    def test_sh000001_price_394_not_rejected_if_ohlc_valid(self):
        """
        如果 OHLC 内部一致，仅价格偏低，是否被拒绝？
        答案：validate_critical_symbol 在 price 校验后独立检查
        price=394.55 在 [2000, 6000] 范围内 → 不拒绝
        price=3.94 不在 [2000, 6000] → 拒绝
        """
        # 价格 394.55（在 [2000, 6000] 外）→ 拒绝
        raw = (
            'var hq_str_s_sh000001="上证指数,3.945,3.945,3.920,3.950,3.910,,,,,'
            ',,,,,,,,,,,,,,,,,,,,,,,,,,-0.00,0.000,,,,,,";'
        )
        result = parse_sina_response(raw, "sh000001")
        assert result is not None
        assert result["price"] == 3.945, f"price={result['price']}"
        # validate_quote 层面拒绝
        from app.services.data_validator import validate_quote
        validated = validate_quote(result, source="sina")
        # 价格 3.945 不在 [2000, 6000]，应返回 None
        assert validated is None, "价格 3.945 不在合理范围，应被 validate_quote 拒绝"

    def test_sh000001_valid_price_accepted(self):
        """正常价格 3948.55 → 完全通过"""
        raw = (
            'var hq_str_s_sh000001="上证指数,3948.555,3948.555,3923.280,3950.123,3910.456,,,'
            ',,,,,,,,,,,,,,,,,,,,,,,,,,0.00,0.000,,,,,,";'
        )
        result = parse_sina_response(raw, "sh000001")
        assert result is not None
        from app.services.data_validator import validate_quote
        validated = validate_quote(result, source="sina")
        assert validated is not None, "正常价格应通过校验"
        assert validated.price == 3948.555


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: SinaFetcher.get_quote 端到端（Mock HTTP）
# ─────────────────────────────────────────────────────────────────────────────
class TestSinaFetcherGetQuote:
    @pytest.mark.asyncio
    async def test_get_quote_returns_correct_price(self):
        """模拟真实场景：HTTP 200 返回 Sina 格式数据 → 价格正确解析"""
        fetcher = SinaFetcher(cb=None)
        raw_response = (
            'var hq_str_s_sh000001="上证指数,3948.555,3948.555,3923.280,3950.123,3910.456,,,'
            ',,,,,,,,,,,,,,,,,,,,,,,,,,0.00,0.000,,,,,,";'
        )

        mock_resp = MagicMock()
        mock_resp.text = raw_response
        mock_resp.status_code = 200

        with patch.object(fetcher, "_get_http") as mock_http:
            http_instance = AsyncMock()
            http_instance.get_with_retry = AsyncMock(return_value=mock_resp)
            mock_http.return_value = http_instance

            result = await fetcher.get_quote("sh000001")

        assert result is not None, "get_quote 返回 None"
        assert result.price == 3948.555, f"价格应为 3948.555，实际 {result.price}"
        assert result.name == "上证指数"
        assert isinstance(result.change_pct, float)
        await fetcher.close()

    @pytest.mark.asyncio
    async def test_get_quote_invalid_response_returns_none(self):
        """无效响应 → None，不抛异常"""
        fetcher = SinaFetcher(cb=None)

        mock_resp = MagicMock()
        mock_resp.text = "invalid response"
        mock_resp.status_code = 200

        with patch.object(fetcher, "_get_http") as mock_http:
            http_instance = AsyncMock()
            http_instance.get_with_retry = AsyncMock(return_value=mock_resp)
            mock_http.return_value = http_instance

            result = await fetcher.get_quote("sh000001")

        assert result is None, "无效响应应返回 None"
        await fetcher.close()

    @pytest.mark.asyncio
    async def test_get_quote_circuit_breaker_failure(self):
        """HTTP 失败 → CircuitBreaker.record_failure() 被调用"""
        cb = CircuitBreaker("sina", config=CircuitBreakerConfig(failure_threshold=3))
        fetcher = SinaFetcher(cb=cb)

        with patch.object(fetcher, "_get_http") as mock_http:
            http_instance = AsyncMock()
            http_instance.get_with_retry = AsyncMock(side_effect=Exception("network error"))
            mock_http.return_value = http_instance

            result = await fetcher.get_quote("sh000001")

        assert result is None
        assert cb._stats.consecutive_failures >= 1, \
            "HTTP 失败应 record_failure"
        await fetcher.close()


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: Ping 健康检查
# ─────────────────────────────────────────────────────────────────────────────
class TestSinaPing:
    @pytest.mark.asyncio
    async def test_ping_success(self):
        """上证指数正常返回 → ping True"""
        fetcher = SinaFetcher(cb=None)
        raw = (
            'var hq_str_s_sh000001="上证指数,3948.555,3948.555,3923.280,3950.123,3910.456,,,'
            ',,,,,,,,,,,,,,,,,,,,,,,,,,0.00,0.000,,,,,,";'
        )
        mock_resp = MagicMock()
        mock_resp.text = raw
        mock_resp.status_code = 200

        with patch.object(fetcher, "_get_http") as mock_http:
            http_instance = AsyncMock()
            http_instance.get_with_retry = AsyncMock(return_value=mock_resp)
            mock_http.return_value = http_instance

            result = await fetcher.ping()

        assert result is True
        await fetcher.close()

    @pytest.mark.asyncio
    async def test_ping_failure(self):
        """网络异常 → ping False"""
        fetcher = SinaFetcher(cb=None)

        with patch.object(fetcher, "_get_http") as mock_http:
            http_instance = AsyncMock()
            http_instance.get_with_retry = AsyncMock(side_effect=Exception("timeout"))
            mock_http.return_value = http_instance

            result = await fetcher.ping()

        assert result is False
        await fetcher.close()


# ─────────────────────────────────────────────────────────────────────────────
# 运行
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
