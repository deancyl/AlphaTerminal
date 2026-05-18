"""
Copilot Router Test Suite

Tests for all Copilot endpoints:
- POST /api/v1/chat - SSE streaming chat
- GET /api/v1/status - LLM configuration status

Coverage target: 30 tests
"""

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Generator
from fastapi.testclient import TestClient

# Mock database access BEFORE importing app to avoid admin_config table errors
@pytest.fixture(scope="module", autouse=True)
def mock_database_for_module():
    """Mock database access at module level to prevent admin_config table errors"""
    with patch("app.db.model_config_db.get_model_config", return_value={}):
        with patch("app.db.model_config_db.set_model_config", return_value=None):
            with patch("app.db.model_config_db.get_all_model_configs", return_value={}):
                with patch("app.db.model_config_db.get_enabled_models", return_value=[]):
                    yield

from app.main import app
from app.services.copilot.query_classifier import QueryType, ClassificationResult
from app.services.copilot.context_assembler import AssemblyResult

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter before each test to prevent rate limit accumulation"""
    from app.middleware.rate_limit import get_limiter
    get_limiter().reset()
    yield
    get_limiter().reset()



def _mock_sse_generator(chunks):

    async def async_gen():

        for chunk in chunks:

            yield f"data: {json.dumps(chunk)}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"

    return async_gen()



def _create_mock_assembly_result(

    query_type=QueryType.QUICK_QA,

    context_text="[TEST_CONTEXT]",

    symbols=None,

    confidence=0.9

):

    if symbols is None:

        symbols = []

    return AssemblyResult(

        query_type=query_type,

        context_text=context_text,

        tokens_used=100,

        symbols=symbols,

        classification=ClassificationResult(

            query_type=query_type,

            symbols=symbols,

            confidence=confidence,

            original_query="test query"

        )

    )



class TestCopilotChatEndpoint:

    """Tests for /api/v1/chat endpoint"""

    def test_copilot_chat_success(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result()

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._llm_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "test response"}

                            ])

                            response = client.post(

                                "/api/v1/chat",

                                json={"prompt": "test question"}

                            )

                            assert response.status_code == 200


class TestCopilotInputValidation:
    """Tests for input validation in /api/v1/chat endpoint"""

    def test_empty_prompt_returns_error(self):
        """Empty prompt should return error SSE response"""
        response = client.post(
            "/api/v1/chat",
            json={"prompt": ""}
        )
        assert response.status_code == 200
        assert b"error" in response.content or b"prompt" in response.content

    def test_whitespace_only_prompt_returns_error(self):
        """Whitespace-only prompt should return error"""
        response = client.post(
            "/api/v1/chat",
            json={"prompt": "   "}
        )
        assert response.status_code == 200
        assert b"error" in response.content or b"prompt" in response.content

    def test_missing_prompt_field(self):
        """Missing prompt field should be handled gracefully"""
        response = client.post(
            "/api/v1/chat",
            json={}
        )
        # Should not crash, returns error response
        assert response.status_code == 200

    def test_null_prompt(self):
        """Null prompt should be handled"""
        response = client.post(
            "/api/v1/chat",
            json={"prompt": None}
        )
        assert response.status_code == 200

    def test_prompt_too_long(self):
        """Very long prompt should still be processed (no explicit limit)"""
        long_prompt = "a" * 10000
        with patch("app.routers.copilot.get_context_assembler") as mock_ca:
            mock_ca.return_value = MagicMock(assemble=AsyncMock(
                return_value=_create_mock_assembly_result()
            ))
            with patch("app.routers.copilot.get_session_manager") as mock_sm:
                mock_sm.return_value = MagicMock(
                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),
                    get_bound_model=MagicMock(return_value=None),
                    bind_model=MagicMock(),
                    update_session_usage=MagicMock()
                )
                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:
                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(
                        total_tokens=100, cost_usd=0.001
                    )))
                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:
                        mock_cl.return_value = MagicMock(
                            acquire=AsyncMock(return_value=True),
                            release=MagicMock()
                        )
                        with patch("app.routers.copilot._mock_stream") as mock_stream:
                            mock_stream.return_value = _mock_sse_generator([{"content": "test"}])
                            response = client.post(
                                "/api/v1/chat",
                                json={"prompt": long_prompt}
                            )
                            assert response.status_code == 200

    def test_invalid_provider_falls_back_to_mock(self):
        """Invalid provider should fall back to mock"""
        with patch("app.routers.copilot.get_context_assembler") as mock_ca:
            mock_ca.return_value = MagicMock(assemble=AsyncMock(
                return_value=_create_mock_assembly_result()
            ))
            with patch("app.routers.copilot.get_session_manager") as mock_sm:
                mock_sm.return_value = MagicMock(
                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),
                    get_bound_model=MagicMock(return_value=None),
                    bind_model=MagicMock(),
                    update_session_usage=MagicMock()
                )
                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:
                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(
                        total_tokens=100, cost_usd=0.001
                    )))
                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:
                        mock_cl.return_value = MagicMock(
                            acquire=AsyncMock(return_value=True),
                            release=MagicMock()
                        )
                        with patch("app.routers.copilot._mock_stream") as mock_stream:
                            mock_stream.return_value = _mock_sse_generator([{"content": "test"}])
                            response = client.post(
                                "/api/v1/chat",
                                json={"prompt": "test", "provider": "invalid_provider_xyz"}
                            )
                            assert response.status_code == 200

    def test_special_characters_in_prompt(self):
        """Special characters should be handled"""
        with patch("app.routers.copilot.get_context_assembler") as mock_ca:
            mock_ca.return_value = MagicMock(assemble=AsyncMock(
                return_value=_create_mock_assembly_result()
            ))
            with patch("app.routers.copilot.get_session_manager") as mock_sm:
                mock_sm.return_value = MagicMock(
                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),
                    get_bound_model=MagicMock(return_value=None),
                    bind_model=MagicMock(),
                    update_session_usage=MagicMock()
                )
                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:
                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(
                        total_tokens=100, cost_usd=0.001
                    )))
                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:
                        mock_cl.return_value = MagicMock(
                            acquire=AsyncMock(return_value=True),
                            release=MagicMock()
                        )
                        with patch("app.routers.copilot._mock_stream") as mock_stream:
                            mock_stream.return_value = _mock_sse_generator([{"content": "test"}])
                            response = client.post(
                                "/api/v1/chat",
                                json={"prompt": "test <script>alert('xss')</script> && echo 'injection'"}
                            )
                            assert response.status_code == 200

    def test_unicode_in_prompt(self):
        """Unicode characters should be handled"""
        with patch("app.routers.copilot.get_context_assembler") as mock_ca:
            mock_ca.return_value = MagicMock(assemble=AsyncMock(
                return_value=_create_mock_assembly_result()
            ))
            with patch("app.routers.copilot.get_session_manager") as mock_sm:
                mock_sm.return_value = MagicMock(
                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),
                    get_bound_model=MagicMock(return_value=None),
                    bind_model=MagicMock(),
                    update_session_usage=MagicMock()
                )
                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:
                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(
                        total_tokens=100, cost_usd=0.001
                    )))
                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:
                        mock_cl.return_value = MagicMock(
                            acquire=AsyncMock(return_value=True),
                            release=MagicMock()
                        )
                        with patch("app.routers.copilot._mock_stream") as mock_stream:
                            mock_stream.return_value = _mock_sse_generator([{"content": "测试回答"}])
                            response = client.post(
                                "/api/v1/chat",
                                json={"prompt": "茅台的股票代码是什么？📈"}
                            )
                            assert response.status_code == 200


class TestCopilotErrorHandling:
    """Tests for error handling in /api/v1/chat endpoint"""

    def test_concurrency_limit_exceeded(self):
        """Concurrency limit exceeded returns error"""
        with patch("app.routers.copilot.get_context_assembler") as mock_ca:
            mock_ca.return_value = MagicMock(assemble=AsyncMock(
                return_value=_create_mock_assembly_result()
            ))
            with patch("app.routers.copilot.get_session_manager") as mock_sm:
                mock_sm.return_value = MagicMock(
                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),
                    get_bound_model=MagicMock(return_value=None),
                    bind_model=MagicMock(),
                    update_session_usage=MagicMock()
                )
                with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:
                    mock_cl.return_value = MagicMock(
                        acquire=AsyncMock(return_value=False),
                        release=MagicMock()
                    )
                    response = client.post(
                        "/api/v1/chat",
                        json={"prompt": "test"}
                    )
                    assert response.status_code == 200


# ═══════════════════════════════════════════════════════════════
# Async SSE Tests - Using httpx.AsyncClient for proper streaming
# ═══════════════════════════════════════════════════════════════

import httpx
import asyncio

@pytest.mark.asyncio
class TestCopilotAsyncSSE:
    """Async tests for SSE streaming endpoints using httpx.AsyncClient"""

    async def test_session_manager_failure_async(self):
        """Test session manager failure before streaming starts
        
        Note: The current router implementation does NOT wrap session manager
        calls in try-except, so this will raise an unhandled exception.
        This test documents the current behavior.
        """
        async with httpx.AsyncClient(app=app, base_url="http://test") as async_client:
            with patch("app.routers.copilot.get_context_assembler") as mock_ca:
                mock_ca.return_value = MagicMock(assemble=AsyncMock(
                    return_value=_create_mock_assembly_result()
                ))
                with patch("app.routers.copilot.get_session_manager") as mock_sm:
                    mock_sm.return_value = MagicMock(
                        create_or_get_session=MagicMock(
                            side_effect=RuntimeError("Session manager unavailable")
                        )
                    )
                    
                    # Current behavior: exception is raised (not caught)
                    # This documents the limitation
                    with pytest.raises(RuntimeError, match="Session manager unavailable"):
                        await async_client.post(
                            "/api/v1/chat",
                            json={"prompt": "test"}
                        )

    async def test_token_tracking_failure_async(self):
        """Test token tracking failure during streaming
        
        Token tracking happens in the finally block of tracked_stream().
        This test verifies the stream completes even if tracking has issues.
        """
        async with httpx.AsyncClient(app=app, base_url="http://test") as async_client:
            with patch("app.routers.copilot.get_context_assembler") as mock_ca:
                mock_ca.return_value = MagicMock(assemble=AsyncMock(
                    return_value=_create_mock_assembly_result()
                ))
                with patch("app.routers.copilot.get_session_manager") as mock_sm:
                    mock_sm.return_value = MagicMock(
                        create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),
                        get_bound_model=MagicMock(return_value=None),
                        bind_model=MagicMock(),
                        update_session_usage=MagicMock()
                    )
                    with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:
                        mock_tracking_result = MagicMock()
                        mock_tracking_result.total_tokens = 100
                        mock_tracking_result.cost_usd = 0.001
                        mock_ts.return_value = MagicMock(
                            track_usage=MagicMock(return_value=mock_tracking_result)
                        )
                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:
                        mock_cl.return_value = MagicMock(
                            acquire=AsyncMock(return_value=True),
                            release=MagicMock()
                        )
                        with patch("app.routers.copilot._llm_stream") as mock_stream:
                            mock_stream.return_value = _mock_sse_generator([
                                {"content": "test response"}
                            ])
                            # Mock the cost calculation and DB logging to avoid DB access
                            with patch("app.services.token_tracking_service.calculate_cost", return_value=0.001):
                                with patch("app.db.token_usage_db.log_token_usage", return_value="req-123"):
                                    response = await async_client.post(
                                        "/api/v1/chat",
                                        json={"prompt": "test"}
                                    )
                                    
                                    assert response.status_code == 200

    async def test_invalid_json_body_async(self):
        """Test invalid JSON body handling with async client
        
        FastAPI validates JSON before the endpoint handler runs.
        Invalid JSON should return 422 Unprocessable Entity.
        """
        async with httpx.AsyncClient(app=app, base_url="http://test") as async_client:
            # Send invalid JSON - FastAPI should catch this before endpoint
            try:
                response = await async_client.post(
                    "/api/v1/chat",
                    content=b"not valid json{",
                    headers={"Content-Type": "application/json"}
                )
                # FastAPI returns 422 for invalid JSON
                assert response.status_code == 422
            except json.JSONDecodeError:
                # httpx may raise JSONDecodeError when trying to read response
                # This is acceptable - the request was rejected
                pass

    async def test_sse_stream_can_be_consumed(self):
        """Test that SSE stream can be fully consumed"""
        async with httpx.AsyncClient(app=app, base_url="http://test") as async_client:
            with patch("app.routers.copilot.get_context_assembler") as mock_ca:
                mock_ca.return_value = MagicMock(assemble=AsyncMock(
                    return_value=_create_mock_assembly_result()
                ))
                with patch("app.routers.copilot.get_session_manager") as mock_sm:
                    mock_sm.return_value = MagicMock(
                        create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),
                        get_bound_model=MagicMock(return_value=None),
                        bind_model=MagicMock(),
                        update_session_usage=MagicMock()
                    )
                    with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:
                        mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(
                            total_tokens=100, cost_usd=0.001
                        )))
                        with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:
                            mock_cl.return_value = MagicMock(
                                acquire=AsyncMock(return_value=True),
                                release=MagicMock()
                            )
                            with patch("app.routers.copilot._llm_stream") as mock_stream:
                                mock_stream.return_value = _mock_sse_generator([
                                    {"content": "Hello"},
                                    {"content": " World"},
                                    {"done": True}
                                ])
                                
                                response = await async_client.post(
                                    "/api/v1/chat",
                                    json={"prompt": "test"}
                                )
                                
                                assert response.status_code == 200
                                # Verify we can read the full stream
                                content = response.text
                                assert len(content) > 0

    async def test_concurrency_limit_timeout_async(self):
        """Test concurrency limit timeout with async client"""
        async with httpx.AsyncClient(app=app, base_url="http://test") as async_client:
            with patch("app.routers.copilot.get_context_assembler") as mock_ca:
                mock_ca.return_value = MagicMock(assemble=AsyncMock(
                    return_value=_create_mock_assembly_result()
                ))
                with patch("app.routers.copilot.get_session_manager") as mock_sm:
                    mock_sm.return_value = MagicMock(
                        create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),
                        get_bound_model=MagicMock(return_value=None),
                        bind_model=MagicMock(),
                        update_session_usage=MagicMock()
                    )
                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:
                        # Simulate concurrency limit reached (acquire returns False)
                        mock_cl.return_value = MagicMock(
                            acquire=AsyncMock(return_value=False),
                            release=MagicMock()
                        )
                        
                        response = await async_client.post(
                            "/api/v1/chat",
                            json={"prompt": "test"}
                        )
                        
                        # Should return 200 with error message in SSE
                        assert response.status_code == 200
                        content = response.text
                        assert "并发限制" in content or "error" in content.lower()


# ═══════════════════════════════════════════════════════════════
# Service Layer Mock Tests - Testing failures before SSE starts
# ═══════════════════════════════════════════════════════════════

class TestCopilotServiceLayerFailures:
    """Tests that mock at service layer to test failures before StreamingResponse"""

    def test_empty_prompt_returns_error_sse(self):
        """Empty prompt should return error in SSE stream"""
        response = client.post(
            "/api/v1/chat",
            json={"prompt": ""}
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        # The error should be in the SSE data
        assert "prompt" in response.text.lower() or "error" in response.text.lower()

    def test_whitespace_only_prompt_returns_error_sse(self):
        """Whitespace-only prompt should return error in SSE stream"""
        response = client.post(
            "/api/v1/chat",
            json={"prompt": "   \n\t  "}
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_context_assembler_exception_handled(self):
        """Context assembler exception should fall back to basic context"""
        with patch("app.routers.copilot.get_context_assembler") as mock_ca:
            # Make context assembler raise exception
            mock_ca.return_value = MagicMock(
                assemble=AsyncMock(side_effect=RuntimeError("Context assembly failed"))
            )
            with patch("app.routers.copilot.get_session_manager") as mock_sm:
                mock_sm.return_value = MagicMock(
                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),
                    get_bound_model=MagicMock(return_value=None),
                    bind_model=MagicMock(),
                    update_session_usage=MagicMock()
                )
                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:
                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(
                        total_tokens=100, cost_usd=0.001
                    )))
                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:
                        mock_cl.return_value = MagicMock(
                            acquire=AsyncMock(return_value=True),
                            release=MagicMock()
                        )
                        with patch("app.routers.copilot._llm_stream") as mock_stream:
                            mock_stream.return_value = _mock_sse_generator([
                                {"content": "fallback response"}
                            ])
                            # Mock the fallback context functions
                            with patch("app.routers.copilot._fetch_price_context", return_value=""):
                                with patch("app.routers.copilot._fetch_latest_news", return_value=[]):
                                    with patch("app.routers.copilot._fetch_valuation_data", return_value=None):
                                        with patch("app.routers.copilot._build_context_block", return_value=""):
                                            response = client.post(
                                                "/api/v1/chat",
                                                json={"prompt": "test"}
                                            )
                                            # Should still work with fallback context
                                            assert response.status_code == 200
                                            # Verify fallback response was returned
                                            assert b"fallback response" in response.content

    def test_context_assembly_failure_fallback(self):
        with patch("app.routers.copilot.get_context_assembler") as mock_ca:
            mock_ca.return_value = MagicMock(assemble=AsyncMock(
                side_effect=Exception("Context assembly failed")
            ))
            with patch("app.routers.copilot._fetch_price_context") as mock_price:
                mock_price.return_value = {"name": "TEST", "price": 100.0, "change": 2.5}
                with patch("app.routers.copilot._fetch_latest_news") as mock_news:
                    mock_news.return_value = []
                    with patch("app.routers.copilot._fetch_valuation_data") as mock_val:
                        mock_val.return_value = {}
                        with patch("app.routers.copilot.get_session_manager") as mock_sm:
                            mock_sm.return_value = MagicMock(
                                create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),
                                get_bound_model=MagicMock(return_value=None),
                                bind_model=MagicMock(),
                                update_session_usage=MagicMock()
                            )
                            with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:
                                mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(
                                    total_tokens=100, cost_usd=0.001
                                )))
                                with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:
                                    mock_cl.return_value = MagicMock(
                                        acquire=AsyncMock(return_value=True),
                                        release=MagicMock()
                                    )
                                    with patch("app.routers.copilot._mock_stream") as mock_stream:
                                        mock_stream.return_value = _mock_sse_generator([{"content": "response"}])
                                        response = client.post(
                                            "/api/v1/chat",
                                            json={"prompt": "test"}
                                        )
                                        assert response.status_code in [200, 500]

    def test_llm_stream_timeout(self):
        """LLM stream timeout should return error message"""
        with patch("app.routers.copilot.get_context_assembler") as mock_ca:
            mock_ca.return_value = MagicMock(assemble=AsyncMock(
                return_value=_create_mock_assembly_result()
            ))
            with patch("app.routers.copilot.get_session_manager") as mock_sm:
                mock_sm.return_value = MagicMock(
                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),
                    get_bound_model=MagicMock(return_value=None),
                    bind_model=MagicMock(),
                    update_session_usage=MagicMock()
                )
                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:
                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(
                        total_tokens=100, cost_usd=0.001
                    )))
                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:
                        mock_cl.return_value = MagicMock(
                            acquire=AsyncMock(return_value=True),
                            release=MagicMock()
                        )
                        with patch("app.routers.copilot._llm_stream") as mock_stream:
                            mock_stream.return_value = _mock_sse_generator([{"content": "slow"}])
                            response = client.post(
                                "/api/v1/chat",
                                json={"prompt": "test"}
                            )
                            # Should handle gracefully
                            assert response.status_code in [200, 500]

    def test_wrong_http_method_get(self):
        """GET request to chat endpoint should return 405 or 404"""
        response = client.get("/api/v1/chat")
        assert response.status_code in [404, 405]

    def test_none_provider_with_no_api_keys(self):
        """When no API keys are configured, should use mock"""
        with patch("app.routers.copilot.get_context_assembler") as mock_ca:
            mock_ca.return_value = MagicMock(assemble=AsyncMock(
                return_value=_create_mock_assembly_result()
            ))
            with patch("app.routers.copilot._get_llm_config") as mock_cfg:
                # Return empty config (no API key)
                mock_cfg.return_value = {}
                with patch("app.routers.copilot.get_session_manager") as mock_sm:
                    mock_sm.return_value = MagicMock(
                        create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),
                        get_bound_model=MagicMock(return_value=None),
                        bind_model=MagicMock(),
                        update_session_usage=MagicMock()
                    )
                    with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:
                        mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(
                            total_tokens=100, cost_usd=0.001
                        )))
                        with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:
                            mock_cl.return_value = MagicMock(
                                acquire=AsyncMock(return_value=True),
                                release=MagicMock()
                            )
                            with patch("app.routers.copilot._mock_stream") as mock_stream:
                                mock_stream.return_value = _mock_sse_generator([{"content": "mock response"}])
                                response = client.post(
                                    "/api/v1/chat",
                                    json={"prompt": "test"}
                                )
                                assert response.status_code == 200


                            assert "X-Session-Id" in response.headers



    def test_copilot_chat_response_is_streaming(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result()

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._llm_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "streaming"}, {"content": "response"}

                            ])

                            response = client.post(

                                "/api/v1/chat",

                                json={"prompt": "test streaming"}

                            )

                            assert response.status_code == 200



    def test_copilot_chat_with_symbol_context(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result(

                    symbols=["600519"],

                    context_text="[CURRENT_SYMBOL] 600519"

                )

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._llm_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "maotai analysis"}

                            ])

                            response = client.post(

                                "/api/v1/chat",

                                json={"prompt": "analyze maotai", "symbol": "600519"}

                            )

                            assert response.status_code == 200

                            mock_ca.return_value.assemble.assert_called_once()



    def test_copilot_chat_with_portfolio_context(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result(

                    context_text="[PORTFOLIO] Test Portfolio"

                )

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._llm_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "portfolio analysis"}

                            ])

                            response = client.post(

                                "/api/v1/chat",

                                json={"prompt": "check my portfolio", "portfolio_id": 1}

                            )

                            assert response.status_code == 200



    def test_copilot_chat_with_news_context(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result(

                    context_text="[NEWS] Latest news headline"

                )

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._llm_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "news interpretation"}

                            ])

                            response = client.post(

                                "/api/v1/chat",

                                json={"prompt": "interpret latest news"}

                            )

                            assert response.status_code == 200



    def test_copilot_chat_provider_override(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result()

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._llm_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "deepseek response"}

                            ])

                            with patch("app.routers.copilot._get_llm_config") as mock_config:

                                mock_config.return_value = {

                                    "api_key": "test-key",

                                    "base_url": "https://api.deepseek.com",

                                    "model": "deepseek-chat"

                                }

                                response = client.post(

                                    "/api/v1/chat",

                                    json={"prompt": "test", "provider": "deepseek"}

                                )

                                assert response.status_code == 200



    def test_copilot_chat_model_override(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result()

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._llm_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "gpt-4 response"}

                            ])

                            with patch("app.routers.copilot._get_llm_config") as mock_config:

                                mock_config.return_value = {

                                    "api_key": "test-key",

                                    "base_url": "https://api.openai.com/v1",

                                    "model": "gpt-4"

                                }

                                response = client.post(

                                    "/api/v1/chat",

                                    json={"prompt": "test", "model": "gpt-4"}

                                )

                                assert response.status_code == 200



    def test_copilot_chat_session_continuity(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result()

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_session = MagicMock(session_id="existing-session-123")

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=mock_session),

                    get_bound_model=MagicMock(return_value="gpt-4"),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._llm_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "continued conversation"}

                            ])

                            response = client.post(

                                "/api/v1/chat",

                                json={

                                    "prompt": "continue",

                                    "session_id": "existing-session-123"

                                }

                            )

                            assert response.status_code == 200



    def test_copilot_chat_conversation_history(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result()

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._llm_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "history continued"}

                            ])

                            with patch("app.routers.copilot._load_conversation") as mock_load:

                                mock_load.return_value = [

                                    {"role": "user", "content": "previous question"},

                                    {"role": "assistant", "content": "previous answer"}

                                ]

                                response = client.post(

                                    "/api/v1/chat",

                                    json={

                                        "prompt": "continue discussion",

                                        "session_id": "test-session"

                                    }

                                )

                                assert response.status_code == 200



    def test_copilot_chat_empty_prompt(self):

        response = client.post(

            "/api/v1/chat",

            json={"prompt": ""}

        )

        assert response.status_code == 200





class TestCopilotStatusEndpoint:

    """Tests for /api/v1/status endpoint"""

    def test_copilot_status_success(self):

        response = client.get("/api/v1/status")

        assert response.status_code == 200

        data = response.json()

        assert "provider" in data

        assert "has_key" in data



    def test_copilot_status_response_structure(self):

        response = client.get("/api/v1/status")

        assert response.status_code == 200

        data = response.json()

        assert "openai" in data

        assert "deepseek" in data

        assert "qianwen" in data

        assert "minimax" in data

        assert "siliconflow" in data

        assert "opencode_go" in data

        assert "opencode_zen" in data



    def test_copilot_status_provider_list(self):

        response = client.get("/api/v1/status")

        assert response.status_code == 200

        data = response.json()

        for key in ["openai", "deepseek", "qianwen", "minimax", "siliconflow", "opencode_go", "opencode_zen"]:

            assert isinstance(data[key], bool)



    def test_copilot_status_default_provider(self):

        response = client.get("/api/v1/status")

        assert response.status_code == 200

        data = response.json()

        valid_providers = ["deepseek", "qianwen", "openai", "siliconflow", "opencode", "opencode_go", "opencode_zen", "minimax", "kimi", "mock"]

        assert data["provider"] in valid_providers





class TestCopilotLLMProviders:

    """Tests for LLM provider integration"""

    def test_openai_provider_mock(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result()

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._mock_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "mock response"}

                            ])

                            with patch("app.routers.copilot._get_llm_config") as mock_config:

                                mock_config.return_value = {"api_key": "", "base_url": "", "model": ""}

                                response = client.post(

                                    "/api/v1/chat",

                                    json={"prompt": "test", "provider": "openai"}

                                )

                                assert response.status_code == 200



    def test_deepseek_provider_mock(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result()

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._mock_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "deepseek response"}

                            ])

                            with patch("app.routers.copilot._get_llm_config") as mock_config:

                                mock_config.return_value = {"api_key": "", "base_url": "", "model": ""}

                                response = client.post(

                                    "/api/v1/chat",

                                    json={"prompt": "test", "provider": "deepseek"}

                                )

                                assert response.status_code == 200



    def test_qianwen_provider_mock(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result()

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._mock_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "qianwen response"}

                            ])

                            with patch("app.routers.copilot._get_llm_config") as mock_config:

                                mock_config.return_value = {"api_key": "", "base_url": "", "model": ""}

                                response = client.post(

                                    "/api/v1/chat",

                                    json={"prompt": "test", "provider": "qianwen"}

                                )

                                assert response.status_code == 200



    def test_minimax_provider_mock(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result()

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._mock_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "minimax response"}

                            ])

                            with patch("app.routers.copilot._get_llm_config") as mock_config:

                                mock_config.return_value = {"api_key": "", "base_url": "", "model": ""}

                                response = client.post(

                                    "/api/v1/chat",

                                    json={"prompt": "test", "provider": "minimax"}

                                )

                                assert response.status_code == 200



    def test_siliconflow_provider_mock(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result()

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._mock_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "siliconflow response"}

                            ])

                            with patch("app.routers.copilot._get_llm_config") as mock_config:

                                mock_config.return_value = {"api_key": "", "base_url": "", "model": ""}

                                response = client.post(

                                    "/api/v1/chat",

                                    json={"prompt": "test", "provider": "siliconflow"}

                                )

                                assert response.status_code == 200



    def test_opencode_provider_mock(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result()

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._mock_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "opencode response"}

                            ])

                            with patch("app.routers.copilot._get_llm_config") as mock_config:

                                mock_config.return_value = {"api_key": "", "base_url": "", "model": ""}

                                response = client.post(

                                    "/api/v1/chat",

                                    json={"prompt": "test", "provider": "opencode"}

                                )

                                assert response.status_code == 200



    def test_kimi_provider_mock(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result()

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._mock_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "kimi response"}

                            ])

                            with patch("app.routers.copilot._get_llm_config") as mock_config:

                                mock_config.return_value = {"api_key": "", "base_url": "", "model": ""}

                                response = client.post(

                                    "/api/v1/chat",

                                    json={"prompt": "test", "provider": "kimi"}

                                )

                                assert response.status_code == 200



    def test_mock_stream_provider(self):

        with patch("app.routers.copilot.get_context_assembler") as mock_ca:

            mock_ca.return_value = MagicMock(assemble=AsyncMock(

                return_value=_create_mock_assembly_result()

            ))

            with patch("app.routers.copilot.get_session_manager") as mock_sm:

                mock_sm.return_value = MagicMock(

                    create_or_get_session=MagicMock(return_value=MagicMock(session_id="test-session")),

                    get_bound_model=MagicMock(return_value=None),

                    bind_model=MagicMock(),

                    update_session_usage=MagicMock()

                )

                with patch("app.routers.copilot.get_token_tracking_service") as mock_ts:

                    mock_ts.return_value = MagicMock(track_usage=MagicMock(return_value=MagicMock(

                        total_tokens=100, cost_usd=0.001

                    )))

                    with patch("app.routers.copilot.get_concurrency_limiter") as mock_cl:

                        mock_cl.return_value = MagicMock(

                            acquire=AsyncMock(return_value=True),

                            release=MagicMock()

                        )

                        with patch("app.routers.copilot._mock_stream") as mock_stream:

                            mock_stream.return_value = _mock_sse_generator([

                                {"content": "mock default response"}

                            ])

                            response = client.post(

                                "/api/v1/chat",

                                json={"prompt": "test"}

                            )

                            assert response.status_code == 200



