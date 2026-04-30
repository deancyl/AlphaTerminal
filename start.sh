#!/usr/bin/env bash
###############################################################################
# AlphaTerminal 一键启动脚本 (Linux/macOS)
# 
# 功能:
#   - 检查环境（Python、Node.js）
#   - 自动安装依赖
#   - 启动后端（FastAPI）
#   - 启动前端（Vite）
#   - 后台运行，提供日志
#
# 用法:
#   ./start.sh              # 启动前后端
#   ./start.sh backend      # 仅启动后端
#   ./start.sh frontend     # 仅启动前端
#   ./start.sh stop         # 停止所有服务
###############################################################################

set -euo pipefail

# ── 颜色定义 ──────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ── 配置 ──────────────────────────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOG_DIR="$PROJECT_ROOT/logs"

BACKEND_PORT=8002
FRONTEND_PORT=60100

BACKEND_PID_FILE="$PROJECT_ROOT/.backend.pid"
FRONTEND_PID_FILE="$PROJECT_ROOT/.frontend.pid"

# ── 日志函数 ──────────────────────────────────────────────────────────────
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${CYAN}[STEP]${NC} $1"; }

# ── 检测操作系统 ──────────────────────────────────────────────────────────
detect_os() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "mac";;
        CYGWIN*|MINGW*|MSYS*) echo "windows";;
        *)          echo "unknown";;
    esac
}

OS=$(detect_os)

# ── 检查端口占用 ──────────────────────────────────────────────────────────
check_port() {
    local port=$1
    if command -v lsof &> /dev/null; then
        lsof -Pi :"$port" -sTCP:LISTEN -t &> /dev/null || true
    elif command -v ss &> /dev/null; then
        ss -tlnp | grep -q ":$port " || true
    elif command -v netstat &> /dev/null; then
        netstat -tlnp 2>/dev/null | grep -q ":$port " || true
    fi
}

# ── 检查命令是否存在 ──────────────────────────────────────────────────────
check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# ── 检查 Python 环境 ──────────────────────────────────────────────────────
check_python() {
    log_step "检查 Python 环境..."
    
    if check_command python3; then
        PYTHON="python3"
    elif check_command python; then
        PYTHON="python"
    else
        log_error "未找到 Python！请安装 Python 3.11+"
        log_info "  macOS: brew install python"
        log_info "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
        log_info "  CentOS/RHEL: sudo yum install python3"
        exit 1
    fi
    
    PYTHON_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
    log_info "Python 版本: $PYTHON_VERSION"
    
    # 检查 Python 版本是否 >= 3.11
    if $PYTHON -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"; then
        log_info "Python 版本符合要求 (>= 3.11)"
    else
        log_warn "Python 版本较低 ($PYTHON_VERSION)，建议升级至 3.11+"
    fi
}

# ── 检查 Node.js 环境 ─────────────────────────────────────────────────────
check_nodejs() {
    log_step "检查 Node.js 环境..."
    
    # 检查项目自带的 node
    if [ -f "$PROJECT_ROOT/node_bin/node" ]; then
        NODE="$PROJECT_ROOT/node_bin/node"
        log_info "使用项目自带的 Node.js"
    elif check_command node; then
        NODE="node"
        log_info "使用系统 Node.js"
    else
        log_error "未找到 Node.js！请安装 Node.js 20+"
        log_info "  下载地址: https://nodejs.org/"
        exit 1
    fi
    
    NODE_VERSION=$($NODE --version 2>&1)
    log_info "Node.js 版本: $NODE_VERSION"
    
    # 检查 npm
    if check_command npm; then
        NPM="npm"
        NPM_VERSION=$(npm --version 2>&1)
        log_info "npm 版本: $NPM_VERSION"
    else
        log_warn "未找到 npm，将使用项目自带方式"
        NPM=""
    fi
}

# ── 安装后端依赖 ──────────────────────────────────────────────────────────
install_backend_deps() {
    log_step "安装后端依赖..."
    
    cd "$BACKEND_DIR"
    
    # 创建虚拟环境（如果不存在）
    if [ ! -d ".venv" ]; then
        log_info "创建 Python 虚拟环境..."
        $PYTHON -m venv .venv
    fi
    
    # 激活虚拟环境
    source .venv/bin/activate
    
    # 升级 pip
    pip install --upgrade pip &> /dev/null
    
    # 安装依赖
    log_info "安装 Python 依赖（这可能需要几分钟）..."
    pip install -r requirements.txt &> /dev/null
    
    # 检查并安装缺失的依赖
    if ! $PYTHON -c "import psutil" 2>/dev/null; then
        log_info "安装额外依赖 psutil..."
        pip install psutil &> /dev/null
    fi
    
    log_info "后端依赖安装完成"
}

