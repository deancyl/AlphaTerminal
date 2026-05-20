# AlphaTerminal 测试编写指南

## 测试框架

| 层 | 框架 | 配置 |
|----|------|------|
| 后端 | pytest + pytest-cov | backend/pytest.ini |
| 前端 (单元) | Vitest + @vue/test-utils | frontend/vitest.config.js |
| 前端 (E2E) | Playwright | frontend/playwright.config.js |

## 后端测试规范

### 文件结构

```
backend/tests/
├── conftest.py           # 共享 fixtures
├── unit/
│   ├── test_utils/       # 工具函数测试
│   ├── test_services/    # 服务层测试
│   └── test_routers/     # 路由层测试
└── integration/          # 集成测试（预留）
```

### 命名规范

- 文件名: `test_*.py`
- 类名: `Test*`
- 方法名: `test_*`

### 装饰器使用

```python
@pytest.mark.skip(reason="需要数据库设置")
def test_complex_feature():
    pass

@patch('app.routers.backtest._get_conn')
def test_with_mock(mock_conn):
    mock_conn.return_value = MagicMock()
    ...
```

### Mock 数据库

```python
from unittest.mock import patch, MagicMock

@patch('app.routers.backtest._get_conn')
def test_backtest_validation(mock_get_conn):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [('data1', 100), ('data2', 200)]
    mock_conn.execute.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    ...
```

## 前端测试规范

### 文件结构

```
frontend/tests/
├── setup.js              # 全局设置
├── unit/
│   ├── utils/            # 工具函数测试
│   └── components/       # 组件测试
└── e2e/                  # E2E测试
```

### 命名规范

- 文件名: `*.test.js` 或 `*.spec.js`
- describe: 组件/模块名
- it/test: 具体行为描述

### 工具函数测试

```javascript
import { describe, it, expect } from 'vitest'
import { myFunction } from '@/utils/myFunction'

describe('myFunction', () => {
  it('should return correct value', () => {
    expect(myFunction('input')).toBe('expected')
  })
})
```

### 组件测试

```javascript
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

describe('MyComponent', () => {
  it('should render correctly', () => {
    const wrapper = mount(MyComponent, {
      props: { data: [] },
    })
    expect(wrapper.find('.container').exists()).toBe(true)
  })
})
```

### E2E测试

```javascript
import { test, expect } from '@playwright/test'

test('should load homepage', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('body')).toBeVisible()
})
```

## Copilot 模块测试覆盖

### 测试结构

`backend/tests/unit/test_routers/test_copilot.py` 包含 **14 个测试类，63 个测试用例**：

| 测试类 | 测试数量 | 覆盖内容 |
|--------|---------|---------|
| `TestCopilotChatEndpoint` | 1 | 基础聊天成功 |
| `TestCopilotInputValidation` | 7 | 输入验证（空、空白、null、长文本、unicode） |
| `TestCopilotErrorHandling` | 1 | 并发限制超限 |
| `TestCopilotAsyncSSE` | 5 | 异步 SSE 流（httpx.AsyncClient） |
| `TestCopilotServiceLayerFailures` | 16 | 服务层 mock、上下文组装、provider 回退 |
| `TestCopilotStatusEndpoint` | 3 | 状态端点结构 |
| `TestCopilotLLMProviders` | 8 | LLM provider 集成（OpenAI/DeepSeek/Qianwen 等） |
| `TestCopilotTokenTracking` | 3 | Token 追踪准确性、成本计算 |
| `TestCopilotSessionBinding` | 3 | 会话创建、模型绑定 |
| `TestCopilotContextLength` | 2 | 上下文长度限制（4096 token） |
| `TestCopilotDatabaseErrors` | 2 | SQLite 错误处理 |
| `TestCopilotProviderFallback` | 3 | Provider 回退链 |
| `TestCopilotRateLimiting` | 3 | 速率限制（30 req/60s） |
| `TestCopilotContextAssembly` | 4 | 上下文组装（symbol/portfolio） |

### 运行测试

```bash
# 运行 Copilot 测试
cd backend && pytest tests/unit/test_routers/test_copilot.py -v

# 运行带覆盖率
cd backend && pytest tests/unit/test_routers/test_copilot.py --cov=app.routers.copilot
```

### Mock 模式

测试使用以下 mock 模式：

```python
# 异步 SSE 生成器
def _mock_sse_generator(chunks):
    async def async_gen():
        for chunk in chunks:
            yield f"data: {json.dumps(chunk)}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
    return async_gen()

# 上下文组装结果
def _create_mock_assembly_result(query_type=QueryType.QUICK_QA, context_text="[TEST]", symbols=None, confidence=0.9):
    return AssemblyResult(
        query_type=query_type,
        context_text=context_text,
        tokens_used=100,
        symbols=symbols or [],
        classification=ClassificationResult(...)
    )
```

### 已知问题

当前有 45 个测试失败，原因是业务代码 `copilot.py` 中存在 **7 处 async/await 错误**：

| 行号 | 函数 | 问题 |
|------|------|------|
| 1114 | `_init_conversations_table()` | 缺少 await |
| 1173 | `_fetch_price_context()` | 缺少 await |
| 1174 | `_fetch_latest_news()` | 缺少 await |
| 1182 | `_fetch_portfolio_data()` | 缺少 await |
| 1188 | `_fetch_historical_data()` | 缺少 await |
| 1205 | `_load_conversation()` | 缺少 await |
| 1215 | `_save_message()` | 缺少 await |

修复业务代码后，所有测试应通过。

## 运行测试命令

```bash
# 后端全部测试
cd backend && pytest tests/ -v

# 后端带覆盖率
cd backend && pytest tests/ --cov=app

# 前端单元测试
cd frontend && npm test -- --run

# E2E测试
cd frontend && npx playwright test

# 全部测试
bash scripts/run-all-tests.sh
```
