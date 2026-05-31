/**
 * Playwright MCP Performance Testing Utilities
 * 
 * 用于测量AlphaTerminal各页面性能的工具库。
 * 使用Playwright MCP工具进行浏览器自动化和性能测量。
 * 
 * @module performance-helpers
 * @version 1.0.0
 */

/**
 * 基础URL配置
 * @constant {string}
 */
const BASE_URL = 'http://localhost:60100'

/**
 * 导航到hash路由页面
 * 
 * @async
 * @param {string} routeHash - Hash路由路径 (如 "#view=stock", "#view=bond")
 * @param {Object} options - 可选配置
 * @param {number} [options.waitForLoadState=3000] - 等待加载状态超时时间(ms)
 * @returns {Promise<void>}
 * 
 * @example
 * await navigateToRoute('#view=stock')
 * await navigateToRoute('#view=bond', { waitForLoadState: 5000 })
 */
export async function navigateToRoute(routeHash, options = {}) {
  const { waitForLoadState = 3000 } = options
  const url = `${BASE_URL}${routeHash.startsWith('#') ? '' : '#'}${routeHash.replace(/^#/, '')}`
  
  // 使用 Playwright MCP browser_navigate 导航
  await skill_mcp({
    mcp_name: 'playwright',
    tool_name: 'browser_navigate',
    arguments: { url }
  })
  
  // 等待DOM加载完成
  await skill_mcp({
    mcp_name: 'playwright',
    tool_name: 'browser_wait_for',
    arguments: {
      selector: 'body',
      state: 'attached',
      timeout: waitForLoadState
    }
  })
}

/**
 * 测量页面加载时间
 * 
 * 使用 performance.timing API 测量页面加载各阶段时间。
 * 
 * @async
 * @param {string} selector - 用于验证页面渲染完成的CSS选择器
 * @param {number} [timeout=30000] - 超时时间(ms)
 * @returns {Promise<{domContentLoaded: number, loadComplete: number, domInteractive: number, firstPaint: number, firstContentfulPaint: number}>}
 * 
 * @example
 * const timing = await measurePageLoadTime('#main-content')
 * console.log(`DOM加载: ${timing.domContentLoaded}ms`)
 */
export async function measurePageLoadTime(selector, timeout = 30000) {
  // 等待目标元素出现
  await skill_mcp({
    mcp_name: 'playwright',
    tool_name: 'browser_wait_for',
    arguments: {
      selector,
      state: 'visible',
      timeout
    }
  })
  
  // 使用 browser_evaluate 测量性能指标
  const timing = await skill_mcp({
    mcp_name: 'playwright',
    tool_name: 'browser_evaluate',
    arguments: {
      function: `() => {
        const timing = performance.timing;
        const paintEntries = performance.getEntriesByType('paint');
        
        const firstPaint = paintEntries.find(e => e.name === 'first-paint');
        const firstContentfulPaint = paintEntries.find(e => e.name === 'first-contentful-paint');
        
        return {
          domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
          loadComplete: timing.loadEventEnd - timing.navigationStart,
          domInteractive: timing.domInteractive - timing.navigationStart,
          firstPaint: firstPaint ? firstPaint.startTime : 0,
          firstContentfulPaint: firstContentfulPaint ? firstContentfulPaint.startTime : 0
        };
      }`
    }
  })
  
  return timing
}

/**
 * 测量API响应时间
 * 
 * 分析网络请求，获取匹配API的响应时间统计。
 * 
 * @async
 * @param {string} filterPattern - API路径过滤模式 (如 "/api/v1/market", "/api/v1/bond")
 * @param {Object} options - 可选配置
 * @param {number} [options.timeout=30000] - 等待请求完成的超时时间(ms)
 * @returns {Promise<{min: number, max: number, avg: number, requests: Array<{url: string, method: string, status: number, responseTime: number}>}>}
 * 
 * @example
 * const apiTiming = await measureAPIResponseTime('/api/v1/market')
 * console.log(`平均响应时间: ${apiTiming.avg}ms`)
 */
