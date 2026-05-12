# AlphaTerminal Week 1-2 前端功能位置指南

## 功能位置总览

### Week 1: 数据导出功能

#### 1. 投资组合导出
**位置**: 投资组合面板右上角
- **组件**: PortfolioDashboard.vue
- **按钮**: "导出" (蓝色按钮)
- **功能**: 导出当前选中组合的持仓数据为 CSV/Excel
- **代码位置**: 
  - 按钮: 第 7-11 行
  - 导出函数: exportPortfolio() (约第 420 行)

#### 2. 回测结果导出
**位置**: 回测结果区域底部
- **组件**: BacktestDashboard.vue
- **按钮**: "导出" (青色边框按钮)
- **功能**: 导出回测结果为 Excel
- **代码位置**:
  - 按钮: 第 343-348 行
  - 导出函数: exportBacktest() (约第 780 行)

#### 3. 图表导出
**位置**: K线图右上角
- **组件**: AdvancedKlinePanel.vue -> QuoteHeader.vue
- **按钮**: 全屏按钮旁边的导出图标
- **功能**: 导出当前图表为 PNG
- **代码位置**: exportPNG() 函数

---

### Week 2: 预警系统

#### 价格预警管理
**位置**: 桌面端 GridStack 网格右下角
- **组件**: AlertManager.vue
- **位置**: DashboardGrid 第 8 个 widget (gs-x="9" gs-y="15")
- **功能**:
  - 添加价格预警（高于/低于/等于目标价格）
  - 启用/禁用预警规则
  - 查看预警历史
  - 浏览器通知推送

**使用步骤**:
1. 在网格布局中找到 "价格预警" 面板
2. 点击 "启用通知" 按钮授权浏览器通知
3. 点击 "+ 添加" 创建新预警
4. 输入股票代码、选择条件、设置目标价格
5. 当价格触发条件时，会收到浏览器通知

---

## 页面导航

### 访问地址
- **前端**: http://localhost:60100
- **后端API**: http://localhost:8002
- **API文档**: http://localhost:8002/docs

### 页面结构
```
AlphaTerminal 主界面
├── 指标图表 (K线图)
├── A股监测 (股票列表)
├── 市场情绪 (涨跌分布)
├── 板块热度 (行业板块)
├── 新闻快讯
├── 投资组合 (含导出按钮)
├── 全市场个股透视
└── 价格预警 (Week 2 新增)
```

---

## 快速测试

### 测试导出功能
1. 打开 http://localhost:60100
2. 找到 "投资组合" 面板
3. 选择一个账户
4. 点击 "导出" 按钮
5. 检查下载的 Excel 文件

### 测试预警功能
1. 找到 "价格预警" 面板
2. 点击 "启用通知"
3. 点击 "+ 添加"
4. 输入股票代码（如: sh600519）
5. 设置条件（如: 价格高于 1500）
6. 等待价格触发或手动测试

---

## 相关文件

### Week 1 文件
- backend/app/routers/export.py - 后端导出API
- frontend/src/components/PortfolioDashboard.vue - 投资组合面板
- frontend/src/components/BacktestDashboard.vue - 回测面板

### Week 2 文件
- frontend/src/composables/useNotifications.js - 通知管理
- frontend/src/components/AlertManager.vue - 预警管理组件
- frontend/src/composables/useMarketStream.js - WebSocket价格检查

---

## 注意事项

1. **浏览器通知**: 首次使用需要点击 "启用通知" 授权
2. **预警触发**: 同一规则5分钟内不会重复触发
3. **导出格式**: 支持 CSV 和 Excel 两种格式
4. **数据实时性**: 预警基于 WebSocket 实时数据流

---

最后更新: 2026-04-29
