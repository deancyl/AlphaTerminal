/**
 * ui_functional_test.js — Phase 2 升级版
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
  log('①', `【${label}】STEP 1 — 导航到「投资组合」`);
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
  log('②', `【${label}】STEP 2 — 打开「新建账户」弹窗`);
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
    log('⚠️', '新建 button not found — trying any button with 新建');
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
  log('③', `【${label}】STEP 3 — 填写账户表单`);
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
  log('④', `【${label}】STEP 4 — 提交「创建账户」`);
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
  log('⑤', `【${label}】STEP 5 — 定位账户 ID`);
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
  log('⑥', `【${label}】STEP 6 — 资金划转（主→子）`);
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
  log('⑦', `【${label}】STEP 7 — 查询流水接口`);
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

// ══════════════════════════════════════════════════════════════════════════════
//  Phase Roll-up: 子账户树形 PnL 聚合 — 自动化验证
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
  log('🔍', '[守恒测试] Step 1 — 获取账户列表');
  const listRes = await api('/portfolio/');
  const portfolios = listRes.data.portfolios || [];
  const parent = portfolios.find(p => p.type === 'main');
  const child  = portfolios.find(p => p.parent_id === parent?.id);

  if (!parent) { console.log('❌ 无主账户，跳过守恒测试'); return results; }
  console.log(`  主账户: id=${parent.id} "${parent.name}"`);
  if (child) console.log(`  子账户: id=${child.id} "${child.name}"`);
  else console.log('  ⚠️  无子账户，跳过划转测试');

  // ── Step 2: 守恒定律验证（划转前）────────────────────────────────
  log('🔍', '[守恒测试] Step 2 — 守恒定律验证（划转前）');
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
  log('🔍', '[守恒测试] Step 3 — 树形端点 /tree');
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
    log('🔍', `[守恒测试] Step 4 — 子账户间划转 ¥1000（${parent.name} → ${child.name}）`);
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
    log('🔍', '[守恒测试] Step 5 — 守恒定律验证（划转后）');
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
    log('🔍', `[守恒测试] Step 6 — 回滚划转 ¥1000（${child.name} → ${parent.name}）`);
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
  log('🔍', '[守恒测试] Step 7 — include_children 各端点验证');
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
  console.log('   PHASE 4 — CHART DOM VERIFICATION      ');
  console.log('═══════════════════════════════════════');
  for (const { label, fatal } of results) {
    if (!fatal) {
      const ctxChart = await browser.newContext();
      const pageChart = await ctxChart.newPage();
      const chartResult = await runChartTests(pageChart, label.split(' ')[0].toLowerCase());
      results.push(chartResult);
      await ctxChart.close();
    }
  }

  await browser.close();

  // ── Phase Roll-up: 子账户树形聚合 + 守恒定律验证 ─────────────
  console.log('\n═══════════════════════════════════════');
  console.log('   PHASE ROLL-UP — TREE PNL + CONSERVATION  ');
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

  printReport(results);

  const totalFails = results.reduce((s, r) => s + r.errors.filter(e => !e.includes('⚠️')).length, 0);
  process.exit((!allPass || totalFails > 0) ? 1 : 0);
})();

// ═══════════════════════════════════════════════════════════════
//  Phase 4 Extended Tests — Chart & DOM Verification
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

    // Navigate to portfolio
    try {
      await page.locator('button').filter({ hasText: '💰' }).first().click({ force: true });
      opsLog.push('CLICK sidebar[💰]');
      await page.waitForTimeout(2000);
    } catch (_) {}

    // Wait for async data (lots/echarts endpoint)
    await page.waitForTimeout(5000);

    opsLog.push('WAIT 5s for chart rendering');

    // ── Check 1: .echart-container exists and has size ─────────────────
    const echartExists = await page.locator('.echart-container').count();
    const echartBox    = echartExists > 0 ? await page.locator('.echart-container').first().boundingBox() : null;
    opsLog.push(`ECHARTS DOM: count=${echartExists} boundingBox=${JSON.stringify(echartBox)}`);
    log('🔍', `echart-container: count=${echartExists} box=${JSON.stringify(echartBox)}`);

    // ── Check 2: .lots-table exists (OpenLotsPanel) ──────────────────
    const lotsTableExists = await page.locator('.lots-table').count();
    opsLog.push(`LOTS TABLE DOM: count=${lotsTableExists}`);
    log('🔍', `lots-table: count=${lotsTableExists}`);

    // ── Check 3: .pnl-card exists (PnL cards row) ─────────────────────
    const pnlCardCount = await page.locator('.pnl-card').count();
    opsLog.push(`PNL CARDS DOM: count=${pnlCardCount}`);
    log('🔍', `pnl-card: count=${pnlCardCount}`);

    // ── Check 4: Pie legend items ──────────────────────────────────────
    const legendCount = await page.locator('.legend-item').count();
    opsLog.push(`PIE LEGEND ITEMS: count=${legendCount}`);
    log('🔍', `legend-item: count=${legendCount}`);

    // ── Check 5: Backend API calls for lots/echarts ──────────────────
    const echartsCall = Array.from(reqMap.values()).find(c => c.path.includes('lots/echarts'));
    const pnlCall     = Array.from(reqMap.values()).find(c => c.path.includes('/pnl'));
    if (echartsCall) opsLog.push(`API /lots/echarts → HTTP ${echartsCall.status}`);
    if (pnlCall)    opsLog.push(`API /pnl → HTTP ${pnlCall.status}`);

    // ── Summary ────────────────────────────────────────────────────────
    const domChecks = [
      { name: 'ECharts DOM (.echart-container)', pass: echartExists > 0 },
      { name: 'Lots Table (.lots-table)',      pass: lotsTableExists > 0 },
      { name: 'PnL Cards (.pnl-card)',          pass: pnlCardCount >= 3 },
      { name: 'Pie Legend (.legend-item)',       pass: legendCount > 0 },
      { name: '/lots/echarts API',              pass: echartsCall?.status === 200 },
      { name: '/pnl API',                       pass: pnlCall?.status === 200 },
    ];

    console.log(`\n╔═══ ${label} DOM 检测 ══════════════════════════════════════════╗`);
    domChecks.forEach((c, i) => {
      const icon = c.pass ? '✅' : '❌';
      console.log(`║  ${icon} ${c.name}: ${c.pass ? 'PASS' : 'FAIL'}`);
    });
    const domPass = domChecks.every(c => c.pass);
    console.log(`║                                                        ║`);
    console.log(`║  结论: ${domPass ? '✅ DOM 渲染通过' : '❌ 部分 DOM 未就绪'}                       ║`);
    console.log(`╚════════════════════════════════════════════════════════════╝`);

    return { label, errors, warns, apiCalls: Array.from(reqMap.values()), opsLog, domPass };
  } catch (e) {
    log('❌', `${label} failed: ${e.message}`);
    return { label, errors, warns, apiCalls: [], opsLog, fatal: true };
  }
}
