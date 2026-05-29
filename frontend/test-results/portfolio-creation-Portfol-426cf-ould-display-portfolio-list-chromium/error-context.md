# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: portfolio-creation.spec.js >> Portfolio Creation >> should display portfolio list
- Location: tests/e2e/portfolio-creation.spec.js:211:3

# Error details

```
Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:60100/
Call log:
  - navigating to "http://localhost:60100/", waiting until "load"

```

# Test source

```ts
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
  122 |     // Look for type selector
  123 |     const typeSelect = page.locator('select[name="type"], .select-type, [data-testid="portfolio-type"], button:has-text("类型")')
  124 |     
  125 |     if (await typeSelect.count() > 0) {
  126 |       await typeSelect.first().click()
  127 |       await page.waitForTimeout(300)
  128 |       
  129 |       // Select an option
  130 |       const option = page.locator('.option, .select-option, [role="option"]').first()
  131 |       if (await option.count() > 0) {
  132 |         await option.click()
  133 |       }
  134 |     }
  135 |   })
  136 | 
  137 |   test('should cancel portfolio creation', async ({ page }) => {
  138 |     await page.goto('/')
  139 |     
  140 |     const createButton = page.locator('button:has-text("新建"), button:has-text("创建"), [data-testid="create-portfolio-btn"]')
  141 |     if (await createButton.count() > 0) {
  142 |       await createButton.first().click()
  143 |       await page.waitForTimeout(500)
  144 |     }
  145 |     
  146 |     // Look for cancel button
  147 |     const cancelButton = page.locator('button:has-text("取消"), button:has-text("Cancel"), [data-testid="cancel-btn"]')
  148 |     
  149 |     if (await cancelButton.count() > 0) {
  150 |       await cancelButton.first().click()
  151 |       await page.waitForTimeout(500)
  152 |       
  153 |       // Dialog should be closed
  154 |       const dialog = page.locator('.dialog, .modal, [role="dialog"]')
  155 |       expect(await dialog.count()).toBe(0)
  156 |     }
  157 |   })
  158 | 
  159 |   test('should submit portfolio creation', async ({ page }) => {
  160 |     await page.goto('/')
  161 |     
  162 |     const createButton = page.locator('button:has-text("新建"), button:has-text("创建"), [data-testid="create-portfolio-btn"]')
  163 |     if (await createButton.count() > 0) {
  164 |       await createButton.first().click()
  165 |       await page.waitForTimeout(500)
  166 |     }
  167 |     
  168 |     // Fill in required fields
  169 |     const nameInput = page.locator('input[placeholder*="名称"], input[placeholder*="name"], [data-testid="portfolio-name-input"]')
  170 |     if (await nameInput.count() > 0) {
  171 |       await nameInput.first().fill('E2E测试组合')
  172 |     }
  173 |     
  174 |     // Look for submit button
  175 |     const submitButton = page.locator('button:has-text("确定"), button:has-text("创建"), button:has-text("Submit"), button[type="submit"], [data-testid="submit-btn"]')
  176 |     
  177 |     if (await submitButton.count() > 0) {
  178 |       await submitButton.first().click()
  179 |       await page.waitForTimeout(2000)
  180 |       
  181 |       // Check for success message or new portfolio in list
  182 |       const successMsg = page.locator('.success, .toast, [data-testid="success-message"]')
  183 |       const portfolioList = page.locator('.portfolio-item, .portfolio-list')
  184 |       
  185 |       expect(await successMsg.count() > 0 || await portfolioList.count() > 0).toBe(true)
  186 |     }
  187 |   })
  188 | 
  189 |   test('should validate required fields', async ({ page }) => {
  190 |     await page.goto('/')
  191 |     
  192 |     const createButton = page.locator('button:has-text("新建"), button:has-text("创建"), [data-testid="create-portfolio-btn"]')
  193 |     if (await createButton.count() > 0) {
  194 |       await createButton.first().click()
  195 |       await page.waitForTimeout(500)
  196 |     }
  197 |     
  198 |     // Try to submit without filling required fields
  199 |     const submitButton = page.locator('button:has-text("确定"), button:has-text("创建"), button[type="submit"]')
  200 |     
  201 |     if (await submitButton.count() > 0) {
  202 |       await submitButton.first().click()
  203 |       await page.waitForTimeout(500)
  204 |       
  205 |       // Check for validation error
  206 |       const errorMsg = page.locator('.error, .validation-error, [data-testid="error-message"]')
  207 |       expect(await errorMsg.count() >= 0).toBe(true)
  208 |     }
  209 |   })
  210 | 
  211 |   test('should display portfolio list', async ({ page }) => {
> 212 |     await page.goto('/')
      |                ^ Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:60100/
  213 |     
  214 |     // Navigate to portfolio section
  215 |     const portfolioLink = page.locator('a[href*="portfolio"], button:has-text("组合"), [data-testid="portfolio-link"]')
  216 |     if (await portfolioLink.count() > 0) {
  217 |       await portfolioLink.first().click()
  218 |       await page.waitForTimeout(1000)
  219 |     }
  220 |     
  221 |     // Check if portfolio list exists
  222 |     const portfolioList = page.locator('.portfolio-list, .portfolios, [data-testid="portfolio-list"]')
  223 |     const portfolioItems = page.locator('.portfolio-item, .portfolio-card')
  224 |     
  225 |     // Either list container or items should exist
  226 |     expect(await portfolioList.count() > 0 || await portfolioItems.count() >= 0).toBe(true)
  227 |   })
  228 | 
  229 |   test('should delete portfolio', async ({ page }) => {
  230 |     await page.goto('/')
  231 |     
  232 |     // Navigate to portfolio section
  233 |     const portfolioLink = page.locator('a[href*="portfolio"], button:has-text("组合"), [data-testid="portfolio-link"]')
  234 |     if (await portfolioLink.count() > 0) {
  235 |       await portfolioLink.first().click()
  236 |       await page.waitForTimeout(1000)
  237 |     }
  238 |     
  239 |     // Look for delete button on first portfolio
  240 |     const deleteButton = page.locator('.delete-btn, button:has-text("删除"), button:has-text("Delete"), [data-testid="delete-portfolio"]').first()
  241 |     
  242 |     if (await deleteButton.count() > 0) {
  243 |       await deleteButton.click()
  244 |       await page.waitForTimeout(500)
  245 |       
  246 |       // Look for confirmation dialog
  247 |       const confirmDialog = page.locator('.confirm-dialog, .modal, [role="dialog"]')
  248 |       expect(await confirmDialog.count() >= 0).toBe(true)
  249 |     }
  250 |   })
  251 | })
  252 | 
```