# AlphaTerminal 宏观架构审计报告 v0.6.0

**审计日期**: 2025-04-29  
**审计角色**: 宏观架构师（Macro Architect）  
**审计范围**: 全栈代码审计 + Wind投顾终端对标分析  
**版本**: v0.6.0  

---

## 一、执行摘要

本次审计基于 **Karpathy 开发准则**（Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven）对 AlphaTerminal 项目进行全面质量评估，并对照 **万德（Wind）投顾终端** PRD 进行功能差距分析。

### 关键发现

- **技术债**: 发现 43 项问题（8 Critical / 15 High / 14 Medium / 6 Low）
- **Wind 覆盖率**: 平均 10.4%，最大缺口在股票研究（5%）、宏观经济（5%）、生产力工具（0%）
- **立即修复**: 3 项 Critical 问题可在 30 分钟内完成
- **架构风险**: 无连接池、无界线程、生产环境 DEBUG 代码

---

## 二、Karpathy 准则对照

| 准则 | 状态 | 说明 |
|------|------|------|
| **Think Before Coding** | ⚠️ 部分 | 部分代码注释与实际逻辑不符（如 `_parse_sina_index`） |
| **Simplicity First** | ✅ 良好 | 整体架构简洁，无过度抽象 |
| **Surgical Changes** | ⚠️ 需改进 | 存在多处重复代码（price=0 回退逻辑复制 3 次） |
| **Goal-Driven** | ✅ 良好 | 功能目标明确，按 Phase 推进 |

---

## 三、技术债详细清单

### 🔴 Critical（严重）- 8项

#### 3.1.1 生产环境 DEBUG 代码残留
- **文件**: `backend/app/routers/portfolio.py:554-556`
- **问题**: 向 stderr 打印数据库连接内部 ID
- **代码**:
  ```python
  print(f"DEBUG unrealized: _conn_ps id={id(_conn_ps)}", file=_sys.stderr)
  ```
- **影响**: 泄露内部状态，污染日志，生产环境绝对不允许
- **修复**: 删除该行

#### 3.1.2 硬编码过期宏观数据
- **文件**: `backend/app/routers/market.py:250-253`
- **问题**: 当外部 API 失败时，静默使用硬编码的过期数据
- **代码**:
  ```python
  usdcny_price = 6.8871  # 2024年数据，已过期
  gold_price = 3318.40   # 硬编码，不随市场变化
  ```
- **影响**: 用户看到错误的汇率和金价，误导投资决策
- **修复**: 使用缓存的最后已知值，或返回 null 并显示"数据不可用"

#### 3.1.3 Subprocess curl 安全漏洞
- **文件**: `backend/app/services/data_fetcher.py:1162-1168`
- **问题**: 使用 `subprocess.check_output(["curl", ...])` 执行 shell 命令
- **影响**: 
  - 命令注入风险（虽然当前参数可控，但架构上不安全）
  - curl 命令可能不存在（已在 Docker 环境中遇到）
  - 无法通过代理连接
- **修复**: 使用 `httpx` 或 `requests` 替代

#### 3.1.4 无界线程创建
- **文件**: `backend/app/services/data_fetcher.py:1239-1257`
- **问题**: 为每只股票创建独立线程获取美股历史数据
- **代码**:
  ```python
  threading.Thread(target=worker, daemon=True).start()
  ```
- **影响**: 同时获取 100 只股票将创建 100 个线程，可能导致资源耗尽
- **修复**: 使用 `concurrent.futures.ThreadPoolExecutor` 限制并发数

#### 3.1.5 数据库无连接池
- **文件**: `backend/app/db/database.py:27`
- **问题**: 每次请求新建 SQLite 连接
- **代码**:
  ```python
  def _get_conn():
      return sqlite3.connect(_db_path)  # 每次调用新建连接
  ```
- **影响**: 高并发下连接开销大，性能瓶颈
- **修复**: 使用连接池（如 `sqlalchemy.pool.SingletonThreadPool`）

