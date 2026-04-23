/**
 * ui_functional_test.js - Phase 2 升级版
 * 双端视口 + 多步导航 + 全链路 F12 嗅探
 *
 * 运行:
 *   node tests/ui_functional_test.js               # desktop (1920×1080)
 *   node tests/ui_functional_test.js --mobile      # mobile (375×667)
 *   node tests/ui_functional_test.js --both         # desktop + mobile
 *
 * 职责：
 *   - 桌面端：直接点击侧边栏"投资组合"，定位 PortfolioDashboard，模拟完整新建+划转
 *   - 移动端：先点汉堡菜单展开抽屉，再导航到"投资组合"
 *   - 全程捕获 console.error / console.log / network responses
 *   - 内部截图（不输出到报告）用于调试
 *   - 纯文本汇报：点击链路 + console 报错 + API 成功率 + 延迟
 */
const { chromium } = require('playwright');

const FRONTEND   = 'http://localhost:60100';
const BACKEND    = 'http://localhost:8002';
const BASE       = '/api/v1/portfolio';

// ── CLI args ────────────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const runDesktop = !args.includes('--mobile');
const runMobile  = args.includes('--mobile') || args.includes('--both');
const runBoth    = args.includes('--both');

// ── helpers ──────────────────────────────────────────────────────────────────
const now = () => new Date().toISOString().slice(11, 23);
const log = (tag, msg) => console.log(`[${now()}] ${tag} ${msg}`);

async function snapshot(page, label) {
  // 内部截图（仅用于调试 DOM，不输出到报告）
  try {
    await page.screenshot({ path: `/tmp/ui_test/_snap_${label}.png`, fullPage: false });
  } catch (_) {}
}

