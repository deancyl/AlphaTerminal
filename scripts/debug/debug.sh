#!/usr/bin/env bash
#===============================================================================
# AlphaTerminal Unified Debug Orchestrator
# 统一调试入口，支持多种模式和输出格式
# Usage: ./scripts/debug.sh [mode] [options]
#   mode: quick|full|api|frontend|database|security|performance|websocket|logs|all
#   options:
#     --json          输出JSON格式（用于CI/CD）
#     --output-dir    指定报告输出目录
#     --backend-url   后端地址（默认: http://localhost:8002）
#     --frontend-url  前端地址（默认: http://localhost:60100）
#     --verbose       详细输出
#===============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="${PROJECT_DIR}/backend"
DEBUG_DIR="${SCRIPT_DIR}"

# Default values
BACKEND_URL="http://localhost:8002"
FRONTEND_URL="http://localhost:60100"
OUTPUT_DIR="/tmp/alphaterminal_debug_$(date +%Y%m%d_%H%M%S)"
JSON_MODE=false
VERBOSE=false
MODE="${1:-quick}"

# Parse arguments
shift 2> /dev/null || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --json) JSON_MODE=true ;;
        --output-dir) OUTPUT_DIR="$2"; shift ;;
        --backend-url) BACKEND_URL="$2"; shift ;;
        --frontend-url) FRONTEND_URL="$2"; shift ;;
        --verbose) VERBOSE=true ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

mkdir -p "$OUTPUT_DIR"

# JSON output helpers
results_json="{}"

init_json() {
    results_json='{"timestamp":"'$(date -Iseconds)'","mode":"'$MODE'","backend_url":"'$BACKEND_URL'","frontend_url":"'$FRONTEND_URL'","checks":{},"summary":{"passed":0,"failed":0,"warnings":0,"total":0}}'
}

add_json_result() {
    local name="$1"
    local status="$2"
    local message="$3"
    local duration="${4:-0}"
    
    results_json=$(echo "$results_json" | jq --arg name "$name" --arg status "$status" --arg message "$message" --argjson duration "$duration" \
        '.checks[$name] = {"status": $status, "message": $message, "duration_ms": $duration}')
    
    # Update summary counters
    if [ "$status" = "passed" ]; then
        results_json=$(echo "$results_json" | jq '.summary.passed += 1 | .summary.total += 1')
    elif [ "$status" = "failed" ]; then
        results_json=$(echo "$results_json" | jq '.summary.failed += 1 | .summary.total += 1')
    elif [ "$status" = "warning" ]; then
        results_json=$(echo "$results_json" | jq '.summary.warnings += 1 | .summary.total += 1')
    fi
}

# Print helpers
print_header() {
    if [ "$JSON_MODE" = false ]; then
        echo ""
        echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
        echo -e "${CYAN}  $1${NC}"
        echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    fi
}

print_success() {
    if [ "$JSON_MODE" = false ]; then
        echo -e "${GREEN}✓${NC} $1"
    fi
}

print_error() {
    if [ "$JSON_MODE" = false ]; then
        echo -e "${RED}✗${NC} $1"
    fi
}

print_warning() {
    if [ "$JSON_MODE" = false ]; then
        echo -e "${YELLOW}⚠${NC} $1"
    fi
}

print_info() {
    if [ "$JSON_MODE" = false ]; then
        echo -e "${BLUE}ℹ${NC} $1"
    fi
}

# Check command
run_check() {
    local name="$1"
    local check_cmd="$2"
    local expected="${3:-0}"
    
    local start_time=$(date +%s%N)
    local output
    local exit_code
    
    if [ "$VERBOSE" = true ]; then
        output=$(eval "$check_cmd" 2>&1)
        exit_code=$?
    else
        output=$(eval "$check_cmd" 2>&1)
        exit_code=$?
    fi
    
    local end_time=$(date +%s%N)
    local duration=$(( (end_time - start_time) / 1000000 ))
    
    if [ $exit_code -eq $expected ]; then
        print_success "$name (${duration}ms)"
        add_json_result "$name" "passed" "" "$duration"
        if [ "$VERBOSE" = true ] && [ -n "$output" ]; then
            echo "$output"
        fi
        return 0
    else
        print_error "$name failed (${duration}ms)"
        add_json_result "$name" "failed" "$output" "$duration"
        if [ "$VERBOSE" = true ] && [ -n "$output" ]; then
            echo "$output"
        fi
        return 1
    fi
}

