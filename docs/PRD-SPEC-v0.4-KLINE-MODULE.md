# AlphaTerminal 进阶 K 线分析模块 — 实施规范

> 基于 `AlphaTerminal - 进阶 K 线分析模块完整 PRD` v1.0
> 版本：0.4（待实施）

---

## 一、架构总览

### 1.1 组件层次

```
DashboardGrid.vue (fullscreen branch)
└── AdvancedKlinePanel.vue          # 全屏 K 线主容器（新建）
    ├── CommandCenter.vue           # 极速指令中心/全局搜索（新建）
    ├── QuoteHeader.vue            # 数据盘口+图表控制台（新建）
    ├── MainChart.vue              # 主图区（从 IndexLineChart 抽取并增强）
    ├── SubChart.vue               # 副图区（VOL/MACD/KDJ/RSI/BOLL Tab）
    ├── DrawingToolbar.vue         # 画线工具栏（新建）
    ├── DrawingCanvas.vue          # 画线层（Canvas 覆盖层，新建）
    └── IntervalStats.vue          # 区间统计浮窗（新建）
```

### 1.2 数据流

```
useMarketStore.setSymbol(symbolCode)
    ↓
AdvancedKlinePanel 监听 → 重置图表 → fetch /api/v1/market/history/{symbol}
    ↓
后端返回 { history: OHLCV[], has_more: bool, next_offset: int }
    ↓
前端计算 MA/MACD/KDJ/BOLL 指标（已有逻辑，抽取为指标计算库）
    ↓
ECharts 渲染主图+副图
```

### 1.3 依赖评估

| 依赖 | 用途 | 状态 |
|------|------|------|
| echarts v5.5.1 | 图表引擎 | ✅ 已有 |
| vue-echarts v7.0.3 | Vue3 绑定 | ✅ 已有 |
| fuse.js | 模糊搜索 | ❌ 需安装 |
| @vueuse/core | ResizeObserver等 | ✅ 已有 |
| localForage (IndexedDB) | 画线持久化 | ❌ 需安装 |

---

## 二、实施阶段

### Phase 1：基础设施 + 命令中心 + 数据盘口

**目标**：全屏内可搜索切换标的 + 实时数据头

#### 2.1.1 Symbol 规范化

现有 `symbol` 格式混乱（`000001` 无市场后缀）。建立统一规范：

```
sh000001  ← 上证
sz399001  ← 深证
usNDX     ← 纳斯达克
hkHSI     ← 恒生
```

- 后端 `/market/history/{symbol}` 需支持规范化格式
- 前端 `useMarketStore` 扩展：增加 `symbolPrefix`（sh/sz/us/hk）
- `useMarketStore.setSymbol('000001', '上证指数', '#f87171', 'sh')` → 内部存 `sh000001`

#### 2.1.2 CommandCenter（极速指令中心）

- 位置：全屏模块左下角（fixed 定位，z-index 高）
- 触发方式：
  - 显式：点击搜索图标/输入框
  - 隐式：键盘任意字母/数字键（无输入框聚焦时）
- 搜索数据源：首次挂载从 `/api/v1/market/symbols` 拉取轻量字典（symbol, name, pinyin, market, type）
- 搜索算法：Fuse.js（代码、拼音首字母、中文三权重）
- 键盘导航：↑↓ 高亮，Enter 选中并关闭，Esc 关闭
- 选中后：调用 `setSymbol()`，关闭面板，触发图表刷新

**API 新增**：
```
GET /api/v1/market/symbols
返回: [{ symbol: "sh000001", code: "000001", name: "上证指数", pinyin: "PA", market: "AShare", type: "index" }, ...]
```

#### 2.1.3 QuoteHeader（数据盘口+控制台）

- 实时快照：最新价、涨跌额、涨跌幅（红绿）、成交量、成交额、振幅、换手率
- 周期切换（12档）：分时、1分、5分、15分、30分、60分、日线、周线、月线、季线、年线
- 复权切换：不复权、前复权、后复权
- Y轴切换：线性/对数
- 导出：CSV（可视/全部）、PNG 截图

---

### Phase 2：主图引擎 + 副图系统

**目标**：专业级 K 线图表，指标完整

#### 2.2.1 MainChart 主图

- 基于现有 `IndexLineChart.vue` 的 K 线渲染逻辑抽取并增强
- ResizeObserver 绑定：容器尺寸变化时自动 `chart.resize()`
- Y 轴：线性/对数切换（ECharts grid yAxis.type: 'value' | 'log'）
- 自适应缩放：根据可见数据范围自动计算 yMin/yMax
- 十字光标：ECharts dataZoom crosshair，浮动面板显示 OHLCV
- 画线层 DrawingCanvas 覆盖在 ECharts canvas 上层（独立 Canvas，捕获鼠标事件）

#### 2.2.2 SubChart 副图

- 底部 Tab：VOL | MACD | KDJ | RSI | BOLL
- 点击 Tab 切换副图内容（复用现有指标计算逻辑）
- 指标参数设置弹窗：点击 ⚙️ 弹出，可修改计算周期参数

#### 2.2.3 后端扩展：分钟 K 线

现有 `/market/history` 仅支持 `minutely/daily/weekly/monthly`。新增：

```
GET /api/v1/market/history/{symbol}?period=1min&limit=300&offset=0
GET /api/v1/market/history/{symbol}?period=5min&limit=300&offset=0
...
```

- `offset` 参数支持分页（懒加载）
- `has_more: true/false` 告知是否还有更早数据
- 日内分钟 K 线从 Eastmoney 5分钟 K 线数据源拉取

