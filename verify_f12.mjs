/**
 * F12 Dynamic Verification Script
 * Captures Console errors, Network failures, and Mobile overflow
 */
import { chromium } from 'playwright';

const CONSOLE_ERRORS = [];
const NETWORK_ERRORS = [];
let MOBILE_OVERFLOW = false;

async function verify() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 375, height: 812 } // iPhone X mobile viewport
  });
  const page = await context.newPage();

  // Console error capture
  page.on('console', msg => {
    if (msg.type() === 'error') {
      CONSOLE_ERRORS.push(msg.text());
    }
  });
  page.on('pageerror', err => CONSOLE_ERRORS.push(err.message));

  // Network failure capture
  page.on('requestfailed', req => {
    NETWORK_ERRORS.push({
      url: req.url(),
      failure: req.failure()?.errorText || 'Unknown'
    });
  });

  try {
    // Navigate to local frontend
    await page.goto('http://localhost:60100', { waitUntil: 'networkidle', timeout: 30000 });
    console.log('✅ Page loaded');

    // Wait for Vue app to mount
    await page.waitForSelector('#app', { timeout: 10000 });

    // Check for overflow in mobile view
    const body = await page.$('body');
    const bounding = await body?.boundingBox();
    if (bounding && bounding.width > 375) {
      MOBILE_OVERFLOW = true;
      console.log('⚠️ Mobile overflow detected:', bounding.width, 'px');
    }

    // Check key API endpoints
    const endpoints = [
      '/api/v1/market/overview',
      '/api/v1/admin/data-sources/status',
      '/api/v1/market/sentiment'
    ];

    for (const ep of endpoints) {
      try {
        const res = await page.request.get(`http://localhost:8002${ep}`);
        if (!res.ok()) {
          NETWORK_ERRORS.push({ url: ep, failure: `HTTP ${res.status()}` });
        }
      } catch (e) {
        NETWORK_ERRORS.push({ url: ep, failure: e.message });
      }
    }

  } catch (e) {
    CONSOLE_ERRORS.push(e.message);
  }

  await browser.close();

  // Output report
  console.log('\n=== F12 VERIFICATION REPORT ===');
  console.log('Console Errors:', CONSOLE_ERRORS.length);
  CONSOLE_ERRORS.forEach(e => console.log('  -', e.substring(0, 100)));

  console.log('\nNetwork Errors:', NETWORK_ERRORS.length);
  NETWORK_ERRORS.forEach(e => console.log('  -', e.url, '->', e.failure));

  console.log('\nMobile Overflow:', MOBILE_OVERFLOW ? 'YES ⚠️' : 'NO ✅');

  // Exit code based on errors
  const hasErrors = CONSOLE_ERRORS.length > 0 || NETWORK_ERRORS.length > 0 || MOBILE_OVERFLOW;
  process.exit(hasErrors ? 1 : 0);
}

verify().catch(e => {
  console.error('F12 verification failed:', e);
  process.exit(1);
});