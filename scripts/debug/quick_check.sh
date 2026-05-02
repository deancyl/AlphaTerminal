#!/usr/bin/env bash
#===============================================================================
# Quick Check Script v2.0 - Enhanced with JSON output support
# Usage: ./scripts/quick_check.sh [--json] [--backend-url URL] [--frontend-url URL]
#===============================================================================

set -uo pipefail

# Parse arguments
JSON_MODE=false
BACKEND_URL="http://localhost:8002"
FRONTEND_URL="http://localhost:60100"

while [[ $# -gt 0 ]]; do
    case $1 in
        --json) JSON_MODE=true ;;
        --backend-url) BACKEND_URL="$2"; shift ;;
        --frontend-url) FRONTEND_URL="$2"; shift ;;
    esac
    shift
done

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Results array for JSON mode
declare -A RESULTS

run_check() {
    local name="$1"
    local cmd="$2"
    local expected="$3"
    
    local start=$(date +%s%N)
    local result=$(eval "$cmd" 2>/dev/null)
    local end=$(date +%s%N)
    local duration=$(( (end - start) / 1000000 ))
    
    if [ "$result" = "$expected" ]; then
        RESULTS[$name]="{\"status\":\"passed\",\"duration\":$duration}"
        if [ "$JSON_MODE" = false ]; then
            echo -e "${GREEN}✓${NC} $name (${duration}ms)"
        fi
        return 0
    else
        RESULTS[$name]="{\"status\":\"failed\",\"duration\":$duration,\"expected\":\"$expected\",\"actual\":\"$result\"}"
        if [ "$JSON_MODE" = false ]; then
            echo -e "${RED}✗${NC} $name (${duration}ms) - Expected $expected, got $result"
        fi
        return 1
    fi
}

if [ "$JSON_MODE" = false ]; then
    echo "=========================================="
    echo "  AlphaTerminal Quick Health Check v2.0"
    echo "=========================================="
    echo ""
fi

# Run checks
run_check "Backend Health" "curl -s -o /dev/null -w '%{http_code}' ${BACKEND_URL}/health" "200"
run_check "Frontend Access" "curl -s -o /dev/null -w '%{http_code}' ${FRONTEND_URL}" "200"
run_check "API Macro" "curl -s -o /dev/null -w '%{http_code}' ${BACKEND_URL}/api/v1/macro/overview" "200"
run_check "API Market" "curl -s -o /dev/null -w '%{http_code}' ${BACKEND_URL}/api/v1/market/overview" "200"
run_check "API News" "curl -s -o /dev/null -w '%{http_code}' ${BACKEND_URL}/api/v1/news/latest" "200"

# Process checks
backend_pid=$(pgrep -c -f 'uvicorn.*8002' 2>/dev/null | tr -d '\n' || echo 0)
frontend_pid=$(pgrep -c -f 'vite.*60100' 2>/dev/null | tr -d '\n' || echo 0)

if [ "$backend_pid" -gt 0 ]; then
    RESULTS["Backend Process"]="{\"status\":\"passed\",\"count\":$backend_pid}"
    if [ "$JSON_MODE" = false ]; then
        echo -e "${GREEN}✓${NC} Backend process ($backend_pid instances)"
    fi
else
    RESULTS["Backend Process"]="{\"status\":\"failed\",\"count\":0}"
    if [ "$JSON_MODE" = false ]; then
        echo -e "${RED}✗${NC} Backend process not running"
    fi
fi

if [ "$frontend_pid" -gt 0 ]; then
    RESULTS["Frontend Process"]="{\"status\":\"passed\",\"count\":$frontend_pid}"
    if [ "$JSON_MODE" = false ]; then
        echo -e "${GREEN}✓${NC} Frontend process ($frontend_pid instances)"
    fi
else
    RESULTS["Frontend Process"]="{\"status\":\"warning\",\"count\":0}"
    if [ "$JSON_MODE" = false ]; then
        echo -e "${YELLOW}⚠${NC} Frontend process not running"
    fi
fi

# Port usage
if [ "$JSON_MODE" = false ]; then
    echo ""
    echo "Port Usage:"
    ss -tlnp 2>/dev/null | grep -E ':(8002|60100)' | while read line; do
        echo "  $line"
    done
fi

output_json() {
    echo "{"
    echo '  "timestamp": "'$(date -Iseconds)'",'
    echo '  "backend_url": "'$BACKEND_URL'",'
    echo '  "frontend_url": "'$FRONTEND_URL'",'
    echo '  "checks": {'
    local first=true
    for key in "${!RESULTS[@]}"; do
        if [ "$first" = true ]; then
            first=false
        else
            echo ","
        fi
        echo -n '    "'$key'": '${RESULTS[$key]}
    done
    echo ""
    echo "  }"
    echo "}"
}

if [ "$JSON_MODE" = true ]; then
    output_json
else
    echo ""
    echo "=========================================="
    echo "Quick check complete."
    echo "=========================================="
fi
