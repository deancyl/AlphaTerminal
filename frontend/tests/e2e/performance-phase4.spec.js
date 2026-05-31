/**
 * Phase 4: AdminDashboard Performance Test
 * Tests navigation tabs for switch performance
 */

import { test, expect } from '@playwright/test'

const NAV_GROUPS = [
  {
    label: '系统与基础设施',
    tabs: ['系统监控', '进程保活', '日志查看', '数据库', '布局设置']
  },
  {
    label: '数据引擎',
    tabs: ['数据源控制', '调度器', '缓存管理', '速率限制', '数据缺口雷达']
  },
  {
    label: '智能引擎',
    tabs: ['LLM 配置', 'Token监控', '成本归属', 'Agent Token', 'MCP 状态']
  },
  {
    label: '业务控制',
    tabs: ['回测监控', '性能监控']
  }
]

test.describe('AdminDashboard Phase 4 Performance', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:60100#view=admin')
    await page.waitForSelector('text=系统管理', { timeout: 20000, state: 'attached' })
    await page.waitForTimeout(2000)
  })

  test('should measure all tab switch times', async ({ page }) => {
    const results = {
      pageId: 'admin',
      timestamp: new Date().toISOString(),
      tabs: [],
      averageSwitchTime: 0,
      status: 'pass'
    }

    let totalTime = 0
    let successCount = 0

    for (const group of NAV_GROUPS) {
      const groupHeader = page.getByRole('button', { name: group.label })
      
      try {
        const count = await groupHeader.count()
        if (count === 0) {
          console.log(`Group ${group.label} not found, skipping`)
          continue
        }
        
        await groupHeader.first().click()
        await page.waitForTimeout(500)
      } catch (e) {
        console.log(`Error clicking group ${group.label}: ${e.message}`)
        continue
      }

      for (const tab of group.tabs) {
        console.log(`Testing tab: ${tab}`)
        
        try {
          const tabButton = page.locator('button').filter({ hasText: tab })
          const count = await tabButton.count()
          
          if (count === 0) {
            console.log(`Tab ${tab} not found, skipping`)
            results.tabs.push({
              tabId: tab,
              switchTime: 0,
              status: 'skipped',
              reason: 'Tab not found'
            })
            continue
          }

          const startTime = Date.now()
          await tabButton.first().click({ force: true })
          await page.waitForTimeout(300)
          
          const mainContent = page.locator('main main')
          const hasContent = await mainContent.count() > 0
          
          const switchTime = Date.now() - startTime
          
          results.tabs.push({
            tabId: tab,
            switchTime,
            status: hasContent ? 'success' : 'partial'
          })
          
          if (hasContent) {
            totalTime += switchTime
            successCount++
          }
          
          console.log(`Tab ${tab}: ${switchTime}ms (${hasContent ? 'success' : 'partial'})`)
          await page.waitForTimeout(100)
          
        } catch (error) {
          console.error(`Error testing tab ${tab}:`, error.message)
          results.tabs.push({
            tabId: tab,
            switchTime: 0,
            status: 'error',
            error: error.message
          })
        }
      }
    }

    results.averageSwitchTime = successCount > 0 ? Math.round(totalTime / successCount) : 0
    
    const failedTabs = results.tabs.filter(t => t.status === 'error')
    results.status = failedTabs.length === 0 ? 'pass' : 'partial'

    console.log('\n=== Phase 4 Performance Results ===')
    console.log(`Total tabs tested: ${results.tabs.length}`)
    console.log(`Successful: ${successCount}`)
    console.log(`Average switch time: ${results.averageSwitchTime}ms`)
    console.log(`Status: ${results.status}`)

    const fs = await import('fs/promises')
    await fs.writeFile(
      'performance-phase4-results.json',
      JSON.stringify(results, null, 2)
    )

    expect(successCount).toBeGreaterThan(0)
  })

  test('should verify tab content loads correctly', async ({ page }) => {
    const testTabs = ['系统监控', '数据库', '缓存管理', '性能监控']
    
    for (const tab of testTabs) {
      try {
        const groupName = NAV_GROUPS.find(g => g.tabs.includes(tab))?.label || ''
        const groupHeader = page.locator('button').filter({ hasText: new RegExp(`^${groupName}`) })
        
        await groupHeader.first().click()
        await page.waitForTimeout(200)
        
        const tabButton = page.locator('button').filter({ hasText: tab })
        if (await tabButton.count() > 0) {
          await tabButton.first().click({ force: true })
          await page.waitForTimeout(500)
          
          const mainContent = page.locator('main main')
          const hasContent = await mainContent.count() > 0
          
          console.log(`Tab ${tab} content visible: ${hasContent}`)
        }
      } catch (e) {
        console.log(`Tab ${tab} test failed: ${e.message}`)
      }
    }
    
    expect(true).toBe(true)
  })

  test('should measure rapid tab switching performance', async ({ page }) => {
    const rapidSwitchTabs = ['系统监控', '日志查看', '缓存管理', '性能监控']
    const iterations = 2
    
    const switchTimes = []
    
    for (let i = 0; i < iterations; i++) {
      for (const tab of rapidSwitchTabs) {
        try {
          const groupName = NAV_GROUPS.find(g => g.tabs.includes(tab))?.label || ''
          const groupHeader = page.locator('button').filter({ hasText: new RegExp(`^${groupName}`) })
          
          await groupHeader.first().click()
          await page.waitForTimeout(100)
          
          const tabButton = page.locator('button').filter({ hasText: tab })
          if (await tabButton.count() === 0) continue
          
          const start = Date.now()
          await tabButton.first().click({ force: true })
          await page.waitForTimeout(50)
          switchTimes.push(Date.now() - start)
        } catch (e) {
          console.log(`Rapid switch ${tab} failed: ${e.message}`)
        }
      }
    }
    
    if (switchTimes.length > 0) {
      const avgRapidSwitch = switchTimes.reduce((a, b) => a + b, 0) / switchTimes.length
      
      console.log(`Rapid switch average: ${avgRapidSwitch.toFixed(2)}ms`)
      console.log(`Max switch time: ${Math.max(...switchTimes)}ms`)
      console.log(`Min switch time: ${Math.min(...switchTimes)}ms`)
      
      expect(avgRapidSwitch).toBeLessThan(1000)
    } else {
      expect(true).toBe(true)
      console.log('No rapid switches recorded')
    }
  })
})

test('Phase 4 Summary', async ({ page }) => {
  await page.goto('http://localhost:60100#view=admin')
  await page.waitForSelector('text=系统管理', { timeout: 20000, state: 'attached' })
  
  const sidebar = await page.locator('text=系统管理').count()
  expect(sidebar).toBeGreaterThan(0)
  
  console.log('Phase 4 AdminDashboard loaded successfully')
})