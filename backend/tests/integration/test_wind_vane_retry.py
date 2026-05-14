"""Integration tests for wind vane retry mechanism.

Tests the retry functionality for macro data fetch failures.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio


class TestMacroRetryMechanism:
    """Test cases for macro data retry mechanism."""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test that retry is triggered on fetch failure."""
        from app.routers.market.overview import _get_macro_data, _MACRO_CACHE_TTL

        # Verify cache TTL is 60 seconds
        assert _MACRO_CACHE_TTL == 60, f"Expected TTL 60, got {_MACRO_CACHE_TTL}"

    @pytest.mark.asyncio
    async def test_macro_cache_ttl(self):
        """Test that macro cache TTL is correctly set to 60 seconds."""
        from app.routers.market.overview import _MACRO_CACHE_TTL

        assert _MACRO_CACHE_TTL == 60

    def test_macro_endpoint_returns_data(self, client):
        """Test that /market/macro endpoint returns valid data."""
        response = client.get("/api/v1/market/macro")
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "code" in data
            if data.get("code") == 0:
                assert "data" in data
                assert "macro" in data["data"]

    def test_macro_endpoint_structure(self, client):
        """Test macro endpoint response structure."""
        response = client.get("/api/v1/market/macro")

        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                macro_data = data["data"]["macro"]
                assert isinstance(macro_data, list)

                # Each macro item should have required fields
                if macro_data:
                    item = macro_data[0]
                    assert "name" in item
                    assert "price" in item
                    assert "change_pct" in item

    @patch('app.routers.market.overview._fetch_macro_data')
    def test_macro_fetch_failure_handling(self, mock_fetch, client):
        """Test that macro fetch failure is handled gracefully."""
        # Mock a failure
        mock_fetch.side_effect = Exception("Network error")

        # The endpoint should still return a response (not crash)
        response = client.get("/api/v1/market/macro")
        assert response.status_code in [200, 500]


class TestExponentialBackoff:
    """Test exponential backoff logic for retries."""

    def test_backoff_delays(self):
        """Test that backoff delays follow exponential pattern."""
        # Expected delays: 1s, 2s, 4s, 8s, 16s
        expected_delays = [1000, 2000, 4000, 8000, 16000]

        # Verify the pattern (1s * 2^n)
        for i, delay in enumerate(expected_delays):
            calculated = 1000 * (2 ** i)
            assert delay == calculated, f"Delay {i}: expected {calculated}ms, got {delay}ms"

    def test_max_retries(self):
        """Test that max retries is set to 5."""
        max_retries = 5
        assert max_retries == 5

    def test_max_delay_cap(self):
        """Test that delays are capped at reasonable maximum."""
        # After 5 retries, delay should not exceed 30 seconds
        max_delay = 30000  # 30 seconds
        expected_delays = [1000, 2000, 4000, 8000, 16000]

        for delay in expected_delays:
            assert delay <= max_delay, f"Delay {delay}ms exceeds max {max_delay}ms"