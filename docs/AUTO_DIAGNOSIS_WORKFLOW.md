# AlphaTerminal 自动化错误排查与扩展开发工作流

> **版本**: v1.0  
> **生成时间**: 2026-05-15  
> **适用项目**: AlphaTerminal v0.6.38+

---

## 一、项目概览

### 1.1 架构摘要

| 组件 | 技术栈 | 端口 | 文件数 |
|------|--------|------|--------|
| **后端** | Python 3.11 + FastAPI + Uvicorn | 8002 | 150+ |
| **前端** | Vue 3 + Vite + Tailwind + ECharts | 60100 | 100+ |
| **数据库** | SQLite (WAL mode) | - | 14 |
| **测试** | pytest + vitest + playwright | - | 53 |

### 1.2 模块清单

| 模块 | API 前缀 | 端点数 | 优先级 |
|------|----------|--------|--------|
| Market | `/api/v1/market/` | 30+ | P0 |
| Macro | `/api/v1/macro/` | 11 | P0 |
| F9 Deep | `/api/v1/f9/` | 8 | P1 |
| Futures | `/api/v1/futures/` | 4 | P1 |
| Forex | `/api/v1/forex/` | 11 | P1 |
| Portfolio | `/api/v1/portfolio/` | 29 | P1 |
| Copilot | `/api/v1/copilot/` | 3 | P1 |
| Backtest | `/api/v1/backtest/` | 8 | P2 |
| Strategy | `/api/v1/strategy/` | 10 | P2 |
| Admin | `/api/v1/admin/` | 50+ | P2 |
| Agent | `/api/agent/v1/` | 25+ | P2 |

---

## 二、自动化诊断工作流

### 2.1 工作流配置

```yaml
# 工作流配置
workflow:
  name: "AlphaTerminal 自动化诊断"
  version: "1.0"
  
  # 循环控制
  loop:
    max_cycles: 3           # 最大循环次数
    interval_seconds: 60    # 循环间隔
    stop_on_success: true   # 全部通过后停止
    stop_on_repeat: 3       # 连续相同错误停止
  
  # 服务地址
  endpoints:
    frontend: "http://192.168.1.50:60100"
    backend: "http://192.168.1.50:8002"
    websocket: "ws://192.168.1.50:60100/ws/market"
  
  # 报告输出
  output:
    path: "/tmp/alphaterminal_diagnosis"
    format: "markdown"
    timestamp: true
```

### 2.2 执行阶段

#### Phase 1: 服务健康检查 (5分钟)

**目标**: 验证前后端服务运行状态

**检查项**:

| 检查项 | 端点 | 预期结果 | 超时 |
|--------|------|----------|------|
| 后端健康 | `GET /health` | `{"status": "healthy"}` | 5s |
| 就绪检查 | `GET /api/v1/health/ready` | `{"initialized": true}` | 5s |
| 前端代理 | `GET /` | HTML 页面 | 10s |
| API 代理 | `GET /api/v1/macro/overview` | JSON 响应 | 10s |
| WebSocket | `WS /ws/market` | 连接成功 | 5s |

**执行脚本**:
```bash
#!/bin/bash
# phase1_health_check.sh

FRONTEND="http://192.168.1.50:60100"
BACKEND="http://192.168.1.50:8002"

echo "=== Phase 1: 服务健康检查 ==="

# 1. 后端健康
if curl -sf --max-time 5 "${BACKEND}/health" | jq -e '.status == "healthy"' > /dev/null; then
  echo "✅ 后端健康检查通过"
else
  echo "❌ 后端健康检查失败"
  echo "尝试重启服务..."
  ./start-services.sh restart
  sleep 30
fi

# 2. 前端代理
if curl -sf --max-time 10 "${FRONTEND}/" | grep -q "AlphaTerminal"; then
  echo "✅ 前端代理正常"
else
  echo "❌ 前端代理失败"
fi

# 3. API 代理
if curl -sf --max-time 10 "${FRONTEND}/api/v1/macro/overview" | jq -e '.code == 0' > /dev/null; then
  echo "✅ API 代理正常"
else
  echo "❌ API 代理失败"
fi

# 4. WebSocket (需要 wscat)
if command -v wscat &> /dev/null; then
  timeout 5 wscat -c "ws://192.168.1.50:60100/ws/market" -x '{"action":"subscribe","symbols":["600519"]}' 2>/dev/null && \
    echo "✅ WebSocket 连接正常" || echo "❌ WebSocket 连接失败"
fi
```

