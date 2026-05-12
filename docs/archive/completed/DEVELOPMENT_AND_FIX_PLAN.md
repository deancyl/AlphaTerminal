# AlphaTerminal 开发与修复计划

> **版本**: V1.0  
> **制定日期**: 2026-05-12  
> **基于**: PRD评估报告（PRD_DEVELOPMENT_PLAN.md V4.0）  
> **目标**: 修正PRD声明与实际实现的差距，补全核心功能

---

## 一、计划概述

### 1.1 背景与目标

经过对PRD文档与实际代码的全面评估，发现以下主要差距：

| 类别 | 差距数量 | 严重程度 |
|------|----------|----------|
| 模块覆盖率不准确 | 6项 | 中 |
| 核心功能缺失 | 4项 | 高 |
| 基础设施不足 | 3项 | 中 |
| 非功能性需求未达标 | 4项 | 中 |

**总体目标**：
1. 修正PRD文档中的不准确声明
2. 补全核心功能（Brinson归因、研报平台、ESG评价）
3. 优化非功能性指标（性能、稳定性）
4. 保持"完全免费、完全开源"的项目定位

### 1.2 约束条件

| 约束 | 说明 |
|------|------|
| 团队规模 | 单人全栈开发 |
| 时间周期 | 3个月/迭代 |
| 数据源 | 仅AkShare免费数据 |
| 预算 | 无付费API预算 |

### 1.3 优先级原则

采用**"功能优先+渐进优化"**策略：

```
P0 (必须实现) → 核心业务功能缺失，用户感知强
P1 (应该实现) → 提升专业度，增强竞争力
P2 (可以实现) → 体验优化，锦上添花
P3 (延后实现) → 复杂度高，ROI不明确
```

---

## 二、分阶段开发计划

### Phase 0: 基础设施修复（1周）

**目标**: 修复PRD文档不准确声明，优化性能瓶颈

#### 任务清单

| 任务ID | 任务描述 | 工作量 | 优先级 | 依赖 |
|--------|----------|--------|--------|------|
| P0-001 | 更新PRD覆盖率矩阵 | 2h | P0 | 无 |
| P0-002 | 优化EDB查询性能（10s→5s） | 3天 | P0 | 无 |
| P0-003 | 补全键盘快捷键至40+ | 1天 | P1 | 无 |
| P0-004 | 实现WebSocket自动重连 | 1天 | P1 | 无 |
| P0-005 | 添加PRD版本变更日志 | 1h | P2 | P0-001 |

#### 详细说明

**P0-001: 更新PRD覆盖率矩阵**

修改文件: `/docs/PRD_DEVELOPMENT_PLAN.md`

需要修正的覆盖率：

| 模块 | 原声明 | 修正为 | 原因 |
|------|--------|--------|------|
| F9 深度资料 | 85% | 100% | 8个Tab全部实现 |
| AI Copilot | 75% | 95% | 支持9个LLM提供商 |
| EDB 宏观经济 | 90% | 70% | 仅中国数据，无国际指标 |
| PMS 组合管理 | 95% | 85% | 无Brinson归因 |
| 新闻资讯 | 95% | 75% | 无研报平台 |
| 外汇研究 | 10% | 25% | 已有AlphaVantage集成 |
| 套利监控 | 0% | 15% | 已有利差图表 |
| 键盘命令 | 40+ | 26 | 实际定义数量 |

**P0-002: 优化EDB查询性能**

问题分析：
- 当前查询耗时~10秒，目标<5秒
- 原因：AkShare API调用慢 + 无查询缓存

解决方案：
```python
# 1. 添加查询结果缓存（已有DataCache，需应用到EDB）
# 2. 并行获取多个指标（asyncio.gather）
# 3. 预加载常用指标（GDP、CPI、PPI、PMI、M2）
```

修改文件：
- `/backend/app/routers/macro.py` - 添加缓存装饰器
- `/backend/app/services/data_cache.py` - 确保缓存生效

**P0-003: 补全键盘快捷键**

当前：26个快捷键
目标：40+个快捷键

需要添加的快捷键：

| 快捷键 | 功能 | 优先级 |
|--------|------|--------|
| F3 | 上证指数 | P0 |
| F4 | 深证成指 | P0 |
| F6 | 自选股 | P0 |
| HOME | 首页 | P1 |
| Ctrl+1-9 | 快速切换视图 | P1 |

