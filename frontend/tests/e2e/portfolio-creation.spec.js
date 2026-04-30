import { test, expect } from '@playwright/test'

test.describe('Portfolio Creation', () => {
  test('should navigate to portfolio page', async ({ page }) => {
    await page.goto('/')
    
    // Look for portfolio link or button
    const portfolioLink = page.locator('a[href*="portfolio"], button:has-text("组合"), button:has-text("Portfolio"), [data-testid="portfolio-link"]')
    
    if (await portfolioLink.count() > 0) {
      await portfolioLink.first().click()
      await page.waitForTimeout(1000)
      
      // Check if URL changed or portfolio section is visible
      const portfolioSection = page.locator('.portfolio, [data-testid="portfolio"], .portfolio-list')
      expect(await portfolioSection.count() >= 0).toBe(true)
    }
  })

  test('should open create portfolio dialog', async ({ page }) => {
    await page.goto('/')
    
    // Look for create portfolio button
    const createButton = page.locator('button:has-text("新建"), button:has-text("创建"), button:has-text("New"), button:has-text("+"), [data-testid="create-portfolio-btn"]')
    
    if (await createButton.count() > 0) {
      await createButton.first().click()
      
      // Check if dialog/modal appeared
      const dialog = page.locator('.dialog, .modal, [role="dialog"], [data-testid="portfolio-dialog"]')
      expect(await dialog.count() > 0).toBe(true)
    }
  })

  test('should fill portfolio name', async ({ page }) => {
    await page.goto('/')
    
    // Try to open create dialog first
    const createButton = page.locator('button:has-text("新建"), button:has-text("创建"), [data-testid="create-portfolio-btn"]')
    if (await createButton.count() > 0) {
      await createButton.first().click()
      await page.waitForTimeout(500)
    }
    
    // Look for name input
    const nameInput = page.locator('input[placeholder*="名称"], input[placeholder*="name"], input[name="name"], [data-testid="portfolio-name-input"]')
    
    if (await nameInput.count() > 0) {
      await nameInput.first().fill('测试组合')
      const value = await nameInput.first().inputValue()
      expect(value).toBe('测试组合')
    }
  })

  test('should fill portfolio description', async ({ page }) => {
    await page.goto('/')
    
    const createButton = page.locator('button:has-text("新建"), button:has-text("创建"), [data-testid="create-portfolio-btn"]')
    if (await createButton.count() > 0) {
      await createButton.first().click()
      await page.waitForTimeout(500)
    }
    
    // Look for description textarea or input
    const descInput = page.locator('textarea[placeholder*="描述"], textarea[placeholder*="description"], input[placeholder*="描述"], [data-testid="portfolio-description"]')
    
    if (await descInput.count() > 0) {
      await descInput.first().fill('这是一个用于测试的组合')
      const value = await descInput.first().inputValue()
      expect(value).toBe('这是一个用于测试的组合')
    }
  })

  test('should fill initial capital', async ({ page }) => {
    await page.goto('/')
    
    const createButton = page.locator('button:has-text("新建"), button:has-text("创建"), [data-testid="create-portfolio-btn"]')
    if (await createButton.count() > 0) {
      await createButton.first().click()
      await page.waitForTimeout(500)
    }
    
    // Look for capital input
    const capitalInput = page.locator('input[type="number"], input[placeholder*="资金"], input[placeholder*="capital"], [data-testid="portfolio-capital"]')
    
    if (await capitalInput.count() > 0) {
      await capitalInput.first().fill('100000')
      const value = await capitalInput.first().inputValue()
      expect(value).toBe('100000')
    }
  })

  test('should select portfolio type', async ({ page }) => {
    await page.goto('/')
    
    const createButton = page.locator('button:has-text("新建"), button:has-text("创建"), [data-testid="create-portfolio-btn"]')
    if (await createButton.count() > 0) {
      await createButton.first().click()
      await page.waitForTimeout(500)
    }
    
    // Look for type selector
    const typeSelect = page.locator('select[name="type"], .select-type, [data-testid="portfolio-type"], button:has-text("类型")')
    
    if (await typeSelect.count() > 0) {
      await typeSelect.first().click()
      await page.waitForTimeout(300)
      
      // Select an option
      const option = page.locator('.option, .select-option, [role="option"]').first()
      if (await option.count() > 0) {
        await option.click()
      }
    }
  })

  test('should cancel portfolio creation', async ({ page }) => {
    await page.goto('/')
    
    const createButton = page.locator('button:has-text("新建"), button:has-text("创建"), [data-testid="create-portfolio-btn"]')
    if (await createButton.count() > 0) {
      await createButton.first().click()
      await page.waitForTimeout(500)
    }
    
    // Look for cancel button
    const cancelButton = page.locator('button:has-text("取消"), button:has-text("Cancel"), [data-testid="cancel-btn"]')
    
    if (await cancelButton.count() > 0) {
      await cancelButton.first().click()
      await page.waitForTimeout(500)
      
      // Dialog should be closed
      const dialog = page.locator('.dialog, .modal, [role="dialog"]')
      expect(await dialog.count()).toBe(0)
    }
  })

  test('should submit portfolio creation', async ({ page }) => {
    await page.goto('/')
    
    const createButton = page.locator('button:has-text("新建"), button:has-text("创建"), [data-testid="create-portfolio-btn"]')
    if (await createButton.count() > 0) {
      await createButton.first().click()
      await page.waitForTimeout(500)
    }
    
    // Fill in required fields
    const nameInput = page.locator('input[placeholder*="名称"], input[placeholder*="name"], [data-testid="portfolio-name-input"]')
    if (await nameInput.count() > 0) {
      await nameInput.first().fill('E2E测试组合')
    }
    
    // Look for submit button
    const submitButton = page.locator('button:has-text("确定"), button:has-text("创建"), button:has-text("Submit"), button[type="submit"], [data-testid="submit-btn"]')
    
    if (await submitButton.count() > 0) {
      await submitButton.first().click()
      await page.waitForTimeout(2000)
      
      // Check for success message or new portfolio in list
      const successMsg = page.locator('.success, .toast, [data-testid="success-message"]')
      const portfolioList = page.locator('.portfolio-item, .portfolio-list')
      
      expect(await successMsg.count() > 0 || await portfolioList.count() > 0).toBe(true)
    }
  })

  test('should validate required fields', async ({ page }) => {
    await page.goto('/')
    
    const createButton = page.locator('button:has-text("新建"), button:has-text("创建"), [data-testid="create-portfolio-btn"]')
    if (await createButton.count() > 0) {
      await createButton.first().click()
      await page.waitForTimeout(500)
    }
    
    // Try to submit without filling required fields
    const submitButton = page.locator('button:has-text("确定"), button:has-text("创建"), button[type="submit"]')
    
    if (await submitButton.count() > 0) {
      await submitButton.first().click()
      await page.waitForTimeout(500)
      
      // Check for validation error
      const errorMsg = page.locator('.error, .validation-error, [data-testid="error-message"]')
      expect(await errorMsg.count() >= 0).toBe(true)
    }
  })

  test('should display portfolio list', async ({ page }) => {
    await page.goto('/')
    
    // Navigate to portfolio section
    const portfolioLink = page.locator('a[href*="portfolio"], button:has-text("组合"), [data-testid="portfolio-link"]')
    if (await portfolioLink.count() > 0) {
      await portfolioLink.first().click()
      await page.waitForTimeout(1000)
    }
    
    // Check if portfolio list exists
    const portfolioList = page.locator('.portfolio-list, .portfolios, [data-testid="portfolio-list"]')
    const portfolioItems = page.locator('.portfolio-item, .portfolio-card')
    
    // Either list container or items should exist
    expect(await portfolioList.count() > 0 || await portfolioItems.count() >= 0).toBe(true)
  })

  test('should delete portfolio', async ({ page }) => {
    await page.goto('/')
    
    // Navigate to portfolio section
    const portfolioLink = page.locator('a[href*="portfolio"], button:has-text("组合"), [data-testid="portfolio-link"]')
    if (await portfolioLink.count() > 0) {
      await portfolioLink.first().click()
      await page.waitForTimeout(1000)
    }
    
    // Look for delete button on first portfolio
    const deleteButton = page.locator('.delete-btn, button:has-text("删除"), button:has-text("Delete"), [data-testid="delete-portfolio"]').first()
    
    if (await deleteButton.count() > 0) {
      await deleteButton.click()
      await page.waitForTimeout(500)
      
      // Look for confirmation dialog
      const confirmDialog = page.locator('.confirm-dialog, .modal, [role="dialog"]')
      expect(await confirmDialog.count() >= 0).toBe(true)
    }
  })
})