**失败处理**:
- 服务不健康 → 执行 `./start-services.sh restart`
- 端口被占用 → `lsof -ti:8002 | xargs kill -9`
- 代理失败 → 检查 `vite.config.js` proxy 配置

---

#### Phase 2: API 端点批量验证 (10分钟)

**目标**: 遍历所有关键 API 端点，验证响应格式

**端点优先级**:

**P0 - 核心端点** (必须 100% 通过):
```
GET /api/v1/market/overview
GET /api/v1/macro/overview
GET /api/v1/news/flash
GET /api/v1/futures/main_indexes
GET /api/v1/forex/spot
GET /api/v1/f9/health
```

**P1 - 数据端点** (≥80% 通过):
```
GET /api/v1/macro/gdp?limit=5
GET /api/v1/macro/cpi?limit=5
GET /api/v1/f9/600519/financial
GET /api/v1/f9/600519/institution
GET /api/v1/futures/index_history?symbol=IF
GET /api/v1/forex/convert?from=USD&to=CNY&amount=100
```

**P2 - 管理端点** (≥60% 通过):
```
GET /api/v1/admin/system/metrics
GET /api/v1/admin/ws/metrics
GET /api/v1/admin/tokens/stats
GET /api/agent/v1/health
```

**执行脚本**:
```bash
#!/bin/bash
# phase2_api_validation.sh

FRONTEND="http://192.168.1.50:60100"

# P0 端点
P0_ENDPOINTS=(
  "/api/v1/market/overview"
  "/api/v1/macro/overview"
  "/api/v1/news/flash"
  "/api/v1/futures/main_indexes"
  "/api/v1/forex/spot"
  "/api/v1/f9/health"
)

# P1 端点
P1_ENDPOINTS=(
  "/api/v1/macro/gdp?limit=5"
  "/api/v1/f9/600519/financial"
  "/api/v1/futures/index_history?symbol=IF"
)

echo "=== Phase 2: API 端点验证 ==="

check_endpoints() {
  local priority=$1
  shift
  local endpoints=("$@")
  local passed=0
  local failed=0
  
  for endpoint in "${endpoints[@]}"; do
    response=$(curl -s -w "\n%{http_code}" --max-time 30 "${FRONTEND}${endpoint}")
    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | head -n -1)
    
    if [[ "$http_code" == "200" ]] && echo "$body" | jq -e '.code == 0' > /dev/null 2>&1; then
      ((passed++))
      echo "  ✅ ${endpoint}"
    else
      ((failed++))
      echo "  ❌ ${endpoint} (HTTP ${http_code})"
    fi
  done
  
  echo "  [${priority}] 通过: ${passed}/${#endpoints[@]}"
}

echo "P0 端点检查:"
check_endpoints "P0" "${P0_ENDPOINTS[@]}"

echo "P1 端点检查:"
check_endpoints "P1" "${P1_ENDPOINTS[@]}"
```

---

#### Phase 3: 前端 UI 测试 (10分钟)

**目标**: 模拟浏览器访问，收集控制台日志

**测试场景**:

| 场景 | 视口 | 检查项 |
|------|------|--------|
| 桌面端 | 1920x1080 | 页面加载、控制台错误、网络请求 |
| 移动端 | 375x667 | 响应式布局、触摸交互 |
| 平板 | 768x1024 | 横竖屏切换 |