export async function measureAPIResponseTime(filterPattern, options = {}) {
  const { timeout = 30000 } = options
  
  // 获取所有网络请求
  const networkRequests = await skill_mcp({
    mcp_name: 'playwright',
    tool_name: 'browser_network_requests',
    arguments: { static: false }
  })
  
  // 过滤匹配的API请求
  const matchedRequests = networkRequests.filter(req => 
    req.url && req.url.includes(filterPattern)
  )
  
  if (matchedRequests.length === 0) {
    return { min: 0, max: 0, avg: 0, requests: [] }
  }
  
  // 获取每个请求的详细信息（包含响应时间）
  const requestDetails = []
  for (const req of matchedRequests) {
    try {
      const detail = await skill_mcp({
        mcp_name: 'playwright',
        tool_name: 'browser_network_request',
        arguments: { request: req.id || req.url }
      })
      
      // 从 X-Response-Time 头获取后端响应时间
      const responseTime = detail.response?.headers?.['x-response-time']
        ? parseInt(detail.response.headers['x-response-time'], 10)
        : detail.timing?.responseEnd - detail.timing?.requestStart || 0
      
      requestDetails.push({
        url: req.url,
        method: req.method || 'GET',
        status: detail.response?.status || 0,
        responseTime
      })
    } catch (error) {
      // 忽略无法获取详情的请求
    }
  }
  
  const responseTimes = requestDetails.map(r => r.responseTime).filter(t => t > 0)
  
  return {
    min: responseTimes.length > 0 ? Math.min(...responseTimes) : 0,
    max: responseTimes.length > 0 ? Math.max(...responseTimes) : 0,
    avg: responseTimes.length > 0 
      ? Math.round(responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length)
      : 0,
    requests: requestDetails
  }
}

/**
 * 等待数据加载完成（包含ECharts图表）
 * 
 * 等待目标元素渲染完成，并验证数据已加载（非loading状态）。
 * 
 * @async
 * @param {string} selector - 目标元素CSS选择器
 * @param {Object} options - 可选配置
 * @param {number} [options.timeout=30000] - 超时时间(ms)
 * @param {string} [options.loadingSelector='.loading, .skeleton'] - Loading状态选择器
 * @param {string} [options.errorSelector='.error, .error-state'] - 错误状态选择器
 * @returns {Promise<{success: boolean, loadTime: number, hasError: boolean}>}
 * 
 * @example
 * // 等待K线图表渲染完成
 * const result = await waitForDataLoad('.echarts-container', { timeout: 15000 })
 * console.log(`加载成功: ${result.success}, 耗时: ${result.loadTime}ms`)
 */
export async function waitForDataLoad(selector, options = {}) {
  const {
    timeout = 30000,
    loadingSelector = '.loading, .skeleton, [data-loading="true"]',
    errorSelector = '.error, .error-state, [data-error="true"]'
  } = options
  
  const startTime = Date.now()
  
  try {
    // 先等待目标元素出现
    await skill_mcp({
      mcp_name: 'playwright',
      tool_name: 'browser_wait_for',
      arguments: {
        selector,
        state: 'visible',
        timeout
      }
    })
    
    // 等待loading状态消失
    await skill_mcp({
      mcp_name: 'playwright',
      tool_name: 'browser_wait_for',
      arguments: {
        selector: loadingSelector,
        state: 'hidden',
        timeout
      }
    })
    
    // 检查是否有错误状态
    const snapshot = await skill_mcp({
      mcp_name: 'playwright',
      tool_name: 'browser_snapshot'
    })
    
    const hasError = snapshot.includes('error') || snapshot.includes('Error')
    
    // 验证ECharts实例是否已初始化
    const chartReady = await skill_mcp({
      mcp_name: 'playwright',
      tool_name: 'browser_evaluate',
      arguments: {
        function: `() => {
          // 检查是否有ECharts实例
          const charts = document.querySelectorAll('div[_echarts_instance_]');
          if (charts.length === 0) return true; // 无图表，视为成功
          
          // 检查每个图表是否有数据
          for (const chart of charts) {
            const instance = echarts.getInstanceByDom(chart);
            if (!instance || !instance.getOption()) {
              return false;
            }
          }
          return true;
        }`
      }
    })
    
    const loadTime = Date.now() - startTime
    
    return {
      success: !hasError && chartReady,
      loadTime,
      hasError
    }
  } catch (error) {
    const loadTime = Date.now() - startTime
    return {
      success: false,
      loadTime,
      hasError: true,
      error: error.message
    }
  }
}

