# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: ai-agent-routes.spec.js >> AI & Agent Section Routes >> should navigate to 策略中心 (strategy-center)
- Location: tests/e2e/ai-agent-routes.spec.js:20:5

# Error details

```
Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:60100/
Call log:
  - navigating to "http://localhost:60100/", waiting until "load"

```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test'
  2  | 
  3  | const AI_AGENT_ROUTES = [
  4  |   { id: 'strategy-center', label: '策略中心' },
  5  |   { id: 'factor-sandbox', label: '因子沙盒' },
  6  |   { id: 'market-radar', label: '市场雷达' },
  7  |   { id: 'timemachine', label: '时光机' },
  8  |   { id: 'multi-asset-matrix', label: '四屏矩阵' },
  9  |   { id: 'walk-forward', label: '策略稳定性测试' },
  10 | ]
  11 | 
  12 | test.describe('AI & Agent Section Routes', () => {
  13 |   test.beforeEach(async ({ page }) => {
> 14 |     await page.goto('/')
     |                ^ Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:60100/
  15 |     await page.evaluate(() => localStorage.clear())
  16 |     await page.waitForLoadState('domcontentloaded')
  17 |   })
  18 | 
  19 |   for (const route of AI_AGENT_ROUTES) {
  20 |     test(`should navigate to ${route.label} (${route.id})`, async ({ page }) => {
  21 |       const navButton = page.locator(`[data-route="${route.id}"]`)
  22 |       await expect(navButton).toBeVisible()
  23 |       await navButton.click()
  24 |       await page.waitForTimeout(500)
  25 |       await expect(page).toHaveURL(new RegExp(`#view=${route.id}`))
  26 |     })
  27 |   }
  28 | 
  29 |   test('should show active state on selected AI route', async ({ page }) => {
  30 |     const strategyButton = page.locator('[data-route="strategy-center"]')
  31 |     await strategyButton.click()
  32 |     await page.waitForTimeout(300)
  33 |     await expect(strategyButton).toHaveAttribute('aria-current', 'page')
  34 |   })
  35 | })
  36 | 
  37 | test.describe('AI & Agent Section Data Loading', () => {
  38 |   test.beforeEach(async ({ page }) => {
  39 |     await page.goto('/')
  40 |     await page.evaluate(() => localStorage.clear())
  41 |     await page.waitForLoadState('domcontentloaded')
  42 |     await page.waitForTimeout(2000)
  43 |   })
  44 | 
  45 |   test('should load strategy center without errors', async ({ page }) => {
  46 |     const strategyButton = page.locator('[data-route="strategy-center"]')
  47 |     await strategyButton.click()
  48 |     await page.waitForTimeout(3000)
  49 |     await expect(page.locator('#main-content')).toBeVisible()
  50 |   })
  51 | 
  52 |   test('should load factor sandbox without errors', async ({ page }) => {
  53 |     const factorButton = page.locator('[data-route="factor-sandbox"]')
  54 |     await factorButton.click()
  55 |     await page.waitForTimeout(3000)
  56 |     await expect(page.locator('#main-content')).toBeVisible()
  57 |   })
  58 | 
  59 |   test('should load market radar without errors', async ({ page }) => {
  60 |     const radarButton = page.locator('[data-route="market-radar"]')
  61 |     await radarButton.click()
  62 |     await page.waitForTimeout(3000)
  63 |     await expect(page.locator('#main-content')).toBeVisible()
  64 |   })
  65 | })
  66 | 
```