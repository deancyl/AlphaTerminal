#!/bin/bash
# auto_diagnosis.sh - AlphaTerminal 自动化诊断脚本
# 用法: ./auto_diagnosis.sh [循环次数]
# 示例: ./auto_diagnosis.sh 3

set -e

# ==================== 配置 ====================
CYCLE_COUNT=${1:-3}
FRONTEND="http://192.168.1.50:60100"
BACKEND="http://192.168.1.50:8002"
REPORT_DIR="/tmp/alphaterminal_diagnosis"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="${REPORT_DIR}/report_${TIMESTAMP}.md"

# 创建报告目录
mkdir -p "$REPORT_DIR"

# ==================== 颜色定义 ====================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ==================== 结果变量 ====================
PHASE1_STATUS="❌"
PHASE1_5_STATUS="❌"
PHASE2_STATUS="❌"
PHASE3_STATUS="❌"
PHASE3_5_STATUS="❌"
PHASE4_STATUS="❌"
PHASE5_STATUS="❌"
PHASE6_STATUS="❌"
PHASE7_STATUS="❌"
PHASE1_DETAIL=""
PHASE1_5_DETAIL=""
PHASE2_DETAIL=""
PHASE3_DETAIL=""
PHASE3_5_DETAIL=""
PHASE4_DETAIL=""
PHASE5_DETAIL=""
PHASE6_DETAIL=""
PHASE7_DETAIL=""

# ==================== 函数定义 ====================

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_phase() { echo -e "${BLUE}========== $1 ==========${NC}"; }

# Phase 1: 服务健康检查
phase1_health() {
    log_phase "Phase 1: 服务健康检查"
    
    local backend_ok=false
    local frontend_ok=false
    local ws_ok=false
    
    # 后端健康
    if curl -sf --max-time 5 "${BACKEND}/health" > /dev/null 2>&1; then
        backend_ok=true
        log_info "后端健康检查通过"
    else
        log_error "后端健康检查失败"
        log_info "尝试重启服务..."
        ./start-services.sh restart 2>/dev/null || true
        sleep 30
        if curl -sf --max-time 5 "${BACKEND}/health" > /dev/null 2>&1; then
            backend_ok=true
            log_info "重启后后端正常"
        fi
    fi
    
    # 前端代理
    if curl -sf --max-time 10 "${FRONTEND}/" | grep -q "AlphaTerminal" 2>/dev/null; then
        frontend_ok=true
        log_info "前端代理正常"
    else
        log_error "前端代理失败"
    fi
    
    # API 代理
    if curl -sf --max-time 10 "${FRONTEND}/api/v1/macro/overview" | jq -e '.code == 0' > /dev/null 2>&1; then
        log_info "API 代理正常"
    else
        log_warn "API 代理可能有问题"
    fi
    
    if $backend_ok && $frontend_ok; then
        PHASE1_STATUS="✅"
        PHASE1_DETAIL="后端: 正常, 前端: 正常"
    else
        PHASE1_STATUS="❌"
        PHASE1_DETAIL="后端: $backend_ok, 前端: $frontend_ok"
    fi
}

