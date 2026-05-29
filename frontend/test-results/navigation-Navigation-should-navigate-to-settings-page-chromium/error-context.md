# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: navigation.spec.js >> Navigation >> should navigate to settings page
- Location: tests/e2e/navigation.spec.js:29:3

# Error details

```
Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:60100/
Call log:
  - navigating to "http://localhost:60100/", waiting until "load"

```

# Test source

```ts
  1   | import { test, expect } from '@playwright/test'
  2   | 
  3   | test.describe('Navigation', () => {
  4   |   test.beforeEach(async ({ page }) => {
> 5   |     await page.goto('/')
      |                ^ Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:60100/
  6   |     await page.evaluate(() => localStorage.clear())
  7   |   })
  8   | 
  9   |   test('should navigate to home page', async ({ page }) => {
  10  |     await page.goto('/')
  11  |     await expect(page).toHaveURL(/\/$|\/#view=/)
  12  |   })
  13  | 
  14  |   test('should navigate to market page', async ({ page }) => {
  15  |     await page.goto('/market')
  16  |     await expect(page).toHaveURL(/.*market.*/)
  17  |   })
  18  | 
  19  |   test('should navigate to portfolio page', async ({ page }) => {
  20  |     await page.goto('/portfolio')
  21  |     await expect(page).toHaveURL(/.*portfolio.*/)
  22  |   })
  23  | 
  24  |   test('should navigate to backtest page', async ({ page }) => {
  25  |     await page.goto('/backtest')
  26  |     await expect(page).toHaveURL(/.*backtest.*/)
  27  |   })
  28  | 
  29  |   test('should navigate to settings page', async ({ page }) => {
  30  |     await page.goto('/settings')
  31  |     await expect(page).toHaveURL(/.*settings.*/)
  32  |   })
  33  | })
  34  | 
  35  | test.describe('Theme and Appearance', () => {
  36  |   test('should have dark mode class', async ({ page }) => {
  37  |     await page.goto('/')
  38  |     
  39  |     const body = page.locator('body')
  40  |     const classList = await body.getAttribute('class')
  41  |     
  42  |     // Check if dark class exists (common dark mode implementations)
  43  |     if (classList) {
  44  |       const hasDarkMode = classList.includes('dark') || classList.includes('dark-mode')
  45  |       expect(hasDarkMode || !hasDarkMode).toBe(true) // Either is fine
  46  |     }
  47  |   })
  48  | 
  49  |   test('should have proper font family', async ({ page }) => {
  50  |     await page.goto('/')
  51  |     
  52  |     const body = page.locator('body')
  53  |     await expect(body).toBeVisible()
  54  |     
  55  |     // Check computed style
  56  |     const fontFamily = await body.evaluate(el => getComputedStyle(el).fontFamily)
  57  |     expect(fontFamily).toBeTruthy()
  58  |   })
  59  | })
  60  | 
  61  | test.describe('Performance', () => {
  62  |   test('should load within 15 seconds (CI environment)', async ({ page }) => {
  63  |     const startTime = Date.now()
  64  |     await page.goto('/')
  65  |     await page.waitForLoadState('domcontentloaded')
  66  |     await page.waitForSelector('#main-content', { state: 'visible', timeout: 15000 })
  67  |     const loadTime = Date.now() - startTime
  68  |     
  69  |     expect(loadTime).toBeLessThan(15000)
  70  |   })
  71  | 
  72  |   test('should not have memory leaks', async ({ page }) => {
  73  |     await page.goto('/')
  74  |     await page.waitForLoadState('domcontentloaded')
  75  |     // Wait for initial data to load (app has continuous polling, networkidle won't work)
  76  |     await page.waitForTimeout(2000)
  77  |     
  78  |     // Take heap snapshot (simplified check)
  79  |     const metrics = await page.evaluate(() => {
  80  |       if (window.performance && window.performance.memory) {
  81  |         return {
  82  |           usedJSHeapSize: window.performance.memory.usedJSHeapSize,
  83  |           totalJSHeapSize: window.performance.memory.totalJSHeapSize,
  84  |         }
  85  |       }
  86  |       return null
  87  |     })
  88  |     
  89  |     if (metrics) {
  90  |       expect(metrics.usedJSHeapSize).toBeGreaterThan(0)
  91  |       expect(metrics.usedJSHeapSize).toBeLessThan(metrics.totalJSHeapSize)
  92  |     }
  93  |   })
  94  | })
  95  | 
  96  | test.describe('Accessibility', () => {
  97  |   test('should have proper heading structure', async ({ page }) => {
  98  |     await page.goto('/')
  99  |     
  100 |     const h1 = page.locator('h1')
  101 |     const h2 = page.locator('h2')
  102 |     const header = page.locator('header, [role="heading"]')
  103 |     
  104 |     // At least one heading or header should exist
  105 |     const h1Count = await h1.count()
```