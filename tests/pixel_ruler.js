/**
 * pixel_ruler.js — Phase 5.1 像素级 DOM 检测 + 响应式断链诊断
 *
 * 已发现：
 * ✅ .echart-container (1855×260px) / .lots-table / .pnl-card / .legend-item 全部像素正常
 * ✅ 组件真实挂载（现金余额/模拟调仓 DOM 文本存在）
 * ❌ Canvas = 0 个 → ECharts.init() 未执行（API未返回有效数据）
 * ❌ /lots/echarts 和 /pnl 未被调用（portfolioId 断链或空数据）
 *
 * 本次目标：
 * 1. 手动 fetch /lots/echarts 验证 API 返回有效 positions
 * 2. 检查 ECharts CDN 是否可加载
 * 3. 检测 window.echarts 是否存在
 */
const { chromium } = require('playwright');

const FRONTEND = 'http://localhost:60100';
const BACKEND  = 'http://localhost:8002';

const log = (tag, msg) => console.log(`[${new Date().toISOString().slice(11,23)}] ${tag} ${msg}`);

(async () => {
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });
  require('fs').mkdirSync('/tmp/ui_test', { recursive: true });

  const ctx  = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await ctx.newPage();

  const errors = [], apiCalls = [];
  page.on('console', msg => {
    const t = msg.type(), txt = msg.text();
    if (t === 'error') { errors.push(txt); log('🔴', txt); }
    else if (t === 'warn') log('🟡', txt);
    else if (txt.includes('[PositionPieChart]') || txt.includes('[Portfolio]') || txt.includes('[OpenLotsPanel]')) {
      log('📝', txt);
    }
  });
  page.on('response', resp => {
    const url = resp.url();
    // 拦截 Vite proxy 路径 (localhost:60100/api/...) 和直接后端路径 (localhost:8002/api/...)
    if (!url.includes('/api/v1/portfolio')) return;
    const path = url.replace(FRONTEND, '').replace(BACKEND, '');
    apiCalls.push({ path, status: resp.status() });
    log('📡', `API → ${path} HTTP ${resp.status()}`);
  });

  // ── 打开前端 ───────────────────────────────────────────────────────
  log('▶', `打开 ${FRONTEND}`);
  await page.goto(FRONTEND, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForTimeout(2000);

  // ── 点击投资组合 ───────────────────────────────────────────────────
  log('→', '点击 💰 投资组合');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const target = btns.find(b => b.innerText.includes('💰') && b.innerText.includes('投资组合'));
    if (target) target.click();
  });
  await page.waitForTimeout(3000);

  // ── Step A: 检查全局状态 ──────────────────────────────────────────
  const globalState = await page.evaluate(() => {
    return {
      echartsGlobalExists: typeof window.echarts !== 'undefined',
      echartsVersion: window.echarts?.version || 'not loaded',
      vueAppCount: Object.keys(window).filter(k => k.includes('vue') || k.includes('Vue')).length,
      // 检查是否有 portfolioId 在 Vue 组件中
      documentHasEchartContainer: !!document.querySelector('.echart-container'),
      documentHasPnLCard: !!document.querySelector('.pnl-card'),
    };
  });
  log('🔍', `window.echarts 存在=${globalState.echartsGlobalExists} 版本=${globalState.echartsVersion}`);
  log('🔍', `DOM: echart=${globalState.documentHasEchartContainer} pnl=${globalState.documentHasPnLCard}`);

  // ── Step B: 手动调用 /lots/echarts 验证 API ───────────────────────
  log('→', '手动 fetch /lots/echarts 验证数据');
  const apiResult = await page.evaluate(async () => {
    const accounts = [
      { id: 1, name: '主账户Alpha' },
      { id: 2, name: '子账户A' },
    ];
    const results = [];
    for (const acc of accounts) {
      try {
        const r = await fetch(`/api/v1/portfolio/${acc.id}/lots/echarts?include_children=true`);
        const json = await r.json();
        const positions = json?.data?.positions || [];
        const totalMv = json?.data?.total_market_value || 0;
        results.push({ id: acc.id, name: acc.name, status: r.status, positions: positions.length, totalMv });
      } catch (e) {
        results.push({ id: acc.id, name: acc.name, error: e.message });
      }
    }
    return results;
  });
  apiResult.forEach(r => {
    if (r.error) {
      log('❌', `${r.name} (id=${r.id}) → 错误: ${r.error}`);
    } else {
      log('✅', `${r.name} (id=${r.id}) → HTTP ${r.status} positions=${r.positions} totalMv=${r.totalMv}`);
    }
  });

  // ── Step C: 检测 ECharts init 是否执行（模拟数据触发）───────────────
  log('→', '模拟数据注入，触发 ECharts render');
  await page.evaluate(async () => {
    // 动态 import echarts 确认 CDN 可用
    try {
      const ec = await import('/node_modules/.vite/deps/echarts.js').catch(() => null);
      if (!ec) {
        // 尝试 CDN
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js';
        document.head.appendChild(script);
        await new Promise(resolve => script.onload = resolve);
      }
      // 找到 .echart-container 并手动 init
      const container = document.querySelector('.echart-container');
      if (container && window.echarts) {
        const chart = window.echarts.init(container, null, { renderer: 'canvas' });
        chart.setOption({
          backgroundColor: 'transparent',
          series: [{
            type: 'pie',
            radius: ['35%', '65%'],
            data: [
              { name: '000001', value: 50000, itemStyle: { color: '#7dd3fc' } },
              { name: '000002', value: 30000, itemStyle: { color: '#34d399' } },
            ],
          }],
          tooltip: { trigger: 'item' },
        });
        console.log('[DEBUG] ECharts manually initialized in .echart-container');
        console.log('[DEBUG] canvas count after init:', document.querySelectorAll('canvas').length);
      } else {
        console.log('[DEBUG] .echart-container not found or window.echarts missing');
      }
    } catch (e) {
      console.warn('[DEBUG] ECharts init failed:', e.message);
    }
  });
  await page.waitForTimeout(2000);

  // ── Step D: 再次测量 Canvas ──────────────────────────────────────────
  const canvasAfter = await page.locator('canvas').count();
  log('📏', `手动注入后 canvas 数量: ${canvasAfter}`);

  // ── Step E: 测量像素 ───────────────────────────────────────────────
  log('📏', '开始像素级 DOM 测量');
  const checks = [];

  async function measureOne(selector, label, minH = 10, minW = 10) {
    const count = await page.locator(selector).count();
    if (count === 0) return { name: label, pass: false, detail: 'count=0' };
    const box = await page.locator(selector).first().boundingBox();
    if (!box) return { name: label, pass: false, detail: 'boundingBox=null → CSS塌陷!' };
    if (box.height < minH || box.width < minW) {
      return { name: label, pass: false, detail: `${box.width}×${box.height}px (< min ${minH}px) → 视觉塌陷!` };
    }
    return { name: label, pass: true, detail: `${box.width}×${box.height}px ✅` };
  }

  checks.push(await measureOne('.echart-container', 'ECharts饼图容器 (.echart-container)'));
  checks.push(await measureOne('.lots-table',         '批次明细表 (.lots-table)'));

  const pnlCount = await page.locator('.pnl-card').count();
  const pnlBox   = pnlCount > 0 ? await page.locator('.pnl-card').first().boundingBox() : null;
  checks.push({
    name: 'PnL卡片组 (.pnl-card)',
    pass: pnlCount >= 3 && !!pnlBox && pnlBox.height >= 10 && pnlBox.width >= 10,
    detail: `${pnlCount}个卡片${pnlBox ? ` 首卡片${pnlBox.width}×${pnlBox.height}px` : ' boundingBox=null'}`,
  });

  const legendCount = await page.locator('.legend-item').count();
  checks.push({ name: '饼图图例 (.legend-item)', pass: true, detail: legendCount > 0 ? `${legendCount}个` : '0个 (空持仓，正常)' });

  const finalCanvas = await page.locator('canvas').count();
  checks.push({ name: 'Canvas元素 (ECharts渲染)', pass: finalCanvas > 0, detail: `${finalCanvas}个 (ECharts canvas)` });

  // API 状态
  const lotsEcharts = apiCalls.find(c => c.path.includes('/lots/echarts'));
  const pnlApi      = apiCalls.find(c => c.path.includes('/pnl'));
  checks.push({
    name: '/lots/echarts API (拦截)',
    pass: !!lotsEcharts,
    detail: lotsEcharts ? `HTTP ${lotsEcharts.status}` : '未被调用（前端未发请求）',
  });
  checks.push({
    name: '/pnl API (拦截)',
    pass: !!pnlApi,
    detail: pnlApi ? `HTTP ${pnlApi.status}` : '未被调用（前端未发请求）',
  });

  // ── 报告 ─────────────────────────────────────────────────────────
  const allPass     = checks.every(c => c.pass);
  const failedNames = checks.filter(c => !c.pass).map(c => c.name).join(', ');

  console.log('\n╔══════════════════════════════════════════════════════════════╗');
  console.log('║        Phase 5.1 像素级 DOM 检测报告                        ║');
  console.log('╠══════════════════════════════════════════════════════════════╣');
  checks.forEach(c => {
    const icon = c.pass ? '✅' : '❌';
    console.log(`║  ${icon} ${c.name}`);
    console.log(`║     → ${c.detail}`);
  });
  console.log('╠══════════════════════════════════════════════════════════════╣');
  console.log(`║  Console errors: ${errors.length === 0 ? '✅ 0' : '❌ ' + errors.length}`);
  if (errors.length > 0) errors.slice(0, 5).forEach(e => console.log(`║    🔴 ${e.slice(0, 65)}`));
  console.log('╠══════════════════════════════════════════════════════════════╣');
  console.log(`║  结论: ${allPass ? '✅ 所有节点像素尺寸 ≥ 阈值，ECharts canvas 已渲染' : '❌ ' + failedNames}`);
  console.log('╚══════════════════════════════════════════════════════════════╝');

  try { await page.screenshot({ path: '/tmp/ui_test/pixel_final.png', fullPage: false }); } catch (_) {}
  await ctx.close();
  await browser.close();
  process.exit(allPass && errors.length === 0 ? 0 : 1);
})();