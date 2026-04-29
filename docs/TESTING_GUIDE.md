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