修改文件：
- `/frontend/src/composables/useKeyboardShortcuts.js`

**P0-004: 实现WebSocket自动重连**

当前：手动重连
目标：指数退避自动重连

实现方案：
```javascript
// 前端WebSocket客户端
class ReconnectingWebSocket {
  constructor(url) {
    this.url = url;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000; // 初始1秒
  }
  
  onclose() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
      setTimeout(() => this.connect(), delay);
      this.reconnectAttempts++;
    }
  }
}
```

修改文件：
- `/frontend/src/services/websocket.js` (新建)
- `/frontend/src/App.vue` - 集成重连逻辑

#### 验收标准

| 任务 | 验收命令 | 预期结果 |
|------|----------|----------|
| P0-001 | `grep "100%" docs/PRD_DEVELOPMENT_PLAN.md` | F9覆盖率显示100% |
| P0-002 | `curl -w "%{time_total}" localhost:8002/api/v1/macro/overview` | 响应时间<5秒 |
| P0-003 | `grep -c "key:" frontend/src/composables/useKeyboardShortcuts.js` | 计数>=40 |
| P0-004 | 断开网络后恢复 | WebSocket自动重连 |

---

### Phase 1: 核心功能补全（4周）

**目标**: 补全PRD声明的核心功能，修正覆盖率差距

#### 任务清单

| 任务ID | 任务描述 | 工作量 | 优先级 | 依赖 |
|--------|----------|--------|--------|------|
| P1-001 | 实现Brinson归因分析 | 2周 | P0 | 无 |
| P1-002 | 实现研报平台（RPP） | 1周 | P0 | 无 |
| P1-003 | 实现ESG评价体系 | 1周 | P0 | 无 |
| P1-004 | 扩展国际宏观数据 | 3天 | P1 | P0-002 |
| P1-005 | 实现文本命令路由 | 3天 | P1 | P0-003 |

#### 详细说明

**P1-001: 实现Brinson归因分析**

功能描述：
将组合超额收益分解为：
1. 配置效应（Allocation Effect）
2. 选择效应（Selection Effect）
3. 交互效应（Interaction Effect）

数据源需求：
- 组合持仓权重
- 基准成分权重（需构建基准数据库）
- 各资产收益率

AkShare可用函数：
- `index_stock_cons_weight_csindex` - 指数成分权重

实现方案：

```
/backend/app/services/attribution/
├── __init__.py
├── brinson.py              # Brinson归因计算
├── benchmark.py            # 基准数据管理
└── report_generator.py     # 归因报告生成

/frontend/src/components/portfolio/
├── AttributionPanel.vue    # 归因分析面板
└── AttributionChart.vue    # 归因可视化图表
```

API设计：
```
POST /api/v1/portfolio/{id}/attribution
Request:
{
  "benchmark": "000300",  # 沪深300
  "period_start": "2025-01-01",
  "period_end": "2025-12-31"
}
Response:
{
  "allocation_effect": 0.023,
  "selection_effect": 0.015,
  "interaction_effect": 0.008,
  "total_excess": 0.046,
  "details": [...]
}
```

**P1-002: 实现研报平台（RPP）**

功能描述：
- 研报列表查询（按股票代码、日期、机构筛选）
- 研报摘要展示
- 研报详情链接

AkShare可用函数：
- `stock_research_report_em(symbol)` - 东方财富研报

实现方案：

```
/backend/app/routers/research.py
├── GET /research/reports?symbol=600519&page=1
├── GET /research/reports/{id}
└── GET /research/summary?symbol=600519

/frontend/src/components/research/
├── ResearchReportList.vue
├── ResearchReportDetail.vue
└── ResearchSummary.vue
```

API设计：
```
GET /api/v1/research/reports?symbol=600519&page=1&page_size=20
Response:
{
  "total": 45,
  "items": [
    {
      "id": "rpt_001",
      "title": "贵州茅台：业绩稳健增长，品牌价值持续提升",
      "institution": "中信证券",
      "analyst": "张三",
      "date": "2025-04-15",
      "rating": "买入",
      "summary": "..."
    }
  ]
}
```

**P1-003: 实现ESG评价体系**