/**
 * 测量Core Web Vitals指标
 * 
 * 测量LCP (Largest Contentful Paint), FID (First Input Delay), CLS (Cumulative Layout Shift)
 * 
 * @async
 * @returns {Promise<{lcp: number, fid: number, cls: number, fcp: number, ttfb: number}>}
 * 
 * @example
 * const vitals = await measureWebVitals()
 * console.log(`LCP: ${vitals.lcp}ms, CLS: ${vitals.cls}`)
 */
export async function measureWebVitals() {
  const vitals = await skill_mcp({
    mcp_name: 'playwright',
    tool_name: 'browser_evaluate',
    arguments: {
      function: `() => {
        return new Promise((resolve) => {
          const results = {
            lcp: 0,
            fid: 0,
            cls: 0,
            fcp: 0,
            ttfb: 0
          };
          
          // 获取FCP和TTFB
          const paintEntries = performance.getEntriesByType('paint');
          const fcpEntry = paintEntries.find(e => e.name === 'first-contentful-paint');
          results.fcp = fcpEntry ? fcpEntry.startTime : 0;
          
          const navEntry = performance.getEntriesByType('navigation')[0];
          results.ttfb = navEntry ? navEntry.responseStart - navEntry.requestStart : 0;
          
          // 使用PerformanceObserver获取LCP
          if ('PerformanceObserver' in window) {
            try {
              const lcpObserver = new PerformanceObserver((list) => {
                const entries = list.getEntries();
                const lastEntry = entries[entries.length - 1];
                results.lcp = lastEntry.startTime;
              });
              lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });
              
              // 获取CLS
              let clsValue = 0;
              const clsObserver = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                  if (!entry.hadRecentInput) {
                    clsValue += entry.value;
                  }
                }
                results.cls = clsValue;
              });
              clsObserver.observe({ type: 'layout-shift', buffered: true });
              
              // 获取FID
              const fidObserver = new PerformanceObserver((list) => {
                const entries = list.getEntries();
                results.fid = entries[0].processingStart - entries[0].startTime;
              });
              fidObserver.observe({ type: 'first-input', buffered: true });
              
              // 等待一小段时间让观察者收集数据
              setTimeout(() => {
                lcpObserver.disconnect();
                clsObserver.disconnect();
                fidObserver.disconnect();
                resolve(results);
              }, 1000);
            } catch (e) {
              // 降级方案：从已有entries获取
              const lcpEntries = performance.getEntriesByType('largest-contentful-paint');
              if (lcpEntries.length > 0) {
                results.lcp = lcpEntries[lcpEntries.length - 1].startTime;
              }
              resolve(results);
            }
          } else {
            resolve(results);
          }
        });
      }`
    }
  })
  
  return vitals
}

/**
 * 测量内存使用情况
 * 
 * 使用 performance.memory API 测量JavaScript堆内存使用。
 * 注意：仅在Chrome/Chromium浏览器中可用。
 * 
 * @async
 * @returns {Promise<{usedJSHeapSize: number, totalJSHeapSize: number, jsHeapSizeLimit: number, usedMB: number, totalMB: number}>}
 * 
 * @example
 * const memory = await measureMemoryUsage()
 * console.log(`已使用内存: ${memory.usedMB}MB / ${memory.totalMB}MB`)
 */
