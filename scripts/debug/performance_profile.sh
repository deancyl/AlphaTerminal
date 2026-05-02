#!/usr/bin/env bash
#===============================================================================
# Performance Profile Script - Measure API response times
# Usage: ./scripts/performance_profile.sh [base_url] [iterations]
#===============================================================================

set -uo pipefail

BASE_URL="${1:-http://localhost:8002}"
ITERATIONS="${2:-5}"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

endpoints=(
    "GET:/health:Health Check"
    "GET:/api/v1/market/overview:Market Overview"
    "GET:/api/v1/market/indices:Market Indices"
    "GET:/api/v1/macro/overview:Macro Overview"
    "GET:/api/v1/portfolios:Portfolios"
    "GET:/api/v1/backtest/strategies:Backtest Strategies"
    "GET:/api/v1/news/latest:Latest News"
    "GET:/api/v1/sentiment/overview:Sentiment Overview"
)

echo "=========================================="
echo "  AlphaTerminal Performance Profile"
echo "  URL: ${BASE_URL}"
echo "  Iterations: ${ITERATIONS}"
echo "=========================================="
echo ""

# Warmup
echo "Warming up..."
curl -s "${BASE_URL}/health" > /dev/null 2>&1
sleep 1

for endpoint in "${endpoints[@]}"; do
    IFS=':' read -r method path desc <<< "$endpoint"
    
    times=()
    min_time=999999
    max_time=0
    total_time=0
    
    for ((i=1; i<=ITERATIONS; i++)); do
        start=$(date +%s%N)
        code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "${BASE_URL}${path}" 2>/dev/null)
        end=$(date +%s%N)
        
        duration=$(( (end - start) / 1000000 ))
        times+=($duration)
        total_time=$((total_time + duration))
        
        if [ $duration -lt $min_time ]; then min_time=$duration; fi
        if [ $duration -gt $max_time ]; then max_time=$duration; fi
    done
    
    avg_time=$((total_time / ITERATIONS))
    
    # Color coding
    if [ $avg_time -lt 100 ]; then
        color="$GREEN"
    elif [ $avg_time -lt 500 ]; then
        color="$YELLOW"
    else
        color="$RED"
    fi
    
    printf "%-25s | avg: ${color}%4d${NC}ms | min: %4dms | max: %4dms | status: %s\n" \
        "$desc" "$avg_time" "$min_time" "$max_time" "$code"
done

echo ""
echo "=========================================="
echo "Performance profile complete."
echo "Legend: ${GREEN}<100ms${NC} Good, ${YELLOW}100-500ms${NC} OK, ${RED}>500ms${NC} Slow"
echo "=========================================="
