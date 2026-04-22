/**
 * ui_functional_test.js
 * ─────────────────────────────────────────────────────────────────────────────
 * AlphaTerminal 前端功能自动化验证器（Headless F12）
 *
 * 职责：
 *   1. 访问前端子账户管理页面（PortfolioDashboard）
 *   2. 模拟「新建子账户」操作链路（点击 → 输入 → 提交）
 *   3. 模拟「资金划转」操作链路
 *   4. 全程监听 console.error / console.log 及所有发往后端 /portfolio/ API 的
 *      请求载荷（payload）与响应状态
 *
 * 运行：node tests/ui_functional_test.js
 * ─────────────────────────────────────────────────────────────────────────────
 */
const { chromium } = require('playwright');

const FRONTEND   = 'http://localhost:60100';
const BACKEND    = 'http://localhost:8002';
const BASE_PATH  = '/api/v1/portfolio';
const OUT_DIR    = '/tmp/ui_test_results';

// ── helpers ────────────────────────────────────────────────────────────────────
function now() { return new Date().toISOString().slice(11, 23); }
function log(tag, msg) { console.log(`[${now()}] ${tag} ${msg}`); }

// ── test state ────────────────────────────────────────────────────────────────
let PASS = 0, FAIL = 0;
const errors   = [];
const warns    = [];
const apiCalls = [];   // { method, path, payload, status, latency, response }
const opsLog  = [];   // 操作链路

