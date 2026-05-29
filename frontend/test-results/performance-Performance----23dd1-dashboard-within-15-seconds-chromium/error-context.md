# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: performance.spec.js >> Performance - Route Specific >> should load macro dashboard within 15 seconds
- Location: tests/e2e/performance.spec.js:72:3

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
  3  | test.describe('Performance', () => {
  4  |   test('should have acceptable first contentful paint (CI relaxed)', async ({ page }) => {
  5  |     await page.goto('/')
  6  |     await page.evaluate(() => localStorage.clear())
  7  |     await page.waitForLoadState('domcontentloaded')
  8  |     const fcp = await page.evaluate(() => {
  9  |       const entries = performance.getEntriesByType('paint')
  10 |       const fcpEntry = entries.find(e => e.name === 'first-contentful-paint')
  11 |       return fcpEntry ? fcpEntry.startTime : null
  12 |     })
  13 |     if (fcp) {
  14 |       expect(fcp).toBeLessThan(15000)
  15 |     }
  16 |   })
  17 | 
  18 |   test('should render main content within 15 seconds (CI)', async ({ page }) => {
  19 |     await page.goto('/')
  20 |     await page.evaluate(() => localStorage.clear())
  21 |     await page.waitForLoadState('domcontentloaded')
  22 |     await page.waitForSelector('#main-content', { state: 'visible', timeout: 15000 })
  23 |     await expect(page.locator('#main-content')).toBeVisible()
  24 |   })
  25 | 
  26 |   test('should not exceed memory limits', async ({ page }) => {
  27 |     await page.goto('/')
  28 |     await page.evaluate(() => localStorage.clear())
  29 |     await page.waitForLoadState('domcontentloaded')
  30 |     await page.waitForTimeout(5000)
  31 |     const metrics = await page.evaluate(() => {
  32 |       if (window.performance && window.performance.memory) {
  33 |         return {
  34 |           usedJSHeapSize: window.performance.memory.usedJSHeapSize,
  35 |           totalJSHeapSize: window.performance.memory.totalJSHeapSize,
  36 |         }
  37 |       }
  38 |       return null
  39 |     })
  40 |     if (metrics) {
  41 |       expect(metrics.usedJSHeapSize).toBeLessThan(150 * 1024 * 1024)
  42 |     }
  43 |   })
  44 | 
  45 |   test('should handle rapid navigation without lag', async ({ page }) => {
  46 |     await page.goto('/')
  47 |     await page.evaluate(() => localStorage.clear())
  48 |     await page.waitForLoadState('domcontentloaded')
  49 |     const routes = ['bond', 'macro', 'futures', 'stock']
  50 |     const startTime = Date.now()
  51 |     for (const route of routes) {
  52 |       const navButton = page.locator(`[data-route="${route}"]`)
  53 |       await navButton.click()
  54 |       await page.waitForTimeout(100)
  55 |     }
  56 |     const totalTime = Date.now() - startTime
  57 |     expect(totalTime).toBeLessThan(10000)
  58 |   })
  59 | })
  60 | 
  61 | test.describe('Performance - Route Specific', () => {
  62 |   test('should load bond dashboard within 15 seconds', async ({ page }) => {
  63 |     await page.goto('/')
  64 |     await page.evaluate(() => localStorage.clear())
  65 |     await page.waitForLoadState('domcontentloaded')
  66 |     const bondButton = page.locator('[data-route="bond"]')
  67 |     await bondButton.click()
  68 |     await page.waitForTimeout(5000)
  69 |     await expect(page.locator('#main-content')).toBeVisible()
  70 |   })
  71 | 
  72 |   test('should load macro dashboard within 15 seconds', async ({ page }) => {
> 73 |     await page.goto('/')
     |                ^ Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:60100/
  74 |     await page.evaluate(() => localStorage.clear())
  75 |     await page.waitForLoadState('domcontentloaded')
  76 |     const macroButton = page.locator('[data-route="macro"]')
  77 |     await macroButton.click()
  78 |     await page.waitForTimeout(5000)
  79 |     await expect(page.locator('#main-content')).toBeVisible()
  80 |   })
  81 | })
```