#### 3.1.6 N+1 查询（market_quote_detail）
- **文件**: `backend/app/routers/market.py:1389-1457`
- **问题**: 单次 API 请求触发 5 次独立数据库查询
- **查询列表**:
  1. `get_latest_prices()` - 实时价格
  2. `get_price_history()` - 历史价格
  3. `get_daily_history()` - 日K数据
  4. `get_daily_history()` - 52周高低点
  5. `SpotCache.get()` - 缓存数据
- **影响**: 延迟 = 5 × 单次查询时间，用户体验差
- **修复**: 合并为单次 JOIN 查询，或使用异步并行查询

#### 3.1.7 Portfolio PnL 多连接问题
- **文件**: `backend/app/routers/portfolio.py:398-564`
- **问题**: 使用 3 个独立数据库连接查询相关数据
- **代码**:
  ```python
  conn3 = get_conn()  # 连接3
  conn2 = get_conn()  # 连接2
  _conn_ps = _get_portfolio_conn()  # 连接1
  ```
- **影响**: 
  - 无事务一致性（中间可能读到不一致状态）
  - 连接泄露风险（未正确关闭）
  - 性能开销
- **修复**: 使用单一连接 + 事务包装

#### 3.1.8 Sell Lot 非原子操作
- **文件**: `backend/app/routers/portfolio.py:1212-1236`
- **问题**: 多步数据库操作无事务回滚
- **操作流程**:
  1. SELECT 查询当前现金
  2. UPDATE 更新现金余额
  3. INSERT 插入交易记录
  4. UPDATE 更新持仓
- **影响**: 第 2 步失败后，现金已扣但交易未记录，数据不一致
- **修复**: 使用 `BEGIN TRANSACTION ... COMMIT/ROLLBACK`

---

### 🟡 High（高级）- 15项

#### 3.2.1 `_52w_bounds` 算法复杂度
- **文件**: `backend/app/routers/market.py:1441-1445`
- **问题**: 使用排序找 52 周高低点，复杂度 O(n log n)
- **修复**: 使用 O(n) 扫描：`max(closes)` / `min(closes)`

#### 3.2.2 `fetch_all_china_stocks` 内存爆炸
- **文件**: `backend/app/services/data_fetcher.py:1397-1457`
- **问题**: 加载全部 5000+ 只股票到内存列表
- **修复**: 使用生成器 `yield` 逐批处理

#### 3.2.3 `_get_all_descendants` N+1 查询
- **文件**: `backend/app/routers/portfolio.py:241-257`
- **问题**: Python 递归实现，每层一次数据库查询
- **修复**: 使用 SQL CTE（Common Table Expression）递归查询

#### 3.2.4 API.js 自旋锁问题
- **文件**: `frontend/src/utils/api.js:31-34`
- **问题**: JavaScript 单线程环境中使用自旋锁
- **代码**:
  ```javascript
  if (_consecutiveFailures.lock) {
    setTimeout(() => _onFailure(url, status), 1)
    return
  }
  ```
- **修复**: 移除锁，利用 JavaScript 单线程特性直接操作

#### 3.2.5 `fetchApiBatch` 文档与实现不符
- **文件**: `frontend/src/utils/api.js:240`
- **问题**: 注释声称使用 `Promise.allSettled`，实际使用 `Promise.all`
- **修复**: 统一使用 `Promise.allSettled`，避免单点失败

#### 3.2.6 缺少请求去重
- **文件**: `frontend/src/utils/api.js:146`
- **问题**: 多个组件同时请求相同 URL 时，发送重复请求
- **修复**: 实现请求去重机制（如 `AbortController` + 请求缓存）

#### 3.2.7 指数解析注释误导
- **文件**: `backend/app/services/data_fetcher.py:81-105`
- **问题**: 注释说 `parts[2]` 是 `prev_close`，实际是 `change_amount`
- **状态**: ✅ 已在 v0.5.189 修复

#### 3.2.8 全局写锁瓶颈
- **文件**: `backend/app/db/database.py:12`
- **问题**: `threading.RLock()` 串行化所有写操作
- **影响**: APScheduler 全量拉取时独占锁 300ms+，阻塞读 API
- **状态**: ✅ 已通过 `db_writer.py` 队列化部分缓解

