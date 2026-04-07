/**
 * usePortfolioStore — 前端组合状态管理
 * API 基础路径: /api/v1/portfolio
 * 自动轮询PnL，每 20 秒刷新一次
 */
import { ref, computed } from 'vue'

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

async function fetchPnL(pid) {
  const d = await api(`/${pid}/pnl`)
  pnl.value = d
  positions.value = d.positions || []
}

async function fetchSnapshots(pid) {
  const d = await api(`/${pid}/snapshots`)
  snapshots.value = d.snapshots || []
}

async function fetchAll(pid) {
  loading.value = true
  try {
    await Promise.all([fetchPnL(pid), fetchSnapshots(pid)])
  } catch(e) {
    console.warn('[PortfolioStore] fetchAll failed:', e)
  } finally {
    loading.value = false
  }
}

async function switchAccount(pid) {
  activePid.value = pid
  await fetchAll(pid)
}

async function createPortfolio(name, type = 'main') {
  const d = await api('/', {
    method: 'POST',
    body: JSON.stringify({ name, type }),
  })
  await fetchPortfolios()
  return d
}

async function upsertPosition(portfolio_id, symbol, shares, avg_cost) {
  const d = await api('/positions', {
    method: 'POST',
    body: JSON.stringify({ portfolio_id, symbol, shares, avg_cost }),
  })
  // 刷新持仓和PnL
  await fetchPnL(portfolio_id)
  return d
}

async function deletePosition(portfolio_id, symbol) {
  const d = await api(`/${portfolio_id}/positions/${symbol}`, { method: 'DELETE' })
  await fetchPnL(portfolio_id)
  return d
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
export function usePortfolioStore() {
  return {
    // state
    portfolios,
    activePid,
    positions,
    pnl,
    snapshots,
    loading,
    // computed
    activePortfolio: computed(() =>
      portfolios.value.find(p => p.id === activePid.value) || null
    ),
    totalValue:  computed(() => pnl.value?.total_value ?? 0),
    totalCost:   computed(() => pnl.value?.total_cost  ?? 0),
    totalPnl:   computed(() => pnl.value?.total_pnl  ?? 0),
    totalPnlPct: computed(() => pnl.value?.total_pnl_pct ?? 0),
    // actions
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
