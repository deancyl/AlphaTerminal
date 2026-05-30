import { test, expect } from '@playwright/test'

test.describe('Real-time Performance Metrics', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:60100')
    await page.waitForTimeout(2000)
  })

  test('PerformancePanel displays real-time indicator', async ({ page }) => {
    // Navigate to admin panel
    await page.click('text=系统管理')
    await page.waitForTimeout(1000)

    // Click performance tab
    await page.click('text=性能监控')
    await page.waitForTimeout(2000)

    // Check for live indicator (green dot)
    const liveIndicator = await page.$('.animate-pulse')
    expect(liveIndicator).toBeTruthy()
  })

  test('PerformancePanel shows metrics data', async ({ page }) => {
    await page.click('text=系统管理')
    await page.waitForTimeout(1000)
    await page.click('text=性能监控')
    await page.waitForTimeout(3000)

    // Check for metrics cards
    const avgLatency = await page.$('text=/平均响应/')
    expect(avgLatency).toBeTruthy()

    const totalRequests = await page.$('text=/总请求数/')
    expect(totalRequests).toBeTruthy()
  })
})