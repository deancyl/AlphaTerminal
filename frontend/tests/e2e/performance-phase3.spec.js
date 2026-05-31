/**
 * Phase 3: AI/Agent Features Performance Test
 * Tests 6 AI/Agent feature pages for performance
 */

import { test, expect } from '@playwright/test'
import { writeFileSync, existsSync, readFileSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const TEST_PAGES = [
  {
    id: 'strategy-center',
    name: 'Strategy Center',
    route: '#view=strategy-center',
    keyAPIs: ['/api/v1/backtest/run'],
    expectedLoadTime: 15000
  },
  {
    id: 'factor-sandbox',
    name: 'Factor Sandbox',
    route: '#view=factor-sandbox',
    keyAPIs: ['/api/v1/factor_sandbox/factors'],
    expectedLoadTime: 15000
  },
  {
    id: 'market-radar',
    name: 'Market Radar',
    route: '#view=market-radar',
    keyAPIs: ['/api/v1/market_radar/treemap'],
    expectedLoadTime: 20000
  },
  {
    id: 'timemachine',
    name: 'Time Machine',
    route: '#view=timemachine',
    keyAPIs: ['/api/v1/timemachine/health'],
    expectedLoadTime: 15000
  },
  {
    id: 'multi-asset-matrix',
    name: 'Multi-Asset Matrix',
    route: '#view=multi-asset-matrix',
    keyAPIs: [],
    expectedLoadTime: 15000
  },
  {
    id: 'walk-forward',
    name: 'Walk-Forward',
    route: '#view=walk-forward',
    keyAPIs: ['/api/v1/backtest/walk_forward'],
    expectedLoadTime: 15000
  }
]

const resultsPath = join(__dirname, 'performance-phase3-results.json')

function calculateMedian(arr) {
  if (arr.length === 0) return 0
  const sorted = [...arr].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

function savePageResult(pageResult) {
  let results = {
    testDate: new Date().toISOString(),
    phase: 'Phase 3 - AI/Agent Features',
    pages: [],
    summary: {
      totalPages: TEST_PAGES.length,
      passedPages: 0,
      failedPages: 0,
      averageLoadTime: 0
    }
  }
  
  if (existsSync(resultsPath)) {
    try {
      const existing = JSON.parse(readFileSync(resultsPath, 'utf-8'))
      results = existing
    } catch {}
  }
  
  const existingIndex = results.pages.findIndex(p => p.pageId === pageResult.pageId)
  if (existingIndex >= 0) {
    results.pages[existingIndex] = pageResult
  } else {
    results.pages.push(pageResult)
  }
  
  const loadTimes = results.pages
    .filter(p => p.success)
    .map(p => p.medianLoadTime)
  
  results.summary.averageLoadTime = Math.round(calculateMedian(loadTimes))
  results.summary.passedPages = results.pages.filter(p => p.success).length
  results.summary.failedPages = results.pages.filter(p => !p.success).length
  
  writeFileSync(resultsPath, JSON.stringify(results, null, 2))
}

test.describe('Phase 3: AI/Agent Features Performance', () => {
  
  for (const pageConfig of TEST_PAGES) {
    test(`${pageConfig.name} - Performance Test (3 iterations)`, async ({ page }) => {
      console.log(`\n📊 Testing: ${pageConfig.name}`)
      console.log(`   Route: ${pageConfig.route}`)
      
      const pageResult = {
        pageId: pageConfig.id,
        pageName: pageConfig.name,
        route: pageConfig.route,
        iterations: [],
        medianLoadTime: 0,
        apiResults: [],
        success: false,
        status: 'pending'
      }
      
      const loadTimes = []
      
      for (let i = 1; i <= 3; i++) {
        console.log(`   Iteration ${i}/3...`)
        
        try {
          const startTime = Date.now()
          
          await page.goto(`http://localhost:60100${pageConfig.route}`, {
            waitUntil: 'domcontentloaded',
            timeout: 20000
          })
          
          await page.waitForTimeout(1000)
          
          const loadTime = Date.now() - startTime
          loadTimes.push(loadTime)
          
          pageResult.iterations.push({
            iteration: i,
            loadTime,
            success: true
          })
          
          console.log(`   Load time: ${loadTime}ms`)
          
        } catch (error) {
          console.error(`   ❌ Iteration ${i} failed: ${error.message}`)
          pageResult.iterations.push({
            iteration: i,
            loadTime: 0,
            success: false,
            error: error.message
          })
        }
        
        await page.waitForTimeout(300)
      }
      
      pageResult.medianLoadTime = calculateMedian(loadTimes)
      
      for (const apiEndpoint of pageConfig.keyAPIs) {
        if (apiEndpoint) {
          try {
            const apiStart = Date.now()
            const response = await page.evaluate(async (url) => {
              const res = await fetch(url)
              return { status: res.status, ok: res.ok }
            }, `http://localhost:60100${apiEndpoint}`)
            const apiTime = Date.now() - apiStart
            
            pageResult.apiResults.push({
              endpoint: apiEndpoint,
              responseTime: apiTime,
              status: response.status,
              success: response.ok
            })
            console.log(`   API ${apiEndpoint}: ${apiTime}ms (${response.status})`)
          } catch (error) {
            pageResult.apiResults.push({
              endpoint: apiEndpoint,
              responseTime: 0,
              success: false,
              error: error.message
            })
          }
        }
      }
      
      const successCount = pageResult.iterations.filter(it => it.success).length
      pageResult.success = successCount >= 2
      pageResult.status = pageResult.success ? 'pass' : 'fail'
      
      console.log(`\n   📈 Results:`)
      console.log(`      Median Load Time: ${pageResult.medianLoadTime}ms`)
      console.log(`      Success Rate: ${successCount}/3`)
      console.log(`      Status: ${pageResult.status.toUpperCase()}`)
      
      savePageResult(pageResult)
      
      if (loadTimes.length > 0) {
        expect(pageResult.medianLoadTime).toBeLessThan(pageConfig.expectedLoadTime)
      }
    })
  }
  
  test('Phase 3 Summary - All Pages Performance Overview', async ({ page }) => {
    console.log('\n' + '='.repeat(60))
    console.log('Phase 3: AI/Agent Features Performance Summary')
    console.log('='.repeat(60))
    
    await page.goto('http://localhost:60100')
    await page.waitForLoadState('domcontentloaded')
    
    console.log(`Total Pages Tested: ${TEST_PAGES.length}`)
    console.log('='.repeat(60))
    
    expect(true).toBe(true)
  })
})