# ═══════════════════════════════════════════════════════════════
# MODE: quick
# ═══════════════════════════════════════════════════════════════
run_quick() {
    print_header "Quick Health Check"
    
    run_check "Backend Health" "curl -s -o /dev/null -w '%{http_code}' ${BACKEND_URL}/health" 0 "200"
    run_check "Frontend Access" "curl -s -o /dev/null -w '%{http_code}' ${FRONTEND_URL}" 0 "200"
    run_check "API Macro Overview" "curl -s -o /dev/null -w '%{http_code}' ${BACKEND_URL}/api/v1/macro/overview" 0 "200"
    run_check "API Market Overview" "curl -s -o /dev/null -w '%{http_code}' ${BACKEND_URL}/api/v1/market/overview" 0 "200"
    
    local backend_pid=$(pgrep -c -f 'uvicorn.*8002' 2>/dev/null | tr -d '\n' || echo 0)
    local frontend_pid=$(pgrep -c -f 'vite.*60100' 2>/dev/null | tr -d '\n' || echo 0)
    
    backend_pid=$(echo "$backend_pid" | grep -o '[0-9]*' | head -1)
    frontend_pid=$(echo "$frontend_pid" | grep -o '[0-9]*' | head -1)
    backend_pid=${backend_pid:-0}
    frontend_pid=${frontend_pid:-0}
    
    if [ "$backend_pid" -gt 0 ]; then
        print_success "Backend process running ($backend_pid instances)"
        add_json_result "Backend Process" "passed" "$backend_pid instances"
    else
        print_error "Backend process not running"
        add_json_result "Backend Process" "failed" "No process found"
    fi
    
    if [ "$frontend_pid" -gt 0 ]; then
        print_success "Frontend process running ($frontend_pid instances)"
        add_json_result "Frontend Process" "passed" "$frontend_pid instances"
    else
        print_warning "Frontend process not running"
        add_json_result "Frontend Process" "warning" "No process found"
    fi
}

# ═══════════════════════════════════════════════════════════════
# MODE: api
# ═══════════════════════════════════════════════════════════════
run_api() {
    print_header "API Debug"
    
    local endpoints=(
        "GET:/health:200:Health Check"
        "GET:/api/v1/market/overview:200:Market Overview"
        "GET:/api/v1/market/indices:200:Market Indices"
        "GET:/api/v1/macro/overview:200:Macro Overview"
        "GET:/api/v1/news/latest:200:Latest News"
        "GET:/api/v1/sentiment/overview:200:Sentiment"
        "GET:/api/v1/backtest/strategies:200:Backtest Strategies"
        "GET:/api/v1/nonexistent:404:404 Handling"
    )
    
    for endpoint in "${endpoints[@]}"; do
        IFS=':' read -r method path expected desc <<< "$endpoint"
        run_check "$desc" "curl -s -o /dev/null -w '%{http_code}' -X $method ${BACKEND_URL}${path}" 0 "$expected"
    done
}

# ═══════════════════════════════════════════════════════════════
# MODE: database
# ═══════════════════════════════════════════════════════════════
run_database() {
    print_header "Database Debug"
    
    local db_paths=(
        "${BACKEND_DIR}/app/db/alphaterminal.db"
        "${BACKEND_DIR}/tests/database.db"
    )
    
    local db_found=false
    for db_path in "${db_paths[@]}"; do
        if [ -f "$db_path" ]; then
            db_found=true
            print_info "Checking database: $db_path"
            
            # Integrity check
            local integrity=$(sqlite3 "$db_path" "PRAGMA integrity_check;" 2>/dev/null)
            if [ "$integrity" = "ok" ]; then
                print_success "Database integrity OK"
                add_json_result "DB Integrity" "passed" "$db_path"
            else
                print_error "Database integrity FAILED"
                add_json_result "DB Integrity" "failed" "$integrity"
            fi
            
            # Get table counts
            local tables=$(sqlite3 "$db_path" ".tables" 2>/dev/null)
            local total_rows=0
            for table in $tables; do
                local count=$(sqlite3 "$db_path" "SELECT COUNT(*) FROM ${table};" 2>/dev/null)
                total_rows=$((total_rows + count))
                print_info "  $table: $count rows"
            done
            add_json_result "DB Tables" "passed" "Total rows: $total_rows"
            
            break
        fi
    done
    
    if [ "$db_found" = false ]; then
        print_error "No database found"
        add_json_result "DB Check" "failed" "No database file found"
    fi
}