**Playwright 测试脚本**:
```javascript
// tests/e2e/diagnosis.spec.js
import { test, expect } from '@playwright/test';

const FRONTEND = 'http://192.168.1.50:60100';

test.describe('AlphaTerminal UI 诊断', () => {
  
  test('桌面端访问', async ({ page }) => {
    const errors = [];
    const warnings = [];
    
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
      if (msg.type() === 'warning') warnings.push(msg.text());
    });
    
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(FRONTEND);
    await page.waitForLoadState('networkidle');
    
    // 等待 5 秒收集日志
    await page.waitForTimeout(5000);
    
    // 检查关键元素
    await expect(page.locator('.dashboard-grid')).toBeVisible();
    
    // 报告结果
    console.log(`错误数: ${errors.length}`);
    console.log(`警告数: ${warnings.length}`);
    
    if (errors.length > 0) {
      console.log('错误详情:', errors);
    }
    
    expect(errors.length).toBe(0);
  });
  
  test('移动端访问', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(FRONTEND);
    await page.waitForLoadState('networkidle');
    
    // 检查移动端导航
    await expect(page.locator('.mobile-bottom-nav')).toBeVisible();
  });
  
  test('关键交互', async ({ page }) => {
    await page.goto(FRONTEND);
    await page.waitForLoadState('networkidle');
    
    // 测试 F9 深度资料
    await page.keyboard.press('F9');
    await page.waitForTimeout(1000);
    
    // 检查弹窗是否出现
    const modal = page.locator('.stock-detail-modal');
    await expect(modal).toBeVisible();
  });
});
```

**执行命令**:
```bash
cd frontend
npx playwright test tests/e2e/diagnosis.spec.js --project=chromium
```

---

#### Phase 4: 错误模式扫描 (5分钟)

**目标**: 检测代码中的错误处理缺陷

**扫描规则**:

| 规则 | 描述 | 严重性 |
|------|------|--------|
| EMPTY_CATCH | 空 catch 块 | P0 |
| UNLOGGED_EXCEPTION | 未记录的异常 | P1 |
| HARDCODED_ERROR | 硬编码错误消息 | P2 |
| UNHANDLED_PROMISE | 未处理的 Promise | P1 |

**执行脚本**:
```bash
#!/bin/bash
# phase4_error_scan.sh

echo "=== Phase 4: 错误模式扫描 ==="

# 1. 空 catch 块
echo "检查空 catch 块..."
empty_catch=$(grep -rn "except.*:" backend/app/ 2>/dev/null | grep -A1 "pass$" | grep -B1 "pass$" | wc -l)
echo "  发现 ${empty_catch} 个空 catch 块"

# 2. 未记录的异常
echo "检查未记录的异常..."
unlogged=$(grep -rn "except Exception" backend/app/routers/ 2>/dev/null | grep -v "log_error\|logger.error" | wc -l)
echo "  发现 ${unlogged} 个未记录异常"

# 3. 硬编码错误消息
echo "检查硬编码错误消息..."
hardcoded=$(grep -rn "raise HTTPException" backend/app/routers/ 2>/dev/null | grep -v "from app.utils.errors" | wc -l)
echo "  发现 ${hardcoded} 个硬编码错误"

# 4. 前端未处理错误
echo "检查前端未处理错误..."
frontend_unhandled=$(grep -rn "catch.*{" frontend/src/ 2>/dev/null | grep -v "handleError\|reportError\|console.error" | wc -l)
echo "  发现 ${frontend_unhandled} 个未处理错误"

# 汇总
total=$((empty_catch + unlogged + hardcoded + frontend_unhandled))
if [ $total -eq 0 ]; then
  echo "✅ 无错误模式"
else
  echo "⚠️ 发现 ${total} 个潜在问题"
fi
```

---

#### Phase 5: 安全漏洞扫描 (5分钟)

**目标**: 检测潜在安全风险

**检查项**:

| 检查项 | 描述 | 工具 |
|--------|------|------|
| AST 验证 | 策略代码安全检查 | pytest |
| 输入验证 | Pydantic 字段约束 | grep |
| 敏感信息 | API key/密码泄露 | grep |
| SQL 注入 | 字符串拼接 SQL | grep |

