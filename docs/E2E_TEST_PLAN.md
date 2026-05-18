# AlphaTerminal E2E 测试计划

> **版本**: v1.0  
> **创建日期**: 2026-05-18  
> **状态**: 设计完成，待实施

---

## 目录

1. [概述](#1-概述)
2. [测试架构](#2-测试架构)
3. [P0 关键路径测试](#3-p0-关键路径测试)
4. [P1 重要测试](#4-p1-重要测试)
5. [P2 可选测试](#5-p2-可选测试)
6. [Mock 策略](#6-mock-策略)
7. [CI/CD 集成](#7-cicd-集成)
8. [实施清单](#8-实施清单)
9. [成功标准](#9-成功标准)

---

## 1. 概述

### 1.1 项目背景

AlphaTerminal 是一个 Vue 3 + FastAPI 金融交易应用，包含：
- **前端**: 124+ Vue 组件，13 个主要视图
- **后端**: 26 个 API 路由，WebSocket 实时数据推送
- **现有测试**: 前端 32 个测试文件，后端 61 个测试文件

### 1.2 测试目标

| 目标 | 描述 |
|------|------|
| **全面覆盖** | 覆盖所有关键用户流程和 API 端点 |
| **自动化** | CI/CD 集成，自动运行测试 |
| **可维护** | Page Object Model 模式，易于维护 |
| **可靠性** | Flaky 测试率 < 1% |

### 1.3 测试工具栈

| 工具 | 用途 |
|------|------|
| **Playwright** | E2E 测试框架（原生 WebSocket 支持） |
| **MSW** | API Mock（网络层拦截） |
| **axe-core** | 无障碍测试 |
| **Lighthouse** | 性能测试 |
| **Pytest** | 后端 E2E 测试 |

### 1.4 测试统计

| 优先级 | 测试数量 | 文件数量 |
|--------|----------|----------|
| **P0 Critical** | 50 | 5 |
| **P1 Important** | 125 | 9 |
| **P2 Nice-to-have** | 85 | 5 |
| **Backend E2E** | 50+ | 12 |
| **总计** | **260+** | **31+** |

---

## 2. 测试架构

### 2.1 前端目录结构

```
frontend/tests/
├── e2e/
│   ├── specs/                           # 测试规格
│   │   ├── critical/                    # P0 - 发布必须
│   │   │   ├── auth.spec.js
│   │   │   ├── portfolio-workflow.spec.js
│   │   │   ├── trade-execution.spec.js
│   │   │   ├── backtest-workflow.spec.js
│   │   │   └── websocket-connection.spec.js
│   │   ├── important/                   # P1 - 质量保障
│   │   │   ├── f9-deep-data.spec.js
│   │   │   ├── copilot-chat.spec.js
│   │   │   ├── macro-dashboard.spec.js
│   │   │   ├── forex-trading.spec.js
│   │   │   ├── futures-dashboard.spec.js
│   │   │   ├── bond-dashboard.spec.js
│   │   │   ├── options-chain.spec.js
│   │   │   ├── ml-strategy.spec.js
│   │   │   └── drawing-tools.spec.js
│   │   └── nice-to-have/                # P2 - 边缘情况
│   │       ├── visual-regression.spec.js
│   │       ├── accessibility.spec.js
│   │       ├── performance.spec.js
│   │       ├── offline-mode.spec.js
│   │       └── error-recovery.spec.js
│   │
│   ├── pages/                           # Page Object Model (14 files)
│   ├── fixtures/                        # 测试数据 (13 files)
│   ├── mocks/                           # API Mock (handlers + data)
│   ├── utils/                           # 测试工具 (8 files)
│   ├── playwright.config.js
│   └── global-setup.js
```

### 2.2 后端目录结构

```
backend/tests/
├── e2e/
│   ├── test_market_workflow.py
│   ├── test_portfolio_workflow.py
│   ├── test_backtest_workflow.py
│   ├── test_f9_workflow.py
│   ├── test_copilot_workflow.py
│   ├── test_macro_workflow.py
│   ├── test_forex_workflow.py
│   ├── test_futures_workflow.py
│   ├── test_bond_workflow.py
│   ├── test_options_workflow.py
│   ├── test_ml_workflow.py
│   └── test_websocket_workflow.py
│
└── fixtures/
    ├── portfolio_fixtures.py
    ├── backtest_fixtures.py
    └── ... (9 more)
```

---

## 3. P0 关键路径测试

### 3.1 测试概览

| 测试文件 | 测试数量 | 描述 |
|----------|----------|------|
| `auth.spec.js` | 5 | 认证流程 |
| `portfolio-workflow.spec.js` | 15 | 组合管理 |
| `trade-execution.spec.js` | 12 | 交易执行 |
| `backtest-workflow.spec.js` | 10 | 回测流程 |
| `websocket-connection.spec.js` | 8 | WebSocket 连接 |
| **总计** | **50** | - |

### 3.2 认证流程测试 (`auth.spec.js`)

| Test ID | 描述 |
|---------|------|
| AUTH-001 | 应用加载无错误 |
| AUTH-002 | 刷新后保持会话 |
| AUTH-003 | 恢复主题偏好 |
| AUTH-004 | 优雅处理会话超时 |
| AUTH-005 | 登出时清除会话 |

### 3.3 组合管理测试 (`portfolio-workflow.spec.js`)

| Test ID | 描述 |
|---------|------|
| PORT-001 | 创建新组合 |
| PORT-002 | 显示组合列表 |
| PORT-003 | 组合初始资金注入 |
| PORT-004 | 账户间资金划转（两步确认） |
| PORT-005 | 编辑组合详情 |
| PORT-006 | 删除组合（需确认） |
| PORT-007 | 显示组合摘要 |
| PORT-008 | 显示持仓列表 |
| PORT-009 | 计算总市值 |
| PORT-010 | 处理空组合状态 |
| PORT-011 | 验证组合名称 |
| PORT-012 | 验证初始资金 |
| PORT-013 | 持久化组合数据 |
| PORT-014 | 处理并发访问 |
| PORT-015 | 导出组合数据 |

### 3.4 交易执行测试 (`trade-execution.spec.js`)

| Test ID | 描述 |
|---------|------|
| TRADE-001 | 执行买入订单（两步确认） |
| TRADE-002 | 执行卖出订单（显示盈亏） |
| TRADE-003 | 验证买入价格 |
| TRADE-004 | 验证买入数量（100 的整数倍） |
| TRADE-005 | 显示订单预览 |
| TRADE-006 | 取消订单 |
| TRADE-007 | 处理资金不足 |
| TRADE-008 | 处理持仓不足 |
| TRADE-009 | 更新持仓 |
| TRADE-010 | 计算佣金 |
| TRADE-011 | 显示交易历史 |
| TRADE-012 | 市价单 vs 限价单 |

### 3.5 回测流程测试 (`backtest-workflow.spec.js`)

| Test ID | 描述 |
|---------|------|
| BACK-001 | 运行均线交叉回测 |
| BACK-002 | 从组合导入持仓 |
| BACK-003 | 显示回测权益曲线 |
| BACK-004 | 显示回测绩效指标 |
| BACK-005 | 验证日期范围 |
| BACK-006 | 验证股票代码格式 |
| BACK-007 | 处理空回测结果 |
| BACK-008 | 策略 vs 基准对比 |
| BACK-009 | 导出回测结果 |
| BACK-010 | 处理回测超时 |

### 3.6 WebSocket 连接测试 (`websocket-connection.spec.js`)

| Test ID | 描述 |
|---------|------|
| WS-001 | 建立 WebSocket 连接 |
| WS-002 | 连接状态转换 (IDLE → CONNECTING → CONNECTED) |
| WS-003 | 接收实时 Tick 更新 |
| WS-004 | 断线重连 |
| WS-005 | 失败后 HTTP 轮询回退 |
| WS-006 | WebSocket 心跳 |
| WS-007 | 取消订阅 |
| WS-008 | 多股票订阅 |

---

## 4. P1 重要测试

### 4.1 测试概览

| 测试文件 | 测试数量 | 描述 |
|----------|----------|------|
| `f9-deep-data.spec.js` | 24 | F9 深度资料（8 个 Tab） |
| `copilot-chat.spec.js` | 15 | AI Copilot 对话 |
| `macro-dashboard.spec.js` | 12 | 宏观经济仪表盘 |
| `forex-trading.spec.js` | 15 | 外汇交易 |
| `futures-dashboard.spec.js` | 12 | 期货仪表盘 |
| `bond-dashboard.spec.js` | 10 | 债券仪表盘 |
| `options-chain.spec.js` | 10 | 期权链 |
| `ml-strategy.spec.js` | 12 | ML 策略 |
| `drawing-tools.spec.js` | 15 | 画线工具 |
| **总计** | **125** | - |

### 4.2 F9 深度资料测试 (`f9-deep-data.spec.js`)

| Test ID | 描述 | Tab |
|---------|------|-----|
| F9-001 ~ F9-009 | 8 个 Tab 测试 | 公司概况/财务摘要/机构持股/盈利预测/股东研究/公司公告/同业比较/融资融券 |
| F9-010 ~ F9-012 | 加载状态/错误处理/刷新数据 | - |

### 4.3 Copilot 对话测试 (`copilot-chat.spec.js`)

| Test ID | 描述 |
|---------|------|
| COP-001 | 打开 Copilot 侧边栏 |
| COP-002 | 发送消息并接收回复 |
| COP-003 | Markdown 格式渲染 |
| COP-004 | 复制代码块 |
| COP-005 | 速率限制（30/60s） |
| COP-006 | 显示速率限制倒计时 |
| COP-007 | 选择上下文股票 |
| COP-008 | 包含股票上下文 |
| COP-009 | 选择模型 |
| COP-010 | 显示输入指示器 |
| COP-011 | 处理 API 错误 |
| COP-012 | 清除对话历史 |
| COP-013 | 使用快捷命令 |
| COP-014 | 处理长流式响应 |
| COP-015 | 刷新后保持对话 |

### 4.4 宏观仪表盘测试 (`macro-dashboard.spec.js`)

| Test ID | 描述 | 指标 |
|---------|------|------|
| MAC-001 | 显示宏观仪表盘 | - |
| MAC-002 | 显示所有 8 个指标 | - |
| MAC-003 ~ MAC-010 | 各指标测试 | GDP/CPI/PPI/PMI/M2/SF/工业生产/失业率 |
| MAC-011 ~ MAC-012 | 趋势图表/刷新数据 | - |

### 4.5 外汇交易测试 (`forex-trading.spec.js`)

| Test ID | 描述 |
|---------|------|
| FX-001 | 显示外汇仪表盘 |
| FX-002 | 显示货币对 |
| FX-003 | 显示交叉汇率矩阵 |
| FX-004 | 计算货币转换 |
| FX-005 | 显示外汇 K 线图 |
| FX-006 ~ FX-015 | 汇率更新/主要货币对/离线模式/熔断器/历史汇率等 |

---

## 5. P2 可选测试

### 5.1 测试概览

| 测试文件 | 测试数量 | 描述 |
|----------|----------|------|
| `visual-regression.spec.js` | 20 | 视觉回归 |
| `accessibility.spec.js` | 25 | 无障碍测试 |
| `performance.spec.js` | 15 | 性能测试 |
| `offline-mode.spec.js` | 10 | 离线模式 |
| `error-recovery.spec.js` | 15 | 错误恢复 |
| **总计** | **85** | - |

### 5.2 视觉回归测试 (`visual-regression.spec.js`)

| Test ID | 描述 |
|---------|------|
| VIS-001 ~ VIS-010 | 各页面截图 |
| VIS-011 ~ VIS-014 | 4 种主题截图 |
| VIS-015 ~ VIS-016 | 移动端/平板布局截图 |
| VIS-017 ~ VIS-020 | K线图/画线工具/Copilot/管理后台截图 |

### 5.3 无障碍测试 (`accessibility.spec.js`)

| Test ID | 描述 |
|---------|------|
| A11Y-001 ~ A11Y-002 | WCAG 2.1 AA 合规 |
| A11Y-003 ~ A11Y-004 | 键盘导航/焦点管理 |
| A11Y-005 ~ A11Y-006 | ARIA 标签/颜色对比度 |
| A11Y-007 ~ A11Y-010 | 表单/表格/图表/对话框无障碍 |

### 5.4 性能测试 (`performance.spec.js`)

| Test ID | 描述 | 指标 |
|---------|------|------|
| PERF-001 | LCP < 2.5s | Largest Contentful Paint |
| PERF-002 | FID < 100ms | First Input Delay |
| PERF-003 | CLS < 0.1 | Cumulative Layout Shift |
| PERF-004 ~ PERF-010 | TTI/首屏/资源/内存/延迟等 | - |

---

## 6. Mock 策略

### 6.1 MSW 服务器配置

```javascript
// frontend/tests/e2e/mocks/server.js
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const mswServer = setupServer(...handlers)

export function setupMSW() {
  beforeAll(() => mswServer.listen({ onUnhandledRequest: 'error' }))
  afterEach(() => mswServer.resetHandlers())
  afterAll(() => mswServer.close())
}
```

### 6.2 Handler 注册表

```javascript
// frontend/tests/e2e/mocks/handlers/index.js
export const handlers = [
  ...marketHandlers,
  ...portfolioHandlers,
  ...backtestHandlers,
  ...f9Handlers,
  ...copilotHandlers,
  ...macroHandlers,
  ...forexHandlers,
  ...futuresHandlers,
  ...bondHandlers,
  ...optionsHandlers,
  ...mlHandlers
]
```

### 6.3 WebSocket Mock 类

```javascript
// frontend/tests/e2e/utils/websocket-mock.js
export class MockWebSocket {
  static instances = []
  static CONNECTING = 0
  static OPEN = 1
  
  constructor(url) {
    this.readyState = MockWebSocket.CONNECTING
    MockWebSocket.instances.push(this)
    setTimeout(() => this._connect(), 100)
  }
  
  send(data) {
    const parsed = JSON.parse(data)
    if (parsed.action === 'subscribe') {
      this._simulateTick(parsed.symbols)
    }
  }
  
  _simulateTick(symbols) {
    setInterval(() => {
      for (const symbol of symbols) {
        this.simulateMessage({
          type: 'tick',
          symbol,
          data: { price: 1800 + Math.random() * 50 }
        })
      }
    }, 1000)
  }
}
```

---

## 7. CI/CD 集成

### 7.1 GitHub Actions Workflow

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨 2 点

jobs:
  e2e-smoke:
    name: Smoke Tests (PR)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm ci
      - run: npx playwright install chromium --with-deps
      - run: npx playwright test tests/e2e/specs/critical/ --grep "@smoke"

  e2e-critical:
    name: Critical Path Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15
    needs: e2e-smoke
    if: github.ref == 'refs/heads/main'
    steps:
      - run: npx playwright test tests/e2e/specs/critical/

  e2e-full:
    name: Full Regression
    runs-on: ubuntu-latest
    timeout-minutes: 45
    if: github.event_name == 'schedule'
    strategy:
      matrix:
        browser: [chromium, firefox, webkit]
    steps:
      - run: npx playwright test --project=${{ matrix.browser }}
```

### 7.2 测试执行命令

```bash
# 运行所有测试
npx playwright test

# 运行特定优先级
npx playwright test tests/e2e/specs/critical/
npx playwright test tests/e2e/specs/important/
npx playwright test tests/e2e/specs/nice-to-have/

# 运行特定浏览器
npx playwright test --project=chromium
npx playwright test --project=firefox

# 调试模式
npx playwright test --debug
npx playwright test --ui

# 生成报告
npx playwright test --reporter=html
npx playwright show-report
```

---

## 8. 实施清单

### 8.1 Phase 1: 基础设施 (Week 1-2)

| 任务 | 文件 | 状态 |
|------|------|------|
| 创建测试目录结构 | `frontend/tests/e2e/` | Pending |
| Playwright 配置 | `playwright.config.js` | Pending |
| MSW 服务器配置 | `mocks/server.js` | Pending |
| Handler 注册表 | `mocks/handlers/index.js` | Pending |
| WebSocket Mock | `utils/websocket-mock.js` | Pending |
| 测试工具类 | `utils/test-helpers.js` 等 | Pending |
| BasePage 类 | `pages/BasePage.js` | Pending |
| 测试数据 Fixtures | `mocks/data/*.json` | Pending |

**Phase 1 交付物: 16 文件**

### 8.2 Phase 2: P0 关键测试 (Week 3-4)

| 任务 | 文件 | 测试数 |
|------|------|--------|
| 认证测试 | `specs/critical/auth.spec.js` | 5 |
| 组合工作流测试 | `specs/critical/portfolio-workflow.spec.js` | 15 |
| 交易执行测试 | `specs/critical/trade-execution.spec.js` | 12 |
| 回测工作流测试 | `specs/critical/backtest-workflow.spec.js` | 10 |
| WebSocket 测试 | `specs/critical/websocket-connection.spec.js` | 8 |
| Page Objects | `pages/*.js` | - |
| API Handlers | `mocks/handlers/*.handlers.js` | - |

**Phase 2 交付物: 16 文件, 50 测试**

### 8.3 Phase 3: P1 重要测试 Part 1 (Week 5-6)

| 任务 | 文件 | 测试数 |
|------|------|--------|
| F9 深度资料测试 | `specs/important/f9-deep-data.spec.js` | 24 |
| Copilot 对话测试 | `specs/important/copilot-chat.spec.js` | 15 |
| 宏观仪表盘测试 | `specs/important/macro-dashboard.spec.js` | 12 |
| 外汇交易测试 | `specs/important/forex-trading.spec.js` | 15 |

**Phase 3 交付物: 20 文件, 66 测试**

### 8.4 Phase 4: P1 重要测试 Part 2 (Week 7-8)

| 任务 | 文件 | 测试数 |
|------|------|--------|
| 期货仪表盘测试 | `specs/important/futures-dashboard.spec.js` | 12 |
| 债券仪表盘测试 | `specs/important/bond-dashboard.spec.js` | 10 |
| 期权链测试 | `specs/important/options-chain.spec.js` | 10 |
| ML 策略测试 | `specs/important/ml-strategy.spec.js` | 12 |
| 画线工具测试 | `specs/important/drawing-tools.spec.js` | 15 |

**Phase 4 交付物: 21 文件, 59 测试**

### 8.5 Phase 5: P2 可选测试 (Week 9-10)

| 任务 | 文件 | 测试数 |
|------|------|--------|
| 视觉回归测试 | `specs/nice-to-have/visual-regression.spec.js` | 20 |
| 无障碍测试 | `specs/nice-to-have/accessibility.spec.js` | 25 |
| 性能测试 | `specs/nice-to-have/performance.spec.js` | 15 |
| 离线模式测试 | `specs/nice-to-have/offline-mode.spec.js` | 10 |
| 错误恢复测试 | `specs/nice-to-have/error-recovery.spec.js` | 15 |

**Phase 5 交付物: 9 文件, 85 测试**

### 8.6 Phase 6: CI/CD & 文档 (Week 11-12)

| 任务 | 文件 |
|------|------|
| GitHub Actions Workflow | `.github/workflows/e2e-tests.yml` |
| 报告配置 | `playwright.reporting.config.js` |
| 全局设置 | `global-setup.js` |
| E2E 测试文档 | `docs/E2E_TEST_PLAN.md` |
| 测试运行指南 | `docs/E2E_RUNNING_GUIDE.md` |
| npm scripts | `package.json` 更新 |

**Phase 6 交付物: 10 文件**

---

## 9. 成功标准

| 指标 | 目标 | 验证命令 |
|------|------|----------|
| **P0 测试通过率** | 100% | `npx playwright test tests/e2e/specs/critical/` |
| **P0 测试时长** | < 10 分钟 | CI Pipeline 时间 |
| **P1 测试通过率** | 95%+ | `npx playwright test tests/e2e/specs/important/` |
| **P1 测试时长** | < 30 分钟 | CI Pipeline 时间 |
| **Flaky 测试率** | < 1% | 连续 5 次运行结果一致 |
| **代码覆盖率** | 80%+ | `pytest --cov=app` |
| **无障碍违规** | 0 critical | axe-core 扫描 |
| **LCP** | < 2.5s | Lighthouse CI |
| **FID** | < 100ms | Lighthouse CI |
| **CLS** | < 0.1 | Lighthouse CI |
| **内存增长** | < 50MB | 内存泄漏测试 |
| **CI Pipeline 时间** | < 45 分钟 | GitHub Actions 时间 |

---

## 10. 文件创建清单

### 10.1 前端测试文件 (72 文件)

| 类别 | 文件数 | 位置 |
|------|--------|------|
| 测试规格 | 19 | `frontend/tests/e2e/specs/` |
| Page Objects | 14 | `frontend/tests/e2e/pages/` |
| MSW Handlers | 12 | `frontend/tests/e2e/mocks/handlers/` |
| Mock 数据 | 15 | `frontend/tests/e2e/mocks/data/` |
| 测试 Fixtures | 13 | `frontend/tests/e2e/fixtures/` |
| 测试工具 | 8 | `frontend/tests/e2e/utils/` |
| 配置文件 | 5 | `frontend/tests/e2e/` |

### 10.2 后端测试文件 (22 文件)

| 类别 | 文件数 | 位置 |
|------|--------|------|
| E2E 测试 | 12 | `backend/tests/e2e/` |
| Fixtures | 10 | `backend/tests/fixtures/` |

### 10.3 CI/CD 文件 (2 文件)

| 文件 | 位置 |
|------|------|
| GitHub Actions | `.github/workflows/e2e-tests.yml` |
| Codecov 配置 | `codecov.yml` |

### 10.4 文档文件 (3 文件)

| 文件 | 位置 |
|------|------|
| E2E 测试计划 | `docs/E2E_TEST_PLAN.md` |
| 测试运行指南 | `docs/E2E_RUNNING_GUIDE.md` |
| AGENTS.md 更新 | `AGENTS.md` |

---

## 11. 实施时间线

```
Week 1-2:   Phase 1 - 基础设施搭建
            ├── 创建测试目录结构
            ├── 配置 Playwright & MSW
            ├── 创建基础工具类
            └── 添加 data-testid 属性

Week 3-4:   Phase 2 - P0 关键测试
            ├── 认证测试 (5)
            ├── 组合工作流测试 (15)
            ├── 交易执行测试 (12)
            ├── 回测工作流测试 (10)
            └── WebSocket 测试 (8)
            Total: 50 测试

Week 5-6:   Phase 3 - P1 重要测试 Part 1
            ├── F9 深度资料测试 (24)
            ├── Copilot 对话测试 (15)
            ├── 宏观仪表盘测试 (12)
            └── 外汇交易测试 (15)
            Total: 66 测试

Week 7-8:   Phase 4 - P1 重要测试 Part 2
            ├── 期货仪表盘测试 (12)
            ├── 债券仪表盘测试 (10)
            ├── 期权链测试 (10)
            ├── ML 策略测试 (12)
            └── 画线工具测试 (15)
            Total: 59 测试

Week 9-10:  Phase 5 - P2 可选测试
            ├── 视觉回归测试 (20)
            ├── 无障碍测试 (25)
            ├── 性能测试 (15)
            ├── 离线模式测试 (10)
            └── 错误恢复测试 (15)
            Total: 85 测试

Week 11-12: Phase 6 - CI/CD & 文档
            ├── GitHub Actions Workflow
            ├── 报告配置
            ├── 文档编写
            └── 最终验证
```

---

**总计**: 92 文件, 260+ 测试, 12 周实施周期
