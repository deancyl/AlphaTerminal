# AlphaTerminal 本地部署与运维指南

> 本指南面向零基础用户，涵盖 Python 环境搭建、依赖安装、后端/前端启动、网络代理配置及常见问题排查。  
> **预计完成时间**：15~30 分钟 | **费用**：免费（数据源全部来自 AkShare + Sina + 东方财富）

---

## 📋 目录

1. [环境要求](#环境要求)
2. [后端部署](#后端部署)
3. [前端部署](#前端部署)
4. [网络与代理配置](#网络与代理配置)
5. [常见问题排查](#常见问题排查)
6. [运维命令速查](#运维命令速查)
7. [架构进阶说明](#架构进阶说明)

---

## 🖥️ 环境要求

| 组件 | 版本要求 | 说明 |
|------|----------|------|
| Python | ≥ 3.10 | 推荐 3.11，GPU 非必须 |
| Node.js | ≥ 18 | 推荐 20 LTS |
| npm | ≥ 9 | 随 Node.js 附带 |
| 系统 | Linux / macOS / Windows (WSL) | 推荐 Linux 或 WSL2 |
| 网络 | 中国大陆网络 **或** 配置代理 | AkShare 数据源位于国内服务器 |

---

## 🔧 后端部署

### Step 1：拉取代码

```bash
git clone https://github.com/deancyl/AlphaTerminal.git
cd AlphaTerminal
```

> ⚠️ **注意**：如果 `git clone` 因 GFW 失败，可以直接下载 ZIP 包（GitHub 页面 → Code → Download ZIP），解压后进入目录。

### Step 2：创建 Python 虚拟环境

```bash
cd backend

# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境（每次新终端都需要）
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate.bat
```

激活成功后，终端前缀会变成 `(.venv) [路径]$`。

### Step 3：安装 Python 依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**关键依赖说明**：

| 包 | 版本 | 作用 |
|----|------|------|
| fastapi | ≥ 0.115 | Web 框架 |
| uvicorn | ≥ 0.30 | ASGI 服务器 |
| akshare | ≥ 1.18 | A股/宏观数据（**需要国内网络**） |
| apscheduler | ≥ 3.10 | 后台定时任务 |
| requests | ≥ 2.28 | HTTP 客户端 |
| numpy | ≥ 1.24 | 数据计算 |
| pandas | ≥ 2.0 | 数据分析 |

> 💡 **如果 pip install 超时或报错**：国内用户建议配置 pip 镜像：
> ```bash
> pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
> ```

### Step 4：初始化数据库

```bash
# 首次启动时，APScheduler 会自动创建 SQLite 数据库和表
# 如需手动初始化：
python -c "from app.db import init_tables; init_tables(); print('DB initialized')"
```

### Step 5：启动后端服务

```bash
# 方式一：直接启动（前台运行）
source .venv/bin/activate
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8002

# 方式二：后台运行（推荐，关闭终端后仍保持运行）
nohup .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 > backend.log 2>&1 &

# 方式三：使用启动脚本
.venv/bin/python start_backend.py
```

### Step 6：验证后端运行状态

```bash
# 检查进程
ps aux | grep uvicorn | grep 8002

# 检查健康端点
curl http://localhost:8002/health
# 期望输出：{"status":"ok","service":"AlphaTerminal"}

# 检查调度器状态
curl http://localhost:8002/api/v1/debug/scheduler
# 期望输出：{"news_last_success":"2026-03-31 21:20:34","spot_cache_ready":true}
```

**成功标志**：
```
✅ uvicorn 进程存在
✅ GET /health 返回 200
✅ spot_cache_ready: true（新闻缓存已就绪）
```

---

## 🌐 前端部署

### Step 1：安装 Node 依赖

```bash
cd frontend
npm install
```

> ⚠️ 如果 npm install 极慢，配置国内镜像：
> ```bash
> npm config set registry https://registry.npmmirror.com
> npm install
> ```

### Step 2：启动前端开发服务器

```bash
# 前端运行在 60100 端口，/api 请求代理到后端 8002
npm run dev

# 局域网访问（用于手机/其他设备测试）：
npm run dev -- --host 0.0.0.0 --port 60100
```

### Step 3：访问 AlphaTerminal

打开浏览器访问：

| 地址 | 说明 |
|------|------|
| `http://localhost:60100` | 本机访问 |
| `http://<本机IP>:60100` | 局域网其他设备访问 |

> 💡 **如何查看本机 IP**：
> ```bash
> # Linux/macOS:
> hostname -I | awk '{print $1}'
> # Windows (PowerShell):
> ipconfig | findstr "IPv4"
> ```

---

## 🌏 网络与代理配置

### 为什么需要代理？

AlphaTerminal 的数据源（AkShare / 东方财富 / Sina）服务器位于**中国大陆**。如果你在海外或公司网络有防火墙，需要配置代理才能访问。

### 方法一：环境变量配置（推荐）

```bash
# Linux/macOS - 在 ~/.bashrc 或 ~/.zshrc 中添加：
export http_proxy="http://192.168.1.50:7897"
export https_proxy="http://192.168.1.50:7897"

# 生效：
source ~/.bashrc

# 验证代理是否生效：
curl -s https://www.eastmoney.com | head -3
```

### 方法二：Docker / 系统代理设置

如果你使用 Clash、V2Ray 等代理工具，确保代理软件：
1. 监听在局域网地址（如 `192.168.1.50:7897`）
2. 勾选"支持局域网连接"或"Allow LAN"
3. 代理协议为 HTTP（而非 SOCKS5）

### 方法三：使用国内镜像源（pip / npm）

```bash
# pip 镜像（解决 Python 包安装问题）
pip install akshare -i https://pypi.tuna.tsinghua.edu.cn/simple

# npm 镜像（解决 Node 包安装问题）
npm config set registry https://registry.npmmirror.com
```

---

## 🔴 常见问题排查

### Q1：后端启动报错 `ModuleNotFoundError: No module named 'akshare'`

**原因**：虚拟环境未激活，或依赖未安装完整。

```bash
# 确认虚拟环境已激活（应该有 .venv 前缀）
source .venv/bin/activate
pip install akshare
python -c "import akshare; print(akshare.__version__)"
```

### Q2：后端启动报错 `Port 8002 is already in use`

**原因**：端口被其他进程占用。

```bash
# 查找并杀死占用端口的进程
lsof -ti :8002 | xargs kill -9
# 或：
pkill -f "uvicorn.*8002"
# 然后重新启动后端
```

### Q3：前端刷新页面卡顿 20 秒

**原因**：查看后端日志，`/market/sectors` 接口正在同步调用 akshare（被阻塞）。  
**解决方案**：确保使用最新代码（v0.1.0-beta），该问题已在 Beta 版本中修复为后台缓存模式。

```bash
# 验证 sectors 接口响应时间：
curl -w "\n耗时: %{time_total}s\n" http://localhost:8002/api/v1/market/sectors
# 期望：< 0.01s（约 3~5ms）
```

### Q4：新闻一直显示"正在加载..."，从不更新

**原因**：首次启动时新闻预热需要 2~3 分钟。

```bash
# 检查新闻缓存是否就绪：
curl http://localhost:8002/api/v1/debug/scheduler
# 如果 news_last_success 显示时间戳，说明新闻已加载

# 手动触发新闻刷新：
curl -X POST http://localhost:8002/api/v1/debug/trigger
```

### Q5：`git push` 报错 `gnutls_handshake() failed`

**原因**：代理与 git-remote-https（GnuTLS）不兼容。  
**解决方案**：使用 REST API 绕过 git push：

```bash
# 方法一：使用 GitHub REST API 推送文件
# （参考项目 issues 或使用 GitHub CLI）
gh auth login
gh repo clone deancyl/AlphaTerminal
# 修改后 push：
gh repo push

# 方法二：配置 SSH over nc 代理
# 编辑 ~/.ssh/config：
Host github.com
    Hostname github.com
    Port 443
    ProxyCommand nc -X connect -x <代理地址>:<端口> %h %p
```

### Q6：K 线图不显示数据

**原因**：日K 历史数据需要等待后台定时任务回填（每日收盘后）。

```bash
# 检查 K 线数据是否已回填：
curl "http://localhost:8002/api/v1/market/history/000001?period=daily" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('K线数据条数:', len(d.get('history',[])))"
# 期望输出：K线数据条数: >100
```

### Q7：代理端口 7897 无法连接

**原因**：代理软件未启动，或监听地址不是 `0.0.0.0`（仅监听 localhost）。

**解决方案**：
1. 打开代理软件设置 → 监听地址改为 `0.0.0.0` 或局域网 IP
2. 重启代理软件
3. 验证：`curl -s --max-time 5 -x http://192.168.1.50:7897 https://www.eastmoney.com`

---

### Q8：前端启动报错 `Exit 127: node: not found`，但 `npm install` 明明成功了

**原因**：Node.js 安装在非标准路径（如 `/var/apps/nodejs_v22/target/bin/`），Shell 的 `PATH` 环境变量未包含该路径。

**诊断**：
```bash
which node     # 如果返回空，说明 PATH 未包含
echo $PATH
```

**解决方案（方案一：永久修改 PATH）**：
```bash
# 在 ~/.bashrc 或 ~/.profile 中添加：
echo 'export PATH="/var/apps/nodejs_v22/target/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
which node   # 应返回 /var/apps/nodejs_v22/target/bin/node
```

**解决方案（方案二：使用绝对路径启动 Vite）**：
```bash
cd frontend
/var/apps/nodejs_v22/target/bin/node \
  ./node_modules/vite/bin/vite.js \
  --host 0.0.0.0 --port 60100
```

**验证**：
```bash
node --version   # 应显示 v22.18.0
npm --version    # 应显示 10.9.3
curl http://localhost:60100/   # 应返回 HTML
```

---

## ⚙️ 运维命令速查

```bash
# ── 后端管理 ──────────────────────────────────────────────────
# 启动后端
cd backend && source .venv/bin/activate
nohup .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 > backend.log 2>&1 &

# 重启后端
pkill -f "uvicorn.*8002"; sleep 2; nohup .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 > backend.log 2>&1 &

# 查看后端日志
tail -f backend.log

# 检查后端状态
curl http://localhost:8002/health

# 检查调度器心跳
curl http://localhost:8002/api/v1/debug/scheduler | python3 -m json.tool

# 手动触发全量刷新
curl -X POST http://localhost:8002/api/v1/debug/trigger

# ── 前端管理 ──────────────────────────────────────────────────
# 启动前端
cd frontend && npm run dev

# 重新安装依赖
cd frontend && rm -rf node_modules && npm install

# ── 数据库管理 ─────────────────────────────────────────────────
# 查看数据库大小
ls -lh backend/cache/alphaterminal.db

# 备份数据库
cp backend/cache/alphaterminal.db /tmp/alphaterminal_backup_$(date +%Y%m%d).db

# 清空实时数据表（保留结构）
sqlite3 backend/cache/alphaterminal.db "DELETE FROM market_data_realtime;"
```

---

## 🏗️ 架构进阶说明

### 为什么 API 这么快？（< 10ms）

传统架构：`API 请求 → 同步调用 AkShare → 等待网络响应（10~20秒）`

AlphaTerminal 优化后的架构：

```
API 请求 (< 1ms)
    ↓
读取内存缓存（SectorsCache / SpotCache / NewsCache）
    ↓
直接返回 JSON

────────────────────────── 分割线 ──────────────────────────

后台线程（每 3~20 分钟运行）
    ↓
调用 AkShare / Sina / 东方财富
    ↓
写入全局缓存变量（进程内存）
```

**核心设计原则**：API 路由**绝对禁止**同步调用外部网络接口，所有数据拉取必须扔进后台线程。

### 数据库 WAL 模式的优势

AlphaTerminal 使用 SQLite WAL（Write-Ahead Logging）模式：

| 模式 | 写入并发 | 读取并发 | 适用场景 |
|------|----------|----------|----------|
| DELETE journal | ❌ 互斥 | ✅ 可并发 | 低并发 |
| WAL（AlphaTerminal 采用） | ✅ 可并发写入 | ✅ 读写可并发 | 高并发写入 |

```python
# WAL 模式在 database.py 中已配置：
conn.execute("PRAGMA journal_mode=WAL")
```

### 后台任务调度（APScheduler）

```python
# 每 3 分钟：拉取全市场数据 → 写入 write_buffer
scheduler.add_job(fetch_all_and_buffer, "interval", seconds=180)

# 每 3 分钟：Sina HQ 刷新个股情绪缓存
scheduler.add_job(trigger_spot_fetch, "interval", seconds=180)

# 每 5 分钟：刷新行业板块缓存
scheduler.add_job(_sectors_job, "interval", seconds=300)

# 每 20 分钟：多源新闻轮询
scheduler.add_job(trigger_news_fetch, "interval", seconds=1200)

# 每 10 秒：write_buffer → market_data_realtime
scheduler.add_job(flush_write_buffer, "interval", seconds=10)
```

### 沪深 300 熔断机制

为防止全量 5000+ 股票抓取导致网络超时，AlphaTerminal 采用 HS300 成分股熔断策略：

```python
# sina_hq_fetcher.py
HS300_POOL = get_hs300_pool()  # 最多 100 只
FOCUS_STOCKS = 15 只蓝筹  # 熔断兜底

def get_stock_pool():
    if _HS300_POOL:
        return _HS300_POOL  # 优先 HS300，最多 100 只
    return FOCUS_STOCKS     # 备选 15 只
```

---

### Q9：后端启动报错 `sqlite3.OperationalError: attempt to write a readonly database`

**原因**：数据库文件或所在目录对当前进程 UID 没有写权限。常见于：
- DB 文件在 SSHFS/FUSE 挂载点上（挂载层强制只读）
- DB 文件权限为 `rw-------`（仅 owner 可写）
- 进程以非文件 owner 的 UID 运行

**诊断**：
```bash
# 检查文件权限和 owner
ls -la /home/deancyl0607/alpha_ultimate.db
# 检查目录权限
ls -ld /home/deancyl0607/
# 检查当前用户 UID
id
```

**解决方案（按优先级）**：

**方案 A：修改文件权限（推荐，最简单）**：
```bash
chmod 666 /home/deancyl0607/alpha_ultimate.db
```

**方案 B：使用 /tmp 本地临时数据库（开发环境）**：
AlphaTerminal 会自动降级为 `/tmp/alpha_ultimate_active.db`（WAL 正常）

**方案 C：修改目录权限**：
```bash
chmod 777 /home/deancyl0607/
chmod 666 /home/deancyl0607/alpha_ultimate.db
```

**方案 D：若遇 SSHFS 强制只读（挂载层限制）**：
```bash
# 将 DB 复制到本地 /tmp，从那里启动
cp /home/deancyl0607/alpha_ultimate.db /tmp/alpha_ultimate_active.db
# AlphaTerminal 会自动使用 /tmp 路径（已内置降级逻辑）
```

**验证修复**：
```bash
python3 -c "
import sqlite3
db = '/home/deancyl0607/alpha_ultimate.db'
conn = sqlite3.connect(db, timeout=5)
conn.execute('PRAGMA journal_mode=WAL')
cnt = conn.execute('SELECT COUNT(*) FROM market_data_realtime').fetchone()[0]
print('OK, realtime rows:', cnt)
conn.close()
"
```

---

## 📞 获取帮助

- **GitHub Issues**: https://github.com/deancyl/AlphaTerminal/issues
- **讨论区**: GitHub Discussions

---

*最后更新：2026-03-31 | AlphaTerminal v0.1.0-beta*
