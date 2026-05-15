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
PHASE2_STATUS="❌"
PHASE3_STATUS="❌"
PHASE4_STATUS="❌"
PHASE5_STATUS="❌"
PHASE6_STATUS="❌"
PHASE7_STATUS="❌"
PHASE1_DETAIL=""
PHASE2_DETAIL=""
PHASE3_DETAIL=""
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

# Phase 2: API 端点验证
phase2_api() {
    log_phase "Phase 2: API 端点验证"
    
    # P0 端点
    local p0_endpoints=(
        "/api/v1/market/overview"
        "/api/v1/macro/overview"
        "/api/v1/news/flash"
        "/api/v1/futures/main_indexes"
        "/api/v1/forex/spot"
        "/api/v1/f9/health"
    )
    
    local p0_passed=0
    local p0_failed=()
    
    for endpoint in "${p0_endpoints[@]}"; do
        if curl -sf --max-time 30 "${FRONTEND}${endpoint}" | jq -e '.code == 0' > /dev/null 2>&1; then
            ((p0_passed++))
            log_info "✅ ${endpoint}"
        else
            p0_failed+=("$endpoint")
            log_error "❌ ${endpoint}"
        fi
    done
    
    local p0_total=${#p0_endpoints[@]}
    
    if [ $p0_passed -eq $p0_total ]; then
        PHASE2_STATUS="✅"
        PHASE2_DETAIL="P0: ${p0_passed}/${p0_total} 全部通过"
    else
        PHASE2_STATUS="⚠️"
        PHASE2_DETAIL="P0: ${p0_passed}/${p0_total} 失败: ${p0_failed[*]}"
    fi
    
    log_info "API 验证结果: ${p0_passed}/${p0_total}"
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

# Phase 4: 错误模式扫描
phase4_errors() {
    log_phase "Phase 4: 错误模式扫描"
    
    local empty_catch=0
    local unlogged=0
    local hardcoded=0
    
    # 检查空 catch 块
    empty_catch=$(grep -rn "except.*:" backend/app/ 2>/dev/null | grep -A1 "pass$" | grep -B1 "pass$" | wc -l || echo 0)
    
    # 检查未记录的异常
    unlogged=$(grep -rn "except Exception" backend/app/routers/ 2>/dev/null | grep -v "log_error\|logger.error" | wc -l || echo 0)
    
    # 检查硬编码错误
    hardcoded=$(grep -rn "raise HTTPException" backend/app/routers/ 2>/dev/null | grep -v "from app.utils.errors" | wc -l || echo 0)
    
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
| API 验证 | ${PHASE2_STATUS} | ${PHASE2_DETAIL} |
| UI 测试 | ${PHASE3_STATUS} | ${PHASE3_DETAIL} |
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
    PHASE2_STATUS="❌"
    PHASE3_STATUS="❌"
    PHASE4_STATUS="❌"
    PHASE5_STATUS="❌"
    PHASE6_STATUS="❌"
    PHASE7_STATUS="❌"
    
    phase1_health
    phase2_api
    phase3_ui
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