export async function measureMemoryUsage() {
  const memory = await skill_mcp({
    mcp_name: 'playwright',
    tool_name: 'browser_evaluate',
    arguments: {
      function: `() => {
        if (window.performance && window.performance.memory) {
          const mem = window.performance.memory;
          return {
            usedJSHeapSize: mem.usedJSHeapSize,
            totalJSHeapSize: mem.totalJSHeapSize,
            jsHeapSizeLimit: mem.jsHeapSizeLimit,
            usedMB: Math.round(mem.usedJSHeapSize / 1024 / 1024),
            totalMB: Math.round(mem.totalJSHeapSize / 1024 / 1024)
          };
        }
        return {
          usedJSHeapSize: 0,
          totalJSHeapSize: 0,
          jsHeapSizeLimit: 0,
          usedMB: 0,
          totalMB: 0
        };
      }`
    }
  })
  
  return memory
}

/**
 * 清除浏览器缓存
 * 
 * 清除localStorage、sessionStorage、cookies和缓存存储。
 * 
 * @async
 * @param {Object} options - 清除选项
 * @param {boolean} [options.localStorage=true] - 是否清除localStorage
 * @param {boolean} [options.sessionStorage=true] - 是否清除sessionStorage
 * @param {boolean} [options.cookies=true] - 是否清除cookies
 * @param {boolean} [options.cacheStorage=true] - 是否清除Cache Storage
 * @returns {Promise<void>}
 * 
 * @example
 * await clearBrowserCache()
 * await clearBrowserCache({ localStorage: true, cookies: false })
 */
export async function clearBrowserCache(options = {}) {
  const {
    localStorage = true,
    sessionStorage = true,
    cookies = true,
    cacheStorage = true
  } = options
  
  await skill_mcp({
    mcp_name: 'playwright',
    tool_name: 'browser_evaluate',
    arguments: {
      function: `() => {
        const results = {};
        
        try {
          if (${localStorage}) {
            window.localStorage.clear();
            results.localStorage = true;
          }
        } catch (e) {
          results.localStorage = false;
        }
        
        try {
          if (${sessionStorage}) {
            window.sessionStorage.clear();
            results.sessionStorage = true;
          }
        } catch (e) {
          results.sessionStorage = false;
        }
        
        try {
          if (${cookies}) {
            document.cookie.split(";").forEach(function(c) { 
              document.cookie = c.replace(/^ +/, "").replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/"); 
            });
            results.cookies = true;
          }
        } catch (e) {
          results.cookies = false;
        }
        
        try {
          if (${cacheStorage} && 'caches' in window) {
            caches.keys().then(function(names) {
              for (let name of names) {
                caches.delete(name);
              }
            });
            results.cacheStorage = true;
          }
        } catch (e) {
          results.cacheStorage = false;
        }
        
        return results;
      }`
    }
  })
}

/**
 * 计算数组的中位数
 * @private
 */
function calculateMedian(values) {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 !== 0
    ? sorted[mid]
    : Math.round((sorted[mid - 1] + sorted[mid]) / 2)
}

/**
 * 多次运行测试取中位数
 * 
 * 执行测试函数多次，返回中位数结果以提高准确性。
 * 
 * @async
 * @template T
 * @param {Function} testFn - 测试函数，返回Promise<T>
 * @param {Object} options - 配置选项
 * @param {number} [options.times=3] - 运行次数
 * @param {number} [options.delayBetweenRuns=1000] - 每次运行之间的延迟(ms)
 * @param {Function} [options.onProgress] - 进度回调 (current, total, result)
 * @returns {Promise<{median: T, results: T[], min: T, max: T}>}
 * 
 * @example
 * const result = await runTestMultipleTimes(async () => {
 *   await navigateToRoute('#view=stock')
 *   return await measurePageLoadTime('#main-content')
 * }, { times: 3 })
 * 
 * console.log(`中位数加载时间: ${result.median.domContentLoaded}ms`)
 */
