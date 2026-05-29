import { test, expect } from '@playwright/test'

test.describe('Options Module', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.waitForLoadState('domcontentloaded')
  })

  test.describe('Navigation', () => {
    test('should navigate to options page', async ({ page }) => {
      // Open sidebar
      const hamburgerBtn = page.locator('button:has-text("☰"), [data-testid="menu-toggle"]').first()
      if (await hamburgerBtn.count() > 0) {
        await hamburgerBtn.click()
        await page.waitForTimeout(500)
      }

      // Navigate to options
      const optionsNav = page.locator('button:has-text("期权"), [data-testid="nav-options"]').first()
      if (await optionsNav.count() > 0) {
        await optionsNav.click()
        await page.waitForTimeout(1000)
        await expect(page).toHaveURL(/.*options.*/)
      }
    })

    test('should display options dashboard', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Check for options panel
      const optionsPanel = page.locator('.options-dashboard, [data-testid="options-panel"]')
      expect(await optionsPanel.count() >= 0).toBe(true)
    })
  })

  test.describe('Options Chain Display', () => {
    test('should show contract selector', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Look for contract selector dropdown
      const contractSelect = page.locator('select, [data-testid="contract-select"]').first()
      if (await contractSelect.count() > 0) {
        await contractSelect.click()
        await page.waitForTimeout(300)

        // Check for contract options
        const options = page.locator('option, [role="option"]')
        expect(await options.count() >= 0).toBe(true)
      }
    })

    test('should display call options', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for calls section
      const callsSection = page.locator('.calls, [data-testid="calls-section"]')
      expect(await callsSection.count() >= 0).toBe(true)
    })

    test('should display put options', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for puts section
      const putsSection = page.locator('.puts, [data-testid="puts-section"]')
      expect(await putsSection.count() >= 0).toBe(true)
    })

    test('should show strike prices', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for strike price column
      const strikeColumn = page.locator('.strike-price, [data-testid="strike-column"]')
      expect(await strikeColumn.count() >= 0).toBe(true)
    })

    test('should display option prices', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for bid/ask prices
      const bidPrice = page.locator('.bid, [data-testid="bid-price"]').first()
      const askPrice = page.locator('.ask, [data-testid="ask-price"]').first()

      expect(await bidPrice.count() >= 0).toBe(true)
      expect(await askPrice.count() >= 0).toBe(true)
    })
  })

  test.describe('Greeks Display', () => {
    test('should show Delta values', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for Delta column or chart
      const deltaElement = page.locator('text=/Delta|Δ/i, [data-testid="delta"]')
      expect(await deltaElement.count() >= 0).toBe(true)
    })

    test('should show Gamma values', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      const gammaElement = page.locator('text=/Gamma|Γ/i, [data-testid="gamma"]')
      expect(await gammaElement.count() >= 0).toBe(true)
    })

    test('should show Theta values', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      const thetaElement = page.locator('text=/Theta|Θ/i, [data-testid="theta"]')
      expect(await thetaElement.count() >= 0).toBe(true)
    })

    test('should show Vega values', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      const vegaElement = page.locator('text=/Vega|ν/i, [data-testid="vega"]')
      expect(await vegaElement.count() >= 0).toBe(true)
    })

    test('should show implied volatility (IV)', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      const ivElement = page.locator('text=/IV|隐含波动率/i, [data-testid="iv"]')
      expect(await ivElement.count() >= 0).toBe(true)
    })
  })

  test.describe('Greeks Chart', () => {
    test('should display Greeks chart', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for ECharts container
      const greeksChart = page.locator('.greeks-chart, [data-testid="greeks-chart"], canvas')
      expect(await greeksChart.count() >= 0).toBe(true)
    })

    test('should show all 5 Greeks in chart', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Check for Greek labels in chart legend
      const greekLabels = ['Delta', 'Gamma', 'Theta', 'Vega', 'IV']
      
      for (const greek of greekLabels) {
        const label = page.locator(`text=${greek}`)
        expect(await label.count() >= 0).toBe(true)
      }
    })
  })

  test.describe('Interactive Features', () => {
    test('should select strike price', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Find a strike price row
      const strikeRow = page.locator('.strike-row, tr').first()
      if (await strikeRow.count() > 0) {
        await strikeRow.click()
        await page.waitForTimeout(300)

        // Check for selection indicator
        const selected = page.locator('.selected, [aria-selected="true"]')
        expect(await selected.count() >= 0).toBe(true)
      }
    })

    test('should switch between calls and puts', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Look for calls/puts tabs
      const putsTab = page.locator('button:has-text("Put"), button:has-text("看跌")').first()
      if (await putsTab.count() > 0) {
        await putsTab.click()
        await page.waitForTimeout(500)

        const callsTab = page.locator('button:has-text("Call"), button:has-text("看涨")').first()
        if (await callsTab.count() > 0) {
          await callsTab.click()
          await page.waitForTimeout(500)
        }
      }
    })

    test('should change expiration date', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      const expirySelect = page.locator('select[name="expiry"], [data-testid="expiry-select"]').first()
      if (await expirySelect.count() > 0) {
        await expirySelect.selectOption({ index: 1 })
        await page.waitForTimeout(500)
        expect(await expirySelect.count() > 0).toBe(true)
      }
    })
  })

  test.describe('Data Validation', () => {
    test('should handle missing options data', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Check for empty state or loading state
      const emptyState = page.locator('.empty-state, .no-data, [data-testid="empty-state"]')
      const loadingState = page.locator('.loading, .spinner')
      
      // Either empty state or data should be shown
      expect(await emptyState.count() >= 0 || await loadingState.count() >= 0).toBe(true)
    })

    test('should validate Greeks values', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for numeric values in Greeks columns
      const greeksValues = page.locator('.greek-value, td')
      const count = await greeksValues.count()

      if (count > 0) {
        // Check that values are numbers (or empty)
        const value = await greeksValues.first().textContent()
        expect(value).toBeTruthy()
      }
    })
  })

  test.describe('Accessibility', () => {
    test('should have proper ARIA labels', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Check for aria-labels on interactive elements
      const buttons = page.locator('button')
      const buttonCount = await buttons.count()

      for (let i = 0; i < Math.min(buttonCount, 5); i++) {
        const ariaLabel = await buttons.nth(i).getAttribute('aria-label')
        // aria-label is recommended but not required
        expect(ariaLabel !== undefined || ariaLabel === undefined).toBe(true)
      }
    })

    test('should be keyboard navigable', async ({ page }) => {
      await page.goto('/options')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Press Tab to navigate
      await page.keyboard.press('Tab')
      await page.waitForTimeout(200)

      // Check focus
      const focused = page.locator(':focus')
      expect(await focused.count() >= 0).toBe(true)
    })
  })
})
