# AlphaTerminal 投资组合功能评估报告
**评估日期**: 2026-04-14
**评估对象**: 投资组合主账户/子账户关系及功能完整性

---

## 一、当前实现概况

### 1.1 数据库Schema

```sql
-- portfolios表
id, name, type, parent_id, created_at, total_cost

-- positions表  
id, portfolio_id, symbol, shares, avg_cost, updated_at

-- portfolio_snapshots表
id, portfolio_id, date, total_asset, total_cost
```

### 1.2 前端功能
- ✅ 主账户/子账户树形展示（折叠/展开）
- ✅ 侧边栏实时总览（总资产、累计盈亏、盈亏率）
- ✅ 风险指标面板（夏普比率、最大回撤、波动率、胜率等10+指标）
- ✅ 行业归因分析
- ✅ 净值走势图
- ✅ 调仓交易弹窗
- ✅ 账户CRUD（创建、删除）

### 1.3 已实现的风险指标
| 指标 | 状态 |
|------|------|
| 年化收益率 | ✅ |
| 夏普比率 | ✅ |
| 年化波动率 | ✅ |
| 最大回撤 | ✅ |
| 胜率 | ✅ |
| 盈亏比 | ✅ |
| 最佳/最差交易日 | ✅ |
| 最大连续涨跌天数 | ✅ |
| 持仓集中度(Top3/Top5) | ✅ |
| β系数(沪深300) | ✅ |

---

## 二、与专业金融终端的差距分析

### 2.1 ❌ 严重缺失（阻碍专业使用）

| 功能 | 专业终端 | AlphaTerminal | 影响 |
|------|---------|---------------|------|
| **币种支持** | CNY/USD/HKD多币种 | ❌ 仅CNY | 无法进行跨境投资分析 |
| **资产类别** | 股票/债券/基金/期货/期权/REITs | ❌ 混为一体 | 无法按资产类别分析配置 |
| **基准对比** | 可设沪深300/中证500等为基准 | ❌ 无 | 无法评估相对收益 |
| **策略标签** | 价值/成长/平衡/指数跟踪/量化 | ❌ 无 | 无法按策略分类管理 |
| **交易记录** | 完整买卖流水、分红、配股 | ❌ 仅当前持仓 | 无法追溯历史操作 |
| **现金管理** | 现金余额、出入金记录 | ❌ 无 | 无法计算真实收益率 |

### 2.2 ⚠️ 需要完善（影响使用体验）

| 功能 | 当前状态 | 问题 | 建议 |
|------|---------|------|------|
| **账户类型** | main/special_plan | 类型太少，语义不清 | 增加：现金/融资/融券/期权/期货 |
| **持仓信息** | symbol/shares/avg_cost | 缺少实时计算字段 | 增加：current_price/market_value/pnl/pnl_pct/weight |
| **子账户功能** | 仅层级展示 | 子账户无独立风险指标 | 子账户应有自己的收益曲线和风险指标 |
| **行业归因** | 简单权重展示 | 缺少行业盈亏贡献 | 增加：行业收益贡献、行业配置偏离 |
| **账户状态** | 无 | 无法标记账户状态 | 增加：active/frozen/closed |

### 2.3 🔧 建议添加（提升专业度）

| 功能 | 优先级 | 说明 |
|------|--------|------|
| **组合对比** | P1 | 多个组合收益曲线叠加对比 |
| **Brinson归因** | P1 | 行业配置效应+个股选择效应分解 |
| **VaR计算** | P2 | 风险价值（95%/99%置信度） |
| **情景分析** | P2 | 市场下跌10%/20%时的组合表现 |
| **再平衡提醒** | P2 | 当仓位偏离目标配置时提醒 |
| **税费计算** | P3 | 印花税、红利税、资本利得税 |
| **分红再投资** | P3 | 自动记录分红并模拟再投资 |
| **多维度筛选** | P3 | 按行业/市值/盈亏状态筛选持仓 |

---

## 三、主账户/子账户关系评估

### 3.1 当前设计
```
主账户 (main)
├── 子账户1 (special_plan)
├── 子账户2 (special_plan)
└── 子账户3 (special_plan)
```

**问题**:
1. ❌ 层级太浅：只有2级，无法支持更复杂的组合结构
2. ❌ 类型单一：special_plan语义不清，无法区分策略类型
3. ❌ 数据孤立：子账户数据不汇总到主账户，主账户仅作为容器
4. ❌ 无汇总视图：无法查看"主账户+所有子账户"合并后的整体表现