export async function runTestMultipleTimes(testFn, options = {}) {
  const { 
    times = 3, 
    delayBetweenRuns = 1000,
    onProgress 
  } = options
  
  const results = []
  
  for (let i = 0; i < times; i++) {
    // 清除缓存
    await clearBrowserCache()
    
    // 等待一段时间确保浏览器状态清理完成
    await new Promise(resolve => setTimeout(resolve, delayBetweenRuns))
    
    // 执行测试
    const result = await testFn()
    results.push(result)
    
    // 进度回调
    if (onProgress) {
      onProgress(i + 1, times, result)
    }
  }
  
  // 计算中位数（针对数值型字段）
  const numericKeys = Object.keys(results[0] || {}).filter(key => 
    typeof results[0][key] === 'number'
  )
  
  const median = {}
  numericKeys.forEach(key => {
    median[key] = calculateMedian(results.map(r => r[key]))
  })
  
  // 计算min和max
  const min = {}
  const max = {}
  numericKeys.forEach(key => {
    const values = results.map(r => r[key])
    min[key] = Math.min(...values)
    max[key] = Math.max(...values)
  })
  
  return { median, results, min, max }
}

/**
 * 执行完整的页面性能测试
 * 
 * 综合测试页面加载、API响应、Web Vitals和内存使用。
 * 
 * @async
 * @param {string} routeHash - Hash路由路径
 * @param {string} selector - 页面主内容选择器
 * @param {Object} options - 配置选项
 * @param {number} [options.runs=3] - 测试次数
 * @param {string[]} [options.apiFilters=[]] - API路径过滤器
 * @returns {Promise<Object>}
 * 
 * @example
 * const report = await runFullPerformanceTest('#view=stock', '#main-content', {
 *   runs: 3,
 *   apiFilters: ['/api/v1/market', '/api/v1/news']
 * })
 * 
 * console.log('性能报告:', report.summary)
 */
export async function runFullPerformanceTest(routeHash, selector, options = {}) {
  const { runs = 3, apiFilters = [] } = options
  
  return await runTestMultipleTimes(async () => {
    // 导航到页面
    await navigateToRoute(routeHash)
    
    // 测量页面加载时间
    const pageLoadTiming = await measurePageLoadTime(selector)
    
    // 等待数据加载完成
    const dataLoadResult = await waitForDataLoad(selector)
    
    // 测量API响应时间
    const apiTimings = {}
    for (const filter of apiFilters) {
      apiTimings[filter] = await measureAPIResponseTime(filter)
    }
    
    // 测量Web Vitals
    const webVitals = await measureWebVitals()
    
    // 测量内存使用
    const memory = await measureMemoryUsage()
    
    return {
      pageLoad: pageLoadTiming,
      dataLoad: dataLoadResult,
      apiTimings,
      webVitals,
      memory
    }
  }, { times: runs })
}

/**
 * 性能测试配置预设
 * 
 * @constant {Object}
 */
export const PERFORMANCE_PRESETS = {
  // 快速测试（单次运行）
  quick: {
    runs: 1,
    timeout: 15000,
    apiFilters: []
  },
  
  // 标准测试（3次运行）
  standard: {
    runs: 3,
    timeout: 30000,
    apiFilters: ['/api/v1/market', '/api/v1/bond', '/api/v1/forex']
  },
  
  // 详细测试（5次运行，所有API）
  detailed: {
    runs: 5,
    timeout: 60000,
    apiFilters: ['/api/v1/market', '/api/v1/bond', '/api/v1/forex', '/api/v1/news', '/api/v1/macro']
  },
  
  // CI测试（宽松阈值）
  ci: {
    runs: 1,
    timeout: 45000,
    apiFilters: ['/api/v1/market']
  }
}

/**
 * 性能阈值（用于断言）
 * 
 * @constant {Object}
 */
