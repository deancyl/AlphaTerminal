import { test, expect } from '@playwright/test'

const AI_AGENT_ROUTES = [
  { id: 'strategy-center', label: '策略中心' },
  { id: 'factor-sandbox', label: '因子沙盒' },
  { id: 'market-radar', label: '市场雷达' },
  { id: 'timemachine', label: '时光机' },
  { id: 'multi-asset-matrix', label: '四屏矩阵' },
  { id: 'walk-forward', label: '策略稳定性测试' },
]

test.describe('AI & Agent Section Routes', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.waitForLoadState('domcontentloaded')
  })

  for (const route of AI_AGENT_ROUTES) {
    test(`should navigate to ${route.label} (${route.id})`, async ({ page }) => {
      const navButton = page.locator(`[data-route="${route.id}"]`)
      await expect(navButton).toBeVisible()
      await navButton.click()
      await page.waitForTimeout(500)
      await expect(page).toHaveURL(new RegExp(`#view=${route.id}`))
    })
  }

  test('should show active state on selected AI route', async ({ page }) => {
    const strategyButton = page.locator('[data-route="strategy-center"]')
    await strategyButton.click()
    await page.waitForTimeout(300)
    await expect(strategyButton).toHaveAttribute('aria-current', 'page')
  })
})

test.describe('AI & Agent Section Data Loading', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('should load strategy center without errors', async ({ page }) => {
    const strategyButton = page.locator('[data-route="strategy-center"]')
    await strategyButton.click()
    await page.waitForTimeout(3000)
    await expect(page.locator('#main-content')).toBeVisible()
  })

  test('should load factor sandbox without errors', async ({ page }) => {
    const factorButton = page.locator('[data-route="factor-sandbox"]')
    await factorButton.click()
    await page.waitForTimeout(3000)
    await expect(page.locator('#main-content')).toBeVisible()
  })

  test('should load market radar without errors', async ({ page }) => {
    const radarButton = page.locator('[data-route="market-radar"]')
    await radarButton.click()
    await page.waitForTimeout(3000)
    await expect(page.locator('#main-content')).toBeVisible()
  })
})
