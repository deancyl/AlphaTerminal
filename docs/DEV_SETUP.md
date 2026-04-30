# AlphaTerminal 开发环境搭建指南

## 系统要求

- **Node.js**: v18+ (推荐 v20)
- **Python**: 3.11+ (推荐 3.12)
- **包管理器**: npm 9+ / pip 23+
- **Git**: 2.30+

## 快速开始

### 方式一：一键启动（推荐）

我们提供了一键启动脚本，自动完成环境检查、依赖安装和服务启动：

#### Linux / macOS
```bash
git clone https://github.com/deancyl/AlphaTerminal.git
cd AlphaTerminal
./start.sh
```

#### Windows
```powershell
git clone https://github.com/deancyl/AlphaTerminal.git
cd AlphaTerminal
.\start.ps1
```

#### 常用命令

| 命令 | Linux/macOS | Windows | 说明 |
|------|-------------|---------|------|
| 启动全部 | `./start.sh` | `.\start.ps1` | 启动前后端 |
| 仅后端 | `./start.sh backend` | `.\start.ps1 backend` | 仅启动后端 |
| 仅前端 | `./start.sh frontend` | `.\start.ps1 frontend` | 仅启动前端 |
| 停止服务 | `./start.sh stop` | `.\start.ps1 stop` | 停止所有服务 |
| 查看状态 | `./start.sh status` | `.\start.ps1 status` | 查看运行状态 |
| 仅安装依赖 | `./start.sh install` | `.\start.ps1 install` | 仅安装依赖 |

### 方式二：手动配置

如果需要手动控制启动过程：

#### 1. 克隆仓库

```bash
git clone https://github.com/deancyl/AlphaTerminal.git
cd AlphaTerminal
```

#### 2. 后端配置

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .\.venv\Scripts\activate  # Windows

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt
pip install psutil  # 额外依赖

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

后端运行在: `http://localhost:8002`
API文档: `http://localhost:8002/docs`

#### 3. 前端配置

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev -- --host 0.0.0.0 --port 60100
```

前端运行在: `http://localhost:60100`

### 4. 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ALLOWED_ORIGINS` | 允许的跨域来源 | `http://localhost:60100` |
| `HTTP_PROXY` | HTTP代理 | 无 |
| `HTTPS_PROXY` | HTTPS代理 | 无 |

## 测试

### 后端测试

```bash
cd backend
source .venv/bin/activate

# 运行所有测试
pytest tests/ -v

# 运行指定模块
pytest tests/unit/test_routers/test_backtest.py -v

# 带覆盖率报告
pytest tests/ --cov=app --cov-report=html
```

### 前端测试

```bash
cd frontend

# 单元测试
npm test -- --run

# E2E测试
npx playwright test

# 查看 E2E 报告
npx playwright show-report
```

## 开发工具

### 推荐的 VS Code 插件

- Vue - Official (Vue 3 支持)
- Python (pytest 集成)
- ESLint (前端代码检查)
- Prettier (代码格式化)

### Git 工作流

```bash
# 创建功能分支
git checkout -b feat/my-feature

# 提交代码
git add .
git commit -m "feat: 描述你的更改"

# 同步到远程
git push origin feat/my-feature
```

## 项目结构

```
AlphaTerminal/
├── backend/              # Python FastAPI 后端
│   ├── app/
│   │   ├── routers/      # API 路由
│   │   ├── services/     # 业务逻辑
│   │   ├── db/           # 数据库层
│   │   └── utils/        # 工具函数
│   └── tests/            # 测试文件
├── frontend/             # Vue 3 前端
│   ├── src/
│   │   ├── components/   # Vue 组件
│   │   ├── composables/  # 组合式函数
│   │   ├── stores/       # Pinia 状态管理
│   │   └── utils/        # 工具函数
│   └── tests/            # 测试文件
├── docs/                 # 文档
└── .github/workflows/    # CI/CD 配置
```