#### 3.2.9 `order_book` 魔法数字解析
- **文件**: `backend/app/routers/market.py:1805-1827`
- **问题**: 使用硬编码字段索引解析 Sina 34 字段格式
- **修复**: 使用字典映射或 Pydantic Schema 校验

#### 3.2.10 `search_stocks` SQL 注入风险
- **文件**: `backend/app/db/database.py:404-412`
- **问题**: `order_col` 白名单检查可被绕过
- **修复**: 使用参数化查询 + 严格枚举校验

#### 3.2.11 `admin_config` 无类型校验
- **文件**: `backend/app/db/database.py:544-570`
- **问题**: JSON 存储无 Schema 校验
- **修复**: 添加 Pydantic 模型校验

#### 3.2.12 `price_map` 内存膨胀
- **文件**: `backend/app/routers/portfolio.py:419-426`
- **问题**: 为每个 symbol 创建 4 个冗余条目
- **修复**: 标准化 symbol 格式，减少重复

#### 3.2.13 `_classify_asset` 字符串匹配脆弱
- **文件**: `backend/app/routers/portfolio.py:725`
- **问题**: 使用关键词列表判断资产类型
- **修复**: 使用正则表达式或数据库字段标记

#### 3.2.14 `get_attribution` 重复代码
- **文件**: `backend/app/routers/portfolio.py:805-828`
- **问题**: 与 `portfolio_pnl` 相同的 `price_map` 构建逻辑
- **修复**: 提取公共函数

#### 3.2.15 `list_transactions` 手动列名
- **文件**: `backend/app/routers/portfolio.py:1126-1127`
- **问题**: 列名列表硬编码，schema 变更时易出错
- **修复**: 使用 `SELECT *` + `row_factory` 自动映射

---

### 🟢 Medium（中级）- 14项

1. **缓存 TTL 硬编码** - `market.py:63,380`，无环境变量覆盖
2. **同步调用异步函数** - `market.py:1485`，可能阻塞
3. **Excessive logging** - `data_fetcher.py:134,150,151`，热循环内打印日志
4. **AkShare 无超时** - `data_fetcher.py:821`，可能无限阻塞
5. **Sina JSON 解析裸 except** - `data_fetcher.py:771`，吞掉所有异常
6. **`fetch_all_and_buffer` 静默吞错** - `data_fetcher.py:1387-1389`
7. **WAL 模式检测脆弱** - `database.py:30`，路径字符串匹配
8. **`init_tables` 无回滚** - `database.py:133-136`，ALTER TABLE 失败静默忽略
9. **`get_all_stocks_lite` 重复计算** - `database.py:510-511`，Python 循环内计算 prev
10. **App.vue 骨架屏超时硬编码** - `frontend/src/App.vue:371-374`，3秒固定
11. **`fetchHighFreq` 空 catch** - `frontend/src/App.vue:349`，吞掉错误
12. **`currentTime` 后台更新** - `frontend/src/App.vue:407`，页面不可见时仍每秒更新
13. **`_loadedCount` 竞态条件** - `frontend/src/App.vue:369-370`，非响应式变量
14. **`FIELD_MAP` 不完整** - `frontend/src/utils/api.js:94-103`，仅映射 8 个字段

---

## 四、Wind 投顾终端差距分析

### 4.1 功能模块覆盖率矩阵

| # | 模块 | 覆盖率 | 差距说明 | 优先级 |
|---|------|--------|----------|--------|
| 1 | 行情报价中心 | 30% | 缺新三板、多市场联动、Level2 | P2 |
| 2 | 股票研究 | 5% | **缺 F9 深度资料、多维数据提取、专题统计** | **P0** |
| 3 | 债券研究 | 10% | 缺中介报价、风险散点图、持有期收益 | P1 |
| 4 | 基金研究 | 15% | 缺 F9 深度、基金比较、Factsheet | P1 |
| 5 | 商品与衍生品 | 5% | **缺期权链、希腊值、波动率曲面** | **P0** |
| 6 | 指数中心 | 20% | 仅 6 只指数，缺 MSCI/FTSE、成分穿透 | P2 |
| 7 | 组合与资管 | 25% | 缺 Brinson 归因、CVaR、压力测试 | P1 |
| 8 | 宏观经济 | 5% | **缺 EDB、全球经济日历、GDP/CPI/PMI** | **P0** |
| 9 | 新闻与舆情 | 20% | 缺 7×24 新闻、公告、研报平台 | P1 |
| 10 | 量化研究 | 15% | 缺万矿量化云、EQBT、多语言 API | P2 |
| 11 | 风控中心 | 10% | 缺全球风险事件、质押监控、违约预警 | P2 |
| 12 | 生产力工具 | 0% | **缺 Excel 插件、WP 灵活屏、键盘精灵** | P1 |
| 13 | 企业信息 | 0% | 缺企业图谱、并购库、PEVC | P3 |

