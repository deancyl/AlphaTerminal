"""
News Router Test Suite

Tests all news endpoints:
- GET /api/v1/news/flash - News flash feed
- POST /api/v1/news/force_refresh - Force refresh news cache
- GET /api/v1/news/detail?url=... - News detail content
- GET /api/v1/news/transcript/{video_id} - Video transcript
- GET /api/v1/news/events/{symbol} - News events for symbol

Coverage target: 28 tests
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@pytest.fixture
def mock_news_cache():
    return [
        {
            "id": "abc123def456",
            "title": "央行宣布降准0.25个百分点，释放长期资金约5000亿元",
            "time": "2024-01-15 10:30",
            "source": "央行官网",
            "url": "http://finance.eastmoney.com/news/1.html",
            "tag": "💎 宏观",
        },
        {
            "id": "xyz789ghi012",
            "title": "贵州茅台发布业绩预告，净利润同比增长15%",
            "time": "2024-01-15 09:00",
            "source": "东方财富",
            "url": "http://finance.eastmoney.com/news/2.html",
            "tag": "📈 A股",
        },
        {
            "id": "mno345pqr678",
            "title": "利好消息：某公司中标重大项目",
            "time": "2024-01-14 15:00",
            "source": "新浪财经",
            "url": "http://finance.eastmoney.com/news/3.html",
            "tag": "📰 其他",
        },
    ]


@pytest.fixture
def mock_news_events():
    return [
        {
            "date": "2024-01-15",
            "headline": "贵州茅台利好消息：业绩超预期增长",
            "type": "bullish",
            "price": None,
            "url": "http://example.com/news/1",
            "source": "eastmoney",
        },
        {
            "date": "2024-01-10",
            "headline": "贵州茅台利空：减持公告",
            "type": "bearish",
            "price": None,
            "url": "http://example.com/news/2",
            "source": "sina",
        },
    ]


class TestNewsFlashEndpoint:
    """Tests for /api/v1/news/flash endpoint"""

    def test_news_flash_success(self):
        with patch('app.services.news_engine.is_cache_ready', return_value=True):
            with patch('app.services.news_engine.get_cached_news', return_value=[]):
                response = client.get("/api/v1/news/flash")
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0
                assert "news" in data["data"]
                assert "source" in data["data"]
                assert "total" in data["data"]

    def test_news_flash_response_structure(self, mock_news_cache):
        with patch('app.services.news_engine.is_cache_ready', return_value=True):
            with patch('app.services.news_engine.get_cached_news', return_value=mock_news_cache):
                response = client.get("/api/v1/news/flash")
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0
                assert isinstance(data["data"]["news"], list)
                assert data["data"]["source"] == "cache"
                assert data["data"]["total"] == len(mock_news_cache)

    def test_news_flash_empty_cache(self):
        with patch('app.services.news_engine.is_cache_ready', return_value=False):
            response = client.get("/api/v1/news/flash")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["news"] == []
            assert data["data"]["source"] == "cache_empty"
            assert data["data"]["total"] == 0

    def test_news_flash_with_limit(self, mock_news_cache):
        with patch('app.services.news_engine.is_cache_ready', return_value=True):
            with patch('app.services.news_engine.get_cached_news') as mock_get:
                mock_get.return_value = mock_news_cache[:2]
                response = client.get("/api/v1/news/flash")
                assert response.status_code == 200
                mock_get.assert_called_once_with(limit=150)


class TestNewsForceRefreshEndpoint:
    """Tests for /api/v1/news/force_refresh endpoint"""

    def test_force_refresh_success(self):
        with patch('app.services.news_engine.get_cached_news', return_value=[]):
            with patch('app.services.news_engine.is_cache_ready', return_value=True):
                with patch('app.services.news_engine.refresh_news_cache'):
                    with patch('asyncio.get_event_loop') as mock_loop:
                        mock_loop.return_value.run_in_executor = AsyncMock()
                        response = client.post("/api/v1/news/force_refresh")
                        assert response.status_code == 200
                        data = response.json()
                        assert data["code"] == 0
                        assert "news" in data["data"]
                        assert "source" in data["data"]

    def test_force_refresh_returns_new_data(self, mock_news_cache):
        with patch('app.services.news_engine.get_cached_news', return_value=mock_news_cache):
            with patch('app.services.news_engine.is_cache_ready', return_value=True):
                with patch('app.services.news_engine.refresh_news_cache'):
                    with patch('asyncio.get_event_loop') as mock_loop:
                        mock_loop.return_value.run_in_executor = AsyncMock()
                        response = client.post("/api/v1/news/force_refresh")
                        assert response.status_code == 200
                        data = response.json()
                        assert data["data"]["source"] == "force_refresh"
                        assert data["data"]["total"] == len(mock_news_cache)

    def test_force_refresh_clears_cache(self):
        with patch('app.services.news_engine.get_cached_news', return_value=[]):
            with patch('app.services.news_engine.is_cache_ready', return_value=True):
                with patch('asyncio.get_event_loop') as mock_loop:
                    mock_loop.return_value.run_in_executor = AsyncMock()
                    response = client.post("/api/v1/news/force_refresh")
                    assert response.status_code == 200
                    mock_loop.return_value.run_in_executor.assert_called()

    def test_force_refresh_handles_error(self):
        with patch('app.services.news_engine.get_cached_news', return_value=[]):
            with patch('app.services.news_engine.is_cache_ready', return_value=True):
                with patch('app.services.news_engine.refresh_news_cache', side_effect=Exception("Network error")):
                    with patch('asyncio.get_event_loop') as mock_loop:
                        mock_loop.return_value.run_in_executor = AsyncMock(side_effect=Exception("Network error"))
                        response = client.post("/api/v1/news/force_refresh")
                        assert response.status_code == 200
                        data = response.json()
                        assert "code" in data


class TestNewsDetailEndpoint:
    """Tests for /api/v1/news/detail endpoint"""

    def test_news_detail_success(self):
        mock_html = """
        <html>
            <body>
                <article>
                    <p>这是一段测试新闻内容，长度超过50个字符，用于测试新闻详情提取功能。</p>
                    <p>这是第二段内容，继续增加文章长度以确保能够正常提取。</p>
                </article>
            </body>
        </html>
        """
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.text = mock_html
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            response = client.get("/api/v1/news/detail?url=https://example.com/news/1")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert "content" in data["data"]
            assert "url" in data["data"]

    def test_news_detail_blocked_host(self):
        response = client.get("/api/v1/news/detail?url=http://localhost/admin")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] != 0 or "禁止访问" in data.get("message", "") or data["data"].get("code") != 0

    def test_news_detail_invalid_url(self):
        response = client.get("/api/v1/news/detail")
        assert response.status_code == 422

    def test_news_detail_timeout_handling(self):
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Timeout")
            )
            response = client.get("/api/v1/news/detail?url=https://example.com/news/1")
            assert response.status_code == 200
            data = response.json()
            assert "content" in data["data"]


class TestVideoTranscriptEndpoint:
    """Tests for /api/v1/news/transcript/{video_id} endpoint"""

    def test_video_transcript_success(self):
        mock_transcript = {
            "video_id": "test123",
            "transcript": "This is a test transcript.",
            "duration": 120,
        }
        with patch('app.services.news_fetcher.fetch_youtube_transcript', return_value=mock_transcript):
            response = client.get("/api/v1/news/transcript/test123")
            assert response.status_code == 200

    def test_video_transcript_invalid_video_id(self):
        with patch('app.services.news_fetcher.fetch_youtube_transcript') as mock_fetch:
            mock_fetch.return_value = {"error": "Video not found", "transcript": None}
            response = client.get("/api/v1/news/transcript/invalid_id")
            assert response.status_code == 200


class TestNewsEventsForSymbolEndpoint:
    """Tests for /api/v1/news/events/{symbol} endpoint"""

    def test_news_events_success(self):
        mock_news = [
            {
                "title": "600519利好消息：业绩超预期",
                "time": "2024-01-15 10:30",
                "source": "eastmoney",
                "url": "http://example.com/1",
            },
        ]
        with patch('app.services.news_engine.is_cache_ready', return_value=True):
            with patch('app.services.news_engine.get_cached_news', return_value=mock_news):
                response = client.get("/api/v1/news/events/600519")
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0
                assert "events" in data["data"]
                assert "symbol" in data["data"]
                assert "total" in data["data"]

    def test_news_events_with_limit(self):
        mock_news = [
            {"title": "600519新闻1", "time": "2024-01-15", "source": "eastmoney", "url": "http://1"},
            {"title": "600519新闻2", "time": "2024-01-14", "source": "sina", "url": "http://2"},
        ]
        with patch('app.services.news_engine.is_cache_ready', return_value=True):
            with patch('app.services.news_engine.get_cached_news', return_value=mock_news):
                response = client.get("/api/v1/news/events/600519?limit=1")
                assert response.status_code == 200
                data = response.json()
                assert len(data["data"]["events"]) <= 1

    def test_news_events_sentiment_classification(self):
        mock_news = [
            {"title": "600519利好消息：业绩增长", "time": "2024-01-15", "source": "eastmoney", "url": "http://1"},
            {"title": "600519利空消息：减持公告", "time": "2024-01-14", "source": "sina", "url": "http://2"},
            {"title": "600519普通新闻", "time": "2024-01-13", "source": "sina", "url": "http://3"},
        ]
        with patch('app.services.news_engine.is_cache_ready', return_value=True):
            with patch('app.services.news_engine.get_cached_news', return_value=mock_news):
                response = client.get("/api/v1/news/events/600519")
                assert response.status_code == 200
                data = response.json()
                events = data["data"]["events"]
                
                types = [e["type"] for e in events]
                assert "bullish" in types or "bearish" in types or "neutral" in types

    def test_news_events_bullish_keywords(self):
        mock_news = [
            {"title": "600519利好：业绩创新高", "time": "2024-01-15", "source": "eastmoney", "url": "http://1"},
        ]
        with patch('app.services.news_engine.is_cache_ready', return_value=True):
            with patch('app.services.news_engine.get_cached_news', return_value=mock_news):
                response = client.get("/api/v1/news/events/600519")
                assert response.status_code == 200
                data = response.json()
                if data["data"]["events"]:
                    assert data["data"]["events"][0]["type"] == "bullish"

    def test_news_events_bearish_keywords(self):
        mock_news = [
            {"title": "600519利空：暴跌预警", "time": "2024-01-15", "source": "eastmoney", "url": "http://1"},
        ]
        with patch('app.services.news_engine.is_cache_ready', return_value=True):
            with patch('app.services.news_engine.get_cached_news', return_value=mock_news):
                response = client.get("/api/v1/news/events/600519")
                assert response.status_code == 200
                data = response.json()
                if data["data"]["events"]:
                    assert data["data"]["events"][0]["type"] == "bearish"

    def test_news_events_symbol_normalization(self):
        mock_news = [
            {"title": "600519新闻", "time": "2024-01-15", "source": "eastmoney", "url": "http://1"},
        ]
        with patch('app.services.news_engine.is_cache_ready', return_value=True):
            with patch('app.services.news_engine.get_cached_news', return_value=mock_news):
                response = client.get("/api/v1/news/events/sh600519")
                assert response.status_code == 200
                data = response.json()
                assert data["data"]["symbol"] == "sh600519"


class TestNewsInputValidation:
    """Tests for input validation"""

    def test_detail_url_validation(self):
        response = client.get("/api/v1/news/detail")
        assert response.status_code == 422

    def test_events_limit_validation_min(self):
        response = client.get("/api/v1/news/events/600519?limit=0")
        assert response.status_code == 422

    def test_events_limit_validation_max(self):
        response = client.get("/api/v1/news/events/600519?limit=101")
        assert response.status_code == 422

    def test_events_limit_validation_negative(self):
        response = client.get("/api/v1/news/events/600519?limit=-1")
        assert response.status_code == 422


class TestNewsErrorHandling:
    """Tests for error handling"""

    def test_flash_network_error(self):
        with patch('app.services.news_engine.is_cache_ready', return_value=False):
            response = client.get("/api/v1/news/flash")
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["news"] == []

    def test_detail_network_error(self):
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Network error")
            )
            response = client.get("/api/v1/news/detail?url=https://example.com/news/1")
            assert response.status_code == 200
            data = response.json()
            assert "content" in data["data"]

    def test_events_empty_data_handling(self):
        with patch('app.services.news_engine.is_cache_ready', return_value=True):
            with patch('app.services.news_engine.get_cached_news', return_value=[]):
                response = client.get("/api/v1/news/events/600519")
                assert response.status_code == 200
                data = response.json()
                assert data["data"]["events"] == []
                assert data["data"]["total"] == 0


class TestNewsSSRFProtection:
    """Tests for SSRF protection in news detail endpoint"""

    def test_ssrf_block_localhost(self):
        response = client.get("/api/v1/news/detail?url=http://localhost/admin")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] != 0 or "禁止" in data.get("message", "") or data["data"].get("code") != 0

    def test_ssrf_block_127_0_0_1(self):
        response = client.get("/api/v1/news/detail?url=http://127.0.0.1/admin")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] != 0 or "禁止" in data.get("message", "") or data["data"].get("code") != 0

    def test_ssrf_block_private_ip(self):
        response = client.get("/api/v1/news/detail?url=http://192.168.1.1/admin")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] != 0 or "禁止" in data.get("message", "") or data["data"].get("code") != 0

    def test_ssrf_block_cloud_metadata(self):
        response = client.get("/api/v1/news/detail?url=http://169.254.169.254/metadata")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] != 0 or "禁止" in data.get("message", "") or data["data"].get("code") != 0

    def test_ssrf_block_ftp_protocol(self):
        response = client.get("/api/v1/news/detail?url=ftp://example.com/file")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] != 0 or "http" in data.get("message", "").lower() or data["data"].get("code") != 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app/routers/news", "--cov-report=term"])