# ── 安装前端依赖 ──────────────────────────────────────────────────────────
install_frontend_deps() {
    log_step "安装前端依赖..."
    
    cd "$FRONTEND_DIR"
    
    # 检查 node_modules 是否存在且完整
    if [ ! -d "node_modules" ] || [ ! -d "node_modules/.bin" ]; then
        log_info "node_modules 缺失，需要重新安装..."
        
        if [ -n "$NPM" ]; then
            # 使用系统 npm
            $NPM install
        else
            # 使用项目自带方式
            log_info "使用项目自带 npm..."
            
            # 查找 npm-cli.js
            NPM_CLI=$(find /usr -name "npm-cli.js" 2>/dev/null | head -1)
            if [ -z "$NPM_CLI" ]; then
                # 尝试从 node_modules 找到 npm
                if [ -f "node_modules/npm/bin/npm-cli.js" ]; then
                    NPM_CLI="node_modules/npm/bin/npm-cli.js"
                fi
            fi
            
            if [ -n "$NPM_CLI" ]; then
                $NODE "$NPM_CLI" install
            else
                log_error "无法找到 npm-cli.js"
                log_info "请手动运行: npm install"
                exit 1
            fi
        fi
    else
        log_info "前端依赖已存在"
    fi
    
    # 修复 rollup native module 问题（Linux x64）
    if [ "$OS" == "linux" ]; then
        ROLLUP_DIR="node_modules/@rollup"
        if [ ! -d "$ROLLUP_DIR/rollup-linux-x64-gnu" ]; then
            log_info "安装 rollup Linux native module..."
            mkdir -p "$ROLLUP_DIR"
            cd "$ROLLUP_DIR"
            
            # 下载并解压
            curl -sL -o rollup-linux-x64-gnu.tgz \
                "https://registry.npmjs.org/@rollup/rollup-linux-x64-gnu/-/rollup-linux-x64-gnu-4.34.8.tgz" && \
                tar xzf rollup-linux-x64-gnu.tgz && \
                mv package rollup-linux-x64-gnu && \
                rm rollup-linux-x64-gnu.tgz
            
            cd "$FRONTEND_DIR"
            log_info "rollup native module 安装完成"
        fi
    fi
    
    log_info "前端依赖准备完成"
}

# ── 启动后端 ──────────────────────────────────────────────────────────────
start_backend() {
    log_step "启动后端服务..."
    
    cd "$BACKEND_DIR"
    
    # 检查端口占用
    if check_port $BACKEND_PORT; then
        log_warn "端口 $BACKEND_PORT 已被占用"
        log_info "尝试停止占用进程..."
        
        if command -v lsof &> /dev/null; then
            kill $(lsof -t -i:$BACKEND_PORT) 2>/dev/null || true
        elif command -v fuser &> /dev/null; then
            fuser -k $BACKEND_PORT/tcp 2>/dev/null || true
        fi
        
        sleep 2
    fi
    
    # 激活虚拟环境
    source .venv/bin/activate
    
    # 启动后端
    log_info "启动 FastAPI 服务 (端口: $BACKEND_PORT)..."
    nohup python start_backend.py > "$LOG_DIR/backend.log" 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > "$BACKEND_PID_FILE"
    
    # 等待启动
    log_info "等待后端启动..."
    for i in {1..30}; do
        if check_port $BACKEND_PORT; then
            log_info "✅ 后端启动成功！PID: $BACKEND_PID"
            log_info "   API 地址: http://localhost:$BACKEND_PORT"
            return 0
        fi
        sleep 1
    done
    
    log_error "后端启动失败！请检查日志: $LOG_DIR/backend.log"
    return 1
}

# ── 启动前端 ──────────────────────────────────────────────────────────────
start_frontend() {
    log_step "启动前端服务..."
    
    cd "$FRONTEND_DIR"
    
    # 检查端口占用
    if check_port $FRONTEND_PORT; then
        log_warn "端口 $FRONTEND_PORT 已被占用"
        log_info "尝试停止占用进程..."
        
        if command -v lsof &> /dev/null; then
            kill $(lsof -t -i:$FRONTEND_PORT) 2>/dev/null || true
        elif command -v fuser &> /dev/null; then
            fuser -k $FRONTEND_PORT/tcp 2>/dev/null || true
        fi
        
        sleep 2
    fi
    
    # 启动前端
    log_info "启动 Vite 开发服务器 (端口: $FRONTEND_PORT)..."
    
    if [ -n "$NPM" ]; then
        nohup $NPM run dev > "$LOG_DIR/frontend.log" 2>&1 &
    else
        nohup $NODE ./node_modules/.bin/vite --host 0.0.0.0 > "$LOG_DIR/frontend.log" 2>&1 &
    fi
    
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$FRONTEND_PID_FILE"
    
    # 等待启动
    log_info "等待前端启动..."
    for i in {1..30}; do
        if check_port $FRONTEND_PORT; then
            log_info "✅ 前端启动成功！PID: $FRONTEND_PID"
            log_info "   访问地址: http://localhost:$FRONTEND_PORT"
            return 0
        fi
        sleep 1
    done
    
    log_error "前端启动失败！请检查日志: $LOG_DIR/frontend.log"
    return 1
}

