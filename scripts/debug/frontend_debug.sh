#!/usr/bin/env bash
#===============================================================================
# Frontend Debug Script - Run Playwright automated tests
# Usage: ./scripts/frontend_debug.sh [mode]
#   mode: quick (screenshot only), full (comprehensive), screenshot (full page)
#===============================================================================

set -uo pipefail

MODE="${1:-full}"
FRONTEND_URL="http://localhost:60100"

echo "=========================================="
echo "  AlphaTerminal Frontend Debug"
echo "  Mode: ${MODE}"
echo "=========================================="
echo ""

# Check if Playwright is installed
if ! python3 -c "import playwright" 2>/dev/null; then
    echo "Installing Playwright..."
    pip install --break-system-packages playwright
    python3 -m playwright install chromium
fi

# Run the debug script
cd backend
python3 debug_page.py --url "${FRONTEND_URL}" --mode "${MODE}" --output-dir /tmp/alphaterminal_debug

echo ""
echo "=========================================="
echo "Frontend debug complete."
echo "Results saved to: /tmp/alphaterminal_debug/"
echo "=========================================="
