# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: stock-search.spec.js >> Stock Search >> should have search input
- Location: tests/e2e/stock-search.spec.js:4:3

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
  3  | test.describe('Stock Search', () => {
  4  |   test('should have search input', async ({ page }) => {
> 5  |     await page.goto('/')
     |                ^ Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:60100/
  6  |     
  7  |     // Look for search input
  8  |     const searchInput = page.locator('input[type="search"], input[placeholder*="搜索"], input[placeholder*="search"], [data-testid="search-input"]')
  9  |     const hasSearch = await searchInput.count() > 0
  10 |     
  11 |     if (hasSearch) {
  12 |       await expect(searchInput.first()).toBeVisible()
  13 |     }
  14 |   })
  15 | 
  16 |   test('should search for stock by symbol', async ({ page }) => {
  17 |     await page.goto('/')
  18 |     
  19 |     // Find search input
  20 |     const searchInput = page.locator('input[type="search"], input[placeholder*="搜索"], input[placeholder*="search"]').first()
  21 |     
  22 |     if (await searchInput.count() > 0) {
  23 |       // Type stock symbol
  24 |       await searchInput.fill('000001')
  25 |       await searchInput.press('Enter')
  26 |       
  27 |       // Wait for results
  28 |       await page.waitForTimeout(1000)
  29 |       
  30 |       // Check if results appeared
  31 |       const results = page.locator('.search-result, .stock-item, [data-testid="search-result"]')
  32 |       // Just verify the search was performed (results may vary)
  33 |       expect(await results.count() >= 0).toBe(true)
  34 |     }
  35 |   })
  36 | 
  37 |   test('should search for stock by name', async ({ page }) => {
  38 |     await page.goto('/')
  39 |     
  40 |     const searchInput = page.locator('input[type="search"], input[placeholder*="搜索"], input[placeholder*="search"]').first()
  41 |     
  42 |     if (await searchInput.count() > 0) {
  43 |       // Type stock name
  44 |       await searchInput.fill('平安银行')
  45 |       await searchInput.press('Enter')
  46 |       
  47 |       await page.waitForTimeout(1000)
  48 |       
  49 |       // Verify search was performed
  50 |       const results = page.locator('.search-result, .stock-item, [data-testid="search-result"]')
  51 |       expect(await results.count() >= 0).toBe(true)
  52 |     }
  53 |   })
  54 | 
  55 |   test('should clear search input', async ({ page }) => {
  56 |     await page.goto('/')
  57 |     
  58 |     const searchInput = page.locator('input[type="search"]').first()
  59 |     
  60 |     if (await searchInput.count() > 0) {
  61 |       await searchInput.fill('test')
  62 |       await searchInput.clear()
  63 |       
  64 |       const value = await searchInput.inputValue()
  65 |       expect(value).toBe('')
  66 |     }
  67 |   })
  68 | 
  69 |   test('should handle empty search', async ({ page }) => {
  70 |     await page.goto('/')
  71 |     
  72 |     const searchInput = page.locator('input[type="search"]').first()
  73 |     
  74 |     if (await searchInput.count() > 0) {
  75 |       await searchInput.fill('')
  76 |       await searchInput.press('Enter')
  77 |       
  78 |       // Page should not crash
  79 |       await expect(page.locator('body')).toBeVisible()
  80 |     }
  81 |   })
  82 | 
  83 |   test('should show search suggestions', async ({ page }) => {
  84 |     await page.goto('/')
  85 |     
  86 |     const searchInput = page.locator('input[type="search"]').first()
  87 |     
  88 |     if (await searchInput.count() > 0) {
  89 |       await searchInput.fill('000')
  90 |       await page.waitForTimeout(500)
  91 |       
  92 |       // Look for dropdown/suggestions
  93 |       const suggestions = page.locator('.dropdown, .suggestions, .autocomplete, [data-testid="suggestions"]')
  94 |       // Suggestions may or may not appear depending on implementation
  95 |       expect(await suggestions.count() >= 0).toBe(true)
  96 |     }
  97 |   })
  98 | })
  99 | 
```