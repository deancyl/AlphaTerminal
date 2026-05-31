/**
 * Phase 2 Core Pages Performance Tests
 * Tests 7 core market pages with performance metrics
 */

import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// Performance thresholds (milliseconds)
// Based on observed load times (~13s for Vue SPA initialization + API calls)
const THRESHOLDS = {
  stock: 15000,
  portfolio: 15000,
  fund: 15000,
  bond: 15000,
  futures: 15000,
  forex: 15000,
  macro: 15000
}

// Page configurations
// Note: Using generic selectors as Vue components use Tailwind classes
const PAGES = [
  {
    id: 'stock',
    route: '#view=stock',
    selector: '.grid-stack',  // DashboardGrid uses grid-stack class
    keyAPIs: ['/api/v1/market/overview', '/api/v1/market/sectors'],
    description: 'DashboardGrid - HTTP polling + WebSocket'
  },
  {
    id: 'portfolio',
    route: '#view=portfolio',
    selector: '.p-4',  // PortfolioDashboard uses p-4 class
    keyAPIs: ['/api/v1/portfolio/'],
    description: 'PortfolioDashboard - HTTP on-demand'
  },
  {
    id: 'fund',
    route: '#view=fund',
    selector: '.p-4',  // FundDashboard uses p-4 class
    keyAPIs: ['/api/v1/fund/open_fund_info'],
    description: 'FundDashboard - HTTP on-demand'
  },
  {
    id: 'bond',
    route: '#view=bond',
    selector: '.p-4',  // BondDashboard uses p-4 class
    keyAPIs: ['/api/v1/bond/curve'],
    description: 'BondDashboard - HTTP on-demand'
  },
  {
    id: 'futures',
    route: '#view=futures',
    selector: '.p-4',  // FuturesDashboard uses p-4 class
    keyAPIs: ['/api/v1/futures/main_indexes'],
    description: 'FuturesDashboard - HTTP on-demand'
  },
  {
    id: 'forex',
    route: '#view=forex',
    selector: '.p-4',  // ForexDashboard uses p-4 class
    keyAPIs: ['/api/v1/forex/spot'],
    description: 'ForexDashboard - HTTP on-demand'
  },
  {
    id: 'macro',
    route: '#view=macro',
    selector: '.p-4',  // MacroDashboard uses p-4 class
    keyAPIs: ['/api/v1/macro/dashboard'],
    description: 'MacroDashboard - BFF aggregation'
  }
]

// Results storage
const results = []