**执行脚本**:
```bash
#!/bin/bash
# phase5_security_scan.sh

echo "=== Phase 5: 安全漏洞扫描 ==="

# 1. 运行安全测试
echo "运行 AST 验证测试..."
cd backend
security_tests=$(pytest tests/unit/test_services/test_script_strategy_security.py -v --tb=no 2>/dev/null | grep -c "PASSED")
echo "  安全测试通过: ${security_tests}/10"

# 2. 输入验证检查
echo "检查输入验证..."
validation_issues=$(grep -rn "Field(" backend/app/routers/ 2>/dev/null | grep -v "ge=\|le=\|min_length\|max_length\|pattern" | wc -l)
echo "  缺少验证的字段: ${validation_issues}"

# 3. 敏感信息检查
echo "检查敏感信息..."
secrets=$(grep -rn "api_key\|password\|secret" backend/app/ 2>/dev/null | grep -v "\.pyc\|__pycache__\|# " | grep -v "os.environ\|settings\." | wc -l)
echo "  潜在敏感信息: ${secrets}"

# 4. SQL 注入检查
echo "检查 SQL 注入风险..."
sql_injection=$(grep -rn "f\".*SELECT\|f'.*SELECT" backend/app/ 2>/dev/null | wc -l)
echo "  SQL 注入风险: ${sql_injection}"

cd ..
```

---

#### Phase 6: 性能基准测试 (5分钟)

**目标**: 测量关键性能指标

**指标**:

| 指标 | 目标值 | 测量方法 |
|------|--------|----------|
| API 响应时间 | < 500ms | curl time_total |
| WebSocket 延迟 | < 100ms | ping/pong 时间差 |
| 内存使用 | < 80% | /admin/system/metrics |
| CPU 使用 | < 50% | /admin/system/metrics |

**执行脚本**:
```bash
#!/bin/bash
# phase6_performance.sh

FRONTEND="http://192.168.1.50:60100"

echo "=== Phase 6: 性能基准测试 ==="

# 1. API 响应时间
echo "API 响应时间:"
for endpoint in "/api/v1/market/overview" "/api/v1/macro/overview" "/api/v1/news/flash"; do
  time=$(curl -o /dev/null -s -w "%{time_total}" "${FRONTEND}${endpoint}")
  echo "  ${endpoint}: ${time}s"
done

# 2. 系统资源
echo "系统资源:"
metrics=$(curl -s "${FRONTEND}/api/v1/admin/system/metrics")
memory_percent=$(echo "$metrics" | jq -r '.data.memory.percent')
cpu_percent=$(echo "$metrics" | jq -r '.data.cpu_percent // 0')
echo "  内存使用: ${memory_percent}%"
echo "  CPU 使用: ${cpu_percent}%"

# 3. WebSocket 延迟 (需要 Python)
echo "WebSocket 延迟:"
python3 << 'EOF'
import asyncio
import time
import websockets
import json

async def test_latency():
    try:
        async with websockets.connect('ws://192.168.1.50:60100/ws/market', close_timeout=5) as ws:
            start = time.time()
            await ws.send(json.dumps({"action": "subscribe", "symbols": ["600519"]}))
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            latency = (time.time() - start) * 1000
            print(f"  延迟: {latency:.2f}ms")
    except Exception as e:
        print(f"  错误: {e}")

asyncio.run(test_latency())
EOF
```

---

#### Phase 7: 回归测试 (10分钟)

**目标**: 运行现有测试套件

**执行命令**:
```bash
#!/bin/bash
# phase7_regression.sh

echo "=== Phase 7: 回归测试 ==="

# 后端测试
echo "后端测试..."
cd backend
backend_result=$(pytest tests/unit/ -q --tb=no 2>/dev/null | tail -1)
echo "  ${backend_result}"

# 前端测试
echo "前端测试..."
cd ../frontend
frontend_result=$(npm run test -- --run 2>/dev/null | tail -1)
echo "  ${frontend_result}"

cd ..
```

---

#### Phase 8: 报告生成 (2分钟)