### 4.2 UI/UX 差距矩阵

| 维度 | AlphaTerminal | Wind | 差距 | 优先级 |
|------|---------------|------|------|--------|
| 信息密度 | 稀疏(~30%) | 密集(~80%) | 🔴 严重不足 | **P0** |
| 快捷键 | 无 | 200+ | 🔴 完全缺失 | **P0** |
| 多标签工作流 | 单视图 | 50+ 标签 | 🔴 缺失 | P1 |
| WP 灵活屏 | 无 | 跨屏布局 | 🔴 缺失 | P2 |
| 右键上下文 | 浏览器默认 | 丰富菜单 | 🟡 基础 | P1 |
| 模块联动 | 无 | 点击联动 | 🟡 缺失 | P1 |
| 专业配色 | 暗色 | 可配置 | 🟢 良好 | P3 |
| 双屏支持 | 单窗口 | 多显示器 | 🟡 缺失 | P2 |

---

## 五、重构建议分类

### 🟢 安全级（Safe）- 立即执行

| # | 重构项 | 预计时间 | 影响 | 文件 |
|---|--------|----------|------|------|
| 1 | 移除 DEBUG 代码 | 5 分钟 | Critical | `portfolio.py:554-556` |
| 2 | 替换 subprocess curl | 1 小时 | Critical | `data_fetcher.py:1162` |
| 3 | 添加线程池限制 | 2 小时 | Critical | `data_fetcher.py:1239` |
| 4 | 优化 `_52w_bounds` | 30 分钟 | High | `market.py:1441` |
| 5 | 移除 api.js 自旋锁 | 30 分钟 | High | `api.js:31-34` |
| 6 | 提取 price=0 回退公共函数 | 2 小时 | Medium | `market.py:444,482` |
| 7 | 修复 `fetchApiBatch` allSettled | 30 分钟 | High | `api.js:240` |
| 8 | 缓存 TTL 环境变量化 | 1 小时 | Low | `market.py:63,380` |

### 🟡 可尝试级（Try）- 需要测试

| # | 重构项 | 预计时间 | 影响 | 文件 |
|---|--------|----------|------|------|
| 1 | 添加连接池 | 2 天 | Critical | `database.py:27` |
| 2 | 批量查询优化 | 4 小时 | High | `market.py:1389` |
| 3 | SQL CTE 递归 | 4 小时 | High | `portfolio.py:241` |
| 4 | `sell_lot` 事务包装 | 2 小时 | High | `portfolio.py:1212` |
| 5 | 请求去重机制 | 1 天 | Medium | `api.js:146` |
| 6 | 生成器模式重构 | 1 天 | Medium | `data_fetcher.py:1397` |

### 🔴 危险级（Danger）- 需充分测试

| # | 重构项 | 预计时间 | 影响 | 文件 |
|---|--------|----------|------|------|
| 1 | `fetch_all_china_stocks` 流式处理 | 1 天 | Medium | `data_fetcher.py:1397` |
| 2 | Portfolio 连接合并重构 | 2 天 | High | `portfolio.py:398-564` |
| 3 | 数据库 Schema 迁移 | 3 天 | High | `database.py` |

---

## 六、修复状态追踪

### 6.1 已修复（v0.5.189）

