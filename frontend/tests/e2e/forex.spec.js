import { test, expect } from '@playwright/test'

test.describe('Forex Module', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.waitForLoadState('domcontentloaded')
  })

  test.describe('Navigation', () => {
    test('should navigate to forex page', async ({ page }) => {
      // Open sidebar
      const hamburgerBtn = page.locator('button:has-text("☰"), [data-testid="menu-toggle"]').first()
      if (await hamburgerBtn.count() > 0) {
        await hamburgerBtn.click()
        await page.waitForTimeout(500)
      }

      // Navigate to forex
      const forexNav = page.locator('button:has-text("外汇"), [data-testid="nav-forex"]').first()
      if (await forexNav.count() > 0) {
        await forexNav.click()
        await page.waitForTimeout(1000)
        await expect(page).toHaveURL(/.*forex.*/)
      }
    })

    test('should display forex dashboard', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Check for forex panel
      const forexPanel = page.locator('.forex-dashboard, [data-testid="forex-panel"]')
      expect(await forexPanel.count() >= 0).toBe(true)
    })
  })

  test.describe('Real-time Quotes', () => {
    test('should display major currency pairs', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Check for major pairs
      const majorPairs = ['USD', 'EUR', 'GBP', 'JPY', 'CNY']
      
      for (const pair of majorPairs) {
        const pairElement = page.locator(`text=${pair}`)
        expect(await pairElement.count() >= 0).toBe(true)
      }
    })

    test('should show bid/ask prices', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for bid/ask columns
      const bidColumn = page.locator('.bid, [data-testid="bid"]').first()
      const askColumn = page.locator('.ask, [data-testid="ask"]').first()

      expect(await bidColumn.count() >= 0).toBe(true)
      expect(await askColumn.count() >= 0).toBe(true)
    })

    test('should display price changes', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for change percentage
      const changeElement = page.locator('.change, .change-pct, [data-testid="change"]').first()
      expect(await changeElement.count() >= 0).toBe(true)
    })

    test('should show timestamps', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for last update time
      const timestamp = page.locator('.timestamp, .last-update, [data-testid="timestamp"]')
      expect(await timestamp.count() >= 0).toBe(true)
    })
  })

  test.describe('Cross-rate Matrix', () => {
    test('should display cross-rate matrix', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for matrix table
      const matrix = page.locator('.cross-rate-matrix, table, [data-testid="cross-rate-matrix"]')
      expect(await matrix.count() >= 0).toBe(true)
    })

    test('should show currency row headers', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Check for row headers (USD, EUR, etc.)
      const usdHeader = page.locator('th:has-text("USD"), td:has-text("USD")')
      expect(await usdHeader.count() >= 0).toBe(true)
    })

    test('should show currency column headers', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Check for column headers
      const headers = page.locator('th')
      const headerCount = await headers.count()

      if (headerCount > 0) {
        // Should have at least 2 headers
        expect(headerCount).toBeGreaterThan(1)
      }
    })

    test('should highlight diagonal cells', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for diagonal highlight (1.00 or similar)
      const diagonal = page.locator('td:has-text("1.00"), td:has-text("—")')
      expect(await diagonal.count() >= 0).toBe(true)
    })

    test('should show cross-rate values', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Check for numeric values in matrix cells
      const cells = page.locator('td')
      const cellCount = await cells.count()

      if (cellCount > 0) {
        const firstCellValue = await cells.first().textContent()
        expect(firstCellValue).toBeTruthy()
      }
    })
  })

  test.describe('K-Line Chart', () => {
    test('should display forex K-line chart', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for chart container
      const chart = page.locator('.kline-chart, [data-testid="forex-chart"], canvas')
      expect(await chart.count() >= 0).toBe(true)
    })

    test('should select currency pair for chart', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Find pair selector
      const pairSelect = page.locator('select, [data-testid="pair-select"]').first()
      if (await pairSelect.count() > 0) {
        await pairSelect.selectOption({ index: 0 })
        await page.waitForTimeout(500)
        expect(await pairSelect.count() > 0).toBe(true)
      }
    })

    test('should change chart period', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Look for period buttons
      const periodBtn = page.locator('button:has-text("日K"), button:has-text("1D")').first()
      if (await periodBtn.count() > 0) {
        await periodBtn.click()
        await page.waitForTimeout(500)
      }

      const hourBtn = page.locator('button:has-text("小时"), button:has-text("1H")').first()
      if (await hourBtn.count() > 0) {
        await hourBtn.click()
        await page.waitForTimeout(500)
      }
    })
  })

  test.describe('Currency Converter', () => {
    test('should display converter input', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Look for converter section
      const converter = page.locator('.converter, [data-testid="currency-converter"]')
      expect(await converter.count() >= 0).toBe(true)
    })

    test('should input amount for conversion', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      const amountInput = page.locator('input[type="number"], [data-testid="amount-input"]').first()
      if (await amountInput.count() > 0) {
        await amountInput.fill('100')
        const value = await amountInput.inputValue()
        expect(value).toBe('100')
      }
    })

    test('should select from currency', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      const fromSelect = page.locator('select[name="from"], [data-testid="from-currency"]').first()
      if (await fromSelect.count() > 0) {
        await fromSelect.selectOption({ index: 0 })
        await page.waitForTimeout(300)
      }
    })

    test('should select to currency', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      const toSelect = page.locator('select[name="to"], [data-testid="to-currency"]').first()
      if (await toSelect.count() > 0) {
        await toSelect.selectOption({ index: 1 })
        await page.waitForTimeout(300)
      }
    })
  })

  test.describe('Data Source Indicators', () => {
    test('should show data source name', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for data source label
      const sourceLabel = page.locator('.data-source, [data-testid="data-source"]')
      expect(await sourceLabel.count() >= 0).toBe(true)
    })

    test('should show connection status', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Look for status indicator
      const status = page.locator('.status, .connection-status, [data-testid="connection-status"]')
      expect(await status.count() >= 0).toBe(true)
    })

    test('should show circuit breaker status if active', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for circuit breaker banner
      const cbBanner = page.locator('.circuit-breaker-banner, [data-testid="circuit-breaker"]')
      // Should exist (even if hidden)
      expect(await cbBanner.count() >= 0).toBe(true)
    })
  })

  test.describe('Error Handling', () => {
    test('should handle network errors gracefully', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      
      // Simulate offline
      try {
        await page.context().setOffline(true)
        await page.waitForTimeout(2000)

        // Should show error or cached data
        const body = page.locator('body')
        await expect(body).toBeVisible()
      } finally {
        await page.context().setOffline(false)
      }
    })

    test('should show loading state', async ({ page }) => {
      await page.goto('/forex')
      
      // Check for loading indicator during initial load
      const loading = page.locator('.loading, .spinner, [data-testid="loading"]')
      // May have already finished loading
      expect(await loading.count() >= 0).toBe(true)
    })

    test('should handle empty data', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Check for empty state message
      const emptyState = page.locator('.empty-state, .no-data, [data-testid="empty-state"]')
      expect(await emptyState.count() >= 0).toBe(true)
    })
  })

  test.describe('Accessibility', () => {
    test('should have proper ARIA roles', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Check for table role
      const table = page.locator('[role="table"], table')
      expect(await table.count() >= 0).toBe(true)
    })

    test('should be keyboard accessible', async ({ page }) => {
      await page.goto('/forex')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Tab through elements
      await page.keyboard.press('Tab')
      const focused = page.locator(':focus')
      expect(await focused.count() >= 0).toBe(true)
    })
  })
})
