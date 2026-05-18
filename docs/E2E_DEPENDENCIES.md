# AlphaTerminal E2E 测试依赖环境指南

> **版本**: v1.0  
> **创建日期**: 2026-05-18  
> **适用环境**: OpenCode / 本地开发 / CI/CD

---

## 目录

1. [系统要求](#1-系统要求)
2. [前端依赖](#2-前端依赖)
3. [后端依赖](#3-后端依赖)
4. [OpenCode 环境配置](#4-opencode-环境配置)
5. [快速安装](#5-快速安装)
6. [环境验证](#6-环境验证)
7. [常见问题](#7-常见问题)

---

## 1. 系统要求

### 1.1 操作系统

| 操作系统 | 最低版本 | 推荐版本 |
|----------|----------|----------|
| **Ubuntu/Debian** | 20.04 LTS | 22.04 LTS |
| **macOS** | 12.0 Monterey | 14.0 Sonoma |
| **Windows** | 10 | 11 |
| **CentOS/RHEL** | 8 | 9 |

### 1.2 运行时环境

| 运行时 | 最低版本 | 推荐版本 | 用途 |
|--------|----------|----------|------|
| **Node.js** | 18.0.0 | 20.x LTS | 前端构建和测试 |
| **Python** | 3.10 | 3.11 | 后端运行和测试 |
| **npm** | 9.0.0 | 10.x | 包管理 |
| **pip** | 23.0 | 24.x | Python 包管理 |

### 1.3 硬件要求

| 资源 | 最低要求 | 推荐配置 |
|------|----------|----------|
| **CPU** | 4 核 | 8 核+ |
| **内存** | 8 GB | 16 GB+ |
| **磁盘** | 20 GB | 50 GB+ |
| **网络** | 稳定连接 | 低延迟连接 |

---

## 2. 前端依赖

### 2.1 核心 E2E 测试依赖

```json
{
  "devDependencies": {
    "@playwright/test": "^1.59.1",
    "@axe-core/playwright": "^4.8.0",
    "axe-core": "^4.8.0",
    "msw": "^2.0.0",
    "@lhci/cli": "^0.13.0",
    "lighthouse": "^12.0.0",
    "vitest": "^3.0.0",
    "@vue/test-utils": "^2.4.6",
    "jsdom": "^26.0.0",
    "vitest-axe": "^0.1.0"
  }
}
```

### 2.2 依赖说明

| 包名 | 版本 | 用途 | 必需 |
|------|------|------|------|
| `@playwright/test` | ^1.59.1 | E2E 测试框架 | 是 |
| `@axe-core/playwright` | ^4.8.0 | 无障碍测试集成 | 是 |
| `axe-core` | ^4.8.0 | 无障碍引擎 | 是 |
| `msw` | ^2.0.0 | API Mock 服务 | 是 |
| `@lhci/cli` | ^0.13.0 | Lighthouse CI | 可选 |
| `lighthouse` | ^12.0.0 | 性能审计 | 可选 |
| `vitest` | ^3.0.0 | 单元测试框架 | 是 |
| `@vue/test-utils` | ^2.4.6 | Vue 组件测试 | 是 |
| `jsdom` | ^26.0.0 | DOM 模拟 | 是 |

### 2.3 Playwright 浏览器安装

```bash
# 安装所有浏览器
npx playwright install

# 安装特定浏览器
npx playwright install chromium
npx playwright install firefox
npx playwright install webkit

# 安装带系统依赖（Linux）
npx playwright install --with-deps
```

**浏览器磁盘占用：**

| 浏览器 | 大小 |
|--------|------|
| Chromium | ~280 MB |
| Firefox | ~90 MB |
| WebKit | ~120 MB |
| **总计** | ~490 MB |

---

## 3. 后端依赖

### 3.1 Python 测试依赖

```txt
# requirements-test.txt
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pytest-xdist>=3.3.0
httpx>=0.24.0
respx>=0.20.0
faker>=19.0.0
freezegun>=1.2.0
pytest-mock>=3.11.0
allure-pytest>=2.13.0
```

### 3.2 依赖说明

| 包名 | 版本 | 用途 | 必需 |
|------|------|------|------|
| `pytest` | >=7.4.0 | 测试框架 | 是 |
| `pytest-asyncio` | >=0.21.0 | 异步测试支持 | 是 |
| `pytest-cov` | >=4.1.0 | 覆盖率报告 | 是 |
| `pytest-xdist` | >=3.3.0 | 并行测试 | 是 |
| `httpx` | >=0.24.0 | HTTP 客户端测试 | 是 |
| `respx` | >=0.20.0 | HTTP Mock | 是 |
| `faker` | >=19.0.0 | 测试数据生成 | 是 |
| `freezegun` | >=1.2.0 | 时间 Mock | 是 |
| `pytest-mock` | >=3.11.0 | Mock 工具 | 是 |
| `allure-pytest` | >=2.13.0 | 测试报告 | 可选 |

### 3.3 数据库测试依赖

```txt
# 用于集成测试
aiosqlite>=0.19.0
sqlalchemy>=2.0.0
pytest-docker>=2.0.0  # Docker 容器测试
```

---

## 4. OpenCode 环境配置

### 4.1 OpenCode 内置工具

OpenCode 提供了 **28 个 Playwright 浏览器自动化工具**，无需额外安装：

| 工具类别 | 工具数量 | 说明 |
|----------|----------|------|
| **页面操作** | 8 | navigate, click, fill, screenshot 等 |
| **元素查询** | 6 | query, queryAll, waitFor 等 |
| **断言验证** | 5 | expectText, expectValue, expectVisible 等 |
| **网络控制** | 4 | intercept, mockRoute, waitForResponse 等 |
| **高级功能** | 5 | evaluate, pdf, video, trace 等 |

### 4.2 OpenCode 配置文件

在项目根目录创建 `.opencode/config.json`：

```json
{
  "browser": {
    "headless": true,
    "browser": "chromium",
    "viewport": {
      "width": 1920,
      "height": 1080
    },
    "timeout": 30000,
    "retries": 2,
    "slowMo": 0
  },
  "test": {
    "parallel": true,
    "workers": 4,
    "reporter": ["list", "html"],
    "screenshot": "only-on-failure",
    "video": "retain-on-failure",
    "trace": "retain-on-failure"
  },
  "env": {
    "BASE_URL": "http://localhost:60100",
    "API_URL": "http://localhost:8002"
  }
}
```

### 4.3 OpenCode 环境变量

```bash
# .opencode/.env
OPENCODE_HEADLESS=true
OPENCODE_BROWSER=chromium
OPENCODE_TIMEOUT=30000
OPENCODE_BASE_URL=http://localhost:60100
OPENCODE_API_URL=http://localhost:8002
OPENCODE_SCREENSHOT_DIR=./test-results/screenshots
OPENCODE_VIDEO_DIR=./test-results/videos
```

### 4.4 OpenCode 特定优化

| 优化项 | 说明 |
|--------|------|
| **WebSocket 原生支持** | OpenCode 工具直接支持 WebSocket 测试 |
| **自动重试** | 失败测试自动重试 2 次 |
| **并行执行** | 默认 4 个 worker 并行 |
| **失败截图** | 失败时自动截图保存 |
| **失败视频** | 失败时录制视频 |
| **Trace 记录** | 失败时记录完整 trace |

---

## 5. 快速安装

### 5.1 一键安装脚本

```bash
#!/bin/bash
# scripts/setup-e2e.sh

set -e

echo "🚀 开始安装 E2E 测试环境..."

# 1. 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装，请先安装 Node.js 18+"
    exit 1
fi

# 2. 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 未安装，请先安装 Python 3.10+"
    exit 1
fi

# 3. 安装前端依赖
echo "📦 安装前端依赖..."
cd frontend
npm install
npx playwright install --with-deps
cd ..

# 4. 安装后端依赖
echo "📦 安装后端依赖..."
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-test.txt 2>/dev/null || pip install pytest pytest-asyncio pytest-cov httpx respx faker
cd ..

# 5. 创建测试目录
echo "📁 创建测试目录..."
mkdir -p frontend/tests/e2e
mkdir -p frontend/test-results
mkdir -p backend/tests/e2e

# 6. 验证安装
echo "✅ 验证安装..."
npx playwright --version
pytest --version

echo "✅ E2E 测试环境安装完成！"
echo ""
echo "运行测试："
echo "  前端 E2E: cd frontend && npx playwright test"
echo "  后端测试: cd backend && pytest tests/"
```

### 5.2 使用方法

```bash
# 赋予执行权限
chmod +x scripts/setup-e2e.sh

# 运行安装
./scripts/setup-e2e.sh
```

### 5.3 Docker 环境安装

```dockerfile
# Dockerfile.e2e
FROM mcr.microsoft.com/playwright:v1.59.1-jammy

WORKDIR /app

# 安装 Python
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# 安装依赖
COPY frontend/package*.json ./frontend/
WORKDIR /app/frontend
RUN npm ci

COPY backend/requirements*.txt ./backend/
WORKDIR /app/backend
RUN pip3 install -r requirements.txt -r requirements-test.txt

WORKDIR /app
```

```bash
# 构建并运行
docker build -f Dockerfile.e2e -t alphaterminal-e2e .
docker run -it alphaterminal-e2e npx playwright test
```

---

## 6. 环境验证

### 6.1 验证脚本

```bash
#!/bin/bash
# scripts/verify-e2e-env.sh

echo "🔍 验证 E2E 测试环境..."

# 1. 检查 Node.js 版本
NODE_VERSION=$(node -v | cut -d 'v' -f 2 | cut -d '.' -f 1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js 版本过低: $(node -v)，需要 18+"
    exit 1
fi
echo "✅ Node.js: $(node -v)"

# 2. 检查 Python 版本
PYTHON_VERSION=$(python3 -c 'import sys; print(sys.version_info.major * 10 + sys.version_info.minor)')
if [ "$PYTHON_VERSION" -lt 310 ]; then
    echo "❌ Python 版本过低: $(python3 --version)，需要 3.10+"
    exit 1
fi
echo "✅ Python: $(python3 --version)"

# 3. 检查 Playwright
if ! npx playwright --version &> /dev/null; then
    echo "❌ Playwright 未安装"
    exit 1
fi
echo "✅ Playwright: $(npx playwright --version)"

# 4. 检查浏览器
BROWSERS=$(npx playwright install --dry-run 2>&1 | grep -c "browser")
if [ "$BROWSERS" -lt 3 ]; then
    echo "⚠️  浏览器未完全安装，运行: npx playwright install"
else
    echo "✅ 浏览器已安装"
fi

# 5. 检查 pytest
if ! pytest --version &> /dev/null; then
    echo "❌ pytest 未安装"
    exit 1
fi
echo "✅ pytest: $(pytest --version | head -1)"

# 6. 检查服务端口
if lsof -i:60100 &> /dev/null; then
    echo "✅ 前端端口 60100 可用"
else
    echo "⚠️  前端端口 60100 未启动"
fi

if lsof -i:8002 &> /dev/null; then
    echo "✅ 后端端口 8002 可用"
else
    echo "⚠️  后端端口 8002 未启动"
fi

echo ""
echo "✅ 环境验证完成！"
```

### 6.2 快速验证命令

```bash
# 一键验证
./scripts/verify-e2e-env.sh

# 手动验证
node -v                    # Node.js 18+
python3 --version          # Python 3.10+
npx playwright --version   # Playwright 1.59+
pytest --version           # pytest 7.4+
npx playwright install --dry-run  # 检查浏览器
```

### 6.3 验证测试运行

```bash
# 前端：运行示例测试
cd frontend
npx playwright test --list  # 列出所有测试

# 后端：运行示例测试
cd backend
pytest tests/ --collect-only  # 列出所有测试
```

---

## 7. 常见问题

### 7.1 Playwright 浏览器安装失败

**问题**: `npx playwright install` 失败

**解决方案**:
```bash
# Linux: 安装系统依赖
npx playwright install-deps
npx playwright install

# 或者使用包管理器
# Ubuntu/Debian
sudo apt-get install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2

# macOS: 通常无需额外依赖
# Windows: 通常无需额外依赖
```

### 7.2 WebSocket 测试连接失败

**问题**: WebSocket 连接在测试中失败

**解决方案**:
```javascript
// playwright.config.js
module.exports = {
  use: {
    // 增加 WebSocket 超时
    actionTimeout: 30000,
    navigationTimeout: 30000,
  },
  // WebSocket 特定配置
  webServer: {
    command: 'npm run dev',
    port: 60100,
    timeout: 120000,
    reuseExistingServer: true,
  },
}
```

### 7.3 MSW Mock 不生效

**问题**: API Mock 不拦截请求

**解决方案**:
```javascript
// tests/setup.js
import { server } from './mocks/server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

// 确保 MSW 在 Playwright 之前初始化
```

### 7.4 测试超时

**问题**: 测试经常超时失败

**解决方案**:
```javascript
// playwright.config.js
module.exports = {
  timeout: 60000,  // 全局超时 60s
  use: {
    actionTimeout: 10000,  // 单个操作 10s
    navigationTimeout: 30000,  // 导航 30s
  },
}
```

### 7.5 并行测试冲突

**问题**: 并行测试时数据冲突

**解决方案**:
```javascript
// 使用隔离的测试数据
test.describe('Portfolio Tests', () => {
  test.use({
    storageState: `./auth-${test.info().parallelIndex}.json`
  })
  
  test('create portfolio', async ({ page }) => {
    const uniqueName = `Portfolio-${Date.now()}-${Math.random()}`
    // ...
  })
})
```

### 7.6 内存不足

**问题**: 测试运行时内存溢出

**解决方案**:
```bash
# 减少 worker 数量
npx playwright test --workers=2

# 或在配置中限制
# playwright.config.js
module.exports = {
  workers: process.env.CI ? 2 : 4,
}
```

### 7.7 截图/视频路径问题

**问题**: 截图或视频保存失败

**解决方案**:
```bash
# 确保目录存在
mkdir -p frontend/test-results/screenshots
mkdir -p frontend/test-results/videos
mkdir -p frontend/test-results/traces

# 设置权限
chmod -R 777 frontend/test-results
```

### 7.8 CI/CD 环境差异

**问题**: 本地通过但 CI 失败

**解决方案**:
```yaml
# .github/workflows/e2e.yml
- name: Install Playwright
  run: npx playwright install --with-deps

- name: Run E2E tests
  run: npx playwright test
  env:
    CI: true
    HEADLESS: true
```

---

## 8. 附录

### 8.1 完整依赖清单

**前端 package.json**:
```json
{
  "devDependencies": {
    "@playwright/test": "^1.59.1",
    "@axe-core/playwright": "^4.8.0",
    "axe-core": "^4.8.0",
    "msw": "^2.0.0",
    "@lhci/cli": "^0.13.0",
    "lighthouse": "^12.0.0",
    "vitest": "^3.0.0",
    "@vue/test-utils": "^2.4.6",
    "jsdom": "^26.0.0",
    "vitest-axe": "^0.1.0",
    "@faker-js/faker": "^8.0.0",
    "dotenv": "^16.0.0"
  }
}
```

**后端 requirements-test.txt**:
```txt
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pytest-xdist>=3.3.0
httpx>=0.24.0
respx>=0.20.0
faker>=19.0.0
freezegun>=1.2.0
pytest-mock>=3.11.0
allure-pytest>=2.13.0
aiosqlite>=0.19.0
sqlalchemy>=2.0.0
```

### 8.2 推荐测试目录结构

```
frontend/
├── tests/
│   ├── e2e/                    # E2E 测试
│   │   ├── auth.spec.js        # 认证流程
│   │   ├── market.spec.js      # 市场数据
│   │   ├── portfolio.spec.js   # 投资组合
│   │   ├── backtest.spec.js    # 回测功能
│   │   ├── websocket.spec.js   # WebSocket
│   │   └── accessibility.spec.js # 无障碍
│   ├── unit/                   # 单元测试
│   ├── mocks/                  # MSW Mocks
│   │   ├── handlers/
│   │   └── server.js
│   └── setup.js                # 测试设置
├── test-results/               # 测试结果
│   ├── screenshots/
│   ├── videos/
│   └── traces/
└── playwright.config.js

backend/
├── tests/
│   ├── unit/                   # 单元测试
│   ├── integration/            # 集成测试
│   ├── e2e/                    # E2E 测试
│   └── conftest.py             # 共享 fixtures
└── pytest.ini
```

### 8.3 相关文档

- [E2E 测试计划](./E2E_TEST_PLAN.md) - 完整测试架构设计
- [测试编写指南](./TESTING_GUIDE.md) - 测试最佳实践
- [API 文档](./API_GUIDE.md) - API 接口说明

---

> **文档版本**: v1.0  
> **最后更新**: 2026-05-18  
> **维护者**: AlphaTerminal Team
