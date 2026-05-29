# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: admin.spec.js >> Admin Section >> should navigate to admin dashboard
- Location: tests/e2e/admin.spec.js:10:3

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
  3  | test.describe('Admin Section', () => {
  4  |   test.beforeEach(async ({ page }) => {
> 5  |     await page.goto('/')
     |                ^ Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:60100/
  6  |     await page.evaluate(() => localStorage.clear())
  7  |     await page.waitForLoadState('domcontentloaded')
  8  |   })
  9  | 
  10 |   test('should navigate to admin dashboard', async ({ page }) => {
  11 |     const adminButton = page.locator('[data-route="admin"]')
  12 |     await expect(adminButton).toBeVisible()
  13 |     await adminButton.click()
  14 |     await page.waitForTimeout(500)
  15 |     await expect(page).toHaveURL(/#view=admin/)
  16 |   })
  17 | 
  18 |   test('should show admin dashboard content', async ({ page }) => {
  19 |     const adminButton = page.locator('[data-route="admin"]')
  20 |     await adminButton.click()
  21 |     await page.waitForTimeout(3000)
  22 |     await expect(page.locator('#main-content')).toBeVisible()
  23 |   })
  24 | 
  25 |   test('should have admin navigation styling', async ({ page }) => {
  26 |     const adminButton = page.locator('[data-route="admin"]')
  27 |     await adminButton.click()
  28 |     await page.waitForTimeout(300)
  29 |     await expect(adminButton).toHaveAttribute('aria-current', 'page')
  30 |   })
  31 | })
  32 | 
```