功能描述：
- ESG评级展示
- 碳排放数据
- ESG评分趋势

AkShare可用函数：
- `stock_esg_hz_sina` - 华证ESG评级
- `stock_esg_msci_sina` - MSCI ESG评级
- `stock_esg_rate_sina` - ESG评级汇总
- `energy_carbon_bj` - 北京碳交易
- `energy_carbon_domestic` - 国内碳交易

实现方案：

```
/backend/app/routers/esg.py
├── GET /esg/rating/{symbol}
├── GET /esg/carbon
└── GET /esg/trend/{symbol}

/frontend/src/components/esg/
├── ESGRatingPanel.vue
├── CarbonDataPanel.vue
└── ESGTrendChart.vue
```

**P1-004: 扩展国际宏观数据**

当前：仅中国宏观数据
目标：添加美国、欧洲主要指标

AkShare可用函数：
- `macro_usa_cpi` - 美国CPI
- `macro_usa_gdp` - 美国GDP
- `macro_usa_unemployment` - 美国失业率
- `macro_euro_gdp` - 欧元区GDP

修改文件：
- `/backend/app/routers/macro.py` - 添加国际指标端点
- `/frontend/src/components/MacroDashboard.vue` - 添加国际指标Tab

**P1-005: 实现文本命令路由**

当前：仅支持股票代码搜索和`:F9`等4个命令
目标：支持BBQ、IRS、FX、CNIX等文本命令

命令映射表：

| 命令 | 功能 | 目标视图 |
|------|------|----------|
| BBQ | 债券报价 | BondDashboard |
| IRS | 利率互换 | (待实现) |
| FX | 外汇综合屏 | ForexPanel |
| CNIX | 离岸人民币 | ForexPanel |
| ECO | 经济日历 | MacroDashboard |
| EDB | 经济数据库 | MacroDashboard |
| RPP | 研报平台 | ResearchReportList |

实现方案：

```javascript
// /frontend/src/composables/useCommandRouter.js
const COMMAND_MAP = {
  'BBQ': { view: 'bond', params: {} },
  'FX': { view: 'forex', params: {} },
  'CNIX': { view: 'forex', params: { currency: 'CNH' } },
  'ECO': { view: 'macro', params: { tab: 'calendar' } },
  'EDB': { view: 'macro', params: {} },
  'RPP': { view: 'research', params: {} },
};

export function routeCommand(input) {
  const cmd = input.toUpperCase().trim();
  if (COMMAND_MAP[cmd]) {
    return COMMAND_MAP[cmd];
  }
  return null;
}
```

修改文件：
- `/frontend/src/composables/useCommandRouter.js` (新建)
- `/frontend/src/components/CommandPalette.vue` - 集成命令路由

#### 验收标准

| 任务 | 验收命令 | 预期结果 |
|------|----------|----------|
| P1-001 | `curl localhost:8002/api/v1/portfolio/1/attribution` | 返回Brinson归因结果 |
| P1-002 | `curl localhost:8002/api/v1/research/reports?symbol=600519` | 返回研报列表 |
| P1-003 | `curl localhost:8002/api/v1/esg/rating/600519` | 返回ESG评级 |
| P1-004 | `curl localhost:8002/api/v1/macro/usa/cpi` | 返回美国CPI数据 |
| P1-005 | 在命令面板输入`FX` | 跳转到外汇视图 |

---

### Phase 2: 专业功能增强（4周）

**目标**: 提升专业度，增强竞争力

#### 任务清单

| 任务ID | 任务描述 | 工作量 | 优先级 | 依赖 |
|--------|----------|--------|--------|------|
| P2-001 | 实现期权分析增强 | 1周 | P1 | 无 |
| P2-002 | 实现套利监控预警 | 1周 | P1 | 无 |
| P2-003 | 实现数据浏览器EDE | 2周 | P1 | 无 |
| P2-004 | 实现投顾服务管理 | 1周 | P2 | P1-001 |

#### 详细说明

**P2-001: 期权分析增强**

当前：前端Black-Scholes计算器（无后端数据）
目标：集成AkShare期权数据，实现波动率曲面

AkShare可用函数：
- `option_cffex_hs300_spot` - 沪深300期权实时
- `option_cffex_sz50_daily` - 上证50期权日行情
- `index_option_300etf_qvix` - 300ETF波动率指数