function median(values) {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

async function clearCache(page) {
  try {
    await page.evaluate(() => {
      if (typeof localStorage !== 'undefined') {
        localStorage.clear()
      }
      if (typeof sessionStorage !== 'undefined') {
        sessionStorage.clear()
      }
      return true
    })
  } catch (e) {
    // localStorage may not be accessible on about:blank
  }
}

async function getPageLoadMetrics(page) {
  return await page.evaluate(() => {
    const timing = performance.timing
    const navigation = performance.getEntriesByType('navigation')[0]
    
    return {
      domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
      loadComplete: timing.loadEventEnd - timing.navigationStart,
      domInteractive: timing.domInteractive - timing.navigationStart,
      resourceCount: performance.getEntriesByType('resource').length
    }
  })
}

async function runSingleTest(page, pageConfig) {
  const startTime = Date.now()
  
  await clearCache(page)
  
  // Track API requests
  const apiRequests = []
  page.on('response', response => {
    const url = response.url()
    const isKeyAPI = pageConfig.keyAPIs.some(api => url.includes(api))
    
    if (isKeyAPI || url.includes('/api/v1/')) {
      apiRequests.push({
        url: url.replace('http://localhost:60100', ''),
        status: response.status(),
        isKeyAPI
      })
    }
  })
  
  const navStartTime = Date.now()
  await page.goto(`http://localhost:60100${pageConfig.route}`, {
    waitUntil: 'domcontentloaded',
    timeout: 30000
  })
  
  try {
    await page.waitForSelector(pageConfig.selector, { timeout: 10000 })
  } catch (e) {
    // Selector might not exist, wait for page to settle
    await page.waitForTimeout(3000)
  }
  
  const dataRenderTime = Date.now() - navStartTime
  const pageLoadMetrics = await getPageLoadMetrics(page)
  const totalTime = Date.now() - startTime
  
  // Extract API response times from Resource Timing API
  const resourceEntries = await page.evaluate(() => {
    return performance.getEntriesByType('resource')
      .filter(e => e.name.includes('/api/v1/'))
      .map(e => ({
        url: e.name.replace('http://localhost:60100', ''),
        duration: e.duration
      }))
  })
  
  const apiResponseTimes = {}
  for (const req of apiRequests.filter(r => r.isKeyAPI)) {
    const apiName = req.url.split('?')[0].replace('/api/v1/', '').replace(/\//g, '_')
    const resource = resourceEntries.find(r => r.url.includes(apiName))
    apiResponseTimes[apiName] = resource ? Math.round(resource.duration) : 0
  }
  
  return {
    apiResponseTimes,
    pageLoadMetrics,
    dataRenderTime,
    totalTime,
    apiRequestCount: apiRequests.length,
    timestamp: new Date().toISOString()
  }
}

async function runMultipleTests(page, pageConfig, iterations = 3) {
  const allMetrics = []
  
  for (let i = 0; i < iterations; i++) {
    console.log(`  Iteration ${i + 1}/${iterations}...`)
    
    try {
      const metrics = await runSingleTest(page, pageConfig)
      allMetrics.push(metrics)
      
      if (i < iterations - 1) {
        await page.waitForTimeout(1000)
      }
    } catch (error) {
      console.error(`  Iteration ${i + 1} failed:`, error.message)
      allMetrics.push({
        error: error.message,
        totalTime: 99999,
        timestamp: new Date().toISOString()
      })
    }
  }
  
  const validMetrics = allMetrics.filter(m => !m.error)
  
  if (validMetrics.length === 0) {
    return {
      pageId: pageConfig.id,
      description: pageConfig.description,
      metrics: null,
      status: 'fail',
      error: 'All iterations failed',
      iterations: allMetrics
    }
  }
  
  // Aggregate API response times
  const apiResponseTimes = {}
  const apiKeys = new Set()
  validMetrics.forEach(m => {
    Object.keys(m.apiResponseTimes || {}).forEach(key => apiKeys.add(key))
  })
  
  for (const key of apiKeys) {
    const values = validMetrics
      .map(m => m.apiResponseTimes?.[key])
      .filter(v => v !== undefined)
    if (values.length > 0) {
      apiResponseTimes[key] = Math.round(median(values))
    }
  }
  
  // Aggregate page load metrics
  const pageLoadTime = {
    domContentLoaded: Math.round(median(validMetrics.map(m => m.pageLoadMetrics?.domContentLoaded || 0))),
    loadComplete: Math.round(median(validMetrics.map(m => m.pageLoadMetrics?.loadComplete || 0))),
    domInteractive: Math.round(median(validMetrics.map(m => m.pageLoadMetrics?.domInteractive || 0)))
  }
  
  const aggregatedMetrics = {
    apiResponseTimes,
    pageLoadTime,
    dataRenderTime: Math.round(median(validMetrics.map(m => m.dataRenderTime || 0))),
    totalTime: Math.round(median(validMetrics.map(m => m.totalTime || 0))),
    apiRequestCount: Math.round(median(validMetrics.map(m => m.apiRequestCount || 0)))
  }
  
  const threshold = THRESHOLDS[pageConfig.id]
  const status = aggregatedMetrics.totalTime <= threshold ? 'pass' : 'fail'
  
  return {
    pageId: pageConfig.id,
    description: pageConfig.description,
    threshold,
    metrics: aggregatedMetrics,
    status,
    iterations: allMetrics.map(m => ({
      totalTime: m.totalTime,
      dataRenderTime: m.dataRenderTime,
      error: m.error
    }))
  }
}

// Generate test for each page
for (const pageConfig of PAGES) {
  test(`Performance: ${pageConfig.id} (${pageConfig.description})`, async ({ page }) => {
    console.log(`\nTesting ${pageConfig.id}...`)
    
    const result = await runMultipleTests(page, pageConfig, 3)
    results.push(result)
    
    console.log(`\n  Results for ${pageConfig.id}:`)
    if (result.metrics) {
      console.log(`    Total Time: ${result.metrics.totalTime}ms (threshold: ${result.threshold}ms)`)
      console.log(`    Data Render Time: ${result.metrics.dataRenderTime}ms`)
      console.log(`    Page Load (DCL): ${result.metrics.pageLoadTime.domContentLoaded}ms`)
      console.log(`    API Response Times:`)
      Object.entries(result.metrics.apiResponseTimes).forEach(([api, time]) => {
        console.log(`      ${api}: ${time}ms`)
      })
    }
    console.log(`    Status: ${result.status.toUpperCase()}`)
    
    expect(result.status).toBe('pass')
    expect(result.metrics).toBeDefined()
    expect(result.metrics.totalTime).toBeLessThanOrEqual(result.threshold)
  })
}

// Summary test
test('Performance Summary', async ({ page }) => {
  console.log('\n' + '='.repeat(60))
  console.log('PERFORMANCE TEST SUMMARY')
  console.log('='.repeat(60))
  
  const passed = results.filter(r => r.status === 'pass').length
  const failed = results.filter(r => r.status === 'fail').length
  
  console.log(`\nTotal Pages: ${results.length}`)
  console.log(`Passed: ${passed}`)
  console.log(`Failed: ${failed}`)
  
  console.log('\nDetailed Results:')
  console.log('-'.repeat(60))
  
  for (const result of results) {
    const statusIcon = result.status === 'pass' ? '✅' : '❌'
    console.log(`\n${statusIcon} ${result.pageId.toUpperCase()}`)
    console.log(`   Description: ${result.description}`)
    if (result.metrics) {
      console.log(`   Total Time: ${result.metrics.totalTime}ms / ${result.threshold}ms`)
      console.log(`   Data Render: ${result.metrics.dataRenderTime}ms`)
    } else {
      console.log(`   Error: ${result.error}`)
    }
  }
  
  console.log('\n' + '='.repeat(60))
  
  // Save results to JSON
  const outputPath = path.join(__dirname, 'performance-phase2-results.json')
  
  const output = {
    timestamp: new Date().toISOString(),
    summary: {
      total: results.length,
      passed,
      failed,
      passRate: `${((passed / results.length) * 100).toFixed(1)}%`
    },
    thresholds: THRESHOLDS,
    results
  }
  
  fs.writeFileSync(outputPath, JSON.stringify(output, null, 2))
  console.log(`\nResults saved to: ${outputPath}`)
  
  expect(failed).toBe(0)
})