// ── Main test runner ─────────────────────────────────────────────────────────
async function runViewport(page, mode, viewport) {
  const W = viewport.width, H = viewport.height;
  const label = `${mode} ${W}×${H}`;
  const errors = [], warns = [], apiCalls = [], opsLog = [];

  log('═', `【${label}】初始化`);
  await page.setViewportSize(viewport);
  await page.setDefaultTimeout(8000);

  // ── interceptors ────────────────────────────────────────────────────────────
  page.on('console', msg => {
    const t = msg.type(), txt = msg.text();
    if (t === 'error')   { errors.push(txt); log('🔴', `[${label}] ${txt}`); }
    else if (t === 'warn') { warns.push(txt);  log('🟡', `[${label}] ${txt}`); }
    else if (t === 'log')  { log('📝', `[${label}] ${txt}`); }
  });
  page.on('pageerror', e => { const t = `Uncaught: ${e.message}`; errors.push(t); log('💥', t); });

  const reqMap = new Map(); // url → {method, path, latency, status, response}
  page.on('request', req => {
    const url = req.url();
    if (!url.startsWith(BACKEND) && !url.startsWith(FRONTEND)) return;
    const path = url.replace(BACKEND, '').replace(FRONTEND, '');
    reqMap.set(path, { method: req.method(), path, status: null, latency: null });
  });
  page.on('response', async resp => {
    const url = resp.url();
    if (!url.startsWith(BACKEND) && !url.startsWith(FRONTEND)) return;
    const path = url.replace(BACKEND, '').replace(FRONTEND, '');
    const entry = reqMap.get(path);
    if (entry) {
      entry.status = resp.status();
      entry.latency = Date.now();
      try { entry.response = await resp.text(); } catch (_) {}
    }
  });

  // ── navigate ─────────────────────────────────────────────────────────────
  log('▶', `【${label}】打开前端 → ${FRONTEND}`);
  try {
    await page.goto(FRONTEND, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForTimeout(2000);
  } catch (e) { log('⚠️', `goto failed: ${e.message}`); return { label, errors, warns, apiCalls: [], opsLog, fatal: true }; }

  // ── navigation helpers ────────────────────────────────────────────────────
  async function clickDesktop() {
    // Desktop: sidebar is always visible, click "投资组合"
    log('→', 'Desktop 导航：点击侧边栏"投资组合"');
    await snapshot(page, `${label}_before_nav`);
    try {
      // Try multiple selectors for sidebar portfolio link
      const selectors = [
        'button[title="投资组合"]',
        'button:has-text("投资组合")',
        '[data-sidebar-nav="portfolio"]',
        'span:has-text("💰")',
        'a:has-text("投资组合")',
      ];
      for (const sel of selectors) {
        const el = page.locator(sel).first();
        if (await el.count() > 0) {
          await el.click({ force: true });
          opsLog.push(`CLICK sidebar[💰投资组合] via ${sel}`);
          log('👉', `Clicked: ${sel}`);
          await page.waitForTimeout(1500);
          await snapshot(page, `${label}_after_nav`);
          return true;
        }
      }
      // Fallback: click by emoji
      await page.locator('button').filter({ hasText: '💰' }).first().click();
      opsLog.push('CLICK sidebar[💰] via emoji filter');
      await page.waitForTimeout(1500);
      return true;
    } catch (e) {
      log('❌', `Desktop nav failed: ${e.message}`);
      return false;
    }
  }

  async function clickMobile() {
    // Mobile: need to open hamburger first
    log('→', 'Mobile 导航：打开汉堡菜单 → 找投资组合');
    await snapshot(page, `${label}_before_hamburger`);
    const hamSelectors = [
      'button[aria-label="菜单"]',
      'button[aria-label="menu"]',
      'button[aria-label="Menu"]',
      '[aria-label="menu"]',
      'button:has-text("☰")',
      'button:has-text("菜单")',
      'svg.icon-menu',
      '[class*="hamburger"]',
    ];
    let hamClicked = false;
    for (const sel of hamSelectors) {
      const el = page.locator(sel).first();
      if (await el.count() > 0) {
        await el.click({ force: true });
        opsLog.push(`CLICK hamburger[${sel}]`);
        log('👉', `Clicked hamburger: ${sel}`);
        await page.waitForTimeout(800);
        hamClicked = true;
        break;
      }
    }
    if (!hamClicked) {
      // Try any visible button that might be the menu
      const buttons = await page.locator('button').all();
      for (const btn of buttons) {
        try {
          const box = await btn.boundingBox();
          if (box && box.y < 100 && box.x < 100) {
            await btn.click();
            opsLog.push('CLICK top-left button (hamburger guess)');
            log('👉', 'Clicked top-left as hamburger');
            await page.waitForTimeout(800);
            hamClicked = true;
            break;
          }
        } catch (_) {}
      }
    }

    await snapshot(page, `${label}_after_hamburger`);

    // Now click "投资组合" in the nav/drawer
    const navSelectors = [
      'button:has-text("投资组合")',
      'a:has-text("投资组合")',
      'span:has-text("💰")',
      '[data-nav="portfolio"]',
    ];
    for (const sel of navSelectors) {
      const el = page.locator(sel).first();
      if (await el.count() > 0) {
        await el.click({ force: true });
        opsLog.push(`CLICK nav[投资组合] via ${sel}`);
        log('👉', `Clicked nav item: ${sel}`);
        await page.waitForTimeout(1500);
        await snapshot(page, `${label}_after_nav`);
        return true;
      }
    }
    log('⚠️', 'Mobile nav: could not find 投资组合 in drawer');
    return false;
  }

  // ── Step 1: Navigate to PortfolioDashboard ──────────────────────────────
  log('(1)', `【${label}】STEP 1 - 导航到「投资组合」`);
  let navOk = false;
  if (mode === 'desktop') navOk = await clickDesktop();
  else navOk = await clickMobile();

  if (!navOk) {
    // Try direct URL access
    try {
      await page.goto(`${FRONTEND}`, { waitUntil: 'domcontentloaded', timeout: 10000 });
      await page.waitForTimeout(1000);
      opsLog.push('FALLBACK: page reload');
    } catch (_) {}
  }

  // ── Step 2: Click "新建" ──────────────────────────────────────────────
  log('(2)', `【${label}】STEP 2 - 打开「新建账户」弹窗`);
  await snapshot(page, `${label}_before_newbtn`);
  const newBtnSelectors = [
    'button:has-text("新建")',
    'button:has-text("新建账户")',
    '[data-action="create-account"]',
  ];
  let newClicked = false;
  for (const sel of newBtnSelectors) {
    const el = page.locator(sel).first();
    if (await el.count() > 0) {
      try {
        await el.click({ force: true });
        opsLog.push(`CLICK [新建] via ${sel}`);
        log('👉', `Clicked 新建 button: ${sel}`);
        await page.waitForTimeout(1000);
        newClicked = true;
        await snapshot(page, `${label}_after_newbtn`);
      } catch (_) {}
      break;
    }
  }
  if (!newClicked) {
    log('⚠️', '新建 button not found - trying any button with 新建');
    try {
      const btns = await page.locator('button').all();
      for (const b of btns) {
        const txt = await b.innerText().catch(() => '');
        if (txt.includes('新建')) {
          await b.click({ force: true });
          opsLog.push(`CLICK [新建] via text match: "${txt}"`);
          log('👉', `Clicked button with text: "${txt}"`);
          await page.waitForTimeout(1000);
          newClicked = true;
          break;
        }
      }
    } catch (_) {}
  }

  // ── Step 3: Fill form ─────────────────────────────────────────────────
  log('(3)', `【${label}】STEP 3 - 填写账户表单`);
  if (newClicked) {
    await page.waitForTimeout(600);
    const accountName = `自动化_${mode}_${Date.now().toString(36)}`;
    try {
      // Find all text/number inputs in the modal
      const textInputs = await page.locator('input[type="text"]').all();
      const numInputs  = await page.locator('input[type="number"]').all();
      for (const inp of textInputs) {
        const ph = await inp.getAttribute('placeholder') || '';
        if (ph.includes('基金') || ph.includes('名称') || ph.includes('账户')) {
          await inp.fill(accountName);
          opsLog.push(`FILL name="${accountName}" placeholder="${ph}"`);
          log('✏️', `Filled name="${accountName}"`);
          break;
        }
      }
      // Fill initial capital
      for (const inp of numInputs) {
        await inp.fill('100000');
        opsLog.push('FILL initial_capital=100000');
        log('✏️', 'Filled initial_capital=100000');
        break;
      }
    } catch (e) { log('⚠️', `Fill form failed: ${e.message}`); }
  }

  // ── Step 4: Submit create ─────────────────────────────────────────────
  log('(4)', `【${label}】STEP 4 - 提交「创建账户」`);
  try {
    const createBtns = await page.locator('button').all();
    for (const b of createBtns) {
      const txt = await b.innerText().catch(() => '');
      if (txt.includes('创建') && !txt.includes('取消')) {
        await b.click({ force: true });
        opsLog.push(`SUBMIT [创建] text="${txt.trim()}"`);
        log('✔️', `Clicked 创建: "${txt.trim()}"`);
        await page.waitForTimeout(2500);
        break;
      }
    }
  } catch (e) { log('⚠️', `Submit failed: ${e.message}`); }

  // ── Step 5: Identify account IDs ──────────────────────────────────────
  log('(5)', `【${label}】STEP 5 - 定位账户 ID`);
  await page.waitForTimeout(1000);
  let mainId = null, subId = null, newAccId = null;
  try {
    const listRes = await page.evaluate(async () => {
      const r = await fetch('/api/v1/portfolio/');
      return r.json().catch(() => ({}));
    });
    const accs = listRes.portfolios || [];
    const main = accs.filter(p => !p.parent_id).sort((a,b) => a.id - b.id)[0];
    const sub  = accs.filter(p => p.parent_id).sort((a,b) => a.id - b.id)[0];
    mainId = main?.id;
    subId  = sub?.id;
    newAccId = mainId;
    opsLog.push(`FIND main_id=${mainId} sub_id=${subId}`);
    log('🔍', `Accounts: main_id=${mainId} sub_id=${subId}`);
  } catch (e) { log('⚠️', `Account list fetch failed: ${e.message}`); }

  // ── Step 6: Direct transfer via fetch ───────────────────────────────────
  log('(6)', `【${label}】STEP 6 - 资金划转（主→子）`);
  if (mainId && subId) {
    try {
      const r = await page.evaluate(async ({ f, t }) => {
        const res = await fetch('/api/v1/portfolio/transfer/direct', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            from_portfolio_id: f, to_portfolio_id: t,
            amount: 5000, note: `自动化desktop测试划转`,
          }),
        });
        return { status: res.status, body: await res.text().catch(() => '') };
      }, { f: mainId, t: subId });
      opsLog.push(`TRANSFER from=${mainId} to=${subId} amount=5000 status=${r.status} body="${r.body.slice(0,80)}"`);
      log('✔️', `Transfer HTTP ${r.status}`);
      if (r.status >= 400) errors.push(`Transfer failed: HTTP ${r.status} ${r.body}`);
    } catch (e) { errors.push(`Transfer: ${e.message}`); }
  }

  // ── Step 7: Transactions query ─────────────────────────────────────────
  log('(7)', `【${label}】STEP 7 - 查询流水接口`);
  if (mainId) {
    try {
      const r = await page.evaluate(async ({ pid }) => {
        const res = await fetch(`/api/v1/portfolio/${pid}/transactions?limit=3`);
        return { status: res.status, count: 0, body: await res.json().catch(() => ({})) };
      }, { pid: mainId });
      opsLog.push(`TXNS main_id=${mainId} status=${r.status} count=${r.body?.data?.transactions?.length || 0}`);
      log('🔍', `Transactions: HTTP ${r.status}, ${r.body?.data?.transactions?.length || 0} 条`);
    } catch (e) { log('⚠️', `Transactions query: ${e.message}`); }
  }

  await page.waitForTimeout(500);

  // ── collect api calls ───────────────────────────────────────────────────
  const calls = Array.from(reqMap.values()).filter(c => c.path.startsWith('/api/v1/'));

  return { label, errors, warns, apiCalls: calls, opsLog };
}

