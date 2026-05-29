import { chromium } from 'playwright';

console.log('Starting browser test...');
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext();
const page = await context.newPage();

// Track console errors
const consoleErrors = [];
page.on('console', msg => {
  if (msg.type() === 'error') {
    consoleErrors.push(msg.text());
    console.log('Console ERROR:', msg.text());
  }
});

// Track page errors
const pageErrors = [];
page.on('pageerror', error => {
  pageErrors.push(error.message);
  console.log('Page ERROR:', error.message);
});

try {
  // Navigate to frontend
  console.log('Navigating to http://localhost:60100...');
  await page.goto('http://localhost:60100', { waitUntil: 'networkidle', timeout: 30000 });
  
  // Wait a bit for Vue to render
  await page.waitForTimeout(3000);
  
  // Take screenshot
  console.log('Taking initial screenshot...');
  await page.screenshot({ path: 'screenshot-initial.png', fullPage: true });
  
  // Check WebSocket status
  console.log('\n=== Checking WebSocket Status ===');
  const wsStatus = await page.evaluate(() => {
    const wsStatusEl = document.querySelector('[class*="ws-status"]') || 
                       document.querySelector('[class*="connection"]') ||
                       document.querySelector('[aria-label*="WebSocket"]') ||
                       document.querySelector('[aria-label*="连接"]');
    return wsStatusEl ? wsStatusEl.textContent : 'No WebSocket status element found';
  });
  console.log('WebSocket status text:', wsStatus);
  
  // Check if dashboard is blank
  console.log('\n=== Checking Dashboard Content ===');
  const dashboardContent = await page.evaluate(() => {
    const mainContent = document.querySelector('main') || document.querySelector('[class*="content"]');
    if (!mainContent) return { hasContent: false, text: 'No main content area found' };
    
    const children = mainContent.children.length;
    const textContent = mainContent.textContent.trim().substring(0, 200);
    const hasVisibleChildren = mainContent.querySelectorAll('*:not(script):not(style)').length;
    
    return {
      hasContent: children > 0 && hasVisibleChildren > 10,
      childrenCount: children,
      visibleElements: hasVisibleChildren,
      textPreview: textContent
    };
  });
  console.log('Dashboard content:', JSON.stringify(dashboardContent, null, 2));
  
  // Check sidebar navigation
  console.log('\n=== Checking Sidebar Navigation ===');
  const sidebarItems = await page.evaluate(() => {
    const sidebar = document.querySelector('[class*="sidebar"]') || 
                     document.querySelector('nav') ||
                     document.querySelector('[role="navigation"]');
    if (!sidebar) return { found: false };
    
    const items = sidebar.querySelectorAll('a, button, [role="button"]');
    return {
      found: true,
      itemCount: items.length,
      itemNames: Array.from(items).slice(0, 15).map(i => i.textContent.trim()).filter(t => t.length > 0)
    };
  });
  console.log('Sidebar items:', JSON.stringify(sidebarItems, null, 2));
  
  // Test navigation to Admin panel
  console.log('\n=== Testing Admin Panel ===');
  try {
    // Find and click Admin in sidebar
    const adminClicked = await page.evaluate(() => {
      const sidebar = document.querySelector('[class*="sidebar"]') || document.querySelector('nav');
      if (!sidebar) return false;
      
      const adminItem = Array.from(sidebar.querySelectorAll('a, button, [role="button"]'))
        .find(item => item.textContent.includes('Admin') || item.textContent.includes('管理'));
      
      if (adminItem) {
        adminItem.click();
        return true;
      }
      return false;
    });
    
    if (adminClicked) {
      console.log('Clicked Admin, waiting for page load...');
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'screenshot-admin.png', fullPage: true });
      
      // Check for 404 or error messages
      const adminStatus = await page.evaluate(() => {
        const body = document.body.textContent;
        const has404 = body.includes('404') || body.includes('Not Found') || body.includes('找不到');
        const hasError = body.includes('error') || body.includes('Error') || body.includes('错误');
        const mainContent = document.querySelector('main')?.textContent?.substring(0, 500);
        return { has404, hasError, contentPreview: mainContent };
      });
      console.log('Admin panel status:', JSON.stringify(adminStatus, null, 2));
    } else {
      console.log('Could not find Admin button in sidebar');
    }
  } catch (e) {
    console.log('Error navigating to Admin:', e.message);
  }
  
  // Test navigation to Macro
  console.log('\n=== Testing Macro Dashboard ===');
  try {
    // Navigate back to home first
    await page.goto('http://localhost:60100', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    
    const macroClicked = await page.evaluate(() => {
      const sidebar = document.querySelector('[class*="sidebar"]') || document.querySelector('nav');
      if (!sidebar) return false;
      
      const macroItem = Array.from(sidebar.querySelectorAll('a, button, [role="button"]'))
        .find(item => item.textContent.includes('Macro') || item.textContent.includes('宏观'));
      
      if (macroItem) {
        macroItem.click();
        return true;
      }
      return false;
    });
    
    if (macroClicked) {
      console.log('Clicked Macro, waiting for page load...');
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'screenshot-macro.png', fullPage: true });
      
      const macroStatus = await page.evaluate(() => {
        const main = document.querySelector('main')?.textContent?.substring(0, 500);
        const hasCards = document.querySelectorAll('[class*="card"]').length > 5;
        return { contentPreview: main, hasCards };
      });
      console.log('Macro dashboard status:', JSON.stringify(macroStatus, null, 2));
    } else {
      console.log('Could not find Macro button in sidebar');
    }
  } catch (e) {
    console.log('Error navigating to Macro:', e.message);
  }
  
  // Final summary
  console.log('\n=== BROWSER TEST SUMMARY ===');
  console.log('Console Errors:', consoleErrors.length);
  if (consoleErrors.length > 0) {
    consoleErrors.forEach(e => console.log('  -', e));
  }
  console.log('Page Errors:', pageErrors.length);
  if (pageErrors.length > 0) {
    pageErrors.forEach(e => console.log('  -', e));
  }
  
} catch (e) {
  console.log('Test failed:', e.message);
  await page.screenshot({ path: 'screenshot-error.png', fullPage: true });
}

await browser.close();
console.log('\nTest completed. Screenshots saved.');
