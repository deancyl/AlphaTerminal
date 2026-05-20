# Copilot 模块测试文档

> 最后更新: 2026-05-20
> 测试文件: `backend/tests/unit/test_routers/test_copilot.py`

## 概述

Copilot 模块测试覆盖 AI 投研助理的所有核心功能，包括 SSE 流式响应、Token 追踪、会话管理、Provider 回退等。

## 测试统计

| 指标 | 数值 |
|------|------|
| 测试类数量 | 14 |
| 测试用例数量 | 63 |
| 新增测试用例 (v0.6.58) | 20 |

## 测试类详情

### 1. TestCopilotChatEndpoint (1 test)

基础聊天端点测试。

```python
def test_copilot_chat_success(self):
    """验证聊天端点返回 200 状态码"""
```

### 2. TestCopilotInputValidation (7 tests)

输入验证测试，覆盖各种边界情况。

| 测试 | 描述 |
|------|------|
| `test_empty_prompt_returns_error` | 空提示词返回错误 |
| `test_whitespace_only_prompt_returns_error` | 仅空白字符返回错误 |
| `test_missing_prompt_field` | 缺少 prompt 字段 |
| `test_null_prompt` | null 提示词 |
| `test_prompt_too_long` | 超长提示词（10000字符） |
| `test_invalid_provider_falls_back_to_mock` | 无效 provider 回退到 mock |
| `test_special_characters_in_prompt` | 特殊字符处理 |
| `test_unicode_in_prompt` | Unicode 字符处理 |

### 3. TestCopilotErrorHandling (1 test)

错误处理测试。

| 测试 | 描述 |
|------|------|
| `test_concurrency_limit_exceeded` | 并发限制超限 |

### 4. TestCopilotAsyncSSE (5 tests)

异步 SSE 流测试，使用 `httpx.AsyncClient`。

| 测试 | 描述 |
|------|------|
| `test_session_manager_failure_async` | Session manager 失败 |
| `test_token_tracking_failure_async` | Token 追踪失败 |
| `test_invalid_json_body_async` | 无效 JSON 请求体 |
| `test_sse_stream_can_be_consumed` | SSE 流可完整消费 |
| `test_concurrency_limit_timeout_async` | 并发限制超时 |

### 5. TestCopilotServiceLayerFailures (16 tests)

服务层失败场景测试。

| 测试 | 描述 |
|------|------|
| `test_empty_prompt_returns_error_sse` | 空提示词返回 SSE 错误 |
| `test_whitespace_only_prompt_returns_error_sse` | 空白提示词返回 SSE 错误 |
| `test_context_assembler_exception_handled` | 上下文组装异常处理 |
| `test_context_assembly_failure_fallback` | 上下文组装失败回退 |
| `test_llm_stream_timeout` | LLM 流超时 |
| `test_wrong_http_method_get` | 错误 HTTP 方法 |
| `test_none_provider_with_no_api_keys` | 无 API key 时使用 mock |
| `test_copilot_chat_response_is_streaming` | 响应为流式 |
| `test_copilot_chat_with_symbol_context` | Symbol 上下文 |
| `test_copilot_chat_with_portfolio_context` | Portfolio 上下文 |
| `test_copilot_chat_with_news_context` | 新闻上下文 |
| `test_copilot_chat_provider_override` | Provider 覆盖 |
| `test_copilot_chat_model_override` | Model 覆盖 |
| `test_copilot_chat_session_continuity` | 会话连续性 |
| `test_copilot_chat_conversation_history` | 对话历史 |
| `test_copilot_chat_empty_prompt` | 空提示词 |

### 6. TestCopilotStatusEndpoint (3 tests)

状态端点测试。

| 测试 | 描述 |
|------|------|
| `test_copilot_status_success` | 状态端点成功 |
| `test_copilot_status_response_structure` | 响应结构验证 |
| `test_copilot_status_provider_list` | Provider 列表 |

### 7. TestCopilotLLMProviders (8 tests)

LLM Provider 集成测试。

| 测试 | 描述 |
|------|------|
| `test_openai_provider_mock` | OpenAI provider |
| `test_deepseek_provider_mock` | DeepSeek provider |
| `test_qianwen_provider_mock` | Qianwen provider |
| `test_minimax_provider_mock` | Minimax provider |
| `test_siliconflow_provider_mock` | SiliconFlow provider |
| `test_opencode_provider_mock` | OpenCode provider |
| `test_kimi_provider_mock` | Kimi provider |
| `test_mock_stream_provider` | Mock provider |

### 8. TestCopilotTokenTracking (3 tests) ⭐ NEW

Token 追踪测试。

| 测试 | 描述 |
|------|------|
| `test_token_tracking_service_called` | Token 追踪服务被调用 |
| `test_token_tracking_with_different_models` | 不同模型的 Token 追踪 |
| `test_session_usage_updated` | 会话使用量更新 |

### 9. TestCopilotSessionBinding (3 tests) ⭐ NEW

会话绑定测试。

| 测试 | 描述 |
|------|------|
| `test_session_created_with_user_id` | 使用 user_id 创建会话 |
| `test_model_binding_to_session` | 模型绑定到会话 |
| `test_bound_model_used_in_stream` | 绑定模型用于流式响应 |

### 10. TestCopilotContextLength (2 tests) ⭐ NEW

上下文长度测试。

