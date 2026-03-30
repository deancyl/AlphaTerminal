#!/usr/bin/env bash
#===============================================================================
# AlphaTerminal Phase-1 初始化脚本
# 纯用户态，无 sudo 依赖
#===============================================================================

set -euo pipefail

#━━━ 0. 基础路径定义 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKSPACE_DIR="/vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal_Workspace"
BACKEND_DIR="${WORKSPACE_DIR}/backend"
FRONTEND_DIR="${WORKSPACE_DIR}/frontend"
CACHE_DIR="${BACKEND_DIR}/cache"
VENV_DIR="${BACKEND_DIR}/.venv"

#━━━ 1. 网络代理环境变量 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export http_proxy="http://192.168.1.50:7897"
export https_proxy="http://192.168.1.50:7897"
export no_proxy="localhost,127.0.0.1,::1,.local,*.minimax.chat,api.minimax.chat"

echo "[PROXY] http_proxy=${http_proxy}"
echo "[PROXY] https_proxy=${https_proxy}"
echo "[PROXY] no_proxy=${no_proxy}"

#━━━ 2. 创建物理目录结构 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "[DIRS] 创建目录结构..."
mkdir -p "${BACKEND_DIR}/app/models"
mkdir -p "${BACKEND_DIR}/app/routers"
mkdir -p "${BACKEND_DIR}/app/services"
mkdir -p "${BACKEND_DIR}/app/utils"
mkdir -p "${CACHE_DIR}"
mkdir -p "${FRONTEND_DIR}/src/components"
mkdir -p "${FRONTEND_DIR}/src/views"
mkdir -p "${FRONTEND_DIR}/src/stores"
mkdir -p "${FRONTEND_DIR}/src/assets"
mkdir -p "${FRONTEND_DIR}/public"
echo "[DIRS] 目录结构创建完成"

#━━━ 3. Python venv + requirements.txt ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "[PY] 初始化 Python 虚拟环境..."
python3 -m venv "${VENV_DIR}"
echo "[PY] venv 创建完成: ${VENV_DIR}"

# 生成 requirements.txt
cat > "${BACKEND_DIR}/requirements.txt" << 'EOF'
fastapi==0.115.0
uvicorn[standard]==0.30.6
akshare==1.14.20
sqlite3 (stdlib)
requests==2.32.3
python-dotenv==1.0.1
apscheduler==3.10.4
pydantic==2.9.2
pydantic-settings==2.5.2
httpx==0.27.2
yfinance==0.2.40
python-dateutil==2.9.0
EOF
echo "[PY] requirements.txt 已生成"

# 安装依赖
echo "[PY] 安装 Python 依赖（可能需要几分钟）..."
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r "${BACKEND_DIR}/requirements.txt"
echo "[PY] Python 依赖安装完成"

#━━━ 4. 初始化 SQLite WAL 缓存 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "[DB] 初始化 SQLite WAL 缓存数据库..."
"${VENV_DIR}/bin/python3" << 'EOF'
import sqlite3, os
db_path = os.path.join(os.getenv("CACHE_DIR", "/vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal_Workspace/backend/cache"), "alphaterminal.db")
conn = sqlite3.connect(db_path, check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL;")
conn.execute("PRAGMA synchronous=NORMAL;")
conn.execute("PRAGMA cache_size=-64000;")   # 64MB cache
conn.execute("PRAGMA temp_store=MEMORY;")
conn.execute("""
    CREATE TABLE IF NOT EXISTS market_data (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol      TEXT    NOT NULL,
        market      TEXT    NOT NULL,
        timestamp   INTEGER NOT NULL,
        open        REAL,
        high        REAL,
        low         REAL,
        close       REAL,
        volume      REAL,
        created_at  INTEGER DEFAULT (strftime('%s','now'))
    );
""")
conn.execute("""
    CREATE TABLE IF NOT EXISTS write_buffer (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol      TEXT    NOT NULL,
        market      TEXT    NOT NULL,
        timestamp   INTEGER NOT NULL,
        data        TEXT    NOT NULL,
        buffered_at INTEGER DEFAULT (strftime('%s','now'))
    );
""")
conn.execute("CREATE INDEX IF NOT EXISTS idx_market_symbol_ts ON market_data(symbol, timestamp);")
conn.commit()
conn.close()
print(f"[DB] SQLite WAL 模式数据库已初始化: {db_path}")
EOF
echo "[DB] SQLite 初始化完成"

#━━━ 5. Vue3 前端脚手架 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "[NPM] 初始化 Vue3 前端（Vite）..."
cd "${FRONTEND_DIR}"

# 使用 Vite 创建 Vue3 项目（非交互模式）
npm create vite@latest . -- --template vue \
  --yes 2>/dev/null || \
  npx --yes create-vite@latest . --template vue

echo "[NPM] 安装前端基础依赖..."
npm install

echo "[NPM] 安装 TailwindCSS + ECharts + 网格拖拽库..."
npm install --save-dev tailwindcss@3 postcss autoprefixer
npx tailwindcss init -p
npm install echarts vue-echarts @vueuse/core
npm install vue-grid-layout   # 网格拖拽布局
echo "[NPM] 前端依赖安装完成"

#━━━ 6. 目录树输出 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " AlphaTerminal_Workspace 目录结构"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
find "${WORKSPACE_DIR}" -not -path "*/node_modules/*" \
  -not -path "*/.venv/*"    \
  -not -path "*/.git/*"     \
  -not -path "*/dist/*"     \
  -not -path "*/__pycache__/*" \
  | sort | while read -r p; do
    if [ -d "$p" ]; then
      depth=$(echo "$p" | tr -cd '/' | wc -c)
      indent=$(printf '%*s' "$((depth - ${WORKSPACE_DIR//\//}))" '' | tr ' ' '  ')
      echo "${indent}├── $(basename "$p")/"
    else
      depth=$(echo "$p" | tr -cd '/' | wc -c)
      indent=$(printf '%*s' "$((depth - ${WORKSPACE_DIR//\//}))" '' | tr ' ' '  ')
      echo "${indent}├── $(basename "$p")"
    fi
  done

echo ""
echo "[DONE] AlphaTerminal Phase-1 初始化完成！"
echo "后端 venv: ${VENV_DIR}"
echo "前端  node_modules 已就绪"
echo "缓存  SQLite WAL: ${CACHE_DIR}/alphaterminal.db"