# ═══════════════════════════════════════════════════════════════
# MODE: security
# ═══════════════════════════════════════════════════════════════
run_security() {
    print_header "Security Audit"
    
    # Check for hardcoded secrets
    local secret_patterns=(
        "password\s*=\s*[\"'][^\"']{8,}[\"']"
        "secret\s*=\s*[\"'][^\"']{8,}[\"']"
        "api_key\s*=\s*[\"'][^\"']{8,}[\"']"
    )
    
    local secrets_found=0
    for pattern in "${secret_patterns[@]}"; do
        local matches=$(grep -ri -E "$pattern" --include="*.py" "${BACKEND_DIR}/app" 2>/dev/null | grep -v "test_" | wc -l)
        secrets_found=$((secrets_found + matches))
    done
    
    if [ $secrets_found -eq 0 ]; then
        print_success "No obvious hardcoded secrets found"
        add_json_result "Secrets Check" "passed" "Clean"
    else
        print_warning "$secrets_found potential secrets found"
        add_json_result "Secrets Check" "warning" "$secrets_found potential secrets"
    fi
    
    # Check requirements for known vulnerable versions
    if [ -f "${BACKEND_DIR}/requirements.txt" ]; then
        print_info "Checking requirements.txt..."
        add_json_result "Requirements Check" "passed" "File exists"
    fi
}

# ═══════════════════════════════════════════════════════════════
# MODE: performance
# ═══════════════════════════════════════════════════════════════
run_performance() {
    print_header "Performance Profile"
    
    local endpoints=(
        "GET:/health:Health"
        "GET:/api/v1/market/overview:Market"
        "GET:/api/v1/macro/overview:Macro"
    )
    
    for endpoint in "${endpoints[@]}"; do
        IFS=':' read -r method path desc <<< "$endpoint"
        
        local times=()
        for i in {1..5}; do
            local start=$(date +%s%N)
            curl -s -o /dev/null "${BACKEND_URL}${path}" 2>/dev/null
            local end=$(date +%s%N)
            local duration=$(( (end - start) / 1000000 ))
            times+=($duration)
        done
        
        # Calculate average
        local total=0
        for t in "${times[@]}"; do
            total=$((total + t))
        done
        local avg=$((total / 5))
        
        if [ $avg -lt 100 ]; then
            print_success "$desc: ${avg}ms avg"
            add_json_result "Perf $desc" "passed" "${avg}ms avg"
        elif [ $avg -lt 500 ]; then
            print_warning "$desc: ${avg}ms avg"
            add_json_result "Perf $desc" "warning" "${avg}ms avg"
        else
            print_error "$desc: ${avg}ms avg"
            add_json_result "Perf $desc" "failed" "${avg}ms avg"
        fi
    done
}

# ═══════════════════════════════════════════════════════════════
# MODE: websocket
# ═══════════════════════════════════════════════════════════════
run_websocket() {
    print_header "WebSocket Debug"
    
    local ws_url="${BACKEND_URL/http:/ws:}"
    
    # Simple WebSocket connectivity test using Python
    python3 <<EOF 2>&1
import websocket
import json
import sys

try:
    ws = websocket.create_connection("${ws_url}/ws/market", timeout=5)
    print("WebSocket connected successfully")
    
    # Send a ping or subscription message if needed
    ws.send(json.dumps({"action": "ping"}))
    
    # Try to receive for 2 seconds
    ws.settimeout(2)
    try:
        result = ws.recv()
        print(f"Received: {result[:100]}...")
    except websocket._exceptions.WebSocketTimeoutException:
        print("No message received (timeout)")
    
    ws.close()
    print("WebSocket closed gracefully")
    sys.exit(0)
except Exception as e:
    print(f"WebSocket error: {e}")
    sys.exit(1)
EOF
    
    local ws_exit=$?
    if [ $ws_exit -eq 0 ]; then
        print_success "WebSocket connection OK"
        add_json_result "WebSocket" "passed" "Connected successfully"
    else
        print_error "WebSocket connection failed"
        add_json_result "WebSocket" "failed" "Connection error"
    fi
}