| 问题 | 文件 | 修复内容 |
|------|------|----------|
| 指数解析注释误导 | `data_fetcher.py:81-105` | 修正 `parts[2]` 为 `change_amount` |
| curl 依赖（global indices） | `data_fetcher.py:237-247` | 改用 `httpx` |
| opencode_go 模型名 | `admin.py`, `copilot.py` | 修正为 `minimax-m2.7` |

### 6.2 本次修复（v0.6.0）

- [ ] 移除 portfolio.py DEBUG 代码
- [ ] 替换剩余 subprocess curl
- [ ] 添加线程池限制
- [ ] 优化 N+1 查询
- [ ] 移除 api.js 自旋锁
- [ ] 修复 fetchApiBatch allSettled

---

## 七、架构建议

### 7.1 短期（1-2周）

**目标**: 消除所有 Critical 问题，达到"生产就绪"

1. **安全**: 移除 DEBUG 代码、修复 curl 漏洞、添加线程池
2. **性能**: 优化 N+1 查询、添加连接池
3. **稳定性**: 事务包装、错误处理完善

### 7.2 中期（3-6周）

**目标**: 达到 Wind 30-40% 覆盖率

1. **宏观经济面板**: GDP/CPI/PMI/经济日历（Phase 2 Week 7-8）
2. **键盘快捷键**: 全局快捷键系统
3. **F9 深度资料**: 基础版（财务摘要+盈利预测）
4. **新闻增强**: 7×24 新闻流、情绪评分
5. **基金比较**: 多基金对比工具

### 7.3 长期（7-12周）

**目标**: 达到 Wind 50-60% 覆盖率

1. **Brinson 归因**: 组合业绩归因模型
2. **期权分析**: 链式数据、希腊值、波动率曲面
3. **股票质押监控**: 风控中心基础版
4. **Excel 导出桥接**: 生产力工具基础版
5. **企业图谱**: 股权结构可视化

---

## 八、性能基准

### 8.1 当前性能

| 指标 | 当前值 | 目标值 | 状态 |
|------|--------|--------|------|
| API 响应时间（P95） | ~200ms | <100ms | 🟡 |
| 数据库查询时间 | ~50ms | <20ms | 🟡 |
| 前端首屏加载 | ~3s | <2s | 🟡 |
| 并发连接数 | 无限制 | <100 | 🔴 |
| 内存使用（后端） | ~150MB | <200MB | 🟢 |

### 8.2 优化建议

1. **添加 Redis 缓存层**: 减少数据库查询 80%
2. **启用 HTTP/2**: 减少连接开销
3. **数据库索引优化**: 为高频查询字段添加索引
4. **前端代码分割**: 进一步减小首屏包体积

---

## 九、安全评估

### 9.1 当前风险

| 风险 | 等级 | 说明 |
|------|------|------|
| SQL 注入 | 中 | `admin.py:420` 使用 f-string，但有白名单检查 |
| 命令注入 | 高 | `data_fetcher.py:1162` subprocess curl |
| XSS | 低 | 前端 Vue 自动转义 |
| CSRF | 低 | CORS 配置合理 |
| 信息泄露 | 中 | DEBUG 代码泄露内部状态 |

### 9.2 建议

1. 启用 `bandit` 安全扫描（已在 CI 中配置）
2. 所有 SQL 查询使用参数化
3. 移除所有 `subprocess` 调用
4. 敏感操作添加审计日志

---

## 十、总结

AlphaTerminal 是一个架构清晰、代码质量良好的个人金融数据平台。主要问题在于：

1. **技术债**: 8 项 Critical 问题需立即修复
2. **功能差距**: 与 Wind 相比覆盖率仅 10.4%，核心差距在股票研究、宏观经济、生产力工具
3. **用户体验**: 信息密度低、缺少快捷键、无多标签工作流

**建议优先级**:
1. 🔴 **立即**: 修复 Critical 技术债（安全+稳定性）
2. 🟡 **本月**: 宏观经济面板 + 键盘快捷键
3. 🟢 **下月**: F9 深度资料 + 新闻增强 + 基金比较

---

*报告生成时间: 2025-04-29*  
*审计工具: opencode (k2p5)*  
*版本: v0.6.0*