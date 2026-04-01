# 事件报告：AlphaTerminal Beta-0.3.1 精准增量灾难

**日期**：2026-04-01
**影响版本**：Phase 5-8（从未成功发布）
**根本原因**：SSHFS 死锁 + git cherry-pick 误判 + 数据库版本混乱
**恢复耗时**：约 6 小时
**恢复 Commit**：`0125dca`

---

## 📋 事件摘要

2026-04-01 上午，AlphaTerminal 项目在尝试发布 Beta-0.3.0 时遭遇多重并发故障。所有 Phase 5-8 代码（侧边栏多视图、债券/期货面板、数据源注册表）以 **dangling commit** 形式存在于本地，从未成功合入 `origin/master`。

---

## 🔍 根本原因分析

### 1. Symbol 为 Key 导致的验证误判

**现象**：物理探针 `curl /api/v1/market/overview` 返回 `wind keys: []`，grep 验证结果始终为 0。

**根因**：`market_overview()` API 返回结构为 **`{symbol: {name, price, change_pct, ...}}`**（字典），而非 `[{symbol, name, price, ...}]`（列表）。验证脚本使用列表长度检查 `len(w)`，始终为 0。

```python
# 错误验证方式（列表逻辑）
rows = d.get('wind', [])
print(len(rows))  # 永远为 0

# 正确验证方式（字典逻辑）
w = d.get('wind', {})
print(len(w))     # 返回指数数量（4 或 6）
```

**教训**：修改核心接口前，必须溯源"生产者"（抓取逻辑）和"消费者"（API 路由），确保全链路契约对齐。

---

### 2. Node 路径脱节（Exit 127）

**现象**：初始化脚本 `init_alphaterminal.sh` 成功执行 `npm install`，但人类在物理终端执行 `which node` 返回空。

**根因**：Node.js 安装在非标准路径 `/var/apps/nodejs_v22/target/bin/`，Shell 的 `PATH` 环境变量未包含该路径。不同 shell 会话（login shell vs non-login shell）有不同的 PATH 初始化逻辑。

**物理路径确认**：
```
/var/apps/nodejs_v22/target/bin/node   (v22.18.0)
/var/apps/nodejs_v22/target/bin/npm    (10.9.3)
```

**解决方案**：
```bash
# 方案一：永久修改 PATH
echo 'export PATH="/var/apps/nodejs_v22/target/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 方案二：使用绝对路径启动 Vite
/var/apps/nodejs_v22/target/bin/node ./node_modules/vite/bin/vite.js --host 0.0.0.0 --port 60100
```

**教训**：AI 容易产生"路径幻觉"，必须验证文件系统真实权属和进程间隔离性。

---

### 3. 多进程内存孤岛（SQLite 死锁）

**现象**：`init_tables()` 在 `PRAGMA journal_mode=WAL` 处卡死，后端启动失败，前端全白。

**根因**：
- 数据库文件放在 `/vol3/@apphome/trim.openclaw/`（SSHFS 挂载点）
- SSHFS 不支持 SQLite WAL 模式的 `mmap()` 系统调用，导致写操作永久阻塞
- 容器内 PID 1 (`/opt/bin/openclaw.sh`) 会清理孤儿 `exec` 子进程（SIGTERM），已启动的后端被意外终止

**附加问题**：
- 三个数据库版本同时存在：
  - `/tmp/alphaterminal.db`（残留测试文件）
  - `/tmp/alphaterminal_v2.db`（另一测试文件）
  - `/home/deancyl0607/alpha_ultimate.db`（生产文件）
- 新启动的后端尝试读写残留的只读/损坏 db 文件，持续报 `attempt to write a readonly database`

**教训**：SQLite 绝对不能放在 SSHFS/FUSE 网络文件系统上；发版前必须验证前端真实渲染。

---

## 🛠️ 恢复步骤

### 精准时间线打捞

1. **定位黄金节点**：`git reflog` 找到 `fe688ed`（Phase 7 VHSI 真实数据 + 热力图修复），此时 Phase 5-7 代码完整存在
2. **执行读档**：`git reset --hard fe688ed` + `git clean -fd`
3. **逐个 Cherry-pick**：f87ea20 → 3f46a2d → 773402f → 16dda82（每步验证后再推进）
4. **冲突解决策略**：保留 Phase 7 更完整版本（fe688ed 包含更新的代码）

### 关键代码修复

