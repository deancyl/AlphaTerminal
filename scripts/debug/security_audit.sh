#!/usr/bin/env bash
#===============================================================================
# Security Audit Script - Run security scanning tools
# Usage: ./scripts/security_audit.sh [target_dir]
#===============================================================================

set -uo pipefail

TARGET_DIR="${1:-backend/app}"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
WARN=0

echo "=========================================="
echo "  AlphaTerminal Security Audit"
echo "  Target: ${TARGET_DIR}"
echo "=========================================="
echo ""

# Install tools if needed
install_tool() {
    local tool="$1"
    local pkg="${2:-$1}"
    if ! command -v "$tool" &> /dev/null; then
        echo "Installing ${tool}..."
        pip install --break-system-packages "$pkg" 2>/dev/null || pip install "$pkg" 2>/dev/null
    fi
}

install_tool "bandit" "bandit"
install_tool "safety" "safety"

# Run Bandit
echo "Running Bandit (Python security scan)..."
if command -v bandit &> /dev/null; then
    bandit -r "$TARGET_DIR" -f json -o /tmp/bandit-report.json 2>/dev/null || true
    bandit -r "$TARGET_DIR" -ll || true
    echo -e "${GREEN}Bandit scan complete${NC}"
else
    echo -e "${YELLOW}Bandit not available${NC}"
fi

echo ""

# Run Safety
echo "Running Safety (dependency vulnerability scan)..."
if command -v safety &> /dev/null; then
    safety check --json > /tmp/safety-report.json 2>/dev/null || true
    safety check || true
    echo -e "${GREEN}Safety scan complete${NC}"
else
    echo -e "${YELLOW}Safety not available${NC}"
fi

echo ""

# Check for hardcoded secrets (basic grep)
echo "Checking for potential hardcoded secrets..."
patterns=(
    "password\s*=\s*[\"'][^\"']{8,}[\"']"
    "secret\s*=\s*[\"'][^\"']{8,}[\"']"
    "api_key\s*=\s*[\"'][^\"']{8,}[\"']"
    "token\s*=\s*[\"'][^\"']{8,}[\"']"
)

found=0
for pattern in "${patterns[@]}"; do
    matches=$(grep -ri -E "$pattern" --include="*.py" "$TARGET_DIR" 2>/dev/null | grep -v "^${TARGET_DIR}/.venv" | grep -v "test_" | head -5)
    if [ -n "$matches" ]; then
        echo -e "${YELLOW}Potential secrets found:${NC}"
        echo "$matches"
        found=1
    fi
done

if [ $found -eq 0 ]; then
    echo -e "${GREEN}No obvious hardcoded secrets found${NC}"
fi

echo ""
echo "=========================================="
echo "Security audit complete."
echo "Reports saved to:"
echo "  /tmp/bandit-report.json"
echo "  /tmp/safety-report.json"
echo "=========================================="
