# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: navigation.spec.js >> Accessibility >> should have proper heading structure
- Location: tests/e2e/navigation.spec.js:97:3

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
  5   |     await page.goto('/')
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
> 98  |     await page.goto('/')
      |                ^ Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:60100/
  99  |     
  100 |     const h1 = page.locator('h1')
  101 |     const h2 = page.locator('h2')
  102 |     const header = page.locator('header, [role="heading"]')
  103 |     
  104 |     // At least one heading or header should exist
  105 |     const h1Count = await h1.count()
  106 |     const h2Count = await h2.count()
  107 |     const headerCount = await header.count()
  108 |     
  109 |     expect(h1Count + h2Count + headerCount).toBeGreaterThan(0)
  110 |   })
  111 | 
  112 |   test('should have alt text on images', async ({ page }) => {
  113 |     await page.goto('/')
  114 |     
  115 |     const images = page.locator('img')
  116 |     const imageCount = await images.count()
  117 |     
  118 |     if (imageCount > 0) {
  119 |       for (let i = 0; i < imageCount; i++) {
  120 |         const alt = await images.nth(i).getAttribute('alt')
  121 |         // Alt can be empty for decorative images, but should exist
  122 |         expect(alt !== undefined).toBe(true)
  123 |       }
  124 |     }
  125 |   })
  126 | 
  127 |   test('should have focusable elements', async ({ page }) => {
  128 |     await page.goto('/')
  129 |     
  130 |     // Check for interactive elements
  131 |     const buttons = page.locator('button')
  132 |     const links = page.locator('a')
  133 |     const inputs = page.locator('input, select, textarea')
  134 |     
  135 |     const totalFocusable = await buttons.count() + await links.count() + await inputs.count()
  136 |     
  137 |     // Should have at least some interactive elements
  138 |     expect(totalFocusable).toBeGreaterThan(0)
  139 |   })
  140 | })
  141 | 
  142 | test.describe('Error Handling', () => {
  143 |   test('should handle 404 errors gracefully', async ({ page }) => {
  144 |     await page.goto('/non-existent-page')
  145 |     
  146 |     // Page should not crash — Vue Router default behavior renders empty or fallback
  147 |     await expect(page.locator('body')).toBeVisible()
  148 |   })
  149 | 
  150 |   test('should recover from network errors', async ({ page }) => {
  151 |     await page.goto('/')
  152 |     
  153 |     // Simulate offline (if supported)
  154 |     try {
  155 |       await page.context().setOffline(true)
  156 |       
  157 |       // Try to navigate
  158 |       await page.goto('/market')
  159 |       
  160 |       // Should show offline message or cached content
  161 |       await expect(page.locator('body')).toBeVisible()
  162 |     } catch (e) {
  163 |       // setOffline may throw ERR_INTERNET_DISCONNECTED; that's acceptable
  164 |     } finally {
  165 |       // Restore network
  166 |       await page.context().setOffline(false)
  167 |     }
  168 |   })
  169 | })
  170 | 
  171 | test.describe('Data Persistence', () => {
  172 |   test('should persist user preferences', async ({ page }) => {
  173 |     await page.goto('/')
  174 |     
  175 |     // Check localStorage (if used)
  176 |     const localStorage = await page.evaluate(() => {
  177 |       return Object.keys(window.localStorage)
  178 |     })
  179 |     
  180 |     // Storage should be accessible
  181 |     expect(Array.isArray(localStorage)).toBe(true)
  182 |   })
  183 | 
  184 |   test('should handle page refresh', async ({ page }) => {
  185 |     await page.goto('/')
  186 |     await page.waitForLoadState('domcontentloaded')
  187 |     await page.waitForTimeout(2000)
  188 |     
  189 |     const initialUrl = page.url()
  190 |     
  191 |     await page.reload()
  192 |     await page.waitForLoadState('domcontentloaded')
  193 |     await page.waitForTimeout(2000)
  194 |     
  195 |     expect(page.url()).toBe(initialUrl)
  196 |     await expect(page.locator('body')).toBeVisible()
  197 |   })
  198 | })
```