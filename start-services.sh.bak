#!/bin/bash
# AlphaTerminal 前后端一键启动脚本
# 使用方法: ./start-services.sh [backend|frontend|all|stop|status]

set -e

WORKSPACE="/vol3/1000/docker/opencode/workspace/AlphaTerminal"
BACKEND_PORT=8002
FRONTEND_PORT=60100
BACKEND_LOG="/tmp/backend.log"
FRONTEND_LOG="/tmp/frontend.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 获取脚本所在目录
cd "$(dirname "$0")"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查端口是否被占用
check_port() {
    local port=$1
    if ss -tlnp | grep -q ":$port "; then
        return 0
    else
        return 1
    fi
}

# 杀掉占用端口的进程
kill_port() {
    local port=$1
    local name=$2
    if check_port $port; then
        log_warn "端口 $port 被占用，正在释放..."
        # 尝试通过ss找到PID并杀掉
        local pids=$(ss -tlnp | grep ":$port " | grep -oP 'pid=\K[0-9]+' | sort -u)
        if [ -n "$pids" ]; then
            echo "$pids" | xargs -r kill -9 2>/dev/null || true
            sleep 1
        fi
        # 如果还在，尝试fuser
        if check_port $port; then
            fuser -k ${port}/tcp 2>/dev/null || true
            sleep 1
        fi
    fi
}

# 杀掉指定名称的进程
kill_process() {
    local pattern=$1
    local name=$2
    local pids=$(ps aux | grep "$pattern" | grep -v grep | awk '{print $2}')
    if [ -n "$pids" ]; then
        log_warn "停止旧的 $name 进程..."
        echo "$pids" | xargs -r kill -9 2>/dev/null || true
        sleep 1
    fi
}

# 检查进程是否存活
check_process() {
    local pattern=$1
    if ps aux | grep "$pattern" | grep -v grep > /dev/null; then
        return 0
    else
        return 1
    fi
}

# 健康检查
health_check() {
    local url=$1
    local name=$2
    local max_wait=${3:-30}
    local waited=0
    
    log_info "等待 $name 启动..."
    while [ $waited -lt $max_wait ]; do
        if curl -s --max-time 2 "$url" > /dev/null 2>&1; then
            log_info "$name 启动成功 ✅"
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
        if [ $((waited % 5)) -eq 0 ]; then
            echo "  已等待 ${waited}s..."
        fi
    done
    
    log_error "$name 启动超时（等待了 ${max_wait}s）❌"
    return 1
}

# 启动后端
start_backend() {
    log_info "启动后端服务..."
    
    # 先停止旧进程
    kill_process "uvicorn.*app.main:app.*$BACKEND_PORT" "后端"
    kill_port $BACKEND_PORT "后端"
    
    # 确保日志目录存在
    touch "$BACKEND_LOG"
    
    # 启动后端（使用setsid创建新会话，完全脱离shell）
    cd "$WORKSPACE/backend"
    setsid bash -c "
        python3 -m uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT > $BACKEND_LOG 2>&1
    " &
    
    local backend_pid=$!
    disown $backend_pid 2>/dev/null || true
    
    log_info "后端进程 PID: $backend_pid"
    
    # 等待后端启动
    if ! health_check "http://localhost:$BACKEND_PORT/api/v1/macro/overview" "后端" 30; then
        log_error "后端启动失败，查看日志: tail -50 $BACKEND_LOG"
        return 1
    fi
    
    return 0
}

# 启动前端
start_frontend() {
    log_info "启动前端服务..."
    
    # 先停止旧进程
    kill_process "http.server.*$FRONTEND_PORT\|vite.*$FRONTEND_PORT" "前端"
    kill_port $FRONTEND_PORT "前端"
    
    # 确保日志目录存在
    touch "$FRONTEND_LOG"
    
    # 启动前端（使用 vite preview 模式，支持 proxy 代理配置）
    cd "$WORKSPACE/frontend"
    setsid bash -c "
        npx vite preview --host 0.0.0.0 --port $FRONTEND_PORT > $FRONTEND_LOG 2>&1
    " &
    
    local frontend_pid=$!
    disown $frontend_pid 2>/dev/null || true
    
    log_info "前端进程 PID: $frontend_pid"
    
    # 等待前端启动
    if ! health_check "http://localhost:$FRONTEND_PORT" "前端" 15; then
        log_error "前端启动失败，查看日志: tail -50 $FRONTEND_LOG"
        return 1
    fi
    
    return 0
}

# 停止所有服务
stop_all() {
    log_info "停止所有服务..."
    kill_process "uvicorn.*app.main:app.*$BACKEND_PORT" "后端"
    kill_process "http.server.*$FRONTEND_PORT" "前端"
    kill_port $BACKEND_PORT "后端"
    kill_port $FRONTEND_PORT "前端"
    log_info "所有服务已停止 ✅"
}

# 查看状态
show_status() {
    echo ""
    echo "========================================"
    echo "  AlphaTerminal 服务状态"
    echo "========================================"
    echo ""
    
    # 后端状态
    echo -n "后端服务 (端口 $BACKEND_PORT): "
    if check_port $BACKEND_PORT; then
        echo -e "${GREEN}运行中 ✅${NC}"
        local backend_pid=$(ss -tlnp | grep ":$BACKEND_PORT " | grep -oP 'pid=\K[0-9]+' | head -1)
        echo "  进程 PID: $backend_pid"
        echo "  健康检查: $(curl -s --max-time 3 "http://localhost:$BACKEND_PORT/api/v1/macro/overview" | python3 -c "import json,sys; d=json.load(sys.stdin); print('通过' if d.get('code')==0 else '失败')" 2>/dev/null || echo '失败')"
    else
        echo -e "${RED}未运行 ❌${NC}"
    fi
    
    echo ""
    
    # 前端状态
    echo -n "前端服务 (端口 $FRONTEND_PORT): "
    if check_port $FRONTEND_PORT; then
        echo -e "${GREEN}运行中 ✅${NC}"
        local frontend_pid=$(ss -tlnp | grep ":$FRONTEND_PORT " | grep -oP 'pid=\K[0-9]+' | head -1)
        echo "  进程 PID: $frontend_pid"
    else
        echo -e "${RED}未运行 ❌${NC}"
    fi
    
    echo ""
    echo "日志文件:"
    echo "  后端: $BACKEND_LOG"
    echo "  前端: $FRONTEND_LOG"
    echo ""
    echo "访问地址:"
    echo "  前端: http://localhost:$FRONTEND_PORT"
    echo "  后端: http://localhost:$BACKEND_PORT"
    echo "========================================"
}

# 主逻辑
case "${1:-all}" in
    backend)
        start_backend
        ;;
    frontend)
        start_frontend
        ;;
    all)
        log_info "启动 AlphaTerminal 所有服务..."
        stop_all
        sleep 1
        start_backend
        start_frontend
        show_status
        ;;
    stop)
        stop_all
        ;;
    status)
        show_status
        ;;
    restart)
        log_info "重启 AlphaTerminal 所有服务..."
        stop_all
        sleep 2
        start_backend
        start_frontend
        show_status
        ;;
    *)
        echo "用法: $0 [backend|frontend|all|stop|status|restart]"
        echo ""
        echo "命令:"
        echo "  backend   - 只启动后端服务"
        echo "  frontend  - 只启动前端服务"
        echo "  all       - 启动所有服务（默认）"
        echo "  stop      - 停止所有服务"
        echo "  status    - 查看服务状态"
        echo "  restart   - 重启所有服务"
        exit 1
        ;;
esac
