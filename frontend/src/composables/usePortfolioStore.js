/**
 * usePortfolioStore — 前端组合状态管理
 * API 基础路径: /api/v1/portfolio
 * 自动轮询PnL，每 20 秒刷新一次
 */
import { ref, computed } from 'vue'
import { logger } from '../utils/logger.js'

const BASE = '/api/v1/portfolio'

// ── 全局状态 ─────────────────────────────────────────────────
const portfolios   = ref([])   // 账户列表
const activePid   = ref(null) // 当前选中账户 id
const positions   = ref([])  // 当前账户持仓
const pnl         = ref(null) // 当前账户实时 PnL
const snapshots   = ref([])  // 当前账户净值历史
const loading     = ref(false)
const pollTimer   = ref(null) // 轮询定时器

// ── 工具 ─────────────────────────────────────────────────────
async function api(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ── Actions ──────────────────────────────────────────────────

async function fetchPortfolios() {
  const d = await api('/')
  portfolios.value = d.portfolios || []
  if (!activePid.value && portfolios.value.length) {
    activePid.value = portfolios.value[0].id
  }
  return portfolios.value
}

async function fetchPnL(pid, includeChildren = false) {
  const query = includeChildren ? '?include_children=true' : ''
  const d = await api(`/${pid}/pnl${query}`)
  pnl.value = d
  positions.value = d.positions || []
  return d
}

async function fetchSnapshots(pid) {
  const d = await api(`/${pid}/snapshots`)
  snapshots.value = d.snapshots || []
}

async function fetchAll(pid, includeChildren = false) {
  // 确保 pid 是原始 id，不是对象
  const id = typeof pid === 'object' && pid !== null ? pid.id : pid
  if (!id) {
    logger.warn('[PortfolioStore] fetchAll: 无效的 pid', pid)
    return
  }
  loading.value = true
  try {
    await Promise.all([fetchPnL(id, includeChildren), fetchSnapshots(id)])
  } catch(e) {
    logger.warn('[PortfolioStore] fetchAll failed:', e)
  } finally {
    loading.value = false
  }
}

async function switchAccount(pid, includeChildren = false) {
  // 确保 pid 是原始 id，不是对象
  const id = typeof pid === 'object' && pid !== null ? pid.id : pid
  if (!id) {
    logger.warn('[PortfolioStore] switchAccount: 无效的 pid', pid)
    return
  }
  activePid.value = id
  await fetchAll(id, includeChildren)
}

async function createPortfolio(name, type = 'main') {
  // 支持 body 对象形式：createPortfolio({ name, type, parent_id })
  const body = typeof name === 'object' ? name : { name, type }
  const res = await fetch(BASE + '/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const body = await res.json()
      msg = body?.message || body?.detail || msg
    } catch (_) {}
    // 清理技术性错误信息
    if (msg.includes('UNIQUE')) msg = '该账户名称已存在，请换一个名字'
    throw new Error(msg)
  }
  await fetchPortfolios()
  return res.json()
}

async function upsertPosition(portfolio_id, symbol, shares, avg_cost) {
  const res = await fetch(BASE + '/positions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ portfolio_id, symbol, shares, avg_cost }),
  })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const body = await res.json()
      msg = body?.message || body?.detail || msg
    } catch (_) {}
    if (msg.includes('UNIQUE')) msg = '该账户名称已存在，请换一个名字'
    throw new Error(msg)
  }
  await fetchPnL(portfolio_id)
  return res.json()
}

async function deletePosition(portfolio_id, symbol) {
  const res = await fetch(`${BASE}/${portfolio_id}/positions/${symbol}`, { method: 'DELETE' })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const body = await res.json()
      msg = body?.message || body?.detail || msg
    } catch (_) {}
    throw new Error(msg)
  }
  await fetchPnL(portfolio_id)
  return res.json()
}

async function saveSnapshot(pid) {
  return api(`/${pid}/snapshots`, { method: 'POST' })
}

// ── 轮询控制 ─────────────────────────────────────────────────

function startPoll(intervalMs = 20_000) {
  stopPoll()
  if (!activePid.value) return
  fetchPnL(activePid.value)
  pollTimer.value = setInterval(() => {
    if (activePid.value) fetchPnL(activePid.value)
  }, intervalMs)
}

function stopPoll() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

// ── 导出 ────────────────────────────────────────────────────
// 必须用 reactive() 包裹，这样 Vue 模板访问 store.portfolios 时会
// 自动解包 ref，不用在 v-for 中写 store.portfolios.value
export function usePortfolioStore() {
  return {
    portfolios,
    activePid,
    positions,
    pnl,
    snapshots,
    loading,
    activePortfolio: computed(() =>
      portfolios.value.find(p => p.id === activePid.value) || null
    ),
    totalValue:  computed(() => pnl.value?.total_value ?? 0),
    totalCost:   computed(() => pnl.value?.total_cost  ?? 0),
    totalPnl:   computed(() => pnl.value?.total_pnl  ?? 0),
    totalPnlPct: computed(() => pnl.value?.total_pnl_pct ?? 0),
    fetchPortfolios,
    fetchPnL,
    fetchSnapshots,
    fetchAll,
    switchAccount,
    createPortfolio,
    upsertPosition,
    deletePosition,
    saveSnapshot,
    startPoll,
    stopPoll,
  }
}
