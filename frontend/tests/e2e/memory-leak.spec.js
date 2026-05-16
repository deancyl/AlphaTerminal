import { test, expect } from '@playwright/test';

const FRONTEND = process.env.FRONTEND_URL || 'http://192.168.1.50:60100';

test.describe('内存泄漏检测', () => {
  
  test('ECharts 实例释放验证', async ({ page }) => {
    await page.goto(FRONTEND);
    await page.waitForLoadState('networkidle');
    
    const initialCount = await page.evaluate(() => {
      return (window as any).__ECHARTS_INSTANCES__?.size || 0;
    });
    
    for (let i = 0; i < 10; i++) {
      const macroBtn = page.locator('[data-route="macro"]');
      const marketBtn = page.locator('[data-route="market"]');
      
      if (await macroBtn.isVisible()) {
        await macroBtn.click();
        await page.waitForTimeout(300);
      }
      
      if (await marketBtn.isVisible()) {
        await marketBtn.click();
        await page.waitForTimeout(300);
      }
    }
    
    const finalCount = await page.evaluate(() => {
      return (window as any).__ECHARTS_INSTANCES__?.size || 0;
    });
    
    expect(finalCount - initialCount).toBeLessThan(2);
  });
  
  test('DOM 节点泄漏检测', async ({ page }) => {
    await page.goto(FRONTEND);
    await page.waitForLoadState('networkidle');
    
    const initialNodes = await page.evaluate(() => 
      document.querySelectorAll('*').length
    );
    
    for (let i = 0; i < 10; i++) {
      const macroBtn = page.locator('[data-route="macro"]');
      const futuresBtn = page.locator('[data-route="futures"]');
      
      if (await macroBtn.isVisible()) {
        await macroBtn.click();
        await page.waitForTimeout(500);
      }
      
      if (await futuresBtn.isVisible()) {
        await futuresBtn.click();
        await page.waitForTimeout(500);
      }
    }
    
    const finalNodes = await page.evaluate(() => 
      document.querySelectorAll('*').length
    );
    
    expect(finalNodes).toBeLessThan(initialNodes * 1.1);
  });
  
  test('事件监听器泄漏检测', async ({ page }) => {
    await page.goto(FRONTEND);
    await page.waitForLoadState('networkidle');
    
    const initialListeners = await page.evaluate(() => {
      return (window as any).__EVENT_LISTENERS__?.size || 0;
    });
    
    for (let i = 0; i < 10; i++) {
      const portfolioBtn = page.locator('[data-route="portfolio"]');
      const backtestBtn = page.locator('[data-route="backtest"]');
      
      if (await portfolioBtn.isVisible()) {
        await portfolioBtn.click();
        await page.waitForTimeout(500);
      }
      
      if (await backtestBtn.isVisible()) {
        await backtestBtn.click();
        await page.waitForTimeout(500);
      }
    }
    
    const finalListeners = await page.evaluate(() => {
      return (window as any).__EVENT_LISTENERS__?.size || 0;
    });
    
    expect(finalListeners - initialListeners).toBeLessThan(5);
  });
  
  test('控制台错误检测', async ({ page }) => {
    const errors: string[] = [];
    
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });
    
    await page.goto(FRONTEND);
    await page.waitForLoadState('networkidle');
    
    await page.waitForTimeout(5000);
    
    const criticalErrors = errors.filter(e => 
      !e.includes('favicon') && 
      !e.includes('extension') &&
      !e.includes('net::ERR_BLOCKED_BY_CLIENT')
    );
    
    expect(criticalErrors.length).toBe(0);
  });
});