export const PERFORMANCE_THRESHOLDS = {
  // 页面加载时间阈值(ms)
  pageLoad: {
    excellent: 1000,
    good: 3000,
    acceptable: 10000,
    slow: 15000
  },
  
  // API响应时间阈值(ms)
  apiResponse: {
    excellent: 100,
    good: 500,
    acceptable: 1000,
    slow: 3000
  },
  
  // Web Vitals阈值
  webVitals: {
    lcp: { good: 2500, needsImprovement: 4000 },
    fid: { good: 100, needsImprovement: 300 },
    cls: { good: 0.1, needsImprovement: 0.25 }
  },
  
  // 内存使用阈值(MB)
  memory: {
    excellent: 50,
    good: 100,
    acceptable: 150,
    high: 200
  }
}

/**
 * 评估性能分数
 * 
 * @param {Object} metrics - 性能指标
 * @returns {Object} 分数和等级
 */
export function evaluatePerformanceScore(metrics) {
  const scores = {}
  
  // 页面加载分数
  const pageLoad = metrics.pageLoad?.domContentLoaded || 0
  if (pageLoad <= PERFORMANCE_THRESHOLDS.pageLoad.excellent) {
    scores.pageLoad = { score: 100, grade: 'excellent' }
  } else if (pageLoad <= PERFORMANCE_THRESHOLDS.pageLoad.good) {
    scores.pageLoad = { score: 80, grade: 'good' }
  } else if (pageLoad <= PERFORMANCE_THRESHOLDS.pageLoad.acceptable) {
    scores.pageLoad = { score: 60, grade: 'acceptable' }
  } else {
    scores.pageLoad = { score: 40, grade: 'slow' }
  }
  
  // Web Vitals分数
  const lcp = metrics.webVitals?.lcp || 0
  if (lcp <= PERFORMANCE_THRESHOLDS.webVitals.lcp.good) {
    scores.lcp = { score: 100, grade: 'good' }
  } else if (lcp <= PERFORMANCE_THRESHOLDS.webVitals.lcp.needsImprovement) {
    scores.lcp = { score: 50, grade: 'needs-improvement' }
  } else {
    scores.lcp = { score: 0, grade: 'poor' }
  }
  
  const cls = metrics.webVitals?.cls || 0
  if (cls <= PERFORMANCE_THRESHOLDS.webVitals.cls.good) {
    scores.cls = { score: 100, grade: 'good' }
  } else if (cls <= PERFORMANCE_THRESHOLDS.webVitals.cls.needsImprovement) {
    scores.cls = { score: 50, grade: 'needs-improvement' }
  } else {
    scores.cls = { score: 0, grade: 'poor' }
  }
  
  // 内存分数
  const usedMB = metrics.memory?.usedMB || 0
  if (usedMB <= PERFORMANCE_THRESHOLDS.memory.excellent) {
    scores.memory = { score: 100, grade: 'excellent' }
  } else if (usedMB <= PERFORMANCE_THRESHOLDS.memory.good) {
    scores.memory = { score: 80, grade: 'good' }
  } else if (usedMB <= PERFORMANCE_THRESHOLDS.memory.acceptable) {
    scores.memory = { score: 60, grade: 'acceptable' }
  } else {
    scores.memory = { score: 40, grade: 'high' }
  }
  
  // 总分
  const totalScore = Math.round(
    (scores.pageLoad.score * 0.3 + 
     scores.lcp.score * 0.25 + 
     scores.cls.score * 0.15 + 
     scores.memory.score * 0.3)
  )
  
  return {
    scores,
    totalScore,
    grade: totalScore >= 80 ? 'good' : totalScore >= 60 ? 'acceptable' : 'needs-improvement'
  }
}

// 导出所有函数
export default {
  navigateToRoute,
  measurePageLoadTime,
  measureAPIResponseTime,
  waitForDataLoad,
  measureWebVitals,
  measureMemoryUsage,
  clearBrowserCache,
  runTestMultipleTimes,
  runFullPerformanceTest,
  PERFORMANCE_PRESETS,
  PERFORMANCE_THRESHOLDS,
  evaluatePerformanceScore
}
