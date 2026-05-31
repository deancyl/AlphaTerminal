/**
 * Performance Testing Examples
 * 
 * 演示如何使用 performance-helpers.js 工具库进行性能测试。
 * 
 * @example
 * // 运行单个测试
 * npm run test:e2e performance-examples.spec.js -- --grep "bond dashboard"
 */

import { test, expect } from '@playwright/test'
import {
  navigateToRoute,
  measurePageLoadTime,
  measureAPIResponseTime,
  waitForDataLoad,
  measureWebVitals,
  measureMemoryUsage,
  clearBrowserCache,
  runTestMultipleTimes,
  runFullPerformanceTest,
  PERFORMANCE_THRESHOLDS,
  evaluatePerformanceScore
} from './utils/performance-helpers'

test.describe('Performance Testing Examples', () => {
  
  test.beforeEach(async ({ page }) => {
    // 每个测试前清除缓存
    await clearBrowserCache()
  })
  
  test('should measure stock dashboard page load time (3 runs)', async ({ page }) => {
    const result = await runTestMultipleTimes(async () => {
      await navigateToRoute('#view=stock')
      return await measurePageLoadTime('#main-content')
    }, { times: 3 })
    
    console.log('Stock Dashboard Performance:')
    console.log(`  DOM加载中位数: ${result.median.domContentLoaded}ms`)
    console.log(`  完全加载中位数: ${result.median.loadComplete}ms`)
    console.log(`  最小/最大: ${result.min.domContentLoaded}ms / ${result.max.domContentLoaded}ms`)
    
    // 断言
    expect(result.median.domContentLoaded).toBeLessThan(PERFORMANCE_THRESHOLDS.pageLoad.acceptable)
    expect(result.median.loadComplete).toBeLessThan(PERFORMANCE_THRESHOLDS.pageLoad.slow)
  })
  
  test('should measure bond dashboard API response times', async ({ page }) => {
    await navigateToRoute('#view=bond')
    await waitForDataLoad('#main-content')
    
    const apiTiming = await measureAPIResponseTime('/api/v1/bond')
    
    console.log('Bond API Performance:')
    console.log(`  最小响应: ${apiTiming.min}ms`)
    console.log(`  最大响应: ${apiTiming.max}ms`)
    console.log(`  平均响应: ${apiTiming.avg}ms`)
    console.log(`  请求总数: ${apiTiming.requests.length}`)
    
    // 断言
    expect(apiTiming.avg).toBeLessThan(PERFORMANCE_THRESHOLDS.apiResponse.acceptable)
  })
  
  test('should measure macro dashboard Web Vitals', async ({ page }) => {
    await navigateToRoute('#view=macro')
    await waitForDataLoad('.macro-dashboard', { timeout: 30000 })
    
    const vitals = await measureWebVitals()
    
    console.log('Macro Dashboard Web Vitals:')
    console.log(`  LCP: ${vitals.lcp}ms`)
    console.log(`  FCP: ${vitals.fcp}ms`)
    console.log(`  CLS: ${vitals.cls}`)
    console.log(`  TTFB: ${vitals.ttfb}ms`)
    
    // 断言
    expect(vitals.lcp).toBeLessThan(PERFORMANCE_THRESHOLDS.webVitals.lcp.needsImprovement)
    expect(vitals.cls).toBeLessThan(PERFORMANCE_THRESHOLDS.webVitals.cls.needsImprovement)
  })
  
  test('should measure memory usage after navigation', async ({ page }) => {
    // 初始内存
    await navigateToRoute('#view=stock')
    const initialMemory = await measureMemoryUsage()
    
    console.log('Initial Memory:')
    console.log(`  已使用: ${initialMemory.usedMB}MB`)
    console.log(`  总分配: ${initialMemory.totalMB}MB`)
    
    // 导航到多个页面
    const routes = ['bond', 'macro', 'futures', 'forex']
    for (const route of routes) {
      await navigateToRoute(`#view=${route}`)
      await waitForDataLoad('#main-content', { timeout: 15000 })
    }
    
    // 最终内存
    const finalMemory = await measureMemoryUsage()
    
    console.log('Final Memory:')
    console.log(`  已使用: ${finalMemory.usedMB}MB`)
    console.log(`  总分配: ${finalMemory.totalMB}MB`)
    console.log(`  增长: ${finalMemory.usedMB - initialMemory.usedMB}MB`)
    
    // 断言：内存增长不应超过50MB
    expect(finalMemory.usedMB - initialMemory.usedMB).toBeLessThan(50)
    expect(finalMemory.usedMB).toBeLessThan(PERFORMANCE_THRESHOLDS.memory.high)
  })
  
  test('should run full performance test for futures dashboard', async ({ page }) => {
    const report = await runFullPerformanceTest(
      '#view=futures',
      '.futures-dashboard',
      {
        runs: 3,
        apiFilters: ['/api/v1/futures']
      }
    )
    
    console.log('Futures Dashboard Full Performance Report:')
    console.log('==========================================')
    console.log(`页面加载时间: ${report.median.pageLoad?.domContentLoaded}ms`)
    console.log(`数据加载成功: ${report.median.dataLoad?.success}`)
    console.log(`API平均响应: ${report.median.apiTimings?.['/api/v1/futures']?.avg}ms`)
    console.log(`LCP: ${report.median.webVitals?.lcp}ms`)
    console.log(`CLS: ${report.median.webVitals?.cls}`)
    console.log(`内存使用: ${report.median.memory?.usedMB}MB`)
    
    // 计算性能分数
    const evaluation = evaluatePerformanceScore(report.median)
    console.log(`\n性能分数: ${evaluation.totalScore}/100 (${evaluation.grade})`)
    
    // 断言
    expect(report.median.dataLoad?.success).toBe(true)
    expect(evaluation.totalScore).toBeGreaterThanOrEqual(60)
  })
  
  test('should measure options chain rendering time', async ({ page }) => {
    await navigateToRoute('#view=options')
    
    const result = await waitForDataLoad('.options-dashboard', { timeout: 30000 })
    
    console.log('Options Dashboard Load Result:')
    console.log(`  成功: ${result.success}`)
    console.log(`  耗时: ${result.loadTime}ms`)
    console.log(`  有错误: ${result.hasError}`)
    
    // 断言
    expect(result.success).toBe(true)
    expect(result.hasError).toBe(false)
    expect(result.loadTime).toBeLessThan(15000)
  })
  
  test('should compare performance across all main pages', async ({ page }) => {
    const pages = [
      { route: '#view=stock', name: 'Stock', selector: '#main-content' },
      { route: '#view=bond', name: 'Bond', selector: '.bond-dashboard' },
      { route: '#view=macro', name: 'Macro', selector: '.macro-dashboard' },
      { route: '#view=futures', name: 'Futures', selector: '.futures-dashboard' },
      { route: '#view=forex', name: 'Forex', selector: '.forex-dashboard' }
    ]
    
    const results = []
    
    for (const pageConfig of pages) {
      const result = await runTestMultipleTimes(async () => {
        await navigateToRoute(pageConfig.route)
        const timing = await measurePageLoadTime(pageConfig.selector)
        const vitals = await measureWebVitals()
        const memory = await measureMemoryUsage()
        
        return {
          name: pageConfig.name,
          domContentLoaded: timing.domContentLoaded,
          loadComplete: timing.loadComplete,
          lcp: vitals.lcp,
          cls: vitals.cls,
          usedMB: memory.usedMB
        }
      }, { times: 1 })
      
      results.push(result.median)
    }
    
    // 打印对比表
    console.log('\nPerformance Comparison:')
    console.log('======================')
    console.log('Page         | DOM Load | LCP     | CLS   | Memory')
    console.log('-------------|----------|---------|-------|--------')
    
    for (const r of results) {
      console.log(
        `${r.name.padEnd(12)} | ` +
        `${String(r.domContentLoaded + 'ms').padEnd(8)} | ` +
        `${String(r.lcp + 'ms').padEnd(7)} | ` +
        `${r.cls.toFixed(3).padEnd(5)} | ` +
        `${r.usedMB}MB`
      )
    }
    
    // 断言所有页面加载时间都在可接受范围内
    for (const r of results) {
      expect(r.domContentLoaded).toBeLessThan(PERFORMANCE_THRESHOLDS.pageLoad.slow)
    }
  })
  
  test('should detect memory leaks after repeated navigation', async ({ page }) => {
    const initialMemory = await measureMemoryUsage()
    
    // 循环导航10次
    const routes = ['stock', 'bond', 'macro', 'futures', 'forex']
    for (let i = 0; i < 10; i++) {
      for (const route of routes) {
        await navigateToRoute(`#view=${route}`)
        await page.waitForTimeout(500) // 等待渲染
      }
    }
    
    // 强制垃圾回收（如果可用）
    if (page.context().browser()?.isConnected()) {
      await page.evaluate(() => {
        if (window.gc) window.gc()
      })
    }
    
    const finalMemory = await measureMemoryUsage()
    const memoryGrowth = finalMemory.usedMB - initialMemory.usedMB
    
    console.log('Memory Leak Test:')
    console.log(`  初始内存: ${initialMemory.usedMB}MB`)
    console.log(`  最终内存: ${finalMemory.usedMB}MB`)
    console.log(`  内存增长: ${memoryGrowth}MB`)
    
    // 断言：内存增长不应超过100MB（可能存在内存泄漏）
    expect(memoryGrowth).toBeLessThan(100)
  })
})

test.describe('CI Performance Tests (Relaxed Thresholds)', () => {
  
  test('should load main content within 15 seconds (CI)', async ({ page }) => {
    await clearBrowserCache()
    await navigateToRoute('#view=stock')
    
    const result = await waitForDataLoad('#main-content', { timeout: 45000 })
    
    expect(result.success).toBe(true)
    expect(result.loadTime).toBeLessThan(15000)
  })
  
  test('should have acceptable Web Vitals (CI)', async ({ page }) => {
    await navigateToRoute('#view=stock')
    await waitForDataLoad('#main-content', { timeout: 30000 })
    
    const vitals = await measureWebVitals()
    
    // CI环境使用更宽松的阈值
    expect(vitals.lcp).toBeLessThan(10000) // CI宽松阈值
    expect(vitals.cls).toBeLessThan(0.5)   // CI宽松阈值
  })
  
  test('should not exceed memory limits (CI)', async ({ page }) => {
    await navigateToRoute('#view=stock')
    await page.waitForTimeout(5000)
    
    const memory = await measureMemoryUsage()
    
    // CI环境允许更高的内存使用
    expect(memory.usedMB).toBeLessThan(200)
  })
})
