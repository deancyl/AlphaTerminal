#!/bin/bash
# scripts/setup-e2e.sh - E2E 测试环境一键安装

set -e

echo "🚀 开始安装 E2E 测试环境..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 检查 Node.js
echo -e "\n${YELLOW}[1/6] 检查 Node.js...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js 未安装，请先安装 Node.js 18+${NC}"
    echo "   推荐使用 nvm 安装: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
    exit 1
fi

NODE_VERSION=$(node -v | cut -d 'v' -f 2 | cut -d '.' -f 1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo -e "${RED}❌ Node.js 版本过低: $(node -v)，需要 18+${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Node.js: $(node -v)${NC}"

# 2. 检查 Python
echo -e "\n${YELLOW}[2/6] 检查 Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 未安装，请先安装 Python 3.10+${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(sys.version_info.major * 10 + sys.version_info.minor)')
if [ "$PYTHON_VERSION" -lt 310 ]; then
    echo -e "${RED}❌ Python 版本过低: $(python3 --version)，需要 3.10+${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python: $(python3 --version)${NC}"

# 3. 安装前端依赖
echo -e "\n${YELLOW}[3/6] 安装前端依赖...${NC}"
cd frontend
if [ ! -d "node_modules" ]; then
    npm install
else
    echo "   node_modules 已存在，跳过 npm install"
fi

# 安装 Playwright 浏览器
echo -e "\n${YELLOW}[4/6] 安装 Playwright 浏览器...${NC}"
if command -v npx &> /dev/null; then
    npx playwright install --with-deps 2>/dev/null || npx playwright install
    echo -e "${GREEN}✅ Playwright 浏览器已安装${NC}"
else
    echo -e "${RED}❌ npx 不可用${NC}"
    exit 1
fi
cd ..

# 4. 安装后端依赖
echo -e "\n${YELLOW}[5/6] 安装后端依赖...${NC}"
cd backend
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "${GREEN}✅ 创建虚拟环境${NC}"
fi

source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null
pip install -q --upgrade pip

if [ -f "requirements.txt" ]; then
    pip install -q -r requirements.txt
fi

# 安装测试依赖
pip install -q pytest pytest-asyncio pytest-cov httpx respx faker freezegun pytest-mock 2>/dev/null || \
    pip install pytest pytest-asyncio pytest-cov httpx respx faker freezegun pytest-mock

echo -e "${GREEN}✅ 后端依赖已安装${NC}"
cd ..

# 5. 创建测试目录
echo -e "\n${YELLOW}[6/6] 创建测试目录...${NC}"
mkdir -p frontend/tests/e2e
mkdir -p frontend/tests/mocks
mkdir -p frontend/test-results/screenshots
mkdir -p frontend/test-results/videos
mkdir -p frontend/test-results/traces
mkdir -p backend/tests/e2e
mkdir -p backend/tests/integration
echo -e "${GREEN}✅ 测试目录已创建${NC}"

# 6. 验证安装
echo -e "\n${YELLOW}验证安装...${NC}"
echo -e "   Playwright: $(npx playwright --version)"
echo -e "   pytest: $(pytest --version 2>&1 | head -1)"

echo -e "\n${GREEN}✅ E2E 测试环境安装完成！${NC}"
echo ""
echo "运行测试："
echo "  前端 E2E: cd frontend && npx playwright test"
echo "  后端测试: cd backend && source .venv/bin/activate && pytest tests/"
echo ""
echo "查看测试计划："
echo "  cat docs/E2E_TEST_PLAN.md"
echo "  cat docs/E2E_DEPENDENCIES.md"