# Phase 1.5: 基础设施健康检查 (WebSocket, Circuit Breaker, Cache)
phase1_5_infrastructure() {
    log_phase "Phase 1.5: 基础设施健康检查"
    
    local ws_ok=true
    local cb_ok=true
    local cache_ok=true
    local session_ok=true
    local token_ok=true
    
    # 1. WebSocket 状态机检查
    local ws_metrics=$(curl -sf --max-time 5 "${FRONTEND}/api/v1/admin/ws/metrics" 2>/dev/null)
    if [ -n "$ws_metrics" ]; then
        local ws_state=$(echo "$ws_metrics" | jq -r '.data.state // "unknown"' 2>/dev/null || echo "unknown")
        local ws_connections=$(echo "$ws_metrics" | jq -r '.data.active_connections // 0' 2>/dev/null || echo "0")
        local ws_pending=$(echo "$ws_metrics" | jq -r '.data.pending_subscriptions // 0' 2>/dev/null || echo "0")
        
        # 检查状态死锁 (CONNECTING 状态超过 10s)
        if [[ "$ws_state" == "connecting" ]]; then
            log_warn "WebSocket 状态异常: ${ws_state}"
            ws_ok=false
        fi
        
        # 检查订阅队列溢出
        if (( ws_pending > 500 )); then
            log_error "订阅队列溢出: ${ws_pending}/500"
            ws_ok=false
        fi
        
        log_info "WebSocket: ${ws_state}, 连接数: ${ws_connections}, 待处理: ${ws_pending}"
    else
        log_warn "WebSocket 指标端点不可用"
    fi
    
    # 2. Circuit Breaker 状态检查
    local cb_status=$(curl -sf --max-time 5 "${FRONTEND}/api/v1/admin/circuit_breaker/status" 2>/dev/null)
    if [ -n "$cb_status" ]; then
        local open_count=$(echo "$cb_status" | jq '[.data.sources[] | select(.state == "OPEN")] | length' 2>/dev/null || echo "0")
        if (( open_count > 0 )); then
            log_warn "${open_count} 个数据源熔断器处于 OPEN 状态"
            cb_ok=false
        fi
        log_info "熔断器检查完成, OPEN 数量: ${open_count}"
    else
        log_info "熔断器端点不可用 (可能未实现)"
    fi
    
    # 3. 缓存命中率检查
    local cache_stats=$(curl -sf --max-time 5 "${FRONTEND}/api/v1/admin/cache/stats" 2>/dev/null)
    if [ -n "$cache_stats" ]; then
        local hit_rate=$(echo "$cache_stats" | jq -r '.data.hit_rate // 0' 2>/dev/null || echo "0")
        if (( $(echo "$hit_rate < 0.5" | bc -l 2>/dev/null || echo "0") )); then
            log_warn "缓存命中率过低: ${hit_rate}"
            cache_ok=false
        fi
        log_info "缓存命中率: ${hit_rate}"
    fi
    
    # 4. 会话管理检查
    local session_stats=$(curl -sf --max-time 5 "${FRONTEND}/api/v1/admin/session/stats" 2>/dev/null)
    if [ -n "$session_stats" ]; then
        local expired_count=$(echo "$session_stats" | jq -r '.data.expired_count // 0' 2>/dev/null || echo "0")
        if (( expired_count > 100 )); then
            log_warn "大量过期会话未清理: ${expired_count}"
            session_ok=false
        fi
        log_info "过期会话数: ${expired_count}"
    fi
    
    # 5. Token 聚合线程检查
    local token_stats=$(curl -sf --max-time 5 "${FRONTEND}/api/v1/admin/tokens/stats" 2>/dev/null)
    if [ -n "$token_stats" ]; then
        local aggregation_running=$(echo "$token_stats" | jq -r '.data.aggregation_thread_running // false' 2>/dev/null || echo "false")
        if [[ "$aggregation_running" != "true" ]]; then
            log_warn "Token 聚合线程可能已停止"
            token_ok=false
        fi
        log_info "Token 聚合线程: ${aggregation_running}"
    fi
    
    # 汇总
    if $ws_ok && $cb_ok && $cache_ok && $session_ok && $token_ok; then
        PHASE1_5_STATUS="✅"
        PHASE1_5_DETAIL="基础设施正常"
        log_info "基础设施健康检查通过"
    else
        PHASE1_5_STATUS="⚠️"
        PHASE1_5_DETAIL="WS:${ws_ok}, CB:${cb_ok}, Cache:${cache_ok}, Session:${session_ok}, Token:${token_ok}"
        log_warn "基础设施存在问题"
    fi
}

