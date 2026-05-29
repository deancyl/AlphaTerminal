# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: market-routes.spec.js >> Market Section Routes >> should navigate to 研报平台 (research)
- Location: tests/e2e/market-routes.spec.js:24:5

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
  3  | const MARKET_ROUTES = [
  4  |   { id: 'stock', label: '股票行情', expectedComponent: 'DashboardGrid' },
  5  |   { id: 'portfolio', label: '投资组合', expectedComponent: 'PortfolioDashboard' },
  6  |   { id: 'fund', label: '基金分析', expectedComponent: 'FundDashboard' },
  7  |   { id: 'bond', label: '债券行情', expectedComponent: 'BondDashboard' },
  8  |   { id: 'futures', label: '期货行情', expectedComponent: 'FuturesDashboard' },
  9  |   { id: 'forex', label: '外汇行情', expectedComponent: 'ForexDashboard' },
  10 |   { id: 'macro', label: '宏观经济', expectedComponent: 'MacroDashboard' },
  11 |   { id: 'options', label: '期权分析', expectedComponent: 'OptionsAnalysis' },
  12 |   { id: 'global-index', label: '全球指数', expectedComponent: 'GlobalIndex' },
  13 |   { id: 'research', label: '研报平台', expectedComponent: 'ResearchDashboard' },
  14 | ]
  15 | 
  16 | test.describe('Market Section Routes', () => {
  17 |   test.beforeEach(async ({ page }) => {
> 18 |     await page.goto('/')
     |                ^ Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:60100/
  19 |     await page.evaluate(() => localStorage.clear())
  20 |     await page.waitForLoadState('domcontentloaded')
  21 |   })
  22 | 
  23 |   for (const route of MARKET_ROUTES) {
  24 |     test(`should navigate to ${route.label} (${route.id})`, async ({ page }) => {
  25 |       const navButton = page.locator(`[data-route="${route.id}"]`)
  26 |       await expect(navButton).toBeVisible()
  27 |       await navButton.click()
  28 |       await page.waitForTimeout(500)
  29 |       if (route.id === 'stock') {
  30 |         await expect(page).toHaveURL(/\/$|\/#view=stock/)
  31 |       } else {
  32 |         await expect(page).toHaveURL(new RegExp(`#view=${route.id}`))
  33 |       }
  34 |     })
  35 |   }
  36 | 
  37 |   test('should show active state on selected route', async ({ page }) => {
  38 |     const stockButton = page.locator('[data-route="stock"]')
  39 |     await stockButton.click()
  40 |     await page.waitForTimeout(300)
  41 |     await expect(stockButton).toHaveAttribute('aria-current', 'page')
  42 |   })
  43 | 
  44 |   test('should persist route on page refresh', async ({ page }) => {
  45 |     const bondButton = page.locator('[data-route="bond"]')
  46 |     await bondButton.click()
  47 |     await page.waitForTimeout(500)
  48 |     const urlBeforeRefresh = page.url()
  49 |     await page.reload()
  50 |     await page.waitForLoadState('domcontentloaded')
  51 |     await page.waitForTimeout(500)
  52 |     expect(page.url()).toBe(urlBeforeRefresh)
  53 |   })
  54 | })
  55 | 
  56 | test.describe('Market Section Data Loading', () => {
  57 |   test.beforeEach(async ({ page }) => {
  58 |     await page.goto('/')
  59 |     await page.evaluate(() => localStorage.clear())
  60 |     await page.waitForLoadState('domcontentloaded')
  61 |     await page.waitForTimeout(2000)
  62 |   })
  63 | 
  64 |   test('should load stock dashboard data', async ({ page }) => {
  65 |     await page.goto('/')
  66 |     await page.waitForLoadState('domcontentloaded')
  67 |     await page.waitForTimeout(3000)
  68 |     const mainContent = page.locator('#main-content')
  69 |     await expect(mainContent).toBeVisible()
  70 |   })
  71 | 
  72 |   test('should load bond dashboard without errors', async ({ page }) => {
  73 |     const bondButton = page.locator('[data-route="bond"]')
  74 |     await bondButton.click()
  75 |     await page.waitForTimeout(3000)
  76 |     await expect(page.locator('#main-content')).toBeVisible()
  77 |   })
  78 | 
  79 |   test('should load macro dashboard without errors', async ({ page }) => {
  80 |     const macroButton = page.locator('[data-route="macro"]')
  81 |     await macroButton.click()
  82 |     await page.waitForTimeout(3000)
  83 |     await expect(page.locator('#main-content')).toBeVisible()
  84 |   })
  85 | })
  86 | 
```