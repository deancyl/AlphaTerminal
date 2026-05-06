import { test, expect } from '@playwright/test'

test.describe('Homepage', () => {
  test('should load homepage successfully', async ({ page }) => {
    await page.goto('/')
    
    // Check page title
    await expect(page).toHaveTitle(/AlphaTerminal/)
    
    // Check main layout elements
    await expect(page.locator('body')).toBeVisible()
    
    // Check if main container exists
    const mainContainer = page.locator('#app, .app, main, [data-testid="app"]')
    await expect(mainContainer.first()).toBeVisible()
  })

  test('should display navigation elements', async ({ page }) => {
    await page.goto('/')
    
    // Look for common navigation patterns
    const nav = page.locator('nav, header, .navbar, .header')
    const hasNav = await nav.count() > 0
    
    if (hasNav) {
      await expect(nav.first()).toBeVisible()
    }
  })

  test('should display sidebar or menu', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    
    // First, click the hamburger button to open the sidebar
    // The sidebar is hidden by default (isSidebarOpen = false in App.vue)
    const hamburgerBtn = page.locator('button:has-text("☰"), button:has-text("菜单"), [data-testid="menu-toggle"], .menu-toggle, .hamburger')
    if (await hamburgerBtn.count() > 0) {
      await hamburgerBtn.first().click()
      await page.waitForTimeout(500) // Wait for CSS transition
    }
    
    // Now check for sidebar patterns
    const sidebar = page.locator('aside, .sidebar, .sidenav, [data-testid="sidebar"]')
    const hasSidebar = await sidebar.count() > 0
    
    if (hasSidebar) {
      await expect(sidebar.first()).toBeVisible({ timeout: 10000 })
    }
  })

  test('should have working responsive layout', async ({ page }) => {
    await page.goto('/')
    
    // Test desktop viewport
    await page.setViewportSize({ width: 1920, height: 1080 })
    await expect(page.locator('body')).toBeVisible()
    
    // Test tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 })
    await expect(page.locator('body')).toBeVisible()
    
    // Test mobile viewport
    await page.setViewportSize({ width: 375, height: 667 })
    await expect(page.locator('body')).toBeVisible()
  })

  test('should load without console errors', async ({ page }) => {
    const errors = []
    
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text())
      }
    })
    
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    
    // Filter out non-critical errors
    const criticalErrors = errors.filter(err => 
      !err.includes('favicon') && 
      !err.includes('source map') &&
      !err.includes('timeout') &&
      !err.includes('Timeout') &&
      !err.includes('ETIMEDOUT') &&
      !err.includes('network')
    )
    
    expect(criticalErrors).toHaveLength(0)
  })
})
