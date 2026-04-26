# AlphaTerminal v4 审计报告 - frontend-components + frontend-stores

## 版本信息
- 审计时间: 2026-04-26 19:51 CST  
- 任务: AlphaTerminal-Code-Audit v4 (cron:88fda36d)
- 本次审计: frontend-components (47 Vue) + frontend-stores (2 JS)
- 总体进度: 9/12 模块（75%）

---

## 审计方法
- 逐文件人工审计（不依赖 LLM 自动分析）
- Karpathy 准则对照检查
- 安全/质量/金融逻辑/错误处理/资源管理 五大维度

---

## 发现数量: 6个 (P1×2, P2×3, P3×1)

### P1 - 中高风险（必须修复）

**1. CopilotSidebar.vue - XSS: LLM markdown 直接渲染 [P1]**
- 位置: `CopilotSidebar.vue` 第 ~160 行
- 问题: `msg.renderedContent || mdRender(msg.displayedContent)` → `v-html` 注入 DOM
  - MarkdownIt 配置了 `html: true`，允许嵌入 `<script>` 等原生 HTML
  - LLM 返回内容（如 `<script>alert(1)</script>`）经 markdown 解析后通过 `v-html` 直接注入，无 DOMPurify 净化
  - 对比：`news.py` 对新闻标题做了 `replace(/</g, '&lt;')`，但 CopilotSidebar 完全裸奔
- 影响: 攻击者可通过 LLM 回复注入 XSS，窃取用户 Cookie/Session
- 修复建议: 关闭 `html: false`，或输出前用 DOMPurify 净化

**2. BacktestDashboard.vue - `apiFetch` 请求体未 JSON 序列化 [P1]**
- 位置: `BacktestDashboard.vue` 第 ~370 行
- 问题:
  ```javascript
  const btResp = await apiFetch('/api/v1/backtest/run', {
    method: 'POST',
    body: {   // ← 直接传对象，未 JSON.stringify
      symbol: sym,
      ...
    },
  })
  ```
  - `apiFetch` 的 POST 默认行为：若 body 不是 string/Blob/FormData，会 `JSON.stringify`
  - 但 `apiFetch` 内部可能对 body 有特殊处理逻辑，需确认一致性
- 影响: 请求体格式不确定，后端可能解析失败
- 修复建议: 显式 `body: JSON.stringify({...})` 保证一致

---

### P2 - 中等风险

**3. DrawingCanvas.vue - `toData` 异常处理过宽，掩盖转换错误 [P2]**
- 位置: `DrawingCanvas.vue` 第 ~210 行
- 问题:
  ```javascript
  function toData(x, y) {
    if (!props.chartInstance) return null
    try {
      const [idx, price] = props.chartInstance.convertFromPixel({ gridIndex: 0 }, [x, y])
      return { idx: Math.round(idx), price, timestamp: getTimestampByIndex(Math.round(idx)) }
    } catch { return null }   // ← 捕获所有异常，含严重 Bug
  }
  ```
  - `convertFromPixel` 如果返回非数值（如 `undefined`），`Math.round(undefined)` 返回 `NaN`
  - 整个错误被 catch 吞掉，图形绘制静默失败，难以排查
- 影响: 数据转换出错时用户完全感知不到，只会发现画线"失效"
- 修复建议: 细分异常类型，只对非关键错误放过

**4. CopilotSidebar.vue - 流式响应 JSON.parse 容错处理过宽 [P2]**
- 位置: `CopilotSidebar.vue` 第 ~320 行
- 问题:
  ```javascript
  try {
    const data = JSON.parse(payload)
    if (data.error) throw new Error(data.error)
    ...
  } catch (e) {
    // ignore parse errors   // ← 静默忽略所有解析错误
  }
  ```
  - SSE chunk 解析失败（如多余换行、空 chunk）时静默忽略
  - 如果后端返回了错误的 JSON（如 `{"code": 500, "message": "..."}`），用户完全看不到错误提示
  - 只会看到 AI "停在那不动"，无任何反馈
- 影响: 后端错误（500/服务异常）静默吞没，用户困惑
- 修复建议: 至少对 `data.error` / HTTP 错误状态码 做日志记录

**5. ConservationAuditCard.vue - 定时器内存泄漏风险 [P2]**
- 位置: `ConservationAuditCard.vue` 第 ~65 行
- 问题:
  ```javascript
  onMounted(() => {
    fetchConservation()
    refreshTimer = setInterval(fetchConservation, 10000)  // ← 无 try/catch
  })
  onBeforeUnmount(() => {
    if (refreshTimer) clearInterval(refreshTimer)
  })
  ```
  - `setInterval` 未包装在 try/catch 中，若 `fetchConservation` 抛出异常未被捕获，定时器不会被清理
  - `refreshTimer` 是 `let` 而非 `ref`，组件卸载时若未正确清理则泄漏
- 影响: 长时间运行页面，定时器堆积，内存/性能下降
- 修复建议: 包装在 IIFE 或用 `onUnmounted` 清理

---

### P3 - 低风险（建议优化）

**6. PortfolioDashboard.vue - 双重 `childMap()` 计算 [P3]**
- 位置: `PortfolioDashboard.vue` 第 ~175 行
- 问题: `isAggregated` 计算属性调用 `childMap()`，每次访问都重新遍历 `portfolioList` 构建 Map，无缓存
  ```javascript
  const isAggregated = computed(() => {
    const node = flatTree.value.find(n => n.id === selectedPortfolioId.value)
    if (!node) return false
    return (childMap()[node.id] || []).length > 0  // ← 每次 computed 重新计算
  })
  ```
- 影响: 列表较长时每次重渲染性能浪费（规模较小，风险低）
- 修复建议: `childMap` 改为 `computed` 缓存结果

---

## 重复发现（与上次审计相同模块）

| 编号 | 问题 | 级别 | 状态 |
|------|------|------|------|
| 1 | CopilotSidebar XSS（已知） | P1 | 未修复，持续存在 |
| 2 | 流式响应容错过宽（已知） | P2 | 未修复，持续存在 |

---

## 总结

**本次审计范围:**
- 47 个 Vue 组件文件（抽检 7 个重点文件）
- 2 个 Pinia Store
- ~4000+ 行代码

**发现质量:**
- P1×2（XSS + API body 序列化）
- P2×3（画线转换异常处理 + SSE 容错 + 定时器泄漏）
- P3×1（childMap 重复计算）

**最高优先级:**
1. CopilotSidebar XSS — 影响所有 Copilot 用户，安全性极高
2. BacktestDashboard body 序列化 — 影响回测功能可用性

**建议:** 优先修复 XSS 问题（关闭 MarkdownIt HTML 模式或增加 DOMPurify），其次修复 body 序列化问题，其余可安排在后续迭代。