实现方案：
```
/backend/app/routers/options.py
├── GET /options/chain?underlying=300ETF
├── GET /options/volatility-surface?underlying=300ETF
└── GET /options/greeks?option_id=xxx

/frontend/src/components/options/
├── OptionChainPanel.vue
├── VolatilitySurfaceChart.vue
└── GreeksDisplay.vue
```

**P2-002: 套利监控预警**

当前：静态利差图表
目标：实时监控 + 预警通知

监控类型：
1. 跨期套利（近月-远月价差）
2. 跨品种套利（相关品种价差）
3. 跨市场套利（A股-H股价差）

实现方案：
```
/backend/app/services/arbitrage/
├── monitor.py          # 监控引擎
├── alert.py            # 预警通知
└── calculator.py       # 价差计算

/frontend/src/components/arbitrage/
├── ArbitrageMonitor.vue
├── SpreadAlert.vue
└── ArbitrageHistory.vue
```

**P2-003: 数据浏览器EDE**

功能描述：
- 三选一提交互（证券池→指标→输出配置）
- 批量数据提取
- 多格式导出

实现方案：
```
/frontend/src/components/ede/
├── EDEPanel.vue           # 主面板
├── UniverseSelector.vue   # 证券池选择
├── IndicatorSelector.vue  # 指标选择
├── OutputConfig.vue       # 输出配置
└── ResultTable.vue        # 结果表格

/backend/app/routers/ede.py
├── POST /ede/query/build
├── POST /ede/query/execute
└── GET /ede/query/export
```

**P2-004: 投顾服务管理**

功能描述：
- 客户档案管理
- 风险测评问卷
- 资产配置方案
- 投顾报告生成

实现方案：
```
/backend/app/routers/advisor/
├── clients.py          # 客户管理
├── risk_assessment.py  # 风险测评
├── allocation.py       # 资产配置
└── reports.py          # 报告生成

/frontend/src/components/advisor/
├── ClientManagement.vue
├── RiskQuestionnaire.vue
├── AllocationPlan.vue
└── AdvisorReport.vue
```

#### 验收标准

| 任务 | 验收命令 | 预期结果 |
|------|----------|----------|
| P2-001 | `curl localhost:8002/api/v1/options/chain?underlying=300ETF` | 返回期权链数据 |
| P2-002 | 设置价差阈值后触发预警 | 收到预警通知 |
| P2-003 | 在EDE选择证券池和指标 | 返回批量数据 |
| P2-004 | 创建客户档案并生成报告 | 返回投顾报告PDF |

---

### Phase 3: 延后功能（按需实现）

以下功能因复杂度高或ROI不明确，建议延后：

| 功能 | 延后原因 | 重新评估条件 |
|------|----------|--------------|
| 3C会议平台 | WebRTC复杂度高，需实名认证+内容审核 | 有明确用户需求 |
| Excel插件 | Office.js开发复杂，已有导出API替代 | 用户强烈需求 |
| 用户认证系统 | 当前Agent令牌足够 | 多用户场景需求 |
| Redis缓存 | 当前内存缓存足够 | 并发用户>100 |
| TLS加密 | 开发环境不需要 | 生产部署 |

---

## 三、风险与缓解措施

### 3.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| Brinson归因数据缺失 | 高 | 中 | 构建基准数据库，使用AkShare指数成分 |
| AkShare API不稳定 | 中 | 中 | 添加重试机制，缓存历史数据 |
| 研报版权问题 | 中 | 低 | 仅存储摘要和链接，不存储全文 |
| 前端性能下降 | 低 | 低 | 虚拟滚动、懒加载、代码分割 |

### 3.2 进度风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 单人开发进度慢 | 高 | 高 | 优先P0任务，延后P2/P3 |
| 需求变更 | 中 | 中 | 保持PRD版本控制，变更需评审 |
| 技术难点卡壳 | 中 | 中 | 预留缓冲时间，寻求社区帮助 |

### 3.3 质量风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 测试覆盖不足 | 中 | 中 | 每个新功能必须有单元测试 |
| 文档不同步 | 低 | 中 | API文档与代码同步更新 |
| 技术债务累积 | 中 | 中 | 每个迭代预留20%时间还债 |

---

## 四、验收标准汇总