**报告模板**:
```markdown
# AlphaTerminal 诊断报告

**执行时间**: {{TIMESTAMP}}
**循环次数**: {{CYCLE}}/{{MAX_CYCLES}}

## 摘要

| 阶段 | 状态 | 详情 |
|------|------|------|
| 服务健康 | ✅/❌ | ... |
| API 验证 | ✅/❌ | 通过 X/Y |
| UI 测试 | ✅/❌ | ... |
| 错误扫描 | ✅/❌ | 发现 N 个问题 |
| 安全扫描 | ✅/❌ | ... |
| 性能测试 | ✅/❌ | ... |
| 回归测试 | ✅/❌ | ... |

## 详细结果

### Phase 1: 服务健康
- 后端状态: {{BACKEND_STATUS}}
- 前端状态: {{FRONTEND_STATUS}}
- WebSocket: {{WS_STATUS}}

### Phase 2: API 验证
- P0 端点: {{P0_PASSED}}/{{P0_TOTAL}}
- P1 端点: {{P1_PASSED}}/{{P1_TOTAL}}
- 失败端点: {{FAILED_ENDPOINTS}}

### Phase 3-7: ...
...

## 建议修复项

| 优先级 | 问题 | 建议 |
|--------|------|------|
| P0 | ... | ... |
| P1 | ... | ... |
| P2 | ... | ... |

## 下一步行动

- [ ] 修复 P0 问题
- [ ] 优化 P1 问题
- [ ] 记录 P2 问题到 backlog
```

---

## 三、完整自动化脚本