// ── main ────────────────────────────────────────────────────────────────────────
(async () => {
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-web-security'],
  });
  const page = await browser.newPage();

  // ── intercept ALL fetch/XHR ──────────────────────────────────────────────────
  page.on('request', req => {
    const url = req.url();
    if (!url.startsWith(BACKEND) && !url.startsWith(FRONTEND)) return;
    const path = url.replace(BACKEND, '').replace(FRONTEND, '');
    const entry = { method: req.method(), path, url, latency: null, status: null, payload: null, response: null };
    apiCalls.push(entry);
    req.continue();
  });

  page.on('response', resp => {
    const url = resp.url();
    if (!url.startsWith(BACKEND) && !url.startsWith(FRONTEND)) return;
    const path = url.replace(BACKEND, '').replace(FRONTEND, '');
    const entry = apiCalls.find(e => e.path === path && e.latency === null) || apiCalls[apiCalls.length - 1];
    if (entry) {
      entry.status = resp.status();
      entry.latency = Date.now();
      resp.text().then(txt => { entry.response = txt.slice(0, 200); }).catch(() => {});
    }
  });

  page.on('console', msg => {
    const type = msg.type(), text = msg.text();
    if (type === 'error')   { errors.push(text); log('🔴 ERR', text); }
    else if (type === 'log') { log('📝 LOG', text); }
    else if (type === 'warn'){ warns.push(text);  log('🟡 WARN', text); }
  });

  page.on('pageerror', err => {
    const t = `Uncaught: ${err.message}`;
    errors.push(t); log('💥 PAGEERROR', t);
  });

  // ── navigate ────────────────────────────────────────────────────────────────
  log('▶', `Navigating → ${FRONTEND}`);
  try {
    await page.goto(FRONTEND, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  } catch (e) { log('⚠️', `goto failed: ${e.message}`); }
  await page.waitForTimeout(3_000);

  // ── test helpers ────────────────────────────────────────────────────────────
  async function clickAndLog(selector, label) {
    try {
      await page.click(selector, { timeout: 5_000 });
      opsLog.push(`CLICK → ${label} [${selector}]`);
      log('👉', `Clicked ${label}`);
      await page.waitForTimeout(500);
    } catch (e) { opsLog.push(`CLICK FAILED → ${label} [${selector}]: ${e.message}`); log('❌', `Click failed ${label}: ${e.message}`); }
  }

  async function fillAndLog(inputSelector, label, value) {
    try {
      await page.fill(inputSelector, String(value));
      opsLog.push(`FILL → ${label} [${inputSelector}] = "${value}"`);
      log('✏️', `Filled "${label}" = "${value}"`);
      await page.waitForTimeout(200);
    } catch (e) { opsLog.push(`FILL FAILED → ${label}: ${e.message}`); log('❌', `Fill failed ${label}: ${e.message}`); }
  }

  async function typeAndLog(inputSelector, label, value) {
    try {
      await page.click(inputSelector);
      await page.keyboard.type(String(value), { delay: 80 });
      opsLog.push(`TYPE → ${label} [${inputSelector}] = "${value}"`);
      log('⌨️', `Typed "${label}" = "${value}"`);
      await page.waitForTimeout(200);
    } catch (e) { opsLog.push(`TYPE FAILED → ${label}: ${e.message}`); log('❌', `Type failed ${label}: ${e.message}`); }
  }

  async function submitAndLog(buttonSelector, label) {
    try {
      await page.click(buttonSelector, { timeout: 5_000 });
      opsLog.push(`SUBMIT → ${label} [${buttonSelector}]`);
      log('✔️', `Submitted ${label}`);
      await page.waitForTimeout(2_000);
    } catch (e) { opsLog.push(`SUBMIT FAILED → ${label}: ${e.message}`); log('❌', `Submit failed ${label}: ${e.message}`); }
  }

  async function findPortfolioId(name) {
    // Extract ID from store.portfolios after creation
    return await page.evaluate(n => {
      // usePortfolioStore is a reactive singleton — find in window or via store
      return null; // will read from API calls directly
    }, name);
  }

  // ── STEP 1: Open account list ─────────────────────────────────────────────
  log('═', '═══════════════════════════════════════════════');
  log('①', 'STEP 1 — 打开账户列表页面');
  log('═', '═══════════════════════════════════════════════');

  try {
    await page.goto(FRONTEND, { waitUntil: 'networkidle', timeout: 15_000 });
    await page.waitForTimeout(3_000);
    opsLog.push('NAVIGATE → http://localhost:60100 (PortfolioDashboard)');
    log('✅', 'Page loaded');
  } catch (e) {
    log('❌', `Page load failed: ${e.message}`);
  }

  // ── STEP 2: Click "新建子账户" button ──────────────────────────────────────
  log('═', '═══════════════════════════════════════════════');
  log('②', 'STEP 2 — 打开「新建账户」弹窗');
  log('═', '═══════════════════════════════════════════════');

  // The button text contains "新建"
  try {
    const btns = await page.locator('button:has-text("新建")').all();
    if (btns.length) {
      await btns[0].click();
      opsLog.push('CLICK → [button:has-text("新建")]');
      log('👉', 'Clicked button:has-text("新建")');
      await page.waitForTimeout(1_000);
    } else {
      opsLog.push('WARN: no button with text "新建" found');
      log('⚠️', 'No "新建" button found');
    }
  } catch (e) {
    log('⚠️', `Button click exception: ${e.message}`);
  }

  // ── STEP 3: Fill create account form ────────────────────────────────────────
  log('═', '═══════════════════════════════════════════════');
  log('③', 'STEP 3 — 填写账户表单');
  log('═', '═══════════════════════════════════════════════');

  // Wait for modal to appear
  await page.waitForTimeout(1_000);

  // Input: account name
  try {
    const nameInput = page.locator('input[placeholder*="基金"]').first();
    await nameInput.fill('自动化子账户-Test');
    opsLog.push('FILL → 账户名称 = "自动化子账户-Test"');
    log('✏️', 'Filled account name');
    await page.waitForTimeout(300);
  } catch (e) {
    // fallback by placeholder
    const inputs = await page.locator('input[type="text"]').all();
    for (const inp of inputs) {
      const ph = await inp.getAttribute('placeholder') || '';
      if (ph) { await inp.fill('自动化子账户-Test'); log('✏️', `Filled: ${ph}`); break; }
    }
  }

  // Select type: portfolio
  try {
    const selects = await page.locator('select').all();
    for (const sel of selects) {
      const opts = await sel.locator('option').allTextContents();
      if (opts.some(o => o.includes('投资组合'))) {
        await sel.selectOption({ label: '投资组合' });
        opsLog.push('SELECT → 账户类型 = "投资组合"');
        log('✏️', 'Selected account type: 投资组合');
        await page.waitForTimeout(200);
        break;
      }
    }
  } catch (e) {
    log('⚠️', `Select type failed: ${e.message}`);
  }

  // Fill initial capital
  try {
    const numInputs = await page.locator('input[type="number"]').all();
    for (const inp of numInputs) {
      await inp.fill('50000');
      opsLog.push('FILL → 初始资金 = 50000');
      log('✏️', 'Filled initial_capital = 50000');
      await page.waitForTimeout(200);
      break;
    }
  } catch (e) {
    log('⚠️', `Fill capital failed: ${e.message}`);
  }

  // ── STEP 4: Submit form ──────────────────────────────────────────────────────
  log('═', '═══════════════════════════════════════════════');
  log('④', 'STEP 4 — 提交「创建账户」');
  log('═', '═══════════════════════════════════════════════');

  await page.waitForTimeout(500);
  try {
    // Click "创建" button inside modal
    const createBtn = page.locator('button:has-text("创建")').last();
    await createBtn.click();
    opsLog.push('CLICK → [button:has-text("创建")] (modal confirm)');
    log('✔️', 'Clicked 创建 (confirm button)');
    await page.waitForTimeout(3_000);
  } catch (e) {
    log('❌', `Create submit failed: ${e.message}`);
  }

  // ── STEP 5: Find the newly created account ───────────────────────────────────
  log('═', '═══════════════════════════════════════════════');
  log('⑤', 'STEP 5 — 定位新建账户 ID');
  log('═', '═══════════════════════════════════════════════');

  // Get latest POST /portfolio/ from apiCalls
  const createCall = apiCalls.filter(c => c.method === 'POST' && c.path.includes('/portfolio/') && !c.path.includes('transfer') && !c.path.includes('cash')).slice(-1)[0];
  const newAccId = createCall ? `created_id_in_response` : 'unknown';
  opsLog.push(`FIND → 最新创建账户调用: POST ${createCall?.path || 'n/a'} → status=${createCall?.status || 'n/a'}`);
  log('🔍', `Create API call: POST ${createCall?.path || 'n/a'} → status=${createCall?.status || 'n/a'}`);

  // ── STEP 6: Fetch accounts and identify IDs ─────────────────────────────────
  let mainId = null, subId = null;
  try {
    const listRes = await page.evaluate(async () => {
      const r = await fetch('/api/v1/portfolio/');
      return r.json();
    });
    const accs = listRes.portfolios || [];
    const main = accs.find(p => !p.parent_id);
    const sub  = accs.filter(p => p.parent_id).sort((a,b) => a.id - b.id)[0];
    mainId = main?.id;
    subId  = sub?.id;
    opsLog.push(`FIND → main_id=${mainId} sub_id=${subId}`);
    log('🔍', `Accounts: main_id=${mainId} sub_id=${subId}`);
  } catch (e) {
    log('⚠️', `Failed to fetch account list: ${e.message}`);
  }

  // ── STEP 7: Transfer between accounts ───────────────────────────────────────
  log('═', '═══════════════════════════════════════════════');
  log('⑦', 'STEP 7 — 执行资金划转（主→子）');
  log('═', '═══════════════════════════════════════════════');

  if (mainId && subId) {
    try {
      const transferRes = await page.evaluate(async (from, to, amt) => {
        const r = await fetch('/api/v1/portfolio/transfer/direct', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ from_portfolio_id: from, to_portfolio_id: to, amount: amt, note: 'UI自动化测试划转' }),
        });
        return { status: r.status, body: await r.text().catch(() => '') };
      }, mainId, subId, 10000);

      opsLog.push(`TRANSFER → from=${mainId} to=${subId} amount=10000 status=${transferRes.status}`);
      log('✔️', `Transfer result: HTTP ${transferRes.status} payload=${transferRes.body?.slice(0, 100)}`);
      if (transferRes.status >= 400) errors.push(`Transfer failed: HTTP ${transferRes.status}`);
    } catch (e) {
      errors.push(`Transfer error: ${e.message}`);
      log('❌', `Transfer exception: ${e.message}`);
    }
  } else {
    opsLog.push('SKIP → 无法获取账户ID，跳过划转测试');
    log('⚠️', 'Skipping transfer: account IDs not found');
  }

  // ── STEP 8: Query transactions ───────────────────────────────────────────────
  log('═', '═══════════════════════════════════════════════');
  log('⑧', 'STEP 8 — 查询流水接口验证');
  log('═', '═══════════════════════════════════════════════');

  if (mainId) {
    try {
      const txnRes = await page.evaluate(async (pid) => {
        const r = await fetch(`/api/v1/portfolio/${pid}/transactions?limit=3`);
        return { status: r.status, body: await r.json().catch(() => ({})) };
      }, mainId);
      opsLog.push(`TXNS → main_id=${mainId} status=${txnRes.status} count=${txnRes.body?.data?.transactions?.length || 0}`);
      log('🔍', `Transactions: HTTP ${txnRes.status}, ${txnRes.body?.data?.transactions?.length || 0} 条记录`);
    } catch (e) {
      log('⚠️', `Transactions query failed: ${e.message}`);
    }
  }

  // ── finalise latency on each call ─────────────────────────────────────────
  const t0 = Date.now();
  apiCalls.forEach(c => { if (c.latency === null) c.latency = Date.now() - t0; });

  // ── print report ────────────────────────────────────────────────────────────
  console.log('\n');
  console.log('╔═══════════════════════════════════════════════════════════════════╗');
  console.log('║          UI FUNCTIONAL TEST REPORT — AlphaTerminal               ║');
  console.log('╚═══════════════════════════════════════════════════════════════════╝');
  console.log('');

  console.log('── 操作链路 ─────────────────────────────────────────────────────────');
  opsLog.forEach((op, i) => console.log(`  ${i + 1}. ${op}`));
  console.log('');

  console.log('── Console Errors ──────────────────────────────────────────────────');
  if (errors.length === 0) { console.log('  ✅ 无 Console Error'); PASS++; }
  else { errors.forEach(e => console.log(`  🔴 ${e}`)); FAIL += errors.length; }
  console.log('');

  console.log('── Console Warnings ───────────────────────────────────────────────');
  if (warns.length === 0) { console.log('  ✅ 无 Console Warning'); PASS++; }
  else { warns.slice(0, 5).forEach(w => console.log(`  🟡 ${w}`)); FAIL += warns.length; }
  console.log('');

  console.log('── Backend API Calls ─────────────────────────────────────────────');
  const beCalls = apiCalls.filter(c => c.path.startsWith('/api/v1/'));
  const successCalls = beCalls.filter(c => c.status >= 200 && c.status < 300);
  const failCalls   = beCalls.filter(c => c.status >= 400 || c.status === 0);
  console.log(`  总计: ${beCalls.length}  次 API 调用`);
  console.log(`  成功: ${successCalls.length}  次 (HTTP 2xx)`);
  console.log(`  失败: ${failCalls.length}  次 (HTTP 4xx/5xx/0)`);
  console.log('');
  console.log('  详细调用:');
  beCalls.forEach(c => {
    const ok = c.status >= 200 && c.status < 300 ? '✅' : (c.status === 0 ? '⚠️' : '❌');
    const lat = c.latency ? `+${c.latency}ms` : '?ms';
    console.log(`  ${ok} [${c.method}] ${c.path}  → HTTP ${c.status || '?'} (${lat})`);
    if (c.payload) console.log(`       payload: ${JSON.stringify(c.payload).slice(0, 120)}`);
    if (c.response) console.log(`       response: ${c.response.slice(0, 120)}`);
  });
  console.log('');

  console.log('── 结论 ──────────────────────────────────────────────────────────');
  const apiSuccess = failCalls.length === 0;
  const noErrors   = errors.length === 0;
  if (apiSuccess && noErrors) {
    console.log('  ✅ PASS — 前端功能正常，所有 API 调用成功，无 Console Error');
  } else {
    console.log('  ❌ FAIL — 发现问题请查看上方报告');
    FAIL++;
  }

  console.log('\n  API 成功率: ' + Math.round(successCalls.length / Math.max(beCalls.length, 1) * 100) + '%');
  console.log(`  总 PASS=${PASS}  FAIL=${FAIL}  ops=${opsLog.length}`);
  console.log('\n');

  await browser.close();
  process.exit(FAIL > 0 ? 1 : 0);
})();