---

### Phase 3：画线系统

**目标**：专业绘图工具 + 本地持久化

#### 2.3.1 DrawingToolbar

- 工具按钮：直线、射线、线段、趋势线、水平线、平行通道、黄金分割（0.382/0.618/1.0）、矩形
- 工具栏可折叠
- 当前选中工具高亮

#### 2.3.2 DrawingCanvas（覆盖层）

- 独立 `<canvas>` 层，position: absolute，覆盖在 ECharts 图表上方，透明背景
- 接收鼠标事件：mousedown/mousemove/mouseup
- 磁吸模式（Magnet Mode）：开启后，鼠标接近 K 线节点时自动吸附到精确 OHLC 价格位
- 绘制模式：根据选中工具绘制图形
- 选中模式：点击已绘制对象可选中（显示控制点），拖拽移动，二次点击删除

#### 2.3.3 持久化

- 存储结构（IndexedDB via localforage）：
```json
{
  "drawings": {
    "sh000001": [
      { "id": "uuid", "type": "line", "points": [...], "color": "#fbbf24", "locked": false }
    ]
  }
}
```
- 标的切换时：保存当前画线 → IndexedDB；加载新标的画线
- localStorage 兜底（简单版）

---

### Phase 4：高阶分析工具

#### 2.4.1 区间统计

- 图表上拖拽选择两个时间点（或右键菜单触发）
- 浮窗展示：区间涨跌幅(%)、最大振幅(%)、最高/最低价、交易日天数、累计成交量/额、累计换手率

#### 2.4.2 历史分时下钻

- 右键单根 K 线 → 「查看历史分时」选项
- 触发 `/api/v1/market/history/{symbol}?period=minutely&trade_date=YYYY-MM-DD`
- 图表清空，渲染该日分时数据

---

## 三、关键工程约束

### 3.1 绝不接受全量 I/O 熔断

- 每次历史数据请求：limit=300，offset=N
- 图表向左拖拽触及最左边界时，触发 `offset += 300` 请求更早数据
- 后端对 `limit` 最大值做限制（如 ≤ 300）

### 3.2 前端指标计算前置

- MA/MACD/KDJ/BOLL/RSI 等全部由前端 `indicators.js` 计算库完成
- 后端仅返回原始 OHLCV 数组
- 导出 CSV 时包含完整字段（含前端计算的指标值）

### 3.3 绝对符号隔离

- 所有 API 调用使用规范化 Symbol（含市场前缀）
- 后端使用精确字典映射，绝不用前缀模糊匹配
- 示例：`GET /api/v1/market/history/sh000001?period=daily`

### 3.4 全屏边界约束

```
<App.vue main 元素>
  width = flex-1（受Sidebar+Copilot约束）
  ┌─────────────────────────────────────────┐
  │ Header (48px, fixed)                   │
  ├─────────────────────────────────────────┤
  │ AdvancedKlinePanel (flex-1)             │
  │ ┌─────────────────────────────────────┐ │
  │ │ QuoteHeader (固定高度)               │ │
  │ ├─────────────────────────────────────┤ │
  │ │ MainChart + DrawingCanvas (flex-1)  │ │
  │ ├─────────────────────────────────────┤ │
  │ │ SubChart (固定高度 200px)            │ │
  │ └─────────────────────────────────────┘ │
  │ CommandCenter (fixed left-bottom)        │
  └─────────────────────────────────────────┘
```

---

## 四、文件变更清单

### 新建文件
- `frontend/src/components/AdvancedKlinePanel.vue`
- `frontend/src/components/CommandCenter.vue`
- `frontend/src/components/QuoteHeader.vue`
- `frontend/src/components/MainChart.vue`
- `frontend/src/components/SubChart.vue`
- `frontend/src/components/DrawingToolbar.vue`
- `frontend/src/components/DrawingCanvas.vue`
- `frontend/src/components/IntervalStats.vue`
- `frontend/src/composables/useKlineStore.js`
- `frontend/src/utils/indicators.js`（指标计算，抽取自 IndexLineChart）
- `frontend/src/utils/drawing.js`（画线工具）
- `frontend/src/utils/symbols.js`（符号规范化）

### 修改文件
- `frontend/src/composables/useMarketStore.js`（扩展 Symbol 规范化）
- `frontend/src/components/DashboardGrid.vue`（全屏分支使用 AdvancedKlinePanel）
- `frontend/src/components/IndexLineChart.vue`（抽取/复用指标逻辑）
- `backend/app/routers/market.py`（新增 `/symbols` 接口，新增分钟周期支持）
- `frontend/package.json`（新增 fuse.js, localforage）
- `frontend/vite.config.js`（若需别名）

---

## 五、测试验证清单

- [ ] 符号搜索：代码/拼音/中文三通道均正常
- [ ] 键盘导航：↑↓/Enter/Esc 全流程无误
- [ ] 周期切换：12档全部可切换，数据正确
- [ ] 复权切换：不复权/前复权/后复权数据一致
- [ ] Y轴切换：线性/对数切换图表无断裂
- [ ] 十字光标：悬浮 K 线顶部信息栏实时更新
- [ ] 副图切换：VOL/MACD/KDJ/RSI/BOLL 切换正常
- [ ] 画线持久化：刷新页面后画线恢复
- [ ] 懒加载：拖拽触及左边界时正确触发追加加载
- [ ] 全屏 resize：Sidebar/Copilot 切换时图表自适应
- [ ] 导出 CSV：可视/全部数据完整
- [ ] 历史分时下钻：右键日K可渲染当日分时