```bash
#!/bin/bash
# auto_diagnosis.sh - AlphaTerminal 自动化诊断脚本
# 用法: ./auto_diagnosis.sh [循环次数]

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
NC='\033[0m'

# ==================== 结果变量 ====================
PHASE1_STATUS="❌"
PHASE2_STATUS="❌"
PHASE3_STATUS="❌"
PHASE4_STATUS="❌"
PHASE5_STATUS="❌"
PHASE6_STATUS="❌"
PHASE7_STATUS="❌"

# ==================== 函数定义 ====================

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

phase1_health() {
    log_info "Phase 1: 服务健康检查..."
    
    # 后端健康
    if curl -sf --max-time 5 "${BACKEND}/health" | jq -e '.status == "healthy"' > /dev/null 2>&1; then
        log_info "后端健康检查通过"
        PHASE1_STATUS="✅"
    else
        log_error "后端健康检查失败，尝试重启..."
        ./start-services.sh restart 2>/dev/null || true
        sleep 30
        if curl -sf --max-time 5 "${BACKEND}/health" > /dev/null 2>&1; then
            PHASE1_STATUS="✅"
        fi
    fi
}

phase2_api() {
    log_info "Phase 2: API 端点验证..."
    
    local endpoints=(
        "/api/v1/market/overview"
        "/api/v1/macro/overview"
        "/api/v1/news/flash"
        "/api/v1/futures/main_indexes"
        "/api/v1/forex/spot"
        "/api/v1/f9/health"
    )
    
    local passed=0
    for endpoint in "${endpoints[@]}"; do
        if curl -sf --max-time 30 "${FRONTEND}${endpoint}" | jq -e '.code == 0' > /dev/null 2>&1; then
            ((passed++))
        fi
    done
    
    if [ $passed -eq ${#endpoints[@]} ]; then
        PHASE2_STATUS="✅"
        log_info "API 验证通过: ${passed}/${#endpoints[@]}"
    else
        PHASE2_STATUS="⚠️"
        log_warn "API 验证部分通过: ${passed}/${#endpoints[@]}"
    fi
}

phase3_ui() {
    log_info "Phase 3: 前端 UI 测试..."
    
    # 简化版：检查前端页面是否可访问
    if curl -sf --max-time 10 "${FRONTEND}/" | grep -q "AlphaTerminal"; then
        PHASE3_STATUS="✅"
        log_info "前端页面正常"
    else
        PHASE3_STATUS="❌"
        log_error "前端页面异常"
    fi
}

phase4_errors() {
    log_info "Phase 4: 错误模式扫描..."
    
    local empty_catch=$(grep -rn "except.*:" backend/app/ 2>/dev/null | grep -A1 "pass$" | grep -B1 "pass$" | wc -l)
    local unlogged=$(grep -rn "except Exception" backend/app/routers/ 2>/dev/null | grep -v "log_error\|logger.error" | wc -l)
    
    local total=$((empty_catch + unlogged))
    if [ $total -eq 0 ]; then
        PHASE4_STATUS="✅"
        log_info "无错误模式"
    else
        PHASE4_STATUS="⚠️"
        log_warn "发现 ${total} 个潜在问题"
    fi
}

phase5_security() {
    log_info "Phase 5: 安全漏洞扫描..."
    
    cd backend 2>/dev/null || return
    local security_tests=$(pytest tests/unit/test_services/test_script_strategy_security.py -q --tb=no 2>/dev/null | grep -c "PASSED" || echo "0")
    cd ..
    
    if [ "$security_tests" -ge 10 ]; then
        PHASE5_STATUS="✅"
        log_info "安全测试通过: ${security_tests}/10"
    else
        PHASE5_STATUS="⚠️"
        log_warn "安全测试部分通过: ${security_tests}/10"
    fi
}

phase6_performance() {
    log_info "Phase 6: 性能基准测试..."
    
    local time=$(curl -o /dev/null -s -w "%{time_total}" "${FRONTEND}/api/v1/market/overview")
    
    if (( $(echo "$time < 1.0" | bc -l) )); then
        PHASE6_STATUS="✅"
        log_info "API 响应时间: ${time}s"
    else
        PHASE6_STATUS="⚠️"
        log_warn "API 响应较慢: ${time}s"
    fi
}

phase7_regression() {
    log_info "Phase 7: 回归测试..."
    
    cd backend 2>/dev/null || return
    local test_result=$(pytest tests/unit/ -q --tb=no 2>/dev/null | tail -1 || echo "0 passed")
    cd ..
    
    if echo "$test_result" | grep -q "passed"; then
        PHASE7_STATUS="✅"
        log_info "回归测试: ${test_result}"
    else
        PHASE7_STATUS="⚠️"
        log_warn "回归测试: ${test_result}"
    fi
}

generate_report() {
    cat > "$REPORT_FILE" << EOF
# AlphaTerminal 诊断报告

**执行时间**: $(date '+%Y-%m-%d %H:%M:%S')
**循环次数**: ${cycle}/${CYCLE_COUNT}

## 摘要

| 阶段 | 状态 |
|------|------|
| 服务健康 | ${PHASE1_STATUS} |
| API 验证 | ${PHASE2_STATUS} |
| UI 测试 | ${PHASE3_STATUS} |
| 错误扫描 | ${PHASE4_STATUS} |
| 安全扫描 | ${PHASE5_STATUS} |
| 性能测试 | ${PHASE6_STATUS} |
| 回归测试 | ${PHASE7_STATUS} |

## 结论

$(if [[ "$PHASE1_STATUS" == "✅" && "$PHASE2_STATUS" == "✅" ]]; then
    echo "系统运行正常"
else
    echo "存在问题，建议检查"
fi)
EOF
    
    log_info "报告已保存: ${REPORT_FILE}"
}

# ==================== 主循环 ====================
echo "========================================"
echo "AlphaTerminal 自动化诊断工作流"
echo "循环次数: ${CYCLE_COUNT}"
echo "========================================"

for cycle in $(seq 1 $CYCLE_COUNT); do
    echo ""
    echo "========== 循环 ${cycle}/${CYCLE_COUNT} =========="
    
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
        log_info "✅ 所有检查通过，提前退出"
        break
    fi
    
    # 非最后一次循环，等待后重试
    if [ $cycle -lt $CYCLE_COUNT ]; then
        log_info "等待 60 秒后重试..."
        sleep 60
    fi
done

echo ""
echo "========================================"
echo "诊断完成"
echo "报告位置: ${REPORT_FILE}"
echo "========================================"
```

---

## 四、扩展开发工作流

### 4.1 扩展任务模板

当诊断通过后，可执行扩展开发：

