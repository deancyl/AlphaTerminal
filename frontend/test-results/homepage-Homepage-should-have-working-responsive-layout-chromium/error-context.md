# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: homepage.spec.js >> Homepage >> should have working responsive layout
- Location: tests/e2e/homepage.spec.js:51:3

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
  3  | test.describe('Homepage', () => {
  4  |   test('should load homepage successfully', async ({ page }) => {
  5  |     await page.goto('/')
  6  |     
  7  |     // Check page title
  8  |     await expect(page).toHaveTitle(/AlphaTerminal/)
  9  |     
  10 |     // Check main layout elements
  11 |     await expect(page.locator('body')).toBeVisible()
  12 |     
  13 |     // Check if main container exists
  14 |     const mainContainer = page.locator('#app, .app, main, [data-testid="app"]')
  15 |     await expect(mainContainer.first()).toBeVisible()
  16 |   })
  17 | 
  18 |   test('should display navigation elements', async ({ page }) => {
  19 |     await page.goto('/')
  20 |     
  21 |     // Look for common navigation patterns
  22 |     const nav = page.locator('nav, header, .navbar, .header')
  23 |     const hasNav = await nav.count() > 0
  24 |     
  25 |     if (hasNav) {
  26 |       await expect(nav.first()).toBeVisible()
  27 |     }
  28 |   })
  29 | 
  30 |   test('should display sidebar or menu', async ({ page }) => {
  31 |     await page.goto('/')
  32 |     await page.waitForLoadState('load')
  33 |     
  34 |     // First, click the hamburger button to open the sidebar
  35 |     // The sidebar is hidden by default (isSidebarOpen = false in App.vue)
  36 |     const hamburgerBtn = page.locator('button:has-text("☰"), button:has-text("菜单"), [data-testid="menu-toggle"], .menu-toggle, .hamburger')
  37 |     if (await hamburgerBtn.count() > 0) {
  38 |       await hamburgerBtn.first().click()
  39 |       await page.waitForTimeout(500) // Wait for CSS transition
  40 |     }
  41 |     
  42 |     // Now check for sidebar patterns
  43 |     const sidebar = page.locator('aside, .sidebar, .sidenav, [data-testid="sidebar"]')
  44 |     const hasSidebar = await sidebar.count() > 0
  45 |     
  46 |     if (hasSidebar) {
  47 |       await expect(sidebar.first()).toBeVisible({ timeout: 10000 })
  48 |     }
  49 |   })
  50 | 
  51 |   test('should have working responsive layout', async ({ page }) => {
> 52 |     await page.goto('/')
     |                ^ Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:60100/
  53 |     
  54 |     // Test desktop viewport
  55 |     await page.setViewportSize({ width: 1920, height: 1080 })
  56 |     await expect(page.locator('body')).toBeVisible()
  57 |     
  58 |     // Test tablet viewport
  59 |     await page.setViewportSize({ width: 768, height: 1024 })
  60 |     await expect(page.locator('body')).toBeVisible()
  61 |     
  62 |     // Test mobile viewport
  63 |     await page.setViewportSize({ width: 375, height: 667 })
  64 |     await expect(page.locator('body')).toBeVisible()
  65 |   })
  66 | 
  67 |   test('should load without console errors', async ({ page }) => {
  68 |     const errors = []
  69 |     
  70 |     page.on('console', msg => {
  71 |       if (msg.type() === 'error') {
  72 |         errors.push(msg.text())
  73 |       }
  74 |     })
  75 |     
  76 |     await page.goto('/')
  77 |     await page.waitForLoadState('domcontentloaded')
  78 |     // Wait for initial data to load (app has continuous polling)
  79 |     await page.waitForTimeout(2000)
  80 |     
  81 |     // Filter out non-critical errors
  82 |     const criticalErrors = errors.filter(err => 
  83 |       !err.includes('favicon') && 
  84 |       !err.includes('source map') &&
  85 |       !err.includes('timeout') &&
  86 |       !err.includes('Timeout') &&
  87 |       !err.includes('ETIMEDOUT') &&
  88 |       !err.includes('network') &&
  89 |       !err.includes('ERR_CONNECTION_CLOSED') &&
  90 |       !err.includes('ERR_CONNECTION_REFUSED')
  91 |     )
  92 |     
  93 |     expect(criticalErrors).toHaveLength(0)
  94 |   })
  95 | })
  96 | 
```