# ── 停止服务 ──────────────────────────────────────────────────────────────
stop_services() {
    log_step "停止服务..."
    
    # 停止后端
    if [ -f "$BACKEND_PID_FILE" ]; then
        BACKEND_PID=$(cat "$BACKEND_PID_FILE")
        if kill -0 "$BACKEND_PID" 2>/dev/null; then
            log_info "停止后端 (PID: $BACKEND_PID)..."
            kill "$BACKEND_PID" 2>/dev/null || true
            sleep 2
        fi
        rm -f "$BACKEND_PID_FILE"
    fi
    
    # 停止前端
    if [ -f "$FRONTEND_PID_FILE" ]; then
        FRONTEND_PID=$(cat "$FRONTEND_PID_FILE")
        if kill -0 "$FRONTEND_PID" 2>/dev/null; then
            log_info "停止前端 (PID: $FRONTEND_PID)..."
            kill "$FRONTEND_PID" 2>/dev/null || true
            sleep 2
        fi
        rm -f "$FRONTEND_PID_FILE"
    fi
    
    # 强制清理端口
    if check_port $BACKEND_PORT; then
        log_warn "强制清理后端端口 $BACKEND_PORT..."
        if command -v lsof &> /dev/null; then
            kill -9 $(lsof -t -i:$BACKEND_PORT) 2>/dev/null || true
        fi
    fi
    
    if check_port $FRONTEND_PORT; then
        log_warn "强制清理前端端口 $FRONTEND_PORT..."
        if command -v lsof &> /dev/null; then
            kill -9 $(lsof -t -i:$FRONTEND_PORT) 2>/dev/null || true
        fi
    fi
    
    log_info "✅ 所有服务已停止"
}

# ── 显示状态 ──────────────────────────────────────────────────────────────
show_status() {
    log_step "服务状态"
    
    if check_port $BACKEND_PORT; then
        log_info "✅ 后端运行中 (端口: $BACKEND_PORT)"
    else
        log_warn "❌ 后端未运行"
    fi
    
    if check_port $FRONTEND_PORT; then
        log_info "✅ 前端运行中 (端口: $FRONTEND_PORT)"
    else
        log_warn "❌ 前端未运行"
    fi
    
    echo ""
    log_info "日志文件:"
    log_info "  后端: $LOG_DIR/backend.log"
    log_info "  前端: $LOG_DIR/frontend.log"
}

# ── 主函数 ────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                              ║${NC}"
    echo -e "${CYAN}║          AlphaTerminal 一键启动脚本                          ║${NC}"
    echo -e "${CYAN}║                                                              ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # 创建日志目录
    mkdir -p "$LOG_DIR"
    
    case "${1:-all}" in
        stop)
            stop_services
            ;;
        status)
            show_status
            ;;
        backend)
            check_python
            install_backend_deps
            start_backend
            ;;
        frontend)
            check_nodejs
            install_frontend_deps
            start_frontend
            ;;
        install)
            check_python
            check_nodejs
            install_backend_deps
            install_frontend_deps
            log_info "✅ 依赖安装完成！"
            ;;
        all|*)
            check_python
            check_nodejs
            install_backend_deps
            install_frontend_deps
            start_backend
            start_frontend
            
            echo ""
            echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
            echo -e "${GREEN}  ✅ AlphaTerminal 启动成功！                                  ${NC}"
            echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
            echo ""
            echo -e "${CYAN}  🌐 前端访问: http://localhost:$FRONTEND_PORT${NC}"
            echo -e "${CYAN}  🔌 API 地址: http://localhost:$BACKEND_PORT${NC}"
            echo -e "${CYAN}  📊 API 文档: http://localhost:$BACKEND_PORT/docs${NC}"
            echo ""
            echo -e "${YELLOW}  📋 常用命令:${NC}"
            echo -e "${YELLOW}     查看状态: ./start.sh status${NC}"
            echo -e "${YELLOW}     停止服务: ./start.sh stop${NC}"
            echo -e "${YELLOW}     仅后端:   ./start.sh backend${NC}"
            echo -e "${YELLOW}     仅前端:   ./start.sh frontend${NC}"
            echo ""
            echo -e "${BLUE}  📝 日志文件:${NC}"
            echo -e "${BLUE}     后端: logs/backend.log${NC}"
            echo -e "${BLUE}     前端: logs/frontend.log${NC}"
            echo ""
            ;;
    esac
}

# 执行主函数
main "$@"