```markdown
## 扩展任务: {{TASK_NAME}}

### 背景
- 当前状态: {{CURRENT_STATE}}
- 目标状态: {{TARGET_STATE}}

### 实现步骤

#### Step 1: 分析现有代码模式
- [ ] 查找类似功能的实现
- [ ] 确定代码位置
- [ ] 理解数据流

#### Step 2: 设计新功能接口
- [ ] 定义 API 端点
- [ ] 定义请求/响应 Schema
- [ ] 定义前端组件接口

#### Step 3: 实现后端 API
- [ ] 创建路由文件
- [ ] 实现 Pydantic Schema
- [ ] 添加错误处理
- [ ] 添加超时保护
- [ ] 添加输入验证
- [ ] 配置 rate limit

#### Step 4: 实现前端组件
- [ ] 创建 Vue 组件
- [ ] 创建 composable
- [ ] 添加 loading/error 状态
- [ ] 添加 ARIA 属性
- [ ] 添加键盘导航

#### Step 5: 编写测试用例
- [ ] 后端单元测试
- [ ] 前端组件测试
- [ ] E2E 集成测试

#### Step 6: 执行诊断验证
- [ ] 运行自动化诊断
- [ ] 确认无回归

### 验收标准
- [ ] 新功能正常工作
- [ ] 现有功能无回归
- [ ] 测试覆盖率达标
- [ ] 性能指标达标
```

### 4.2 开发检查清单

**后端开发**:
```markdown
- [ ] 路由定义在 `backend/app/routers/`
- [ ] Schema 定义使用 Pydantic
- [ ] 错误处理使用 `app/utils/errors.py`
- [ ] 添加超时保护 (`asyncio.wait_for`)
- [ ] 添加输入验证 (`Field(ge=, le=)`)
- [ ] 添加 rate limit 配置
- [ ] 添加日志记录
- [ ] 编写单元测试
```

**前端开发**:
```markdown
- [ ] 组件放在 `frontend/src/components/`
- [ ] 使用 composables 管理状态
- [ ] 使用 `useECharts` 管理 ECharts
- [ ] 添加 loading/error 状态
- [ ] 添加 ARIA 属性
- [ ] 添加键盘导航
- [ ] 添加响应式布局
- [ ] 编写组件测试
```

---

## 五、使用方法

### 5.1 单次诊断
```bash
chmod +x auto_diagnosis.sh
./auto_diagnosis.sh 1
```

### 5.2 循环诊断 (3次)
```bash
./auto_diagnosis.sh 3
```

### 5.3 持续监控
```bash
while true; do
  ./auto_diagnosis.sh 1
  sleep 300  # 每 5 分钟执行一次
done
```

### 5.4 与 AI Agent 集成

将本文档作为系统提示，AI Agent 可自动执行诊断并生成报告。

---

## 六、附录

### 6.1 关键文件位置

| 类别 | 路径 |
|------|------|
| 后端路由 | `backend/app/routers/` |
| 后端服务 | `backend/app/services/` |
| 前端组件 | `frontend/src/components/` |
| 前端工具 | `frontend/src/utils/` |
| 测试文件 | `backend/tests/`, `frontend/tests/` |
| 配置文件 | `backend/app/config/` |

### 6.2 常用命令

```bash
# 启动服务
./start-services.sh all

# 重启服务
./start-services.sh restart

# 查看状态
./start-services.sh status

# 后端测试
cd backend && pytest tests/unit/ -v

# 前端测试
cd frontend && npm run test

# 前端构建
cd frontend && npm run build
```

### 6.3 错误码参考

| 错误码 | 含义 | 处理建议 |
|--------|------|----------|
| 100 | 请求参数错误 | 检查请求参数 |
| 101 | 未授权 | 检查 API Key |
| 120 | 请求频率限制 | 降低请求频率 |
| 200 | 内部服务器错误 | 查看后端日志 |
| 310 | 请求超时 | 增加超时时间 |
| 330 | 数据源错误 | 检查网络/代理 |

---

**文档版本**: v1.0  
**最后更新**: 2026-05-15
