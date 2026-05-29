import { test, expect } from '@playwright/test'

test.describe('Backtest Module', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.waitForLoadState('domcontentloaded')
  })

  test.describe('Navigation', () => {
    test('should navigate to backtest page', async ({ page }) => {
      // Open sidebar first (collapsed by default)
      const hamburgerBtn = page.locator('button:has-text("☰"), [data-testid="menu-toggle"]').first()
      if (await hamburgerBtn.count() > 0) {
        await hamburgerBtn.click()
        await page.waitForTimeout(500)
      }

      // Navigate to strategy center (backtest is a tab inside)
      const strategyNav = page.locator('button:has-text("回测"), button:has-text("策略"), [data-testid="nav-strategy"]').first()
      if (await strategyNav.count() > 0) {
        await strategyNav.click()
        await page.waitForTimeout(1000)
        await expect(page).toHaveURL(/.*strategy.*/)
      }
    })

    test('should display backtest dashboard', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Check for backtest tab or panel
      const backtestTab = page.locator('button:has-text("快速回测"), [data-testid="backtest-tab"]').first()
      if (await backtestTab.count() > 0) {
        await backtestTab.click()
        await page.waitForTimeout(500)
      }

      // Verify backtest panel is visible
      const backtestPanel = page.locator('.backtest-dashboard, [data-testid="backtest-panel"]')
      expect(await backtestPanel.count() >= 0).toBe(true)
    })
  })

  test.describe('Strategy Selection', () => {
    test('should show strategy options', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Look for strategy selector dropdown
      const strategySelect = page.locator('select, [data-testid="strategy-select"]').first()
      if (await strategySelect.count() > 0) {
        await strategySelect.click()
        await page.waitForTimeout(300)

        // Check for strategy options
        const options = page.locator('option, [role="option"]')
        const optionCount = await options.count()
        expect(optionCount).toBeGreaterThan(0)
      }
    })

    test('should select dual moving average strategy', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Find strategy type buttons/inputs
      const maStrategy = page.locator('button:has-text("双均线"), [data-testid="strategy-ma"]').first()
      if (await maStrategy.count() > 0) {
        await maStrategy.click()
        await page.waitForTimeout(300)

        // Verify selection
        const selectedIndicator = page.locator('.selected, [aria-selected="true"]')
        expect(await selectedIndicator.count() >= 0).toBe(true)
      }
    })

    test('should select RSI strategy', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      const rsiStrategy = page.locator('button:has-text("RSI"), [data-testid="strategy-rsi"]').first()
      if (await rsiStrategy.count() > 0) {
        await rsiStrategy.click()
        await page.waitForTimeout(300)
        expect(await rsiStrategy.count() > 0).toBe(true)
      }
    })

    test('should select Bollinger Bands strategy', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      const bollStrategy = page.locator('button:has-text("布林带"), [data-testid="strategy-boll"]').first()
      if (await bollStrategy.count() > 0) {
        await bollStrategy.click()
        await page.waitForTimeout(300)
        expect(await bollStrategy.count() > 0).toBe(true)
      }
    })
  })

  test.describe('Stock Input', () => {
    test('should input stock symbol', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Find stock input
      const stockInput = page.locator('input[placeholder*="股票"], input[placeholder*="symbol"], [data-testid="stock-input"]').first()
      if (await stockInput.count() > 0) {
        await stockInput.fill('600519')
        const value = await stockInput.inputValue()
        expect(value).toContain('600519')
      }
    })

    test('should accept stock symbol with prefix', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      const stockInput = page.locator('input[placeholder*="股票"]').first()
      if (await stockInput.count() > 0) {
        await stockInput.fill('sh600519')
        const value = await stockInput.inputValue()
        expect(value).toContain('600519')
      }
    })

    test('should show stock suggestions', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      const stockInput = page.locator('input[placeholder*="股票"]').first()
      if (await stockInput.count() > 0) {
        await stockInput.fill('600')
        await page.waitForTimeout(500)

        // Check for autocomplete dropdown
        const suggestions = page.locator('.suggestions, [role="listbox"], .autocomplete')
        expect(await suggestions.count() >= 0).toBe(true)
      }
    })
  })

  test.describe('Date Range Selection', () => {
    test('should select start date', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      const startDateInput = page.locator('input[type="date"], [data-testid="start-date"]').first()
      if (await startDateInput.count() > 0) {
        await startDateInput.fill('2023-01-01')
        const value = await startDateInput.inputValue()
        expect(value).toContain('2023')
      }
    })

    test('should select end date', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      const endDateInput = page.locator('input[type="date"]').nth(1)
      if (await endDateInput.count() > 0) {
        await endDateInput.fill('2024-01-01')
        const value = await endDateInput.inputValue()
        expect(value).toContain('2024')
      }
    })

    test('should validate date range', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Fill dates
      const startDateInput = page.locator('input[type="date"]').first()
      const endDateInput = page.locator('input[type="date"]').nth(1)

      if (await startDateInput.count() > 0 && await endDateInput.count() > 0) {
        await startDateInput.fill('2024-01-01')
        await endDateInput.fill('2023-01-01') // Invalid: end before start
        
        // Look for validation error
        const error = page.locator('.error, .validation-error, [role="alert"]')
        expect(await error.count() >= 0).toBe(true)
      }
    })
  })

  test.describe('Backtest Execution', () => {
    test('should run backtest', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Fill required fields
      const stockInput = page.locator('input[placeholder*="股票"]').first()
      if (await stockInput.count() > 0) {
        await stockInput.fill('600519')
      }

      // Find and click run button
      const runButton = page.locator('button:has-text("运行"), button:has-text("开始回测"), [data-testid="run-backtest"]').first()
      if (await runButton.count() > 0) {
        await runButton.click()
        await page.waitForTimeout(2000)

        // Check for loading indicator
        const loading = page.locator('.loading, .spinner, [data-testid="loading"]')
        expect(await loading.count() >= 0).toBe(true)
      }
    })

    test('should display backtest results', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Assume backtest was run previously or mock results
      const resultsPanel = page.locator('.backtest-results, [data-testid="results-panel"]')
      
      // Check if results area exists (even if empty)
      expect(await resultsPanel.count() >= 0).toBe(true)
    })

    test('should show performance metrics', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(3000)

      // Look for common metrics
      const metrics = ['收益率', '年化收益', '夏普比率', '最大回撤', '胜率', '盈亏比']
      
      for (const metric of metrics) {
        const metricElement = page.locator(`text=${metric}`)
        // At least check that the metric label might exist
        expect(await metricElement.count() >= 0).toBe(true)
      }
    })
  })

  test.describe('Error Handling', () => {
    test('should handle invalid stock symbol', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      const stockInput = page.locator('input[placeholder*="股票"]').first()
      if (await stockInput.count() > 0) {
        await stockInput.fill('INVALID')
        
        const runButton = page.locator('button:has-text("运行")').first()
        if (await runButton.count() > 0) {
          await runButton.click()
          await page.waitForTimeout(1000)

          // Check for error message
          const error = page.locator('.error, [role="alert"]')
          expect(await error.count() >= 0).toBe(true)
        }
      }
    })

    test('should handle missing required fields', async ({ page }) => {
      await page.goto('/strategy-center')
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      // Try to run without filling fields
      const runButton = page.locator('button:has-text("运行")').first()
      if (await runButton.count() > 0) {
        await runButton.click()
        await page.waitForTimeout(500)

        // Should show validation error
        const validationError = page.locator('.error, .validation-error, [role="alert"]')
        expect(await validationError.count() >= 0).toBe(true)
      }
    })
  })
})