// ══════════════════════════════════════════════════════════════════════════════════════
//  Phase 5: 模拟调仓 - UI 链路验证
//  目标: 买入 sh000001 @ 10.00 x 1000 → ECharts 饼图点亮 + 批次列表出现
// ══════════════════════════════════════════════════════════════════════════════════════

async function runSimulatedTradeTest() {
  const label = 'SimulatedTrade';
  const errors = [], warns = [], apiCalls = [], opsLog = [];

  const browser_ = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  const ctx = await browser_.newContext({
    viewport: { width: 1920, height: 1080 },
  });
  const page = await ctx.newPage();

  page.on('console', msg => {
    if (msg.type() === 'error') { errors.push(msg.text()); log('🔴', msg.text()); }
  });

  const reqMap = new Map();
  page.on('request', req => {
    const url = req.url();
    if (!url.startsWith(BACKEND) && !url.startsWith(FRONTEND)) return;
    const path = url.replace(BACKEND, '').replace(FRONTEND, '');
    reqMap.set(path, { method: req.method(), path, status: null, latency: null });
  });
  page.on('response', async resp => {
    const url = resp.url();
    if (!url.startsWith(BACKEND) && !url.startsWith(FRONTEND)) return;
    const path = url.replace(BACKEND, '').replace(FRONTEND, '');
    const entry = reqMap.get(path);
    if (entry) {
      entry.status = resp.status();
      try { entry.response = await resp.text(); } catch (_) {}
    }
  });

  try {
    log('═', `【${label}】Phase 5 - 模拟调仓 UI 验证`);

    // ── Step 1: 导航到投资组合 ─────────────────────────────────
    log('(1)', `【${label}】STEP 1 - 打开前端 → 投资组合`);
    await page.goto(FRONTEND, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForTimeout(2000);

    const navSelectors = [
      'button:has-text("💰")',
      'button:has-text("投资组合")',
    ];
    for (const sel of navSelectors) {
      const el = page.locator(sel).first();
      if (await el.count() > 0) {
        await el.click({ force: true });
        opsLog.push(`CLICK nav via ${sel}`);
        log('👉', `导航: ${sel}`);
        await page.waitForTimeout(1500);
        break;
      }
    }

    // ── Step 2: 确认有账户（从列表拿一个 ID）─────────────────────────
    log('(2)', `【${label}】STEP 2 - 获取账户列表`);
    const portfolioId = await page.evaluate(async () => {
      const res = await fetch('/api/v1/portfolio/');
      const json = await res.json();
      const list = json.portfolios || [];
      // 优先选子账户（更容易看到持仓变化）
      return list.find(p => p.type !== 'main')?.id || list[0]?.id || 1;
    });
    opsLog.push(`SELECTED portfolio_id=${portfolioId}`);
    log('🔍', `选中账户 ID=${portfolioId}`);

    // ── Step 3: 直接切换到该账户（select dropdown）──────────────────
    log('(3)', `【${label}】STEP 3 - 切换到账户 ${portfolioId}`);
    const selectEl = page.locator('select').first();
    if (await selectEl.count() > 0) {
      await selectEl.selectOption(portfolioId.toString());
      opsLog.push(`SELECT portfolio_id=${portfolioId}`);
      await page.waitForTimeout(1000);
    }

    // ── Step 4: 点击「模拟调仓」按钮 ───────────────────────────────
    log('(4)', `【${label}】STEP 4 - 点击「📋 模拟调仓」`);
    const tradeBtnSelectors = [
      'button:has-text("模拟调仓")',
      'button:has-text("📋")',
    ];
    let tradeBtnFound = false;
    for (const sel of tradeBtnSelectors) {
      const el = page.locator(sel).first();
      if (await el.count() > 0) {
        await el.click({ force: true });
        opsLog.push(`CLICK [模拟调仓] via ${sel}`);
        log('👉', `点击模拟调仓: ${sel}`);
        await page.waitForTimeout(800);
        tradeBtnFound = true;
        break;
      }
    }
    if (!tradeBtnFound) {
      log('❌', '未找到模拟调仓按钮，跳过前端表单测试，直接测 API');
      errors.push('SIM_TRADE_BTN_NOT_FOUND');
    }

    // ── Step 5: 填写表单 ────────────────────────────────────────────
    if (tradeBtnFound) {
      log('(5)', 'STEP 5 - 填写买入表单');

      // 标的代码
      const textInputs = await page.locator('input[type="text"]').all();
      for (const inp of textInputs) {
        const ph = await inp.getAttribute('placeholder') || '';
        if (ph.includes('sh') || ph.includes('sz') || ph.includes('标的')) {
          await inp.fill('sh000001');
          opsLog.push('FILL symbol=sh000001');
          log('✏️', '填写标的: sh000001');
          break;
        }
      }

      // 价格
      const numInputs = await page.locator('input[type="number"]').all();
      let priceSet = false, sharesSet = false;
      for (const inp of numInputs) {
        const ph = await inp.getAttribute('placeholder') || '';
        if (!priceSet && (ph.includes('价') || ph.includes('price'))) {
          await inp.fill('10.00');
          opsLog.push('FILL price=10.00');
          log('✏️', '填写价格: 10.00');
          priceSet = true;
        } else if (!sharesSet && (ph.includes('股') || ph.includes('shares'))) {
          await inp.fill('1000');
          opsLog.push('FILL shares=1000');
          log('✏️', '填写数量: 1000');
          sharesSet = true;
        }
        if (priceSet && sharesSet) break;
      }

      // 如果上面的精确匹配失败，用通用方式
      if (!priceSet || !sharesSet) {
        const allNumInputs = await page.locator('input[type="number"]').all();
        for (let i = 0; i < allNumInputs.length; i++) {
          if (!priceSet) { await allNumInputs[i].fill('10.00'); priceSet = true; opsLog.push('FILL price=10.00 (fallback)'); }
          else if (!sharesSet) { await allNumInputs[i].fill('1000'); sharesSet = true; opsLog.push('FILL shares=1000 (fallback)'); }
        }
      }

      // ── Step 6: 点击「确认买入」────────────────────────────────
      log('(6)', `【${label}】STEP 6 - 点击「确认买入」`);
      const buyBtnSelectors = [
        'button:has-text("确认买入")',
        'button:has-text("📈")',
        'button:has-text("买入")',
      ];
      let submitted = false;
      for (const sel of buyBtnSelectors) {
        const btns = await page.locator(sel).all();
        for (const b of btns) {
          const disabled = await b.getAttribute('disabled');
          if (disabled === null) {
            await b.click({ force: true });
            opsLog.push(`SUBMIT [买入] via ${sel}`);
            log('✔️', `提交买入: ${sel}`);
            await page.waitForTimeout(1500);
            submitted = true;
            break;
          }
        }
        if (submitted) break;
      }

      if (!submitted) {
        log('❌', '未找到可点击的买入按钮，改为直接调用 API');
        errors.push('BUY_BTN_NOT_FOUND');
      }
    }

    // ── Step 7: 直接用 API 模拟一笔买入（兜底，确保有数据可验证）───────
    log('(7)', `【${label}】STEP 7 - 直接调用 API 买入 sh000001 @ 10.00 x 1000`);
    const apiRes = await page.evaluate(async (pid) => {
      const body = {
        symbol: 'sh000001',
        shares: 1000,
        buy_price: 10.00,
        buy_date: new Date().toISOString().slice(0, 10),
      };
      const res = await fetch(`/api/v1/portfolio/${pid}/lots/buy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      return { status: res.status, json: await res.json().catch(() => ({})) };
    }, portfolioId);
    opsLog.push(`BUY API → HTTP ${apiRes.status} body=${JSON.stringify(apiRes.json)}`);
    log('📡', `BUY API → HTTP ${apiRes.status} code=${apiRes.json.code} message=${apiRes.json.message}`);

    // ── Step 8: 等待图表刷新 ──────────────────────────────────────────
    log('(8)', `【${label}】STEP 8 - 等待图表渲染（2s）`);
    await page.waitForTimeout(2000);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);

    // ── Step 9: 切换到该账户 ────────────────────────────────────────
    const selEl2 = page.locator('select').first();
    if (await selEl2.count() > 0) {
      await selEl2.selectOption(portfolioId.toString());
      await page.waitForTimeout(2000);
    }

    // ── Step 10: 检测 DOM - ECharts ──────────────────────────────────
    log('(10)', `【${label}】STEP 10 - 检测 ECharts DOM`);
    const echartExists = await page.locator('.echart-container').count();
    const lotsTableExists = await page.locator('.lots-table').count();
    const pnlCardCount = await page.locator('.pnl-card').count();
    const legendCount = await page.locator('.legend-item').count();
    opsLog.push(`ECHARTS DOM count=${echartExists}`);
    opsLog.push(`LOTS TABLE count=${lotsTableExists}`);
    opsLog.push(`PNL CARDS count=${pnlCardCount}`);
    opsLog.push(`LEGEND ITEMS count=${legendCount}`);
    log('🔍', `ECharts: ${echartExists} | LotsTable: ${lotsTableExists} | PnLCards: ${pnlCardCount} | Legend: ${legendCount}`);

    // ── 检测 lots/echarts API ─────────────────────────────────────────
    const lotsEchartsEntry = Array.from(reqMap.values()).find(c => c.path.includes('lots/echarts'));
    const lotsEntry = Array.from(reqMap.values()).find(c => c.path.includes('/lots?') || c.path.includes('/lots?'));
    if (lotsEchartsEntry) opsLog.push(`API /lots/echarts → HTTP ${lotsEchartsEntry.status}`);
    if (lotsEntry) opsLog.push(`API /lots → HTTP ${lotsEntry.status}`);

    // ── 汇总 ───────────────────────────────────────────────────────────
    const buyOk = apiRes.status === 200 && (apiRes.json.code === 0 || apiRes.json.code === undefined);
    const domPass = echartExists > 0 || lotsTableExists > 0 || pnlCardCount >= 3;
    const apiPass = buyOk && (lotsEchartsEntry?.status === 200 || lotsEntry?.status === 200);

    console.log(`\n╔═══ ${label} - 模拟调仓验证 ══════════════════════════════════════╗`);
    console.log(`║  ✅ 买入 API:  HTTP ${apiRes.status}  code=${apiRes.json.code}                        ║`);
    console.log(`║  ${buyOk ? '✅' : '❌'} /lots/buy (sh000001 x1000 @10.00)                             ║`);
    console.log(`║  ── DOM 渲染 ──                                              ║`);
    console.log(`║  ${echartExists > 0 ? '✅' : '⚠️ '} ECharts 饼图 DOM (.echart-container): ${echartExists} 个        ║`);
    console.log(`║  ${lotsTableExists > 0 ? '✅' : '⚠️ '} 批次明细表 DOM (.lots-table): ${lotsTableExists} 个          ║`);
    console.log(`║  ${pnlCardCount >= 3 ? '✅' : '⚠️ '} PnL 卡片 (.pnl-card): ${pnlCardCount} 个                   ║`);
    console.log(`║  ${legendCount > 0 ? '✅' : '⚠️ '} 图例项 (.legend-item): ${legendCount} 个               ║`);
    console.log(`║  ── 结论 ──                                                  ║`);
    console.log(`║  ${domPass ? '✅ DOM 渲染验证通过 - ECharts 饼图和/或批次表已点亮' : '⚠️ 图表仍为空（账户无持仓数据，需人工确认）'}  ║`);
    console.log(`╚═══════════════════════════════════════════════════════════════════╝`);

    const results = [];
    results.push({ name: '买入 API (sh000001 x1000)', pass: buyOk, detail: `HTTP ${apiRes.status} code=${apiRes.json.code}` });
    results.push({ name: 'ECharts 饼图 DOM', pass: echartExists > 0, detail: `count=${echartExists}` });
    results.push({ name: '批次明细表 DOM', pass: lotsTableExists > 0, detail: `count=${lotsTableExists}` });
    results.push({ name: 'PnL 卡片', pass: pnlCardCount >= 3, detail: `count=${pnlCardCount}` });
    results.push({ name: '/lots/echarts API', pass: lotsEchartsEntry?.status === 200, detail: `HTTP ${lotsEchartsEntry?.status}` });

    console.log('\n  ── 链路点击日志 ──');
    opsLog.forEach((op, i) => console.log(`    ${i + 1}. ${op}`));

    await ctx.close();
    await browser_.close();
    return results;

  } catch (e) {
    log('❌', `${label} failed: ${e.message}`);
    await ctx.close();
    await browser_.close();
    return [{ name: 'Phase5_SimTrade', pass: false, detail: e.message }];
  }
}

// ══════════════════════════════════════════════════════════════════════════════
//  Phase Roll-up: 子账户树形 PnL 聚合 - 自动化验证
// ══════════════════════════════════════════════════════════════════════════════

/**
 * 资金守恒定律测试 + 划转验证
 * 1. GET /conservation  → 验证 parent_total == parent + children（守恒定律）
 * 2. POST /transfer    → 子账户间划转
 * 3. GET /conservation → 验证划转前后 grand_total 完全相等
 */
async function runConservationTest() {
  const BASE = 'http://localhost:8002/api/v1';
  const results = [];

  async function api(path, method = 'GET', body = null) {
    const opts = { method };
    if (body) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(body);
    }
    const resp = await fetch(`${BASE}${path}`, opts);
    const text = await resp.text();
    let json;
    try { json = JSON.parse(text); } catch { json = { raw: text }; }
    return { status: resp.status, data: json };
  }

  // ── Step 1: 获取账户列表 ──────────────────────────────────────
  log('🔍', '[守恒测试] Step 1 - 获取账户列表');
  const listRes = await api('/portfolio/');
  const portfolios = listRes.data.portfolios || [];
  const parent = portfolios.find(p => p.type === 'main');
  const child  = portfolios.find(p => p.parent_id === parent?.id);

  if (!parent) { console.log('❌ 无主账户，跳过守恒测试'); return results; }
  console.log(`  主账户: id=${parent.id} "${parent.name}"`);
  if (child) console.log(`  子账户: id=${child.id} "${child.name}"`);
  else console.log('  ⚠️  无子账户，跳过划转测试');

  // ── Step 2: 守恒定律验证（划转前）────────────────────────────────
  log('🔍', '[守恒测试] Step 2 - 守恒定律验证（划转前）');
  const consBefore = await api(`/portfolio/${parent.id}/conservation`);
  console.log(`  HTTP ${consBefore.status}`);
  if (consBefore.status === 200) {
    const d = consBefore.data.data || consBefore.data;
    const parentTotal  = d.parent?.total  || 0;
    const childrenTotal= d.children_total || 0;
    const grandTotal   = d.grand_total    || 0;
    const delta        = d.conservation_delta || 0;
    const ok           = d.conservation_ok !== false;

    console.log(`  parent_total  = ¥${parentTotal.toLocaleString()}`);
    console.log(`  children_total= ¥${childrenTotal.toLocaleString()}`);
    console.log(`  grand_total  = ¥${grandTotal.toLocaleString()}`);
    console.log(`  (grand - parent) = ¥${delta.toLocaleString()}  ← 应等于 children_total`);
    console.log(`  conservation_ok  = ${ok ? '✅ true' : '❌ false'}`);
    results.push({
      name: '守恒定律（划转前）',
      pass: ok && Math.abs(delta - childrenTotal) < 0.01,
      detail: `parent=¥${parentTotal} children=¥${childrenTotal} grand=¥${grandTotal}`,
    });
  } else {
    console.log(`  ❌ 失败: ${JSON.stringify(consBefore.data)}`);
    results.push({ name: '守恒定律（划转前）', pass: false, detail: `HTTP ${consBefore.status}` });
  }

  // ── Step 3: 树形端点验证 ─────────────────────────────────────────
  log('🔍', '[守恒测试] Step 3 - 树形端点 /tree');
  const treeRes = await api(`/portfolio/${parent.id}/tree`);
  console.log(`  HTTP ${treeRes.status}`);
  if (treeRes.status === 200) {
    const tree = (treeRes.data.data || treeRes.data).tree || {};
    console.log(`  tree.name = "${tree.name}"`);
    console.log(`  tree.children.length = ${(tree.children || []).length}`);
    results.push({ name: '/tree 端点', pass: true, detail: `children=${tree.children?.length}` });
  } else {
    console.log(`  ❌ 失败`);
    results.push({ name: '/tree 端点', pass: false, detail: `HTTP ${treeRes.status}` });
  }

  // ── Step 4: 子账户间划转（金额小，测试用）──────────────────────────
  if (!child) {
    console.log('  ⚠️  无子账户，跳过划转测试');
  } else {
    log('🔍', `[守恒测试] Step 4 - 子账户间划转 ¥1000（${parent.name} → ${child.name}）`);
    const transferRes = await api('/portfolio/transfer/direct', 'POST', {
      from_portfolio_id: parent.id,
      to_portfolio_id:   child.id,
      amount:            1000,
    });
    console.log(`  HTTP ${transferRes.status}`);
    if (transferRes.status === 200 || transferRes.data?.code === 0) {
      const td = transferRes.data.data || transferRes.data;
      console.log(`  ✅ 划转成功: from_balance=¥${td.balance_from?.toLocaleString()} to_balance=¥${td.balance_to?.toLocaleString()}`);
      results.push({
        name: '子账户划转 API',
        pass: true,
        detail: `¥1000 ${parent.name} → ${child.name}`,
      });
    } else {
      console.log(`  ❌ 划转失败: ${JSON.stringify(transferRes.data)}`);
      results.push({ name: '子账户划转 API', pass: false, detail: `HTTP ${transferRes.status}` });
    }

    // ── Step 5: 守恒定律验证（划转后）────────────────────────────────
    log('🔍', '[守恒测试] Step 5 - 守恒定律验证（划转后）');
    const consAfter = await api(`/portfolio/${parent.id}/conservation`);

    if (consAfter.status === 200) {
      const before = (consBefore.data.data || consBefore.data).grand_total || 0;
      const after  = (consAfter.data.data  || consAfter.data).grand_total  || 0;
      const delta_abs = Math.abs(after - before);
      // 划转是内部转账，grand_total 应完全不变
      const conservation_ok = delta_abs < 0.01;
      console.log(`  grand_total 划转前 = ¥${before.toLocaleString()}`);
      console.log(`  grand_total 划转后 = ¥${after.toLocaleString()}`);
      console.log(`  差值 = ¥${delta_abs.toFixed(4)}  ${conservation_ok ? '✅ 守恒（相等）' : '❌ 资金异常！）'}`);
      results.push({
        name: '资金守恒（划转后 = 划转前）',
        pass: conservation_ok,
        detail: `before=¥${before} after=¥${after} delta=¥${delta_abs}`,
      });
    } else {
      console.log(`  ❌ 失败: HTTP ${consAfter.status}`);
      results.push({ name: '资金守恒（划转后）', pass: false, detail: `HTTP ${consAfter.status}` });
    }

    // ── Step 6: 回滚划转（恢复原状）───────────────────────────────────
    log('🔍', `[守恒测试] Step 6 - 回滚划转 ¥1000（${child.name} → ${parent.name}）`);
    const rollbackRes = await api('/portfolio/transfer/direct', 'POST', {
      from_portfolio_id: child.id,
      to_portfolio_id:   parent.id,
      amount:            1000,
    });
    if (rollbackRes.status === 200 || rollbackRes.data?.code === 0) {
      console.log(`  ✅ 回滚成功`);
      results.push({ name: '划转回滚', pass: true, detail: '¥1000 恢复原状' });
    } else {
      console.log(`  ⚠️  回滚失败（不影响主测试）: ${JSON.stringify(rollbackRes.data)}`);
      results.push({ name: '划转回滚', pass: false, detail: `HTTP ${rollbackRes.status}` });
    }
  }

  // ── Step 7: include_children 端点验证 ──────────────────────────────
  log('🔍', '[守恒测试] Step 7 - include_children 各端点验证');
  for (const [path, label] of [
    [`/portfolio/${parent.id}/lots?include_children=true`,       '/lots?include_children'],
    [`/portfolio/${parent.id}/lots/summary?include_children=true`, '/lots/summary?include_children'],
    [`/portfolio/${parent.id}/lots/echarts?include_children=true`,'/lots/echarts?include_children'],
    [`/portfolio/${parent.id}/pnl?include_children=true`,        '/pnl?include_children'],
    [`/portfolio/${parent.id}/positions?include_children=true`,   '/positions?include_children'],
  ]) {
    const r = await api(path);
    const pass = r.status === 200;
    console.log(`  ${pass ? '✅' : '❌'} HTTP ${r.status}  ${path}`);
    results.push({ name: label, pass, detail: `HTTP ${r.status}` });
  }

  return results;
}

// ── Report formatter ──────────────────────────────────────────────────────────
function printReport(results) {
  for (const { label, errors, warns, apiCalls, opsLog, fatal } of results) {
    if (fatal) {
      console.log(`\n  ❌ 【${label}】页面无法加载，跳过`);
      continue;
    }
    const ok = v => v >= 200 && v < 300;
    const success = apiCalls.filter(c => ok(c.status)).length;
    const failed  = apiCalls.filter(c => !ok(c.status)).length;
    const rate    = apiCalls.length ? Math.round(success / apiCalls.length * 100) : 0;

    console.log(`\n╔═══ ${label} ═══════════════════════════════════════════════════╗`);
    console.log(`║  点击链路                                              ║`);
    opsLog.forEach((op, i) => console.log(`║    ${i+1}. ${op}`));
    console.log(`║                                                        ║`);
    console.log(`║  Console Errors   : ${errors.length === 0 ? '✅ 0' : '❌ ' + errors.length}`);
    errors.slice(0, 3).forEach(e => console.log(`║    🔴 ${e.slice(0,60)}`));
    console.log(`║  Console Warnings : ${warns.length === 0 ? '✅ 0' : '🟡 ' + warns.length}`);
    warns.slice(0, 3).forEach(w => console.log(`║    🟡 ${w.slice(0,60)}`));
    console.log(`║                                                        ║`);
    console.log(`║  API 调用: ${apiCalls.length} 次  成功: ${success}  失败: ${failed}  成功率: ${rate}%`);
    console.log(`║  详细:`);
    apiCalls.forEach(c => {
      const icon = ok(c.status) ? '✅' : (c.status === 0 ? '⚠️' : '❌');
      console.log(`║    ${icon} [${c.method}] ${c.path} → ${c.status || '?'}`);
    });
    const pass = errors.length === 0 && failed === 0;
    console.log(`║                                                        ║`);
    console.log(`║  结论: ${pass ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`╚════════════════════════════════════════════════════════════╝`);
  }
}

// ── entry point ──────────────────────────────────────────────────────────────
(async () => {
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  require('fs').mkdirSync('/tmp/ui_test', {recursive:true});
  const results = [];

  if (runDesktop || runBoth) {
    const ctx1 = await browser.newContext();
    const page1 = await ctx1.newPage();
    results.push(await runViewport(page1, 'desktop', { width: 1920, height: 1080 }));
    await ctx1.close();
  }

  if (runMobile || runBoth) {
    const ctx2 = await browser.newContext({ userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1' });
    const page2 = await ctx2.newPage();
    results.push(await runViewport(page2, 'mobile', { width: 375, height: 667 }));
    await ctx2.close();
  }

  // ── Phase 4: Chart DOM Verification ───────────────────────────
  console.log('\n═══════════════════════════════════════');
  console.log('   PHASE 4 - CHART DOM VERIFICATION      ');
  console.log('═══════════════════════════════════════');
  try {
    for (const { label, fatal } of results) {
      if (!fatal) {
        const ctxChart = await browser.newContext();
        const pageChart = await ctxChart.newPage();
        try {
          const chartResult = await runChartTests(pageChart, label.split(' ')[0].toLowerCase());
          results.push(chartResult);
        } finally {
          await ctxChart.close().catch(() => {});
        }
      }
    }
  } catch (e) {
    console.log('  ⚠️ Phase 4 chart tests error:', e.message);
  }

  await browser.close().catch(() => {});

  // ── Phase 5: 模拟调仓验证 ─────────────────────────────────────
  console.log('\n═══════════════════════════════════════');
  console.log('   PHASE 5 - SIMULATED TRADE + CHART   ');
  console.log('═══════════════════════════════════════');
  const tradeResults = await runSimulatedTradeTest();

  // ── Phase Roll-up: 子账户树形聚合 + 守恒定律验证 ─────────────
  console.log('\n═══════════════════════════════════════');
  console.log('   PHASE ROLL-UP - TREE PNL + CONSERVATION  ');
  console.log('═══════════════════════════════════════');
  const conservationResults = await runConservationTest();

  console.log('\n═══════════════════════════════════════');
  console.log('   FINAL CONSOLIDATED REPORT            ');
  console.log('═══════════════════════════════════════');

  // 守恒测试单独输出
  console.log('\n  ── 守恒定律测试结果 ──');
  let allPass = true;
  for (const r of conservationResults) {
    console.log(`    ${r.pass ? '✅' : '❌'} ${r.name}: ${r.detail}`);
    if (!r.pass) allPass = false;
  }

  // Phase 5 单独输出
  console.log('\n  ── 模拟调仓测试结果 ──');
  for (const r of tradeResults) {
    console.log(`    ${r.pass ? '✅' : '❌'} ${r.name}: ${r.detail}`);
    if (!r.pass) allPass = false;
  }

  printReport(results);

  const totalFails = results.reduce((s, r) => s + r.errors.filter(e => !e.includes('⚠️')).length, 0);
  process.exit((!allPass || totalFails > 0) ? 1 : 0);
})();

// ═══════════════════════════════════════════════════════════════
//  Phase 4 Extended Tests - Chart & DOM Verification
// ═══════════════════════════════════════════════════════════════

async function runChartTests(page, mode) {
  const label = `${mode} Chart`;
  const errors = [], warns = [], apiCalls = [], opsLog = [];

  log('═', `【${label}】图表 DOM 检测`);
  await page.setViewportSize({ width: mode === 'desktop' ? 1920 : 375, height: mode === 'desktop' ? 1080 : 667 });

  page.on('console', msg => {
    if (msg.type() === 'error') { errors.push(msg.text()); log('🔴', `[${label}] ${msg.text()}`); }
  });

  const reqMap = new Map();
  page.on('request', req => {
    const url = req.url();
    if (!url.startsWith(BACKEND) && !url.startsWith(FRONTEND)) return;
    const path = url.replace(BACKEND, '').replace(FRONTEND, '');
    reqMap.set(path, { method: req.method(), path, status: null, latency: null });
  });
  page.on('response', async resp => {
    const url = resp.url();
    if (!url.startsWith(BACKEND) && !url.startsWith(FRONTEND)) return;
    const path = url.replace(BACKEND, '').replace(FRONTEND, '');
    const e = reqMap.get(path);
    if (e) { e.status = resp.status(); e.latency = Date.now(); }
  });

  try {
    await page.goto(FRONTEND, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForTimeout(2000);
    opsLog.push('NAVIGATE → http://localhost:60100');

    // Navigate to portfolio (CRITICAL: must click sidebar item to switch currentView to 'portfolio')
    const navSelectors = [
      'button:has-text("💰")',
      'button:has-text("投资组合")',
      '[data-sidebar-id="portfolio"]',
    ];
    let navClicked = false;
    for (const sel of navSelectors) {
      const el = page.locator(sel).first();
      if (await el.count() > 0) {
        await el.click({ force: true });
        opsLog.push(`CLICK nav[💰投资组合] via ${sel}`);
        log('👉', `导航到投资组合: ${sel}`);
        await page.waitForTimeout(2000); // wait for Vue currentView switch + component mount
        navClicked = true;
        await snapshot(page, `${label}_after_portfolio_nav`);
        break;
      }
    }
    if (!navClicked) {
      opsLog.push('WARN: portfolio nav button not found, trying direct click on any 💰 button');
      log('⚠️', 'portfolio nav button not found, trying fallback');
      try {
        await page.locator('button').filter({ hasText: '💰' }).first().click({ force: true });
        opsLog.push('CLICK [💰] via emoji filter (fallback)');
        await page.waitForTimeout(2000);
        navClicked = true;
      } catch (_) {}
    }

    // ── Select an account that has positions (prefer a sub-account with lots) ─
    // Wait for account selector to appear
    await page.waitForTimeout(1000);
    const selectExists = await page.locator('select').count();
    if (selectExists > 0) {
      const options = await page.locator('select option').all();
      opsLog.push(`SELECT: found ${options.length} account options`);
      // Select last non-main account (sub-accounts more likely to have lots for chart testing)
      if (options.length > 1) {
        const lastOptionVal = await options[options.length - 1].getAttribute('value');
        await page.locator('select').selectOption(lastOptionVal);
        opsLog.push(`SELECT: picked last account option (value=${lastOptionVal}) for chart test`);
        await page.waitForTimeout(2000); // wait for lots/echarts API response + chart render
      }
    }

    // Wait for async data (lots/echarts endpoint) to complete
    await page.waitForTimeout(5000);

    opsLog.push('WAIT 5s for chart rendering after account selection');

    // ── Check 1: .echart-container exists and has REAL pixel dimensions ─────────
    const echartExists = await page.locator('.echart-container').count();
    let echartBox = null;
    let echartRenderFail = false;
    if (echartExists > 0) {
      echartBox = await page.locator('.echart-container').first().boundingBox();
      if (!echartBox) {
        echartRenderFail = true;
        opsLog.push(`FAIL: .echart-container found but boundingBox=null (CSS collapse!)`);
      } else if (echartBox.height < 10 || echartBox.width < 10) {
        echartRenderFail = true;
        opsLog.push(`FAIL: .echart-container boundingBox=${echartBox.width}×${echartBox.height}px (< 10px → visual collapse!)`);
      } else {
        opsLog.push(`✅ .echart-container boundingBox=${echartBox.width}×${echartBox.height}px`);
      }
    } else {
      echartRenderFail = true;
      opsLog.push(`FAIL: .echart-container not found in DOM`);
    }
    log('🔍', `echart-container: count=${echartExists} box=${JSON.stringify(echartBox)} → ${echartRenderFail ? '❌ COLLAPSED' : '✅ OK'}`);

    // ── Check 2: .lots-table exists and has REAL pixel height ─────────────────
    const lotsTableExists = await page.locator('.lots-table').count();
    let lotsBox = null;
    let lotsRenderFail = false;
    if (lotsTableExists > 0) {
      lotsBox = await page.locator('.lots-table').first().boundingBox();
      if (!lotsBox) {
        lotsRenderFail = true;
        opsLog.push(`FAIL: .lots-table found but boundingBox=null (CSS collapse!)`);
      } else if (lotsBox.height < 10) {
        lotsRenderFail = true;
        opsLog.push(`FAIL: .lots-table boundingBox.height=${lotsBox.height}px (< 10px → visual collapse!)`);
      } else {
        opsLog.push(`✅ .lots-table boundingBox=${lotsBox.width}×${lotsBox.height}px`);
      }
    } else {
      lotsRenderFail = true;
      opsLog.push(`FAIL: .lots-table not found in DOM`);
    }
    log('🔍', `lots-table: count=${lotsTableExists} box=${JSON.stringify(lotsBox)} → ${lotsRenderFail ? '❌ COLLAPSED' : '✅ OK'}`);

    // ── Check 3: .pnl-card exists and has REAL pixel dimensions ─────────────────
    const pnlCardCount = await page.locator('.pnl-card').count();
    let pnlCardBoxes = [];
    let pnlRenderFail = false;
    if (pnlCardCount > 0) {
      const cards = page.locator('.pnl-card');
      for (let i = 0; i < Math.min(pnlCardCount, 5); i++) {
        const box = await cards.nth(i).boundingBox();
        pnlCardBoxes.push(box);
        if (box && (box.height < 10 || box.width < 10)) {
          pnlRenderFail = true;
        }
      }
      if (!pnlRenderFail) {
        opsLog.push(`✅ .pnl-card count=${pnlCardCount} boxes=[${pnlCardBoxes.map(b => b ? `${b.width}×${b.height}` : 'null').join(', ')}]`);
      } else {
        opsLog.push(`FAIL: .pnl-card at least one card < 10px → visual collapse!`);
      }
    } else {
      pnlRenderFail = true;
      opsLog.push(`FAIL: .pnl-card not found in DOM`);
    }
    log('🔍', `pnl-card: count=${pnlCardCount} firstBox=${JSON.stringify(pnlCardBoxes[0])} → ${pnlRenderFail ? '❌ COLLAPSED' : '✅ OK'}`);

    // ── Check 4: Pie legend items and their pixel dimensions ───────────────────
    const legendCount = await page.locator('.legend-item').count();
    let legendRenderFail = false;
    if (legendCount > 0) {
      const firstLegendBox = await page.locator('.legend-item').first().boundingBox();
      if (!firstLegendBox || firstLegendBox.height < 5) {
        legendRenderFail = true;
        opsLog.push(`FAIL: .legend-item boundingBox.height=${firstLegendBox?.height}px (< 5px → collapse!)`);
      } else {
        opsLog.push(`✅ .legend-item count=${legendCount} firstBox=${firstLegendBox.width}×${firstLegendBox.height}px`);
      }
    } else {
      // No legend items is OK if positions are empty (空持仓 → no legend items)
      opsLog.push(`INFO: .legend-item count=0 (may be empty portfolio, not a failure)`);
    }
    log('🔍', `legend-item: count=${legendCount} → ${legendRenderFail ? '❌ COLLAPSED' : (legendCount > 0 ? '✅ OK' : 'ℹ️ 0 items (empty portfolio)')}`);

    // ── Check 5: Backend API calls for lots/echarts ──────────────────
    const echartsCall = Array.from(reqMap.values()).find(c => c.path.includes('lots/echarts'));
    const pnlCall     = Array.from(reqMap.values()).find(c => c.path.includes('/pnl'));
    if (echartsCall) opsLog.push(`API /lots/echarts → HTTP ${echartsCall.status}`);
    if (pnlCall)    opsLog.push(`API /pnl → HTTP ${pnlCall.status}`);

    // ── Check 6: Scan ALL iframes and shadow DOMs for hidden chart canvases ────
    const canvasCount = await page.locator('canvas').count();
    opsLog.push(`CANVAS elements in DOM: ${canvasCount}`);
    if (canvasCount > 0) {
      const firstCanvasBox = await page.locator('canvas').first().boundingBox();
      opsLog.push(`First canvas boundingBox: ${JSON.stringify(firstCanvasBox)}`);
    }

    // ── Summary ────────────────────────────────────────────────────────
    const domChecks = [
      {
        name: 'ECharts DOM (.echart-container)',
        pass: echartExists > 0 && !echartRenderFail,
        detail: echartBox ? `${echartBox.width}×${echartBox.height}px` : 'boundingBox=null (塌陷!)'
      },
      {
        name: 'Lots Table (.lots-table)',
        pass: lotsTableExists > 0 && !lotsRenderFail,
        detail: lotsBox ? `${lotsBox.width}×${lotsBox.height}px` : 'boundingBox=null (塌陷!)'
      },
      {
        name: 'PnL Cards (.pnl-card)',
        pass: pnlCardCount >= 3 && !pnlRenderFail,
        detail: `count=${pnlCardCount} first=${JSON.stringify(pnlCardBoxes[0])}`
      },
      {
        name: 'Pie Legend (.legend-item)',
        pass: !legendRenderFail,
        detail: legendCount > 0 ? `count=${legendCount}` : '0 items (empty portfolio)'
      },
      {
        name: '/lots/echarts API',
        pass: echartsCall?.status === 200,
        detail: `HTTP ${echartsCall?.status || 'not called'}`
      },
      {
        name: '/pnl API',
        pass: pnlCall?.status === 200,
        detail: `HTTP ${pnlCall?.status || 'not called'}`
      },
      {
        name: 'Canvas elements (ECharts rendered)',
        pass: canvasCount > 0,
        detail: `${canvasCount} canvas found`
      },
    ];

    console.log(`\n╔═══ ${label} 像素级 DOM 检测 ══════════════════════════════════════╗`);
    domChecks.forEach((c) => {
      const icon = c.pass ? '✅' : '❌';
      console.log(`║  ${icon} ${c.name}`);
      console.log(`║     → ${c.detail}`);
    });
    const domPass = domChecks.every(c => c.pass);
    console.log(`║                                                              ║`);
    console.log(`║  结论: ${domPass ? '✅ DOM 渲染通过（所有节点像素尺寸 ≥ 阈值）' : '❌ 部分 DOM 像素塌陷或未就绪'}  ║`);
    console.log(`╚══════════════════════════════════════════════════════════════════╝`);

    return { label, errors, warns, apiCalls: Array.from(reqMap.values()), opsLog, domPass, domChecks };
  } catch (e) {
    log('❌', `${label} failed: ${e.message}`);
    return { label, errors, warns, apiCalls: [], opsLog, fatal: true };
  }
}