# Phase 2: API 端点验证
phase2_api() {
    log_phase "Phase 2: API 端点验证"
    
    # P0 端点 - 核心功能
    local p0_endpoints=(
        "/api/v1/market/overview"
        "/api/v1/macro/overview"
        "/api/v1/news/flash"
        "/api/v1/futures/main_indexes"
        "/api/v1/forex/spot"
        "/api/v1/f9/health"
    )
    
    # P1 端点 - 数据获取
    local p1_endpoints=(
        "/api/v1/macro/gdp?limit=5"
        "/api/v1/macro/cpi?limit=5"
        "/api/v1/f9/600519/financial"
        "/api/v1/f9/600519/institution"
        "/api/v1/f9/600519/margin"
        "/api/v1/f9/600519/forecast"
        "/api/v1/f9/600519/shareholder"
        "/api/v1/f9/600519/announcements"
        "/api/v1/f9/600519/peers"
        "/api/v1/futures/index_history?symbol=IF"
        "/api/v1/forex/convert?from=USD&to=CNY&amount=100"
    )
    
    # P2 端点 - 管理功能
    local p2_endpoints=(
        "/api/v1/admin/system/metrics"
        "/api/v1/admin/ws/metrics"
        "/api/v1/admin/tokens/stats"
        "/api/v1/admin/cache/stats"
        "/api/v1/admin/session/stats"
        "/api/v1/admin/circuit_breaker/status"
        "/api/agent/v1/health"
    )
    
    # P3 端点 - Portfolio/Backtest
    local p3_endpoints=(
        "/api/v1/portfolio/"
        "/api/v1/portfolio/positions"
        "/api/v1/backtest/strategies"
        "/api/v1/strategy/validate"
    )
    
    local p0_passed=0 p0_failed=0
    local p1_passed=0 p1_failed=0
    local p2_passed=0 p2_failed=0
    local p3_passed=0 p3_failed=0
    
    echo "P0 核心端点检查:"
    for endpoint in "${p0_endpoints[@]}"; do
        if curl -sf --max-time 30 "${FRONTEND}${endpoint}" | jq -e '.code == 0' > /dev/null 2>&1; then
            ((p0_passed++))
            log_info "  ✅ ${endpoint}"
        else
            ((p0_failed++))
            log_error "  ❌ ${endpoint}"
        fi
    done
    
    echo "P1 数据端点检查:"
    for endpoint in "${p1_endpoints[@]}"; do
        if curl -sf --max-time 30 "${FRONTEND}${endpoint}" | jq -e '.code == 0' > /dev/null 2>&1; then
            ((p1_passed++))
            log_info "  ✅ ${endpoint}"
        else
            ((p1_failed++))
            log_warn "  ⚠️ ${endpoint}"
        fi
    done
    
    echo "P2 管理端点检查:"
    for endpoint in "${p2_endpoints[@]}"; do
        local response=$(curl -sf --max-time 10 "${FRONTEND}${endpoint}" 2>/dev/null)
        if [ -n "$response" ] && echo "$response" | jq -e '.code == 0' > /dev/null 2>&1; then
            ((p2_passed++))
            log_info "  ✅ ${endpoint}"
        else
            ((p2_failed++))
            log_warn "  ⚠️ ${endpoint}"
        fi
    done
    
    echo "P3 Portfolio端点检查:"
    for endpoint in "${p3_endpoints[@]}"; do
        local response=$(curl -sf --max-time 10 "${FRONTEND}${endpoint}" 2>/dev/null)
        if [ -n "$response" ]; then
            ((p3_passed++))
            log_info "  ✅ ${endpoint}"
        else
            ((p3_failed++))
            log_warn "  ⚠️ ${endpoint}"
        fi
    done
    
    local p0_total=${#p0_endpoints[@]}
    local p1_total=${#p1_endpoints[@]}
    local p2_total=${#p2_endpoints[@]}
    local p3_total=${#p3_endpoints[@]}
    local total_passed=$((p0_passed + p1_passed + p2_passed + p3_passed))
    local total_endpoints=$((p0_total + p1_total + p2_total + p3_total))
    
    if [ $p0_passed -eq $p0_total ] && [ $p1_passed -ge $((p1_total * 80 / 100)) ]; then
        PHASE2_STATUS="✅"
        PHASE2_DETAIL="P0: ${p0_passed}/${p0_total}, P1: ${p1_passed}/${p1_total}, P2: ${p2_passed}/${p2_total}, P3: ${p3_passed}/${p3_total}"
    else
        PHASE2_STATUS="⚠️"
        PHASE2_DETAIL="P0: ${p0_passed}/${p0_total}, P1: ${p1_passed}/${p1_total}, P2: ${p2_passed}/${p2_total}, P3: ${p3_passed}/${p3_total}"
    fi
    
    log_info "API 验证结果: ${total_passed}/${total_endpoints} 端点通过"
}

# Phase 3: 前端 UI 测试
phase3_ui() {
    log_phase "Phase 3: 前端 UI 测试"
    
    # 简化版：检查前端页面是否可访问
    local html_content=$(curl -sf --max-time 10 "${FRONTEND}/" 2>/dev/null)
    
    if echo "$html_content" | grep -q "AlphaTerminal"; then
        PHASE3_STATUS="✅"
        PHASE3_DETAIL="前端页面正常渲染"
        log_info "前端页面正常"
    else
        PHASE3_STATUS="❌"
        PHASE3_DETAIL="前端页面异常"
        log_error "前端页面异常"
    fi
    
    # 检查静态资源
    local js_file=$(echo "$html_content" | grep -o 'src="/assets/[^"]*\.js"' | head -1 | sed 's/src="//;s/"//')
    if [ -n "$js_file" ]; then
        if curl -sf --max-time 5 "${FRONTEND}${js_file}" > /dev/null 2>&1; then
            log_info "静态资源加载正常"
        else
            log_warn "静态资源加载失败"
        fi
    fi
}

# Phase 3.5: 前端内存泄漏检测
phase3_5_memory() {
    log_phase "Phase 3.5: 前端内存泄漏检测"
    
    local memory_ok=true
    local leak_detected=false
    
    # 检查是否存在 Playwright
    if ! command -v npx &> /dev/null || [ ! -f "frontend/package.json" ]; then
        PHASE3_5_STATUS="⚠️"
        PHASE3_5_DETAIL="Playwright 未安装或前端不存在"
        log_warn "跳过内存泄漏检测 (需要 Playwright)"
        return
    fi
    
    # 运行内存泄漏测试
    if [ -f "frontend/tests/e2e/memory-leak.spec.js" ]; then
        cd frontend 2>/dev/null || return
        local result=$(npx playwright test tests/e2e/memory-leak.spec.js --reporter=list 2>&1 | tail -20)
        cd ..
        
        if echo "$result" | grep -q "passed"; then
            PHASE3_5_STATUS="✅"
            PHASE3_5_DETAIL="内存泄漏测试通过"
            log_info "内存泄漏检测通过"
        else
            PHASE3_5_STATUS="⚠️"
            PHASE3_5_DETAIL="内存泄漏测试失败或未运行"
            log_warn "内存泄漏检测异常"
        fi
    else
        PHASE3_5_STATUS="⚠️"
        PHASE3_5_DETAIL="内存泄漏测试文件不存在"
        log_warn "内存泄漏测试文件不存在: frontend/tests/e2e/memory-leak.spec.js"
    fi
}

# Phase 4: 错误模式扫描
phase4_errors() {
    log_phase "Phase 4: 错误模式扫描"
    
    local empty_catch=0
    local unlogged=0
    local hardcoded=0
    local use_agent=false
    
    # 检查是否可以使用 Explore Agent
    if command -v opencode &> /dev/null; then
        use_agent=true
        log_info "检测到 OpenCode CLI，使用 Explore Agent 增强扫描..."
    fi
    
    if $use_agent; then
        # 使用 Explore Agent 进行语义分析
        local agent_output="/tmp/alphaterminal_diagnosis/phase4_agent_scan.json"
        opencode task --agent explore --output "$agent_output" --prompt "
扫描以下目录的错误处理模式：
- backend/app/routers/
- backend/app/services/
- frontend/src/components/

检测以下问题：
1. 空 catch 块 (except: pass)
2. 未记录的异常 (except Exception without logger)
3. 硬编码错误消息 (HTTPException with literal string)
4. 缺少超时保护 (async function without asyncio.wait_for)

输出格式：JSON，包含 file, line, issue_type, suggestion
" 2>/dev/null || true
        
        if [ -f "$agent_output" ]; then
            empty_catch=$(jq '[.[] | select(.issue_type == "empty_catch")] | length' "$agent_output" 2>/dev/null || echo 0)
            unlogged=$(jq '[.[] | select(.issue_type == "unlogged_exception")] | length' "$agent_output" 2>/dev/null || echo 0)
            hardcoded=$(jq '[.[] | select(.issue_type == "hardcoded_error")] | length' "$agent_output" 2>/dev/null || echo 0)
            log_info "Explore Agent 扫描完成"
        else
            log_warn "Explore Agent 输出未找到，回退到 grep 扫描"
            use_agent=false
        fi
    fi
    
    if ! $use_agent; then
        # 传统 grep 扫描
        empty_catch=$(grep -rn "except.*:" backend/app/ 2>/dev/null | grep -A1 "pass$" | grep -B1 "pass$" | wc -l || echo 0)
        unlogged=$(grep -rn "except Exception" backend/app/routers/ 2>/dev/null | grep -v "log_error\|logger.error" | wc -l || echo 0)
        hardcoded=$(grep -rn "raise HTTPException" backend/app/routers/ 2>/dev/null | grep -v "from app.utils.errors" | wc -l || echo 0)
    fi
    
    local total=$((empty_catch + unlogged + hardcoded))
    
    if [ $total -eq 0 ]; then
        PHASE4_STATUS="✅"
        PHASE4_DETAIL="无错误模式"
        log_info "无错误模式"
    else
        PHASE4_STATUS="⚠️"
        PHASE4_DETAIL="空catch: ${empty_catch}, 未记录: ${unlogged}, 硬编码: ${hardcoded}"
        log_warn "发现 ${total} 个潜在问题"
    fi
}

# Phase 5: 安全漏洞扫描
phase5_security() {
    log_phase "Phase 5: 安全漏洞扫描"
    
    local security_passed=0
    
    # 运行安全测试
    if [ -d "backend/tests/unit/test_services" ]; then
        cd backend 2>/dev/null || return
        security_passed=$(pytest tests/unit/test_services/test_script_strategy_security.py -q --tb=no 2>/dev/null | grep -c "PASSED" || echo "0")
        cd ..
    fi
    
    if [ "$security_passed" -ge 10 ]; then
        PHASE5_STATUS="✅"
        PHASE5_DETAIL="安全测试: ${security_passed}/10 通过"
        log_info "安全测试通过: ${security_passed}/10"
    elif [ "$security_passed" -gt 0 ]; then
        PHASE5_STATUS="⚠️"
        PHASE5_DETAIL="安全测试: ${security_passed}/10 部分通过"
        log_warn "安全测试部分通过: ${security_passed}/10"
    else
        PHASE5_STATUS="⚠️"
        PHASE5_DETAIL="安全测试未运行或失败"
        log_warn "安全测试未运行"
    fi
}

# Phase 6: 性能基准测试
phase6_performance() {
    log_phase "Phase 6: 性能基准测试"
    
    # API 响应时间
    local time_total=$(curl -o /dev/null -s -w "%{time_total}" "${FRONTEND}/api/v1/market/overview" 2>/dev/null || echo "0")
    
    # 系统资源
    local memory_percent="N/A"
    local cpu_percent="N/A"
    
    local metrics=$(curl -sf --max-time 5 "${FRONTEND}/api/v1/admin/system/metrics" 2>/dev/null)
    if [ -n "$metrics" ]; then
        memory_percent=$(echo "$metrics" | jq -r '.data.memory.percent // "N/A"' 2>/dev/null || echo "N/A")
        cpu_percent=$(echo "$metrics" | jq -r '.data.cpu_percent // "N/A"' 2>/dev/null || echo "N/A")
    fi
    
    # 判断性能是否达标
    local time_ok=false
    if (( $(echo "$time_total < 1.0" | bc -l 2>/dev/null || echo "0") )); then
        time_ok=true
    fi
    
    if $time_ok; then
        PHASE6_STATUS="✅"
        PHASE6_DETAIL="API响应: ${time_total}s, 内存: ${memory_percent}%, CPU: ${cpu_percent}%"
        log_info "API 响应时间: ${time_total}s"
    else
        PHASE6_STATUS="⚠️"
        PHASE6_DETAIL="API响应: ${time_total}s (较慢)"
        log_warn "API 响应较慢: ${time_total}s"
    fi
    
    log_info "内存使用: ${memory_percent}%, CPU: ${cpu_percent}%"
}

# Phase 7: 回归测试
phase7_regression() {
    log_phase "Phase 7: 回归测试"
    
    local backend_tests="N/A"
    local frontend_tests="N/A"
    
    # 后端测试
    if [ -d "backend/tests" ]; then
        cd backend 2>/dev/null || return
        backend_tests=$(pytest tests/unit/ -q --tb=no 2>/dev/null | tail -1 || echo "未运行")
        cd ..
    fi
    
    # 前端测试
    if [ -f "frontend/package.json" ]; then
        cd frontend 2>/dev/null || return
        frontend_tests=$(npm run test -- --run 2>/dev/null | tail -1 || echo "未运行")
        cd ..
    fi
    
    if echo "$backend_tests" | grep -q "passed"; then
        PHASE7_STATUS="✅"
        PHASE7_DETAIL="后端: ${backend_tests}"
        log_info "后端测试: ${backend_tests}"
    else
        PHASE7_STATUS="⚠️"
        PHASE7_DETAIL="后端: ${backend_tests}"
        log_warn "后端测试: ${backend_tests}"
    fi
}

# 生成报告
generate_report() {
    cat > "$REPORT_FILE" << EOF
# AlphaTerminal 诊断报告

**执行时间**: $(date '+%Y-%m-%d %H:%M:%S')
**循环次数**: ${cycle}/${CYCLE_COUNT}
**服务地址**: ${FRONTEND}

## 摘要

| 阶段 | 状态 | 详情 |
|------|------|------|
| 服务健康 | ${PHASE1_STATUS} | ${PHASE1_DETAIL} |
| 基础设施 | ${PHASE1_5_STATUS} | ${PHASE1_5_DETAIL} |
| API 验证 | ${PHASE2_STATUS} | ${PHASE2_DETAIL} |
| UI 测试 | ${PHASE3_STATUS} | ${PHASE3_DETAIL} |
| 内存泄漏 | ${PHASE3_5_STATUS} | ${PHASE3_5_DETAIL} |
| 错误扫描 | ${PHASE4_STATUS} | ${PHASE4_DETAIL} |
| 安全扫描 | ${PHASE5_STATUS} | ${PHASE5_DETAIL} |
| 性能测试 | ${PHASE6_STATUS} | ${PHASE6_DETAIL} |
| 回归测试 | ${PHASE7_STATUS} | ${PHASE7_DETAIL} |

## 结论

$(if [[ "$PHASE1_STATUS" == "✅" && "$PHASE2_STATUS" == "✅" ]]; then
    echo "✅ 系统运行正常，所有核心检查通过"
elif [[ "$PHASE1_STATUS" == "✅" ]]; then
    echo "⚠️ 系统基本正常，但存在部分问题"
else
    echo "❌ 系统存在问题，建议检查后端服务"
fi)

## 建议操作

$(if [[ "$PHASE1_STATUS" != "✅" ]]; then
    echo "- [ ] 执行 \`./start-services.sh restart\` 重启服务"
fi)
$(if [[ "$PHASE2_STATUS" != "✅" ]]; then
    echo "- [ ] 检查失败的 API 端点"
fi)
$(if [[ "$PHASE4_STATUS" == "⚠️" ]]; then
    echo "- [ ] 修复代码中的错误处理缺陷"
fi)

---
*报告生成时间: $(date '+%Y-%m-%d %H:%M:%S')*
EOF
    
    log_info "报告已保存: ${REPORT_FILE}"
}

# ==================== 主循环 ====================
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AlphaTerminal 自动化诊断工作流${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "循环次数: ${CYCLE_COUNT}"
echo "服务地址: ${FRONTEND}"
echo ""

for cycle in $(seq 1 $CYCLE_COUNT); do
    echo ""
    echo -e "${BLUE}========== 循环 ${cycle}/${CYCLE_COUNT} ==========${NC}"
    echo ""
    
    # 重置状态
    PHASE1_STATUS="❌"
    PHASE1_5_STATUS="❌"
    PHASE2_STATUS="❌"
    PHASE3_STATUS="❌"
    PHASE3_5_STATUS="❌"
    PHASE4_STATUS="❌"
    PHASE5_STATUS="❌"
    PHASE6_STATUS="❌"
    PHASE7_STATUS="❌"
    
    phase1_health
    phase1_5_infrastructure
    phase2_api
    phase3_ui
    phase3_5_memory
    phase4_errors
    phase5_security
    phase6_performance
    phase7_regression
    
    generate_report
    
    # 检查是否全部通过
    if [[ "$PHASE1_STATUS" == "✅" && "$PHASE2_STATUS" == "✅" && "$PHASE3_STATUS" == "✅" ]]; then
        echo ""
        log_info "✅ 所有核心检查通过，提前退出"
        break
    fi
    
    # 非最后一次循环，等待后重试
    if [ $cycle -lt $CYCLE_COUNT ]; then
        log_info "等待 60 秒后重试..."
        sleep 60
    fi
done

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}诊断完成${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "报告位置: ${REPORT_FILE}"
echo ""