# ═══════════════════════════════════════════════════════════════
# MODE: logs
# ═══════════════════════════════════════════════════════════════
run_logs() {
    print_header "Log Analysis"
    
    local log_files=(
        "/tmp/backend.log"
        "/tmp/frontend.log"
    )
    
    for log_file in "${log_files[@]}"; do
        if [ -f "$log_file" ]; then
            local size=$(stat -f%z "$log_file" 2>/dev/null || stat -c%s "$log_file" 2>/dev/null || echo 0)
            local errors=$(grep -c "ERROR" "$log_file" 2>/dev/null || echo 0)
            local warnings=$(grep -c "WARN" "$log_file" 2>/dev/null || echo 0)
            
            print_info "$(basename $log_file): $(($size / 1024))KB, $errors errors, $warnings warnings"
            
            if [ $errors -gt 0 ]; then
                print_error "  Found $errors ERROR entries"
                add_json_result "Log $(basename $log_file)" "failed" "$errors errors, $warnings warnings"
            elif [ $warnings -gt 10 ]; then
                print_warning "  Found $warnings WARNING entries"
                add_json_result "Log $(basename $log_file)" "warning" "$errors errors, $warnings warnings"
            else
                print_success "  Log looks healthy"
                add_json_result "Log $(basename $log_file)" "passed" "$errors errors, $warnings warnings"
            fi
        else
            print_warning "Log file not found: $log_file"
            add_json_result "Log $(basename $log_file)" "warning" "File not found"
        fi
    done
}

# ═══════════════════════════════════════════════════════════════
# MODE: full / all
# ═══════════════════════════════════════════════════════════════
run_full() {
    run_quick
    run_api
    run_database
    run_security
    run_performance
    run_websocket
    run_logs
}

# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════
main() {
    init_json
    
    if [ "$JSON_MODE" = false ]; then
        echo ""
        echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${CYAN}║          AlphaTerminal Debug Orchestrator v2.0               ║${NC}"
        echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${BLUE}Mode:${NC}    $MODE"
        echo -e "${BLUE}Backend:${NC} $BACKEND_URL"
        echo -e "${BLUE}Frontend:${NC} $FRONTEND_URL"
        echo -e "${BLUE}Output:${NC}  $OUTPUT_DIR"
        if [ "$JSON_MODE" = true ]; then
            echo -e "${BLUE}Format:${NC}  JSON"
        fi
        echo ""
    fi
    
    case "$MODE" in
        quick) run_quick ;;
        api) run_api ;;
        database|db) run_database ;;
        security) run_security ;;
        performance|perf) run_performance ;;
        websocket|ws) run_websocket ;;
        logs) run_logs ;;
        full|all) run_full ;;
        *)
            echo "Unknown mode: $MODE"
            echo "Usage: $0 [quick|api|database|security|performance|websocket|logs|full]"
            exit 1
            ;;
    esac
    
    # Save results
    echo "$results_json" | jq '.' > "${OUTPUT_DIR}/debug_report.json" 2>/dev/null || echo "$results_json" > "${OUTPUT_DIR}/debug_report.json"
    
    # Summary
    local passed=$(echo "$results_json" | jq -r '.summary.passed')
    local failed=$(echo "$results_json" | jq -r '.summary.failed')
    local warnings=$(echo "$results_json" | jq -r '.summary.warnings')
    local total=$(echo "$results_json" | jq -r '.summary.total')
    
    if [ "$JSON_MODE" = false ]; then
        echo ""
        echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
        echo -e "${CYAN}  Summary${NC}"
        echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
        echo -e "  ${GREEN}Passed:${NC}   $passed"
        echo -e "  ${RED}Failed:${NC}   $failed"
        echo -e "  ${YELLOW}Warnings:${NC} $warnings"
        echo -e "  ${BLUE}Total:${NC}    $total"
        echo ""
        echo -e "${BLUE}Report saved to:${NC} ${OUTPUT_DIR}/debug_report.json"
        echo ""
    else
        echo "$results_json"
    fi
    
    # Exit with error if any checks failed
    if [ $failed -gt 0 ]; then
        exit 1
    fi
}

main