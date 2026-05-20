import { test, expect } from '@playwright/test'

const MARKET_ROUTES = [
  { id: 'stock', label: '股票行情', expectedComponent: 'DashboardGrid' },
  { id: 'portfolio', label: '投资组合', expectedComponent: 'PortfolioDashboard' },
  { id: 'fund', label: '基金分析', expectedComponent: 'FundDashboard' },
  { id: 'bond', label: '债券行情', expectedComponent: 'BondDashboard' },
  { id: 'futures', label: '期货行情', expectedComponent: 'FuturesDashboard' },
  { id: 'forex', label: '外汇行情', expectedComponent: 'ForexDashboard' },
  { id: 'macro', label: '宏观经济', expectedComponent: 'MacroDashboard' },
  { id: 'options', label: '期权分析', expectedComponent: 'OptionsAnalysis' },
  { id: 'global-index', label: '全球指数', expectedComponent: 'GlobalIndex' },
  { id: 'research', label: '研报平台', expectedComponent: 'ResearchDashboard' },
]

test.describe('Market Section Routes', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.waitForLoadState('domcontentloaded')
  })

  for (const route of MARKET_ROUTES) {
    test(`should navigate to ${route.label} (${route.id})`, async ({ page }) => {
      const navButton = page.locator(`[data-route="${route.id}"]`)
      await expect(navButton).toBeVisible()
      await navButton.click()
      await page.waitForTimeout(500)
      if (route.id === 'stock') {
        await expect(page).toHaveURL(/\/$|\/#view=stock/)
      } else {
        await expect(page).toHaveURL(new RegExp(`#view=${route.id}`))
      }
    })
  }

  test('should show active state on selected route', async ({ page }) => {
    const stockButton = page.locator('[data-route="stock"]')
    await stockButton.click()
    await page.waitForTimeout(300)
    await expect(stockButton).toHaveAttribute('aria-current', 'page')
  })

  test('should persist route on page refresh', async ({ page }) => {
    const bondButton = page.locator('[data-route="bond"]')
    await bondButton.click()
    await page.waitForTimeout(500)
    const urlBeforeRefresh = page.url()
    await page.reload()
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(500)
    expect(page.url()).toBe(urlBeforeRefresh)
  })
})

test.describe('Market Section Data Loading', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('should load stock dashboard data', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(3000)
    const mainContent = page.locator('#main-content')
    await expect(mainContent).toBeVisible()
  })

  test('should load bond dashboard without errors', async ({ page }) => {
    const bondButton = page.locator('[data-route="bond"]')
    await bondButton.click()
    await page.waitForTimeout(3000)
    await expect(page.locator('#main-content')).toBeVisible()
  })

  test('should load macro dashboard without errors', async ({ page }) => {
    const macroButton = page.locator('[data-route="macro"]')
    await macroButton.click()
    await page.waitForTimeout(3000)
    await expect(page.locator('#main-content')).toBeVisible()
  })
})