### 4.1 功能验收

| 功能 | 验收命令 | 预期结果 |
|------|----------|----------|
| Brinson归因 | `curl localhost:8002/api/v1/portfolio/{id}/attribution` | 返回allocation/selection/interaction |
| 研报平台 | `curl localhost:8002/api/v1/research/reports?symbol=600519` | 返回研报列表 |
| ESG评级 | `curl localhost:8002/api/v1/esg/rating/600519` | 返回ESG评级 |
| 国际宏观 | `curl localhost:8002/api/v1/macro/usa/cpi` | 返回美国CPI |
| 文本命令 | 命令面板输入`FX` | 跳转外汇视图 |
| 期权链 | `curl localhost:8002/api/v1/options/chain?underlying=300ETF` | 返回期权链 |

### 4.2 性能验收

| 指标 | 目标 | 验收方法 |
|------|------|----------|
| EDB查询 | <5秒 | `curl -w "%{time_total}" localhost:8002/api/v1/macro/overview` |
| F9页面加载 | <2秒 | 浏览器开发者工具 |
| WebSocket重连 | <5秒 | 断开网络后恢复，观察重连时间 |

### 4.3 质量验收

| 指标 | 目标 | 验收方法 |
|------|------|----------|
| 测试覆盖率 | >10% | `pytest --cov` |
| 前端构建 | 无错误 | `npm run build` |
| Lint检查 | 无错误 | `npm run lint` |

---

## 五、时间线

```
Week 1: Phase 0 - 基础设施修复
├── Day 1-2: P0-001 PRD更新, P0-002 EDB性能优化
├── Day 3-4: P0-003 键盘快捷键补全
└── Day 5: P0-004 WebSocket重连

Week 2-3: Phase 1.1 - Brinson归因
├── Week 2: 后端归因计算引擎
└── Week 3: 前端归因面板 + 测试

Week 4: Phase 1.2 - 研报平台
├── Day 1-2: 后端研报API
├── Day 3-4: 前端研报列表
└── Day 5: 集成测试

Week 5: Phase 1.3 - ESG评价
├── Day 1-2: 后端ESG API
├── Day 3-4: 前端ESG面板
└── Day 5: 集成测试

Week 6: Phase 1.4-1.5 - 国际宏观 + 文本命令
├── Day 1-3: 国际宏观数据扩展
└── Day 4-5: 文本命令路由

Week 7-8: Phase 2.1-2.2 - 期权增强 + 套利监控
Week 9-10: Phase 2.3-2.4 - EDE + 投顾管理
```

---

## 六、附录

### A. AkShare函数清单

#### 已使用
- `macro_china_*` - 中国宏观数据
- `stock_individual_*` - 个股数据
- `stock_financial_analysis_indicator` - 财务指标
- `stock_institute_hold_detail` - 机构持股
- `stock_profit_forecast_ths` - 盈利预测

#### 待集成
- `stock_esg_*` - ESG评级（9个函数）
- `stock_research_report_em` - 研报数据
- `option_cffex_*` - 期权数据（30+个函数）
- `macro_usa_*` - 美国宏观数据
- `macro_euro_*` - 欧元区宏观数据
- `currency_*` - 汇率数据
- `forex_*` - 外汇数据

### B. 文件修改清单

#### 后端新增文件
```
/backend/app/services/attribution/
├── __init__.py
├── brinson.py
├── benchmark.py
└── report_generator.py

/backend/app/routers/
├── research.py
├── esg.py
├── options.py
└── ede.py

/backend/app/services/arbitrage/
├── monitor.py
├── alert.py
└── calculator.py
```

#### 前端新增文件
```
/frontend/src/composables/
└── useCommandRouter.js

/frontend/src/components/
├── portfolio/AttributionPanel.vue
├── research/ResearchReportList.vue
├── esg/ESGRatingPanel.vue
├── options/OptionChainPanel.vue
├── arbitrage/ArbitrageMonitor.vue
└── ede/EDEPanel.vue
```

### C. 参考文档

- PRD开发计划: `/docs/PRD_DEVELOPMENT_PLAN.md`
- AkShare文档: https://akshare.akfamily.xyz/
- Vue 3文档: https://vuejs.org/
- FastAPI文档: https://fastapi.tiangolo.com/

---

**文档结束**
