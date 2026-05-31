# Performance Testing Utilities

Playwright MCP性能测试工具库，用于测量AlphaTerminal各页面性能。

## 📦 安装

工具库位于 `frontend/tests/e2e/utils/performance-helpers.js`，无需额外安装。

## 🚀 快速开始

### 基本用法

```javascript
import { 
  navigateToRoute, 
  measurePageLoadTime,
  waitForDataLoad 
} from './utils/performance-helpers'

test('should load stock dashboard', async ({ page }) => {
  // 导航到页面
  await navigateToRoute('#view=stock')
  
  // 测量加载时间
  const timing = await measurePageLoadTime('#main-content')
  console.log(`DOM加载: ${timing.domContentLoaded}ms`)
  
  // 等待数据渲染完成
  const result = await waitForDataLoad('#main-content')
  expect(result.success).toBe(true)
})
```

### 多次测试取中位数

```javascript
import { runTestMultipleTimes } from './utils/performance-helpers'

const result = await runTestMultipleTimes(async () => {
  await navigateToRoute('#view=stock')
  return await measurePageLoadTime('#main-content')
}, { times: 3 })

console.log(`中位数加载时间: ${result.median.domContentLoaded}ms`)
```

## 📚 API参考

### 导航函数

#### `navigateToRoute(routeHash, options?)`

导航到hash路由页面。

**参数:**
- `routeHash` (string): Hash路由路径 (如 `"#view=stock"`)
- `options.waitForLoadState` (number): 等待加载状态超时(ms)，默认3000

**示例:**
```javascript
await navigateToRoute('#view=stock')
await navigateToRoute('#view=bond', { waitForLoadState: 5000 })
```

---

### 性能测量函数

#### `measurePageLoadTime(selector, timeout?)`

测量页面加载时间。

**参数:**
- `selector` (string): 用于验证页面渲染完成的CSS选择器
- `timeout` (number): 超时时间(ms)，默认30000

**返回值:**
```javascript
{
  domContentLoaded: number,      // DOM加载完成时间(ms)
  loadComplete: number,          // 页面完全加载时间(ms)
  domInteractive: number,        // DOM可交互时间(ms)
  firstPaint: number,            // 首次绘制时间(ms)
  firstContentfulPaint: number   // 首次内容绘制时间(ms)
}
```

**示例:**
```javascript
const timing = await measurePageLoadTime('#main-content')
console.log(`DOM加载: ${timing.domContentLoaded}ms`)
console.log(`FCP: ${timing.firstContentfulPaint}ms`)
```

---

#### `measureAPIResponseTime(filterPattern, options?)`

测量API响应时间。

**参数:**
- `filterPattern` (string): API路径过滤模式
- `options.timeout` (number): 超时时间(ms)，默认30000

**返回值:**
```javascript
{
  min: number,      // 最小响应时间(ms)
  max: number,      // 最大响应时间(ms)
  avg: number,      // 平均响应时间(ms)
  requests: [       // 请求详情数组
    {
      url: string,
      method: string,
      status: number,
      responseTime: number
    }
  ]
}
```

**示例:**
```javascript
const apiTiming = await measureAPIResponseTime('/api/v1/market')
console.log(`平均响应: ${apiTiming.avg}ms`)
console.log(`请求总数: ${apiTiming.requests.length}`)
```

---

#### `waitForDataLoad(selector, options?)`

等待数据加载完成（包含ECharts图表）。

**参数:**
- `selector` (string): 目标元素CSS选择器
- `options.timeout` (number): 超时时间(ms)，默认30000
- `options.loadingSelector` (string): Loading状态选择器
- `options.errorSelector` (string): 错误状态选择器

**返回值:**
```javascript
{
  success: boolean,    // 是否成功
  loadTime: number,    // 加载耗时(ms)
  hasError: boolean,   // 是否有错误
  error?: string       // 错误信息
}
```

**示例:**
```javascript
const result = await waitForDataLoad('.echarts-container', {
  timeout: 15000,
  loadingSelector: '.loading, .skeleton'
})
expect(result.success).toBe(true)
```

---

#### `measureWebVitals()`

测量Core Web Vitals指标。

