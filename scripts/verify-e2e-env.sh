#!/bin/bash
# scripts/verify-e2e-env.sh - 验证 E2E 测试环境

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0

echo "🔍 验证 E2E 测试环境..."
echo ""

# 1. 检查 Node.js 版本
echo -e "${YELLOW}[1/8] Node.js${NC}"
if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v | cut -d 'v' -f 2 | cut -d '.' -f 1)
    if [ "$NODE_VERSION" -ge 18 ]; then
        echo -e "   ${GREEN}✅ Node.js: $(node -v)${NC}"
    else
        echo -e "   ${RED}❌ Node.js 版本过低: $(node -v)，需要 18+${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "   ${RED}❌ Node.js 未安装${NC}"
    ERRORS=$((ERRORS + 1))
fi

# 2. 检查 Python 版本
echo -e "${YELLOW}[2/8] Python${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(sys.version_info.major * 10 + sys.version_info.minor)')
    if [ "$PYTHON_VERSION" -ge 310 ]; then
        echo -e "   ${GREEN}✅ Python: $(python3 --version)${NC}"
    else
        echo -e "   ${RED}❌ Python 版本过低: $(python3 --version)，需要 3.10+${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "   ${RED}❌ Python 未安装${NC}"
    ERRORS=$((ERRORS + 1))
fi

# 3. 检查 Playwright
echo -e "${YELLOW}[3/8] Playwright${NC}"
if npx playwright --version &> /dev/null; then
    echo -e "   ${GREEN}✅ Playwright: $(npx playwright --version)${NC}"
else
    echo -e "   ${RED}❌ Playwright 未安装${NC}"
    ERRORS=$((ERRORS + 1))
fi

# 4. 检查浏览器
echo -e "${YELLOW}[4/8] 浏览器${NC}"
if [ -d "$HOME/.cache/ms-playwright" ]; then
    BROWSER_COUNT=$(ls -1 "$HOME/.cache/ms-playwright" 2>/dev/null | wc -l)
    if [ "$BROWSER_COUNT" -ge 3 ]; then
        echo -e "   ${GREEN}✅ 浏览器已安装 ($BROWSER_COUNT 个)${NC}"
    else
        echo -e "   ${YELLOW}⚠️  浏览器未完全安装，运行: npx playwright install${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  浏览器未安装，运行: npx playwright install${NC}"
fi

# 5. 检查 pytest
echo -e "${YELLOW}[5/8] pytest${NC}"
if pytest --version &> /dev/null; then
    echo -e "   ${GREEN}✅ pytest: $(pytest --version 2>&1 | head -1)${NC}"
else
    echo -e "   ${RED}❌ pytest 未安装${NC}"
    ERRORS=$((ERRORS + 1))
fi

# 6. 检查前端 node_modules
echo -e "${YELLOW}[6/8] 前端依赖${NC}"
if [ -d "frontend/node_modules" ]; then
    echo -e "   ${GREEN}✅ node_modules 已安装${NC}"
else
    echo -e "   ${YELLOW}⚠️  node_modules 未安装，运行: cd frontend && npm install${NC}"
fi

# 7. 检查后端虚拟环境
echo -e "${YELLOW}[7/8] 后端虚拟环境${NC}"
if [ -d "backend/.venv" ]; then
    echo -e "   ${GREEN}✅ 虚拟环境已创建${NC}"
else
    echo -e "   ${YELLOW}⚠️  虚拟环境未创建，运行: cd backend && python3 -m venv .venv${NC}"
fi

# 8. 检查服务端口
echo -e "${YELLOW}[8/8] 服务端口${NC}"
if lsof -i:60100 &> /dev/null 2>&1; then
    echo -e "   ${GREEN}✅ 前端端口 60100 已启动${NC}"
else
    echo -e "   ${YELLOW}⚠️  前端端口 60100 未启动${NC}"
fi

if lsof -i:8002 &> /dev/null 2>&1; then
    echo -e "   ${GREEN}✅ 后端端口 8002 已启动${NC}"
else
    echo -e "   ${YELLOW}⚠️  后端端口 8002 未启动${NC}"
fi

# 总结
echo ""
if [ "$ERRORS" -eq 0 ]; then
    echo -e "${GREEN}✅ 环境验证通过！${NC}"
    echo ""
    echo "运行测试："
    echo "  前端 E2E: cd frontend && npx playwright test"
    echo "  后端测试: cd backend && source .venv/bin/activate && pytest tests/"
else
    echo -e "${RED}❌ 发现 $ERRORS 个错误，请先修复${NC}"
    exit 1
fi