| 测试 | 描述 |
|------|------|
| `test_context_length_limit_respected` | 上下文限制 4096 token |
| `test_conversation_history_trimming` | 对话历史裁剪 |

### 11. TestCopilotDatabaseErrors (2 tests) ⭐ NEW

数据库错误测试。

| 测试 | 描述 |
|------|------|
| `test_conversation_load_error_handled` | 对话加载错误处理 |
| `test_message_save_error_handled` | 消息保存错误处理 |

### 12. TestCopilotProviderFallback (3 tests) ⭐ NEW

Provider 回退测试。

| 测试 | 描述 |
|------|------|
| `test_openai_fallback_to_mock` | OpenAI 回退到 mock |
| `test_deepseek_fallback_to_mock` | DeepSeek 回退到 mock |
| `test_unknown_provider_falls_back` | 未知 provider 回退 |

### 13. TestCopilotRateLimiting (3 tests) ⭐ NEW

速率限制测试。

| 测试 | 描述 |
|------|------|
| `test_rate_limit_header_present` | 速率限制头存在 |
| `test_concurrent_request_limit` | 并发请求限制 |
| `test_rate_limit_reset_between_tests` | 测试间速率限制重置 |

### 14. TestCopilotContextAssembly (4 tests) ⭐ NEW

上下文组装测试。

| 测试 | 描述 |
|------|------|
| `test_context_with_symbol_only` | 仅 Symbol 上下文 |
| `test_context_with_portfolio_only` | 仅 Portfolio 上下文 |
| `test_context_with_symbol_and_portfolio` | Symbol + Portfolio 上下文 |
| `test_context_assembler_exception_fallback` | 上下文组装异常回退 |

## Mock 模式

### 异步 SSE 生成器

```python
def _mock_sse_generator(chunks):
    async def async_gen():
        for chunk in chunks:
            yield f"data: {json.dumps(chunk)}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
    return async_gen()
```

### 上下文组装结果

```python
def _create_mock_assembly_result(
    query_type=QueryType.QUICK_QA,
    context_text="[TEST_CONTEXT]",
    symbols=None,
    confidence=0.9
):
    return AssemblyResult(
        query_type=query_type,
        context_text=context_text,
        tokens_used=100,
        symbols=symbols or [],
        classification=ClassificationResult(
            query_type=query_type,
            symbols=symbols or [],
            confidence=confidence,
            original_query="test query"
        )
    )
```

### 数据库 Mock

```python
@pytest.fixture(scope="module", autouse=True)
def mock_database_for_module():
    with patch("app.db.model_config_db.get_model_config", return_value={}):
        with patch("app.db.model_config_db.set_model_config", return_value=None):
            with patch("app.db.model_config_db.get_all_model_configs", return_value={}):
                with patch("app.db.model_config_db.get_enabled_models", return_value=[]):
                    yield
```

## 运行测试

```bash
# 运行所有 Copilot 测试
cd backend && pytest tests/unit/test_routers/test_copilot.py -v

# 运行特定测试类
cd backend && pytest tests/unit/test_routers/test_copilot.py::TestCopilotTokenTracking -v

# 运行带覆盖率
cd backend && pytest tests/unit/test_routers/test_copilot.py --cov=app.routers.copilot --cov-report=html

# 运行并显示打印输出
cd backend && pytest tests/unit/test_routers/test_copilot.py -v -s
```

## 已知问题

### 业务代码 async/await 错误

当前有 **45 个测试失败**，原因是业务代码 `backend/app/routers/copilot.py` 中存在 **7 处 async/await 错误**：

| 行号 | 函数 | 问题 | 严重性 |
|------|------|------|--------|
| 1114 | `_init_conversations_table()` | 缺少 await | HIGH |
| 1173 | `_fetch_price_context()` | 缺少 await | HIGH |
| 1174 | `_fetch_latest_news()` | 缺少 await | HIGH |
| 1182 | `_fetch_portfolio_data()` | 缺少 await | HIGH |
| 1188 | `_fetch_historical_data()` | 缺少 await | HIGH |
| **1205** | `_load_conversation()` | 缺少 await | **CRITICAL** |
| 1215 | `_save_message()` | 缺少 await | HIGH |

### 错误表现

```python
# 错误示例
history = _load_conversation(session_id) if session_id else []
# 返回 coroutine 对象而非 list

# 正确写法
history = await _load_conversation(session_id) if session_id else []
```

### 修复后的预期结果

修复业务代码后，所有 63 个测试应通过。

## 测试覆盖缺口

以下场景仍需补充测试：

| 缺口 | 描述 | 优先级 |
|------|------|--------|
| WebSocket 实时推送 | 测试 WebSocket 消息广播 | P1 |
| 多轮对话 | 测试多轮对话上下文保持 | P1 |
| 流式响应中断 | 测试客户端断开连接的处理 | P2 |
| 超时重试 | 测试 LLM 超时后的重试逻辑 | P2 |
| 并发安全 | 测试高并发下的数据一致性 | P2 |

## 相关文档

- [TESTING_GUIDE.md](../TESTING_GUIDE.md) - 测试编写指南
- [COPILOT_OPTIMIZATION_SUMMARY.md](../COPILOT_OPTIMIZATION_SUMMARY.md) - Copilot 优化总结
- [API_GUIDE.md](../API_GUIDE.md) - API 文档
