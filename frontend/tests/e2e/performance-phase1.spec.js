// @ts-check
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

// Performance metrics storage
const performanceResults = {
  testDate: new Date().toISOString(),
  tests: []
};

/**
 * Helper to record test metrics
 */
function recordTestResult(testName, success, metrics = {}) {
  performanceResults.tests.push({
    name: testName,
    success,
    timestamp: new Date().toISOString(),
    ...metrics
  });
}

/**
 * Helper to save results to JSON
 */
function saveResults() {
  const resultsPath = path.join(__dirname, 'performance-phase1-results.json');
  fs.writeFileSync(resultsPath, JSON.stringify(performanceResults, null, 2));
}

test.describe('Phase 1: Basic Connectivity Tests', () => {
  
  test.afterAll(() => {
    saveResults();
  });

  test('Test 1: Homepage Loads Successfully', async ({ page }) => {
    const startTime = Date.now();
    let success = false;
    let loadTime = 0;
    let statusCode = 0;

    try {
      // Navigate to homepage
      const response = await page.goto('http://localhost:60100', {
        waitUntil: 'networkidle',
        timeout: 30000
      });

      statusCode = response?.status() || 0;
      loadTime = Date.now() - startTime;

      // Verify 200 status
      expect(statusCode).toBe(200);

      // Wait for main content to render (look for main app container)
      await page.waitForSelector('#app', { timeout: 10000 });
      
      // Wait for sidebar or main content
      await page.waitForSelector('nav, main, [data-testid="sidebar"]', { timeout: 10000 });

      success = true;

      recordTestResult('Homepage Loads Successfully', success, {
        loadTimeMs: loadTime,
        statusCode,
        url: 'http://localhost:60100'
      });

    } catch (error) {
      loadTime = Date.now() - startTime;
      
      recordTestResult('Homepage Loads Successfully', false, {
        loadTimeMs: loadTime,
        statusCode,
        error: error.message,
        url: 'http://localhost:60100'
      });

      throw error;
    }

    expect(success).toBe(true);
    expect(loadTime).toBeLessThan(10000); // Should load within 10s
  });

  test('Test 2: Health Endpoint Responds', async ({ page }) => {
    const startTime = Date.now();
    let success = false;
    let responseTime = 0;
    let statusCode = 0;
    let responseTimeHeader = null;

    try {
      // Navigate to health endpoint
      const response = await page.goto('http://localhost:60100/api/v1/health', {
        waitUntil: 'networkidle',
        timeout: 10000
      });

      statusCode = response?.status() || 0;
      responseTime = Date.now() - startTime;

      // Get X-Response-Time header if available
      responseTimeHeader = await response?.headerValue('x-response-time');

      // Verify status code
      expect(statusCode).toBe(200);

      // Verify response body
      const body = await response?.json();
      expect(body).toBeDefined();
      expect(body.status).toBe('healthy');

      success = true;

      recordTestResult('Health Endpoint Responds', success, {
        responseTimeMs: responseTime,
        statusCode,
        responseTimeHeader,
        endpoint: '/api/v1/health'
      });

    } catch (error) {
      responseTime = Date.now() - startTime;
      
      recordTestResult('Health Endpoint Responds', false, {
        responseTimeMs: responseTime,
        statusCode,
        error: error.message,
        endpoint: '/api/v1/health'
      });

      throw error;
    }

    expect(success).toBe(true);
    expect(responseTime).toBeLessThan(5000); // Should respond within 5s
  });

  test('Test 3: Market Overview API Responds', async ({ page }) => {
    const startTime = Date.now();
    let success = false;
    let responseTime = 0;
    let statusCode = 0;
    let responseTimeHeader = null;
    let dataKeys = [];

    try {
      // Navigate to market overview endpoint
      const response = await page.goto('http://localhost:60100/api/v1/market/overview', {
        waitUntil: 'networkidle',
        timeout: 15000
      });

      statusCode = response?.status() || 0;
      responseTime = Date.now() - startTime;

      // Get X-Response-Time header if available
      responseTimeHeader = await response?.headerValue('x-response-time');

      // Verify status code
      expect(statusCode).toBe(200);

      // Verify response body has valid data
      const body = await response?.json();
      expect(body).toBeDefined();
      expect(body.code).toBe(0);
      expect(body.data).toBeDefined();

      // Check for expected data keys
      dataKeys = Object.keys(body.data);
      expect(dataKeys.length).toBeGreaterThan(0);

      success = true;

      recordTestResult('Market Overview API Responds', success, {
        responseTimeMs: responseTime,
        statusCode,
        responseTimeHeader,
        dataKeysCount: dataKeys.length,
        endpoint: '/api/v1/market/overview'
      });

    } catch (error) {
      responseTime = Date.now() - startTime;
      
      recordTestResult('Market Overview API Responds', false, {
        responseTimeMs: responseTime,
        statusCode,
        error: error.message,
        endpoint: '/api/v1/market/overview'
      });

      throw error;
    }

    expect(success).toBe(true);
    expect(responseTime).toBeLessThan(10000); // Should respond within 10s
  });

  test('Test 4: WebSocket Endpoint Accessible', async ({ page }) => {
    const startTime = Date.now();
    let success = false;
    let connectionTime = 0;

    try {
      // Navigate to a blank page first
      await page.goto('about:blank');

      // Execute WebSocket connection test in browser context
      const result = await page.evaluate(() => {
        return new Promise((resolve) => {
          const startTime = Date.now();
          const ws = new WebSocket('ws://localhost:8002/ws/market');
          
          ws.onopen = () => {
            const connectionTime = Date.now() - startTime;
            ws.close();
            resolve({ 
              success: true, 
              connectionTimeMs: connectionTime,
              url: 'ws://localhost:8002/ws/market'
            });
          };
          
          ws.onerror = (event) => {
            resolve({ 
              success: false, 
              error: 'WebSocket connection failed',
              url: 'ws://localhost:8002/ws/market'
            });
          };
          
          // Timeout after 5 seconds
          setTimeout(() => {
            ws.close();
            resolve({ 
              success: false, 
              error: 'Connection timeout after 5s',
              url: 'ws://localhost:8002/ws/market'
            });
          }, 5000);
        });
      });

      connectionTime = Date.now() - startTime;
      success = result.success;

      recordTestResult('WebSocket Endpoint Accessible', success, {
        connectionTimeMs: result.connectionTimeMs || connectionTime,
        wsUrl: 'ws://localhost:8002/ws/market',
        error: result.error || null
      });

      expect(result.success).toBe(true);
      expect(result.connectionTimeMs || connectionTime).toBeLessThan(5000);

    } catch (error) {
      connectionTime = Date.now() - startTime;
      
      recordTestResult('WebSocket Endpoint Accessible', false, {
        connectionTimeMs: connectionTime,
        wsUrl: 'ws://localhost:8002/ws/market',
        error: error.message
      });

      throw error;
    }

    expect(success).toBe(true);
  });
});
