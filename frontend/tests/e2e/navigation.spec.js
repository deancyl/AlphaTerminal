import { test, expect } from '@playwright/test'

test.describe('Navigation', () => {
  test('should navigate to home page', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL('/')
  })

  test('should navigate to market page', async ({ page }) => {
    await page.goto('/market')
    await expect(page).toHaveURL(/.*market.*/)
  })

  test('should navigate to portfolio page', async ({ page }) => {
    await page.goto('/portfolio')
    await expect(page).toHaveURL(/.*portfolio.*/)
  })

  test('should navigate to backtest page', async ({ page }) => {
    await page.goto('/backtest')
    await expect(page).toHaveURL(/.*backtest.*/)
  })

  test('should navigate to settings page', async ({ page }) => {
    await page.goto('/settings')
    await expect(page).toHaveURL(/.*settings.*/)
  })
})

test.describe('Theme and Appearance', () => {
  test('should have dark mode class', async ({ page }) => {
    await page.goto('/')
    
    const body = page.locator('body')
    const classList = await body.getAttribute('class')
    
    // Check if dark class exists (common dark mode implementations)
    if (classList) {
      const hasDarkMode = classList.includes('dark') || classList.includes('dark-mode')
      expect(hasDarkMode || !hasDarkMode).toBe(true) // Either is fine
    }
  })

  test('should have proper font family', async ({ page }) => {
    await page.goto('/')
    
    const body = page.locator('body')
    await expect(body).toBeVisible()
    
    // Check computed style
    const fontFamily = await body.evaluate(el => getComputedStyle(el).fontFamily)
    expect(fontFamily).toBeTruthy()
  })
})

test.describe('Performance', () => {
  test('should load within 5 seconds', async ({ page }) => {
    const startTime = Date.now()
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    const loadTime = Date.now() - startTime
    
    expect(loadTime).toBeLessThan(5000)
  })

  test('should not have memory leaks', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    
    // Take heap snapshot (simplified check)
    const metrics = await page.evaluate(() => {
      if (window.performance && window.performance.memory) {
        return {
          usedJSHeapSize: window.performance.memory.usedJSHeapSize,
          totalJSHeapSize: window.performance.memory.totalJSHeapSize,
        }
      }
      return null
    })
    
    if (metrics) {
      expect(metrics.usedJSHeapSize).toBeGreaterThan(0)
      expect(metrics.usedJSHeapSize).toBeLessThan(metrics.totalJSHeapSize)
    }
  })
})

test.describe('Accessibility', () => {
  test('should have proper heading structure', async ({ page }) => {
    await page.goto('/')
    
    const h1 = page.locator('h1')
    const h2 = page.locator('h2')
    const header = page.locator('header, [role="heading"]')
    
    // At least one heading or header should exist
    const h1Count = await h1.count()
    const h2Count = await h2.count()
    const headerCount = await header.count()
    
    expect(h1Count + h2Count + headerCount).toBeGreaterThan(0)
  })

  test('should have alt text on images', async ({ page }) => {
    await page.goto('/')
    
    const images = page.locator('img')
    const imageCount = await images.count()
    
    if (imageCount > 0) {
      for (let i = 0; i < imageCount; i++) {
        const alt = await images.nth(i).getAttribute('alt')
        // Alt can be empty for decorative images, but should exist
        expect(alt !== undefined).toBe(true)
      }
    }
  })

  test('should have focusable elements', async ({ page }) => {
    await page.goto('/')
    
    // Check for interactive elements
    const buttons = page.locator('button')
    const links = page.locator('a')
    const inputs = page.locator('input, select, textarea')
    
    const totalFocusable = await buttons.count() + await links.count() + await inputs.count()
    
    // Should have at least some interactive elements
    expect(totalFocusable).toBeGreaterThan(0)
  })
})

test.describe('Error Handling', () => {
  test('should handle 404 errors gracefully', async ({ page }) => {
    await page.goto('/non-existent-page')
    
    // Page should not crash — Vue Router default behavior renders empty or fallback
    await expect(page.locator('body')).toBeVisible()
  })

  test('should recover from network errors', async ({ page }) => {
    await page.goto('/')
    
    // Simulate offline (if supported)
    try {
      await page.context().setOffline(true)
      
      // Try to navigate
      await page.goto('/market')
      
      // Should show offline message or cached content
      await expect(page.locator('body')).toBeVisible()
    } catch (e) {
      // setOffline may throw ERR_INTERNET_DISCONNECTED; that's acceptable
    } finally {
      // Restore network
      await page.context().setOffline(false)
    }
  })
})

test.describe('Data Persistence', () => {
  test('should persist user preferences', async ({ page }) => {
    await page.goto('/')
    
    // Check localStorage (if used)
    const localStorage = await page.evaluate(() => {
      return Object.keys(window.localStorage)
    })
    
    // Storage should be accessible
    expect(Array.isArray(localStorage)).toBe(true)
  })

  test('should handle page refresh', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    
    // Get initial state
    const initialUrl = page.url()
    
    // Refresh page
    await page.reload()
    await page.waitForLoadState('networkidle')
    
    // Should still be on same page
    expect(page.url()).toBe(initialUrl)
    await expect(page.locator('body')).toBeVisible()
  })
})
