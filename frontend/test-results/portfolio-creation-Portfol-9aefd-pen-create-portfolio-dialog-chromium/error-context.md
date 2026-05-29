# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: portfolio-creation.spec.js >> Portfolio Creation >> should open create portfolio dialog
- Location: tests/e2e/portfolio-creation.spec.js:20:3

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
  3   | test.describe('Portfolio Creation', () => {
  4   |   test('should navigate to portfolio page', async ({ page }) => {
  5   |     await page.goto('/')
  6   |     
  7   |     // Look for portfolio link or button
  8   |     const portfolioLink = page.locator('a[href*="portfolio"], button:has-text("组合"), button:has-text("Portfolio"), [data-testid="portfolio-link"]')
  9   |     
  10  |     if (await portfolioLink.count() > 0) {
  11  |       await portfolioLink.first().click()
  12  |       await page.waitForTimeout(1000)
  13  |       
  14  |       // Check if URL changed or portfolio section is visible
  15  |       const portfolioSection = page.locator('.portfolio, [data-testid="portfolio"], .portfolio-list')
  16  |       expect(await portfolioSection.count() >= 0).toBe(true)
  17  |     }
  18  |   })
  19  | 
  20  |   test('should open create portfolio dialog', async ({ page }) => {
> 21  |     await page.goto('/')
      |                ^ Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:60100/
  22  |     await page.waitForLoadState('domcontentloaded')
  23  |     // Wait for initial data to load
  24  |     await page.waitForTimeout(2000)
  25  |     
  26  |     // First, click the hamburger button to open the sidebar
  27  |     // The sidebar is hidden by default (isSidebarOpen = false in App.vue)
  28  |     const hamburgerBtn = page.locator('button:has-text("☰"), button:has-text("菜单"), [data-testid="menu-toggle"], .menu-toggle, .hamburger')
  29  |     if (await hamburgerBtn.count() > 0) {
  30  |       await hamburgerBtn.first().click()
  31  |       await page.waitForTimeout(500)
  32  |     }
  33  |     
  34  |     // Navigate to portfolio view first (click portfolio sidebar item)
  35  |     // Note: sidebar uses v-if when closed, so we need to open it first
  36  |     const portfolioNav = page.locator('button:has-text("💰"), button:has-text("组合"), button:has-text("portfolio"), [data-testid="nav-portfolio"]').first()
  37  |     if (await portfolioNav.count() > 0) {
  38  |       await portfolioNav.click()
  39  |       await page.waitForTimeout(1000) // Wait for view to change
  40  |     }
  41  |     
  42  |     // Look for create portfolio button
  43  |     const createButton = page.locator('button:has-text("新建"), button:has-text("+"), [data-testid="create-portfolio-btn"]').first()
  44  |     
  45  |     if (await createButton.count() > 0) {
  46  |       await createButton.click()
  47  |       await page.waitForTimeout(1000) // Wait for dialog animation
  48  |       
  49  |       // Check if dialog/modal appeared
  50  |       const dialog = page.locator('.dialog, .modal, [role="dialog"], [data-testid="portfolio-dialog"]')
  51  |       await expect(dialog.first()).toBeVisible({ timeout: 10000 })
  52  |     }
  53  |   })
  54  | 
  55  |   test('should fill portfolio name', async ({ page }) => {
  56  |     await page.goto('/')
  57  |     
  58  |     // Try to open create dialog first
  59  |     const createButton = page.locator('button:has-text("新建"), button:has-text("创建"), [data-testid="create-portfolio-btn"]')
  60  |     if (await createButton.count() > 0) {
  61  |       await createButton.first().click()
  62  |       await page.waitForTimeout(500)
  63  |     }
  64  |     
  65  |     // Look for name input
  66  |     const nameInput = page.locator('input[placeholder*="名称"], input[placeholder*="name"], input[name="name"], [data-testid="portfolio-name-input"]')
  67  |     
  68  |     if (await nameInput.count() > 0) {
  69  |       await nameInput.first().fill('测试组合')
  70  |       const value = await nameInput.first().inputValue()
  71  |       expect(value).toBe('测试组合')
  72  |     }
  73  |   })
  74  | 
  75  |   test('should fill portfolio description', async ({ page }) => {
  76  |     await page.goto('/')
  77  |     
  78  |     const createButton = page.locator('button:has-text("新建"), button:has-text("创建"), [data-testid="create-portfolio-btn"]')
  79  |     if (await createButton.count() > 0) {
  80  |       await createButton.first().click()
  81  |       await page.waitForTimeout(500)
  82  |     }
  83  |     
  84  |     // Look for description textarea or input
  85  |     const descInput = page.locator('textarea[placeholder*="描述"], textarea[placeholder*="description"], input[placeholder*="描述"], [data-testid="portfolio-description"]')
  86  |     
  87  |     if (await descInput.count() > 0) {
  88  |       await descInput.first().fill('这是一个用于测试的组合')
  89  |       const value = await descInput.first().inputValue()
  90  |       expect(value).toBe('这是一个用于测试的组合')
  91  |     }
  92  |   })
  93  | 
  94  |   test('should fill initial capital', async ({ page }) => {
  95  |     await page.goto('/')
  96  |     
  97  |     const createButton = page.locator('button:has-text("新建"), button:has-text("创建"), [data-testid="create-portfolio-btn"]')
  98  |     if (await createButton.count() > 0) {
  99  |       await createButton.first().click()
  100 |       await page.waitForTimeout(500)
  101 |     }
  102 |     
  103 |     // Look for capital input
  104 |     const capitalInput = page.locator('input[type="number"], input[placeholder*="资金"], input[placeholder*="capital"], [data-testid="portfolio-capital"]')
  105 |     
  106 |     if (await capitalInput.count() > 0) {
  107 |       await capitalInput.first().fill('100000')
  108 |       const value = await capitalInput.first().inputValue()
  109 |       expect(value).toBe('100000')
  110 |     }
  111 |   })
  112 | 
  113 |   test('should select portfolio type', async ({ page }) => {
  114 |     await page.goto('/')
  115 |     
  116 |     const createButton = page.locator('button:has-text("新建"), button:has-text("创建"), [data-testid="create-portfolio-btn"]')
  117 |     if (await createButton.count() > 0) {
  118 |       await createButton.first().click()
  119 |       await page.waitForTimeout(500)
  120 |     }
  121 |     
```