### 3.2 专业终端的设计
```
投资组合 (Portfolio) - 顶层视图
├── A股组合
│   ├── 价值投资策略
│   ├── 成长投资策略
│   └── 指数跟踪策略
├── 港股组合 (USD/HKD)
├── 债券组合
└── 期货对冲账户
```

**特点**:
1. ✅ 多层级嵌套（理论上无限级）
2. ✅ 按资产类别/策略/币种分组
3. ✅ 自动汇总：父节点自动汇总所有子节点数据
4. ✅ 独立核算：每个节点都有独立的收益曲线和风险指标

### 3.3 改进建议

**方案A：扩展现有模型（推荐）**
```sql
-- 扩展 portfolios 表
ALTER TABLE portfolios ADD COLUMN currency TEXT DEFAULT 'CNY';  -- CNY/USD/HKD
ALTER TABLE portfolios ADD COLUMN asset_class TEXT DEFAULT 'stock';  -- stock/bond/fund/futures/options
ALTER TABLE portfolios ADD COLUMN strategy TEXT;  -- value/growth/balanced/index/quant
ALTER TABLE portfolios ADD COLUMN benchmark TEXT;  -- 000001/000300/399001
ALTER TABLE portfolios ADD COLUMN status TEXT DEFAULT 'active';  -- active/frozen/closed
ALTER TABLE portfolios ADD COLUMN initial_capital REAL DEFAULT 0;  -- 初始资金
ALTER TABLE portfolios ADD COLUMN leverage_enabled BOOLEAN DEFAULT 0;  -- 是否融资账户
ALTER TABLE portfolios ADD COLUMN tags TEXT;  -- JSON数组: ["高波动", "科技股"]
ALTER TABLE portfolios ADD COLUMN description TEXT;  -- 账户说明
ALTER TABLE portfolios ADD COLUMN target_allocation TEXT;  -- JSON: {"stock":60, "bond":40}
```

**方案B：增加 transactions 表（交易记录）**
```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY,
    portfolio_id INTEGER,
    symbol TEXT,
    action TEXT,  -- BUY/SELL/DIVIDEND/SPLIT/TRANSFER
    shares INTEGER,
    price REAL,
    amount REAL,  -- 总金额（含税费）
    fee REAL,  -- 手续费
    tax REAL,  -- 税费
    trade_date TEXT,
    notes TEXT,
    created_at TEXT
);
```

**方案C：增加 cash_balances 表（现金管理）**
```sql
CREATE TABLE cash_balances (
    id INTEGER PRIMARY KEY,
    portfolio_id INTEGER,
    currency TEXT,
    balance REAL,
    last_updated TEXT
);
```

---

## 四、优先级开发计划

### Phase 1: 账户属性增强（1-2天）
- [ ] 扩展 portfolios 表字段（currency/asset_class/strategy/benchmark/status）
- [ ] 前端新增账户属性编辑界面
- [ ] 侧边栏显示币种和策略标签

### Phase 2: 持仓信息完善（2-3天）
- [ ] 后端API返回实时计算字段（current_price/market_value/pnl）
- [ ] 前端持仓列表显示仓位占比
- [ ] 增加持仓排序和筛选功能

### Phase 3: 交易记录（3-5天）
- [ ] 创建 transactions 表
- [ ] 调仓时自动记录交易
- [ ] 交易历史查询界面
- [ ] 支持导入导出交易记录

### Phase 4: 现金管理（2-3天）
- [ ] 创建 cash_balances 表
- [ ] 出入金记录功能
- [ ] 现金+持仓合并计算总资产

### Phase 5: 高级功能（可选）
- [ ] 组合对比功能
- [ ] Brinson归因分析
- [ ] VaR计算
- [ ] 再平衡提醒

---

## 五、总结

### 5.1 当前评分: 5/10（可用但不专业）

**优势**:
- ✅ 基础层级关系已建立
- ✅ 风险指标计算较全面
- ✅ 行业归因已初步实现

**劣势**:
- ❌ 账户属性过于简单
- ❌ 缺少币种、资产类别、策略等关键字段
- ❌ 无交易记录，无法追溯历史
- ❌ 无现金管理，收益率计算不准确
- ❌ 子账户数据不汇总到主账户

### 5.2 达到专业终端需要：
- **最少需要**: Phase 1 + Phase 2（账户属性+持仓完善）
- **完整功能**: Phase 1-4（增加交易记录+现金管理）
- **超越竞品**: Phase 1-5（增加高级分析功能）

**预计工作量**: 2-3周达到专业水平
