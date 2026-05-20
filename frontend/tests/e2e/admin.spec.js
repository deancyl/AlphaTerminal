import { test, expect } from '@playwright/test'

test.describe('Admin Section', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.waitForLoadState('domcontentloaded')
  })

  test('should navigate to admin dashboard', async ({ page }) => {
    const adminButton = page.locator('[data-route="admin"]')
    await expect(adminButton).toBeVisible()
    await adminButton.click()
    await page.waitForTimeout(500)
    await expect(page).toHaveURL(/#view=admin/)
  })

  test('should show admin dashboard content', async ({ page }) => {
    const adminButton = page.locator('[data-route="admin"]')
    await adminButton.click()
    await page.waitForTimeout(3000)
    await expect(page.locator('#main-content')).toBeVisible()
  })

  test('should have admin navigation styling', async ({ page }) => {
    const adminButton = page.locator('[data-route="admin"]')
    await adminButton.click()
    await page.waitForTimeout(300)
    await expect(adminButton).toHaveAttribute('aria-current', 'page')
  })
})
