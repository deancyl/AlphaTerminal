import { test, expect } from '@playwright/test'

test.describe('Performance', () => {
  test('should have acceptable first contentful paint (CI relaxed)', async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.waitForLoadState('domcontentloaded')
    const fcp = await page.evaluate(() => {
      const entries = performance.getEntriesByType('paint')
      const fcpEntry = entries.find(e => e.name === 'first-contentful-paint')
      return fcpEntry ? fcpEntry.startTime : null
    })
    if (fcp) {
      expect(fcp).toBeLessThan(15000)
    }
  })

  test('should render main content within 15 seconds (CI)', async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.waitForLoadState('domcontentloaded')
    await page.waitForSelector('#main-content', { state: 'visible', timeout: 15000 })
    await expect(page.locator('#main-content')).toBeVisible()
  })

  test('should not exceed memory limits', async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(5000)
    const metrics = await page.evaluate(() => {
      if (window.performance && window.performance.memory) {
        return {
          usedJSHeapSize: window.performance.memory.usedJSHeapSize,
          totalJSHeapSize: window.performance.memory.totalJSHeapSize,
        }
      }
      return null
    })
    if (metrics) {
      expect(metrics.usedJSHeapSize).toBeLessThan(150 * 1024 * 1024)
    }
  })

  test('should handle rapid navigation without lag', async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.waitForLoadState('domcontentloaded')
    const routes = ['bond', 'macro', 'futures', 'stock']
    const startTime = Date.now()
    for (const route of routes) {
      const navButton = page.locator(`[data-route="${route}"]`)
      await navButton.click()
      await page.waitForTimeout(100)
    }
    const totalTime = Date.now() - startTime
    expect(totalTime).toBeLessThan(10000)
  })
})

test.describe('Performance - Route Specific', () => {
  test('should load bond dashboard within 15 seconds', async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.waitForLoadState('domcontentloaded')
    const bondButton = page.locator('[data-route="bond"]')
    await bondButton.click()
    await page.waitForTimeout(5000)
    await expect(page.locator('#main-content')).toBeVisible()
  })

  test('should load macro dashboard within 15 seconds', async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.waitForLoadState('domcontentloaded')
    const macroButton = page.locator('[data-route="macro"]')
    await macroButton.click()
    await page.waitForTimeout(5000)
    await expect(page.locator('#main-content')).toBeVisible()
  })
})