**返回值:**
```javascript
{
  lcp: number,   // Largest Contentful Paint (ms)
  fid: number,   // First Input Delay (ms)
  cls: number,   // Cumulative Layout Shift
  fcp: number,   // First Contentful Paint (ms)
  ttfb: number   // Time to First Byte (ms)
}
```

**示例:**
```javascript
const vitals = await measureWebVitals()
console.log(`LCP: ${vitals.lcp}ms`)
console.log(`CLS: ${vitals.cls}`)
```

---

#### `measureMemoryUsage()`

测量内存使用情况。

**返回值:**
```javascript
{
  usedJSHeapSize: number,   // 已使用堆大小(bytes)
  totalJSHeapSize: number,  // 总堆大小(bytes)
  jsHeapSizeLimit: number,  // 堆大小限制(bytes)
  usedMB: number,           // 已使用(MB)
  totalMB: number           // 总分配(MB)
}
```

**示例:**
```javascript
const memory = await measureMemoryUsage()
console.log(`已使用内存: ${memory.usedMB}MB / ${memory.totalMB}MB`)
```

---

### 工具函数

#### `clearBrowserCache(options?)`

清除浏览器缓存。

**参数:**
- `options.localStorage` (boolean): 是否清除localStorage，默认true
- `options.sessionStorage` (boolean): 是否清除sessionStorage，默认true
- `options.cookies` (boolean): 是否清除cookies，默认true
- `options.cacheStorage` (boolean): 是否清除Cache Storage，默认true

**示例:**
```javascript
await clearBrowserCache()
await clearBrowserCache({ localStorage: true, cookies: false })
```

---

#### `runTestMultipleTimes(testFn, options?)`

多次运行测试取中位数。

**参数:**
- `testFn` (Function): 测试函数
- `options.times` (number): 运行次数，默认3
- `options.delayBetweenRuns` (number): 每次运行之间的延迟(ms)，默认1000
- `options.onProgress` (Function): 进度回调

**返回值:**
```javascript
{
  median: T,      // 中位数结果
  results: T[],   // 所有结果
  min: T,         // 最小值
  max: T          // 最大值
}
```

**示例:**
```javascript
const result = await runTestMultipleTimes(async () => {
  await navigateToRoute('#view=stock')
  return await measurePageLoadTime('#main-content')
}, { 
  times: 3,
  onProgress: (current, total, result) => {
    console.log(`Run ${current}/${total}: ${result.domContentLoaded}ms`)
  }
})
```

---

#### `runFullPerformanceTest(routeHash, selector, options?)`

执行完整的页面性能测试。

**参数:**
- `routeHash` (string): Hash路由路径
- `selector` (string): 页面主内容选择器
- `options.runs` (number): 测试次数，默认3
- `options.apiFilters` (string[]): API路径过滤器

**返回值:**
```javascript
{
  median: {
    pageLoad: {...},
    dataLoad: {...},
    apiTimings: {...},
    webVitals: {...},
    memory: {...}
  },
  results: [...],
  min: {...},
  max: {...}
}
```

**示例:**
```javascript
const report = await runFullPerformanceTest('#view=futures', '.futures-dashboard', {
  runs: 3,
  apiFilters: ['/api/v1/futures']
})

console.log(`页面加载: ${report.median.pageLoad.domContentLoaded}ms`)
console.log(`API平均响应: ${report.median.apiTimings['/api/v1/futures'].avg}ms`)
```

---

### 常量与预设

#### `PERFORMANCE_THRESHOLDS`

性能阈值常量。