| 修复 | 文件 | 变更 |
|------|------|------|
| RLock 死锁 | `backend/app/routers/market.py` | `threading.Lock()` → `threading.RLock()` |
| ECharts 溢出 | `BondDashboard.vue` | `+ overflow-hidden relative min-h-0` |
| ECharts 溢出 | `FuturesDashboard.vue` | `+ overflow-hidden relative min-h-0` |
| `_parse_sina_index` | `backend/app/services/data_fetcher.py` | `len < 10` → `len < 6` |
| Wind 6 指数 | `backend/app/routers/market.py` | `WIND_SYMBOLS` 新增 399001/399006 |
| data_sources 注册表 | `backend/app/config/data_sources.py` | 新建 147 行配置 |

### 数据库迁移

- **生产路径**：`/home/deancyl0607/alpha_ultimate.db`（deancyl0607 用户目录，本地磁盘）
- **DB_PATH 修改**：`database.py` 中 `_db_path` 硬编码为生产路径

---

## 📊 验证结果

| 指标 | 修复前 | Beta 0.3.1 |
|------|--------|-----------|
| Wind 指数数量 | 4（含 000001/000300/HSI/IXIC） | **6**（新增 399001/399006） |
| 深证成指价格 | 0 | **13706.52** |
| 创业板指价格 | 0 | **3247.52** |
| ECharts 图表 | 溢出/塌陷 | **正常渲染** |
| Bond 接口 | 500 错误 | **8 期限曲线** |
| Futures 接口 | 500 错误 | **IF/IC/IM 3 品种** |
| Git 合入状态 | Dangling commits | **0125dca 强制推送** |

---

## 🚨 触发事件时间线

```
07:09  f87ea20 Phase 5 RLock 修复（未合入 master）
07:27  3f46a2d Phase 6 UI 组件（未合入 master）
08:10  773402f Phase 7 bond/futures 路由（未合入 master）
08:56  fe688ed Phase 7 VHSI 真实数据 ✅ 黄金节点
10:58  16dda82 Phase 8 data_sources（灾难触发点，未合入 master）
12:40  0e5d1c5 Beta-0.3.0 fixes（从未发布）
13:33  82bba4e Beta-0.3.0 重建（从未发布）
16:42  重置到 origin/master（Beta-0.2.3 基线）
19:03  0125dca Phase 5-8 精准增量合入 ✅
```

### 4. 000001 张冠李戴（11.xx 错误价格）

**现象**：上证指数分时图显示价格为 11.xx（平安银行股价）。

**根因**：`fetch_index_minute_history` 使用 `startswith("000")` 模糊判断交易所：
```python
if symbol.startswith("000") or symbol.startswith("399"):
    secid = f"0.{symbol}"   # 深圳 ← 000001 进入此分支
else:
    secid = f"1.{symbol}"   # 上海
```
`000001`（上证指数）被错误判定为深圳交易所 → secid=`0.000001` → 平安银行（深交所）→ 价格 11.xx。

**正确映射**：
```python
_INDEX_SECID_MAP = {
    "000001": "1.000001",  # 上证指数（上海）
    "000300": "1.000300",  # 沪深300（上海）
    "399001": "0.399001",  # 深证成指（深圳）
    "399006": "0.399006",  # 创业板指（深圳）
}
```

**教训**：股票代码与指数代码不能使用相同的 `startswith` 逻辑，必须用精确映射表。

---

## 💡 工程改进建议

1. **数据库路径验证**：在 `init_tables()` 启动前增加文件系统类型检查，拒绝在 SSHFS/FUSE 上初始化 WAL 模式
2. **发版前检查清单**：
   - [ ] 前端真实页面截图验证
   - [ ] 数据库路径确认为本地磁盘
   - [ ] 所有 API 端点物理探针
   - [ ] Git cherry-pick 后立即验证
3. **文档强制更新**：每次架构变更后更新 KNOWN_ISSUES_TODO.md

---

## ✅ 修复后状态

- **Git HEAD**：`0125dca Phase 5-8 recovery`
- **origin/master**：已强制更新
- **后端端口**：8002（PID 1328687）
- **前端端口**：60100
- **数据库**：`/home/deancyl0607/alpha_ultimate.db`
- **Wind 6 指数**：全非零 ✅
- **Bond/Futures API**：200 OK ✅
- **ECharts 溢出**：已修复 ✅
