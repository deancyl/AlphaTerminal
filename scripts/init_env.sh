#!/usr/bin/env bash
#===============================================================================
# AlphaTerminal 环境初始化脚本
# 用法: bash scripts/init_env.sh
# 克隆仓库后运行此脚本，即可完成环境搭建
#===============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 颜色输出
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET} $*"; }
ok()      { echo -e "${GREEN}[OK]${RESET}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
fail()    { echo -e "${RED}[FAIL]${RESET}  $*"; exit 1; }

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 0. 前置检查
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
info "AlphaTerminal 环境初始化"
echo "   根目录: ${ROOT_DIR}"

if [ ! -f "${BACKEND_DIR}/requirements.txt" ]; then
    fail "requirements.txt 不存在，请确认在正确目录运行"
fi
if [ ! -f "${FRONTEND_DIR}/package.json" ]; then
    fail "frontend/package.json 不存在，请确认在正确目录运行"
fi

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 后端 Python 环境
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
info "━━━ 后端 Python 环境 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

VENV_DIR="${BACKEND_DIR}/.venv"

if [ -d "${VENV_DIR}" ]; then
    ok "虚拟环境已存在: ${VENV_DIR}"
else
    info "创建 Python 虚拟环境..."
    python3 -m venv "${VENV_DIR}" || fail "venv 创建失败"
    ok "虚拟环境创建完成"
fi

info "安装 Python 依赖（首次约需 3-5 分钟）..."
"${VENV_DIR}/bin/pip" install --upgrade pip -q
"${VENV_DIR}/bin/pip" install -r "${BACKEND_DIR}/requirements.txt" -q
ok "Python 依赖安装完成"

# 初始化数据库
info "初始化 SQLite 数据库..."
"${VENV_DIR}/bin/python3" - << 'PYEOF'
import sys, os
sys.path.insert(0, os.path.join(os.getenv("ROOT_DIR","."), "backend"))
try:
    from app.db.database import init_tables
    init_tables()
    print("[OK] 数据库初始化完成")
except Exception as e:
    # 数据库模块可能还没完全就绪，仅记录错误不退出
    print(f"[WARN] 数据库初始化跳过: {e}")
PYEOF

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 前端 Node.js 环境
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
info "━━━ 前端 Node.js 环境 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ! command -v node &>/dev/null; then
    fail "Node.js 未安装，请先安装 https://nodejs.org/"
fi

if [ -d "${FRONTEND_DIR}/node_modules" ]; then
    ok "node_modules 已存在"
else
    info "安装前端依赖（首次约需 2-3 分钟）..."
    cd "${FRONTEND_DIR}" && npm install --silent
    ok "前端依赖安装完成"
fi

# 检查 vite 配置
if [ ! -f "${FRONTEND_DIR}/vite.config.js" ]; then
    warn "vite.config.js 不存在，前端可能无法启动"
fi

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 代理配置提示
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
info "━━━ 代理配置 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
PROXY_HINT="

  如需通过代理访问外网（AkShare/东方财富数据源），请在启动前设置：

    # Linux/macOS
    export HTTP_PROXY=http://你的代理IP:端口
    export HTTPS_PROXY=http://你的代理IP:端口

    # Windows PowerShell
    \$env:HTTP_PROXY='http://你的代理IP:端口'
    \$env:HTTPS_PROXY='http://你的代理IP:端口'

  数据代理（HTTP_PROXY）：编辑 ${BACKEND_DIR}/start_backend.py
  将 PROXY = os.environ.get('HTTP_PROXY', '') 替换为你的代理地址

"
echo "${PROXY_HINT}"

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 启动命令
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
info "━━━ 启动命令 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
STARTUP_HINT="

  # 终端 1 — 后端（端口 8002）
  cd ${BACKEND_DIR}
  source .venv/bin/activate        # Linux/macOS
  # .venv\\Scripts\\Activate.ps1    # Windows PowerShell
  python start_backend.py

  # 终端 2 — 前端（端口 60100）
  cd ${FRONTEND_DIR}
  npm run dev -- --host 0.0.0.0 --port 60100

  # 访问 http://localhost:60100

"
echo "${STARTUP_HINT}"

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 完成
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "AlphaTerminal 环境初始化完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