```javascript
import { PERFORMANCE_THRESHOLDS } from './utils/performance-helpers'

// 页面加载时间阈值(ms)
PERFORMANCE_THRESHOLDS.pageLoad.excellent  // 1000
PERFORMANCE_THRESHOLDS.pageLoad.good       // 3000
PERFORMANCE_THRESHOLDS.pageLoad.acceptable // 10000
PERFORMANCE_THRESHOLDS.pageLoad.slow       // 15000

// API响应时间阈值(ms)
PERFORMANCE_THRESHOLDS.apiResponse.excellent  // 100
PERFORMANCE_THRESHOLDS.apiResponse.good       // 500
PERFORMANCE_THRESHOLDS.apiResponse.acceptable // 1000
PERFORMANCE_THRESHOLDS.apiResponse.slow       // 3000

// Web Vitals阈值
PERFORMANCE_THRESHOLDS.webVitals.lcp.good              // 2500
PERFORMANCE_THRESHOLDS.webVitals.lcp.needsImprovement  // 4000
PERFORMANCE_THRESHOLDS.webVitals.fid.good              // 100
PERFORMANCE_THRESHOLDS.webVitals.fid.needsImprovement  // 300
PERFORMANCE_THRESHOLDS.webVitals.cls.good              // 0.1
PERFORMANCE_THRESHOLDS.webVitals.cls.needsImprovement  // 0.25

// 内存使用阈值(MB)
PERFORMANCE_THRESHOLDS.memory.excellent  // 50
PERFORMANCE_THRESHOLDS.memory.good       // 100
PERFORMANCE_THRESHOLDS.memory.acceptable // 150
PERFORMANCE_THRESHOLDS.memory.high       // 200
```

---

#### `PERFORMANCE_PRESETS`

性能测试配置预设。

```javascript
import { PERFORMANCE_PRESETS } from './utils/performance-helpers'

// 快速测试（单次运行）
PERFORMANCE_PRESETS.quick
// { runs: 1, timeout: 15000, apiFilters: [] }

// 标准测试（3次运行）
PERFORMANCE_PRESETS.standard
// { runs: 3, timeout: 30000, apiFilters: ['/api/v1/market', '/api/v1/bond', ...] }

// 详细测试（5次运行，所有API）
PERFORMANCE_PRESETS.detailed
// { runs: 5, timeout: 60000, apiFilters: [...] }

// CI测试（宽松阈值）
PERFORMANCE_PRESETS.ci
// { runs: 1, timeout: 45000, apiFilters: ['/api/v1/market'] }
```

---

### 评估函数

#### `evaluatePerformanceScore(metrics)`

评估性能分数。

**参数:**
- `metrics` (Object): 性能指标对象

**返回值:**
```javascript
{
  scores: {
    pageLoad: { score: number, grade: string },
    lcp: { score: number, grade: string },
    cls: { score: number, grade: string },
    memory: { score: number, grade: string }
  },
  totalScore: number,  // 总分 (0-100)
  grade: string        // 'good' | 'acceptable' | 'needs-improvement'
}
```

**示例:**
```javascript
const metrics = {
  pageLoad: { domContentLoaded: 2000 },
  webVitals: { lcp: 2500, cls: 0.08 },
  memory: { usedMB: 80 }
}

const evaluation = evaluatePerformanceScore(metrics)
console.log(`性能分数: ${evaluation.totalScore}/100 (${evaluation.grade})`)
```

## 📊 完整示例

### 示例1: 测量单个页面性能

```javascript
test('should measure stock dashboard performance', async ({ page }) => {
  // 清除缓存
  await clearBrowserCache()
  
  // 导航到页面
  await navigateToRoute('#view=stock')
  
  // 测量加载时间
  const timing = await measurePageLoadTime('#main-content')
  console.log(`DOM加载: ${timing.domContentLoaded}ms`)
  
  // 等待数据加载
  const result = await waitForDataLoad('#main-content')
  expect(result.success).toBe(true)
  
  // 测量Web Vitals
  const vitals = await measureWebVitals()
  console.log(`LCP: ${vitals.lcp}ms, CLS: ${vitals.cls}`)
  
  // 断言
  expect(timing.domContentLoaded).toBeLessThan(PERFORMANCE_THRESHOLDS.pageLoad.acceptable)
  expect(vitals.lcp).toBeLessThan(PERFORMANCE_THRESHOLDS.webVitals.lcp.needsImprovement)
})
```

### 示例2: 多次测试取中位数

```javascript
test('should measure bond dashboard (3 runs)', async ({ page }) => {
  const result = await runTestMultipleTimes(async () => {
    await clearBrowserCache()
    await navigateToRoute('#view=bond')
    
    const timing = await measurePageLoadTime('.bond-dashboard')
    const vitals = await measureWebVitals()
    
    return {
      domContentLoaded: timing.domContentLoaded,
      lcp: vitals.lcp,
      cls: vitals.cls
    }
  }, { times: 3 })
  
  console.log('Bond Dashboard Performance (Median):')
  console.log(`  DOM加载: ${result.median.domContentLoaded}ms`)
  console.log(`  LCP: ${result.median.lcp}ms`)
  console.log(`  CLS: ${result.median.cls}`)
  
  expect(result.median.domContentLoaded).toBeLessThan(10000)
})
```

