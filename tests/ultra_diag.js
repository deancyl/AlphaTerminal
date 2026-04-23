/**
 * ultra_diag.js — 无依赖自包含诊断脚本
 * 
 * 目标: 在一次 page.goto 中完成所有诊断，不依赖任何前端模块
 * 
 * 诊断项:
 * 1. 页面加载后检查 sidebar 按钮的准确文本和 boundingBox
 * 2. 点击后检查 PortfolioDashboard 是否挂载
 * 3. 检查 PositionPieChart 挂载情况
 * 4. 检查 Playwright page.locator vs document.querySelector 差异
 * 5. 强制重新渲染后再次检测
 */
const { chromium } = require('playwright');
const FRONTEND = 'http://localhost:60100';

(async () => {
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });
  require('fs').mkdirSync('/tmp/ui_test', { recursive: true });

  const ctx  = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await ctx.newPage();

  const allLogs = [];
  const apiCalls = [];
  page.on('console', msg => allLogs.push(`[${msg.type()}] ${msg.text().slice(0,200)}`));
  page.on('response', r => {
    const p = r.url().replace(FRONTEND, '');
    if (p.includes('/portfolio')) apiCalls.push(`${p}→HTTP${r.status()}`);
  });

  // ── 1. 加载页面 ─────────────────────────────────────────────────────
  await page.goto(FRONTEND, { waitUntil: 'networkidle', timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(3000);

  // ── 2. 精确检查 sidebar 按钮状态 ─────────────────────────────────
  const sidebarState = await page.evaluate(() => {
    const allBtns = Array.from(document.querySelectorAll('button'));
    const portfolioBtns = allBtns.filter(b =>
      b.innerText.includes('💰') && b.innerText.includes('投资组合')
    );
    return {
      totalButtons: allBtns.length,
      portfolioBtnCount: portfolioBtns.length,
      portfolioBtnTexts: portfolioBtns.map(b => JSON.stringify(b.innerText.trim())),
      portfolioBtnBoxes: portfolioBtns.map(b => {
        const r = b.getBoundingClientRect();
        return { top: r.top, left: r.left, width: r.width, height: r.height, visible: r.width > 0 && r.height > 0 };
      }),
      bodyText: document.body.innerText.slice(0, 300),
    };
  });
  console.log('=== [Step1] Sidebar State ===');
  console.log(JSON.stringify(sidebarState, null, 2));
  await page.screenshot({ path: '/tmp/ui_test/01_after_load.png' }).catch(() => {});

  // ── 3. 点击投资组合 ────────────────────────────────────────────────
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const target = btns.find(b => b.innerText.includes('💰') && b.innerText.includes('投资组合'));
    if (target) { target.click(); console.log('[DEBUG] click succeeded'); }
    else console.log('[DEBUG] no target found');
  });
  console.log('[Step3] clicked portfolio button');
  await page.waitForTimeout(5000);
  await page.screenshot({ path: '/tmp/ui_test/03_after_nav.png' }).catch(() => {});

  // ── 4. 导航后 DOM 深度分析 ─────────────────────────────────────────
  const navState = await page.evaluate(() => {
    const mainEl = document.querySelector('main');
    const bodyText = document.body.innerText;
    
    // 查找所有可能相关的元素
    const allDivs = Array.from(document.querySelectorAll('div'));
    const pieDivs = allDivs.filter(d => d.className && d.className.includes('pie'));
    const chartDivs = allDivs.filter(d => d.className && d.className.includes('chart'));
    const echartDivs = allDivs.filter(d => d.className && d.className.includes('echart'));
    
    // Playwright-style locators (CSS selectors)
    const pwEchart = document.querySelector('.echart-container');
    const pwPnLCard = document.querySelector('.pnl-card');
    const pwLotsTable = document.querySelector('.lots-table');
    const pwLegendItem = document.querySelector('.legend-item');
    
    // getBoundingClientRect for all key elements
    const rects = {
      echart: pwEchart ? JSON.stringify(pwEchart.getBoundingClientRect()) : 'null',
      pieChart: document.querySelector('.position-pie-chart') ? 
        JSON.stringify(document.querySelector('.position-pie-chart').getBoundingClientRect()) : 'null',
    };
    
    // CSS computed styles for .echart-container
    const cs = pwEchart ? window.getComputedStyle(pwEchart) : null;
    const computedStyle = cs ? {
      display: cs.display, visibility: cs.visibility, opacity: cs.opacity,
      width: cs.width, height: cs.height,
      position: cs.position, overflow: cs.overflow,
    } : null;
    
    return {
      mainExists: !!mainEl,
      mainText: mainEl?.innerText?.slice(0, 200)?.replace(/\n/g, ' '),
      bodyHasPortfolio: bodyText.includes('投资组合'),
      bodyHasCashBalance: bodyText.includes('现金余额'),
      bodyHas模拟调仓: bodyText.includes('模拟调仓'),
      echartFound: !!pwEchart,
      echartClass: pwEchart?.className,
      echartRect: rects.echart,
      pieChartClass: document.querySelector('.position-pie-chart')?.className,
      pieChartRect: rects.pieChart,
      pnlCardFound: !!pwPnLCard,
      lotsTableFound: !!pwLotsTable,
      legendItemFound: !!pwLegendItem,
      canvasCount: document.querySelectorAll('canvas').length,
      computedStyle,
      pieDivsCount: pieDivs.length,
      chartDivsCount: chartDivs.length,
      echartDivsCount: echartDivs.length,
      echartDivClasses: echartDivs.map(d => d.className),
    };
  });
  console.log('=== [Step4] Post-Nav DOM State ===');
  console.log(JSON.stringify(navState, null, 2));
  console.log('\n=== API Calls (portfolio) ===');
  apiCalls.forEach(a => console.log(a));

  // ── 5. 如果 echart-container 不存在，强制切换 App.vue 的 currentView ──
  if (!navState.echartFound) {
    console.log('\n=== [Step5] Force currentView=portfolio ===');
    const forceResult = await page.evaluate(() => {
      // Try to find App's view state via Vue internals
      const appEl = document.querySelector('#app');
      const vueApp = appEl?.__vue_app__;
      
      // Access Vue's reactive root component
      let currentView = 'unknown';
      if (vueApp?._instance) {
        const root = vueApp._instance;
        // Try to find currentView in the component's data
        // In Vue 3, root.data is the reactive state
        currentView = root.data?.currentView || root.setupState?.currentView || 'cannot read';
      }
      
      // Try to find the component via exposed instance
      const exposed = root?.exposed;
      
      return { currentView, hasVueApp: !!vueApp, vueVersion: vueApp?.version, exposedKeys: Object.keys(exposed || {}) };
    });
    console.log('Vue state:', JSON.stringify(forceResult));
    
    // Try dispatching a click event with dispatchEvent (more reliable than click())
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const target = btns.find(b => b.innerText.includes('💰') && b.innerText.includes('投资组合'));
      if (target) {
        target.dispatchEvent(new MouseEvent('click', { view: window, bubbles: true, cancelable: true }));
        console.log('[FORCE] dispatchEvent click sent');
      }
    });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: '/tmp/ui_test/05_after_force.png' }).catch(() => {});
    
    // Check again
    const afterForce = await page.evaluate(() => ({
      bodyHasPortfolio: document.body.innerText.includes('投资组合'),
      bodyHasCashBalance: document.body.innerText.includes('现金余额'),
      echartFound: !!document.querySelector('.echart-container'),
    }));
    console.log('After force click:', JSON.stringify(afterForce));
  }

  // ── 6. 如果 echart-container 存在但 canvas = 0，手动 ECharts init ──
  const echartEl = await page.evaluate(() => !!document.querySelector('.echart-container'));
  if (echartEl) {
    console.log('\n=== [Step6] Manual ECharts init test ===');
    await page.evaluate(async () => {
      const ec = document.querySelector('.echart-container');
      
      // Dynamic import echarts
      let Echarts;
      try {
        // Check if Vite pre-bundled echarts is available
        const mod = await import('/node_modules/.vite/deps/echarts.js');
        Echarts = mod;
      } catch(e1) {
        // Try CDN as fallback
        console.log('[MANUAL] Vite echarts import failed:', e1.message.slice(0, 100));
        try {
          await new Promise((resolve, reject) => {
            const s = document.createElement('script');
            s.src = 'https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js';
            s.onload = resolve; s.onerror = reject;
            document.head.appendChild(s);
          });
          Echarts = window.echarts;
          console.log('[MANUAL] CDN echarts loaded');
        } catch(e2) {
          console.log('[MANUAL] CDN failed:', e2.message);
          return;
        }
      }
      
      if (Echarts) {
        const chart = Echarts.init(ec, null, { renderer: 'canvas' });
        chart.setOption({
          backgroundColor: 'transparent',
          series: [{
            type: 'pie', radius: ['35%', '65%'],
            data: [
              { name: '测试持仓A', value: 50000, itemStyle: { color: '#7dd3fc' } },
              { name: '测试持仓B', value: 30000, itemStyle: { color: '#34d399' } },
            ],
          }],
        });
        console.log('[MANUAL] ECharts init done, canvas count:', document.querySelectorAll('canvas').length);
      }
    });
    await page.waitForTimeout(2000);
  }

  // ── Final DOM state ──────────────────────────────────────────────
  const final = await page.evaluate(() => ({
    canvas: document.querySelectorAll('canvas').length,
    echart: document.querySelector('.echart-container')?.getBoundingClientRect(),
    pnlCard: document.querySelector('.pnl-card')?.getBoundingClientRect(),
    legend: document.querySelectorAll('.legend-item').length,
  }));
  console.log('\n=== [Final] DOM State ===');
  console.log(JSON.stringify(final, null, 2));
  console.log('\n=== Warning Logs (last 20) ===');
  allLogs.filter(l => l.startsWith('[warning]')).slice(-20).forEach(l => console.log(l));

  await page.screenshot({ path: '/tmp/ui_test/final.png' }).catch(() => {});
  await ctx.close();
  await browser.close();
  process.exit(0);
})();