/**
 * true_f12_sniffer.js — 真正的 F12 嗅探器
 * 
 * 目标：捕获所有静默错误，验证 ECharts 真实渲染状态
 * 
 * 拦截三种错误源：
 * 1. page.on('pageerror') — 未捕获的 JS 异常
 * 2. 注入 Vue app.config.errorHandler — Vue 全局错误
 * 3. 注入 window.onerror + window.onunhandledrejection — 全局错误
 * 4. 检查 ECharts 实例状态（不是 DOM 尺寸！）
 * 5. 强制截图验证视觉状态
 */
const { chromium } = require('playwright');

const FRONTEND = 'http://localhost:60100';

const log = (tag, msg) => console.log(`[${new Date().toISOString().slice(11,23)}] ${tag} ${msg}`);

(async () => {
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });
  require('fs').mkdirSync('/tmp/ui_test', { recursive: true });

  const ctx  = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await ctx.newPage();

  // ── 错误收集器 ────────────────────────────────────────────────────
  const pageErrors = [];
  const consoleErrors = [];
  const vueErrors = [];
  const networkErrors = [];

  page.on('pageerror', err => {
    const entry = { type: 'pageerror', message: err.message, stack: err.stack?.slice(0, 500) };
    pageErrors.push(entry);
    log('🔴', `pageerror: ${err.message}`);
  });

  page.on('console', msg => {
    const txt = msg.text();
    if (msg.type() === 'error') {
      consoleErrors.push({ type: 'console.error', text: txt.slice(0, 500) });
      log('🔴', `console.error: ${txt.slice(0, 200)}`);
    }
    if (msg.type() === 'warning') {
      log('🟡', `console.warn: ${txt.slice(0, 200)}`);
    }
  });

  page.on('response', resp => {
    if (!resp.ok()) {
      networkErrors.push({ url: resp.url(), status: resp.status() });
      log('🔴', `HTTP ${resp.status()}: ${resp.url().slice(0, 100)}`);
    }
  });

  // ── 1. 加载页面 ───────────────────────────────────────────────────
  log('▶', `加载 ${FRONTEND}`);
  await page.goto(FRONTEND, { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(3000);

  // ── 2. 注入 Vue 全局错误拦截器（在导航前注入，确保覆盖所有后续操作）───
  log('→', '注入 Vue errorHandler + window.onerror');
  await page.evaluateOnNewDocument(() => {
    // 全局错误拦截
    window.__f12_errors = [];
    
    const origOnError = window.onerror;
    window.onerror = function(msg, url, line, col, err) {
      window.__f12_errors.push({ type: 'window.onerror', message: msg, url, line, col, stack: err?.stack?.slice(0, 300) });
      return origOnError ? origOnError.apply(this, arguments) : false;
    };
    
    const origOnRejection = window.onunhandledrejection;
    window.onunhandledrejection = function(e) {
      window.__f12_errors.push({ type: 'unhandledrejection', message: e.reason?.message || String(e.reason), stack: e.reason?.stack?.slice(0, 300) });
      return origOnRejection ? origOnRejection.apply(this, arguments) : false;
    };
  });

  // ── 2b. 页面加载后注入 Vue errorHandler ──────────────────────────
  log('→', '注入 Vue errorHandler');
  await page.evaluate(() => {
    // 等待 Vue app 可用（轮询检查）
    const injectVueHandler = () => {
      const appEl = document.querySelector('#app');
      const vueApp = appEl?.__vue_app__;
      if (vueApp) {
        const origErrorHandler = vueApp.config.errorHandler;
        vueApp.config.errorHandler = function(err, vm, info) {
          window.__f12_errors.push({ 
            type: 'Vue.errorHandler', 
            message: err?.message || String(err), 
            stack: err?.stack?.slice(0, 500),
            component: vm?.$options?.name || 'unknown',
            info
          });
          console.error('[Vue.errorHandler]', err?.message, 'in', vm?.$options?.name, info);
          if (origErrorHandler) origErrorHandler(err, vm, info);
        };
        console.log('[F12] Vue errorHandler injected, version:', vueApp.version);
        return true;
      }
      return false;
    };
    
    if (!injectVueHandler()) {
      // 如果立即注入失败，等待 DOM 变化后重试
      const observer = new MutationObserver(() => {
        if (injectVueHandler()) {
          observer.disconnect();
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
      // 5秒后停止观察
      setTimeout(() => observer.disconnect(), 5000);
    }
  });
  log('→', '点击 💰 投资组合');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const target = btns.find(b => b.innerText.includes('💰') && b.innerText.includes('投资组合'));
    if (target) {
      target.click();
      console.log('[F12] portfolio button clicked');
    } else {
      console.log('[F12] portfolio button NOT FOUND');
    }
  });
  await page.waitForTimeout(5000);

  // ── 4. 截图验证视觉状态 ───────────────────────────────────────────
  log('📸', '截图: /tmp/ui_test/debug_real_ui.png');
  await page.screenshot({ path: '/tmp/ui_test/debug_real_ui.png', fullPage: true });

  // ── 5. 深度诊断：ECharts 实例状态 ────────────────────────────────
  log('🔍', '诊断 ECharts 实例状态');
  const echartsState = await page.evaluate(() => {
    const ec = document.querySelector('.echart-container');
    const ppc = document.querySelector('.position-pie-chart');
    
    // 检查 window.echarts 是否存在
    const echartsGlobal = typeof window.echarts !== 'undefined' ? {
      exists: true,
      version: window.echarts?.version,
      initType: typeof window.echarts?.init,
    } : { exists: false };
    
    // 尝试获取 ECharts 实例（通过 DOM 属性）
    let chartInstance = null;
    if (ec && window.echarts) {
      chartInstance = window.echarts.getInstanceByDom(ec);
    }
    
    // 检查 canvas 实际绘制内容
    const canvas = ec?.querySelector('canvas');
    let canvasInfo = null;
    if (canvas) {
      const ctx = canvas.getContext('2d');
      const imageData = ctx?.getImageData(0, 0, canvas.width, canvas.height);
      const pixelSum = imageData ? imageData.data.reduce((a, b) => a + b, 0) : 0;
      canvasInfo = {
        width: canvas.width,
        height: canvas.height,
        pixelSum,  // 如果 > 0 说明有实际像素绘制
        hasContent: pixelSum > 0,
      };
    }
    
    return {
      echartContainerExists: !!ec,
      echartContainerHTML: ec?.innerHTML?.slice(0, 200),
      echartContainerChildren: ec?.children?.length,
      positionPieChartExists: !!ppc,
      positionPieChartHTML: ppc?.innerHTML?.slice(0, 300),
      echartsGlobal,
      chartInstanceExists: !!chartInstance,
      chartInstanceType: chartInstance ? typeof chartInstance : 'none',
      canvasInfo,
      legendItems: document.querySelectorAll('.legend-item').length,
      pnlCards: document.querySelectorAll('.pnl-card').length,
    };
  });
  console.log('=== ECharts 诊断 ===');
  console.log(JSON.stringify(echartsState, null, 2));

  // ── 6. 收集所有错误 ──────────────────────────────────────────────
  log('📋', '收集全局错误');
  const globalErrors = await page.evaluate(() => window.__f12_errors || []);
  
  console.log('\n╔══════════════════════════════════════════════════════════════╗');
  console.log('║           TRUE F12 嗅探器报告                               ║');
  console.log('╠══════════════════════════════════════════════════════════════╣');
  console.log(`║  pageerror 数量:     ${pageErrors.length}`);
  console.log(`║  console.error 数量: ${consoleErrors.length}`);
  console.log(`║  Vue errorHandler:   ${vueErrors.length}`);
  console.log(`║  network error 数量: ${networkErrors.length}`);
  console.log(`║  全局错误数量:       ${globalErrors.length}`);
  console.log('╠══════════════════════════════════════════════════════════════╣');
  
  if (pageErrors.length > 0) {
    console.log('║  [pageerror]');
    pageErrors.forEach(e => console.log(`║    🔴 ${e.message.slice(0, 80)}`));
  }
  if (consoleErrors.length > 0) {
    console.log('║  [console.error]');
    consoleErrors.forEach(e => console.log(`║    🔴 ${e.text.slice(0, 80)}`));
  }
  if (globalErrors.length > 0) {
    console.log('║  [全局错误]');
    globalErrors.forEach(e => console.log(`║    🔴 [${e.type}] ${(e.message || '').slice(0, 80)}`));
  }
  if (networkErrors.length > 0) {
    console.log('║  [network error]');
    networkErrors.forEach(e => console.log(`║    🔴 HTTP ${e.status}: ${e.url.slice(0, 80)}`));
  }
  
  // 检查 PnL 卡片实际文本
  const pnlText = await page.evaluate(() => {
    const cards = document.querySelectorAll('.pnl-card');
    return Array.from(cards).map(c => ({
      label: c.querySelector('.pnl-card-label')?.innerText?.trim(),
      value: c.querySelector('.pnl-card-value')?.innerText?.trim(),
    }));
  });
  console.log('╠══════════════════════════════════════════════════════════════╣');
  console.log('║  PnL 卡片实际内容:');
  pnlText.forEach(c => console.log(`║    ${c.label}: ${c.value}`));
  
  // 检查是否有 NaN
  const hasNaN = pnlText.some(c => c.value?.includes('NaN') || c.value?.includes('undefined'));
  console.log('╠══════════════════════════════════════════════════════════════╣');
  console.log(`║  发现 NaN/异常: ${hasNaN ? '❌ 是' : '✅ 否'}`);
  console.log(`║  Canvas 绘制验证: ${echartsState.canvasInfo?.hasContent ? '✅ 有实际像素' : '❌ 空白/无 Canvas'}`);
  console.log('╚══════════════════════════════════════════════════════════════╝');

  await ctx.close();
  await browser.close();
  process.exit(hasNaN || pageErrors.length > 0 || !echartsState.canvasInfo?.hasContent ? 1 : 0);
})();