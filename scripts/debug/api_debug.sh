#!/usr/bin/env bash
#===============================================================================
# API Debug Script v2.1 - 修复参数解析
#===============================================================================

set -uo pipefail

# 解析参数
JSON_MODE=false
BASE_URL="http://localhost:8002"

for arg in "$@"; do
    case "$arg" in
        --json) JSON_MODE=true ;;
        --backend-url) ;;  # 忽略，下一个参数会被跳过
        --frontend-url) ;; # 忽略
        http://*|https://*) BASE_URL="$arg" ;;
    esac
done

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

api_test() {
    local method="$1"
    local endpoint="$2"
    local expected_code="${3:-200}"
    local desc="${4:-$endpoint}"
    
    local start_time=$(date +%s%N)
    local http_code
    
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "${BASE_URL}${endpoint}" 2>/dev/null)
    
    local end_time=$(date +%s%N)
    local duration=$(( (end_time - start_time) / 1000000 ))
    
    if [ "$http_code" = "$expected_code" ]; then
        ((PASS++))
    else
        ((FAIL++))
    fi
}

endpoints=(
    "GET:/health:200:Health"
    "GET:/api/v1/market/overview:200:Market"
    "GET:/api/v1/macro/overview:200:Macro"
    "GET:/api/v1/news/flash:200:News"
    "GET:/api/v1/backtest/strategies:200:Backtest"
    "GET:/api/v1/admin/sources/status:200:Admin"
    "GET:/api/v1/nonexistent:404:404"
)

for ep in "${endpoints[@]}"; do
    IFS=':' read -r method path expected desc <<< "$ep"
    api_test "$method" "$path" "$expected" "$desc"
done

if [ "$JSON_MODE" = true ]; then
    cat <<JSON
{
  "base_url": "$BASE_URL",
  "passed": $PASS,
  "failed": $FAIL,
  "total": $((PASS + FAIL)),
  "status": "$([ $FAIL -eq 0 ] && echo 'passed' || echo 'failed')"
}
JSON
else
    echo "=========================================="
    echo -e "Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}"
    echo "=========================================="
fi

exit $([ $FAIL -eq 0 ] && echo 0 || echo 1)