### 示例3: 完整性能报告

```javascript
test('should generate full performance report', async ({ page }) => {
  const report = await runFullPerformanceTest(
    '#view=futures',
    '.futures-dashboard',
    {
      runs: 3,
      apiFilters: ['/api/v1/futures']
    }
  )
  
  // 评估性能分数
  const evaluation = evaluatePerformanceScore(report.median)
  
  console.log('Performance Report:')
  console.log('===================')
  console.log(`页面加载: ${report.median.pageLoad?.domContentLoaded}ms`)
  console.log(`LCP: ${report.median.webVitals?.lcp}ms`)
  console.log(`CLS: ${report.median.webVitals?.cls}`)
  console.log(`内存使用: ${report.median.memory?.usedMB}MB`)
  console.log(`API平均响应: ${report.median.apiTimings?.['/api/v1/futures']?.avg}ms`)
  console.log(`\n总分: ${evaluation.totalScore}/100 (${evaluation.grade})`)
  
  expect(evaluation.totalScore).toBeGreaterThanOrEqual(60)
})
```

### 示例4: 内存泄漏检测

```javascript
test('should detect memory leaks', async ({ page }) => {
  const initialMemory = await measureMemoryUsage()
  
  // 循环导航
  for (let i = 0; i < 10; i++) {
    await navigateToRoute('#view=stock')
    await page.waitForTimeout(500)
    await navigateToRoute('#view=bond')
    await page.waitForTimeout(500)
  }
  
  const finalMemory = await measureMemoryUsage()
  const memoryGrowth = finalMemory.usedMB - initialMemory.usedMB
  
  console.log(`内存增长: ${memoryGrowth}MB`)
  
  // 断言：内存增长不应超过100MB
  expect(memoryGrowth).toBeLessThan(100)
})
```

## 🧪 运行测试

```bash
# 运行所有性能测试
npm run test:e2e performance-examples.spec.js

# 运行特定测试
npm run test:e2e performance-examples.spec.js -- --grep "stock dashboard"

# 运行CI测试
npm run test:e2e performance-examples.spec.js -- --grep "CI"
```

## 📝 注意事项

1. **ECharts图表检测**: `waitForDataLoad()` 会检查页面中的ECharts实例是否已初始化并加载数据。

2. **内存测量**: `measureMemoryUsage()` 仅在Chrome/Chromium浏览器中可用，其他浏览器返回0值。

3. **Web Vitals**: `measureWebVitals()` 使用PerformanceObserver API，需要等待约1秒收集数据。

4. **多次测试**: `runTestMultipleTimes()` 会在每次运行前自动清除浏览器缓存。

5. **CI环境**: 使用 `PERFORMANCE_PRESETS.ci` 预设，包含更宽松的超时和阈值。

## 🔧 故障排除

### 问题1: `measureAPIResponseTime()` 返回空结果

**原因**: 页面尚未发起API请求，或请求已完成。

**解决**: 在调用前等待数据加载完成：
```javascript
await waitForDataLoad('#main-content')
const apiTiming = await measureAPIResponseTime('/api/v1/market')
```

### 问题2: `measureWebVitals()` 返回0值

**原因**: 页面刚加载，PerformanceObserver尚未收集到数据。

**解决**: 等待页面稳定后再测量：
```javascript
await page.waitForTimeout(2000)
const vitals = await measureWebVitals()
```

### 问题3: `waitForDataLoad()` 超时

**原因**: 选择器不正确，或页面渲染时间过长。

**解决**: 
- 检查选择器是否正确
- 增加超时时间：`waitForDataLoad(selector, { timeout: 45000 })`
- 检查网络请求是否正常

## 📖 参考资料

- [Web Vitals](https://web.dev/vitals/)
- [Performance API](https://developer.mozilla.org/en-US/docs/Web/API/Performance)
- [Playwright API](https://playwright.dev/docs/api/class-page)
