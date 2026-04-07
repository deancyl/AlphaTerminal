<template>
  <div class="flex h-full overflow-hidden bg-terminal-bg">

    <!-- ═══ 左侧边栏：账户选择 + 总览 ════════════════════════ -->
    <div class="w-44 shrink-0 flex flex-col gap-1 p-2 border-r border-gray-700 overflow-y-auto">

      <!-- 标题 -->
      <div class="flex items-center justify-between mb-1">
        <span class="text-terminal-accent font-bold text-sm">💰 投资组合</span>
        <button @click="showCreateModal = true"
                class="text-[10px] px-1.5 py-0.5 rounded border border-terminal-accent/40 text-terminal-accent hover:bg-terminal-accent/10 transition">
          + 新建
        </button>
      </div>

      <!-- 账户列表 -->
      <div v-for="acc in store.portfolios" :key="acc.id"
           class="rounded border p-2 cursor-pointer transition-all text-xs"
           :class="acc.id === store.activePid
             ? 'border-terminal-accent/60 bg-terminal-accent/10'
             : 'border-gray-700 hover:border-gray-500'"
           @click="handleSwitch(acc.id)">
        <div class="flex items-center justify-between">
          <span class="text-gray-200 font-medium">{{ acc.name }}</span>
          <span class="text-[9px] text-terminal-dim">{{ acc.type === 'main' ? '主账户' : '子账户' }}</span>
        </div>
        <!-- 实时总览（仅选中账户显示） -->
        <div v-if="acc.id === store.activePid && store.pnl" class="mt-1.5 grid grid-cols-2 gap-x-1">
          <div>
            <div class="text-[9px] text-terminal-dim">总资产</div>
            <div class="text-[10px] font-mono text-gray-200">{{ fmtYuan(store.totalValue) }}</div>
          </div>
          <div>
            <div class="text-[9px] text-terminal-dim">累计盈亏</div>
            <div class="text-[10px] font-mono" :class="store.totalPnl >= 0 ? 'text-red-400' : 'text-green-400'">
              {{ store.totalPnl >= 0 ? '+' : '' }}{{ fmtYuan(store.totalPnl) }}
            </div>
          </div>
          <div class="col-span-2">
            <div class="text-[9px] text-terminal-dim">盈亏率</div>
            <div class="text-[10px] font-mono" :class="store.totalPnlPct >= 0 ? 'text-red-400' : 'text-green-400'">
              {{ store.totalPnlPct >= 0 ? '+' : '' }}{{ store.totalPnlPct }}%
            </div>
          </div>
        </div>
      </div>

      <!-- 刷新按钮 -->
      <button @click="handleRefresh"
              class="mt-1 w-full py-1 rounded border border-gray-700 text-[10px] text-terminal-dim hover:border-terminal-accent/40 hover:text-gray-300 transition">
        🔄 刷新
      </button>

      <!-- 净值曲线图 -->
      <div class="mt-2">
        <div class="text-[9px] text-terminal-dim mb-1">📈 净值走势</div>
        <div ref="chartEl" class="w-full" style="height: 120px;"></div>
      </div>
    </div>

    <!-- ═══ 右侧主区域 ══════════════════════════════════════ -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">

      <!-- 操作栏 -->
      <div class="flex items-center gap-2 px-3 py-1.5 border-b border-gray-700 shrink-0">
        <span class="text-xs text-terminal-dim">
          {{ store.activePortfolio?.name }} — 持仓 {{ store.positions.length }} 只
        </span>
        <div class="flex items-center gap-1 ml-auto text-[10px]">
          <span class="text-terminal-dim">排序:</span>
          <button v-for="col in sortCols" :key="col.key"
                  class="px-1.5 py-0.5 rounded border transition"
                  :class="sortKey === col.key ? 'border-terminal-accent/50 text-terminal-accent' : 'border-gray-700 text-gray-400 hover:border-gray-500'"
                  @click="setSort(col.key)">
            {{ col.label }}
          </button>
        </div>
        <button @click="showTradeModal = true"
                class="ml-2 px-3 py-1 rounded bg-terminal-accent/20 border border-terminal-accent/50 text-terminal-accent text-[10px] hover:bg-terminal-accent/30 transition">
          + 调仓
        </button>
      </div>

      <!-- 持仓明细表 -->
      <div class="flex-1 overflow-y-auto">
        <table class="w-full text-[10px]">
          <thead class="sticky top-0 z-10 bg-terminal-panel text-terminal-dim">
            <tr class="border-b border-gray-700">
              <th class="text-left py-1 px-2">代码</th>
              <th class="text-left py-1 px-2">名称</th>
              <th class="text-right py-1 px-2">持仓(股)</th>
              <th class="text-right py-1 px-2">成本价</th>
              <th class="text-right py-1 px-2">现价</th>
              <th class="text-right py-1 px-2">市值</th>
              <th class="text-right py-1 px-2">浮动盈亏</th>
              <th class="text-right py-1 px-2">盈亏率</th>
              <th class="text-right py-1 px-2">占比</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="pos in sortedPositions" :key="pos.symbol"
                class="border-b border-gray-800 hover:bg-white/4 cursor-pointer transition"
                @click="openTrade(pos)">
              <td class="py-1 px-2 text-terminal-dim font-mono">{{ pos.symbol }}</td>
              <td class="py-1 px-2 text-gray-200">{{ pos.symbol }}</td>
              <td class="py-1 px-2 text-right font-mono">{{ pos.shares }}</td>
              <td class="py-1 px-2 text-right font-mono text-gray-300">{{ pos.avg_cost }}</td>
              <td class="py-1 px-2 text-right font-mono text-gray-300">{{ pos.price }}</td>
              <td class="py-1 px-2 text-right font-mono text-gray-200">{{ fmtYuan(pos.market_value) }}</td>
              <td class="py-1 px-2 text-right font-mono" :class="pos.pnl >= 0 ? 'text-red-400' : 'text-green-400'">
                {{ pos.pnl >= 0 ? '+' : '' }}{{ fmtYuan(pos.pnl) }}
              </td>
              <td class="py-1 px-2 text-right font-mono" :class="pos.pnl_pct >= 0 ? 'text-red-400' : 'text-green-400'">
                {{ pos.pnl_pct >= 0 ? '+' : '' }}{{ pos.pnl_pct }}%
              </td>
              <td class="py-1 px-2 text-right text-terminal-dim">
                {{ store.totalValue > 0 ? ((pos.market_value / store.totalValue) * 100).toFixed(1) + '%' : '--' }}
              </td>
            </tr>
            <tr v-if="!sortedPositions.length">
              <td colspan="9" class="py-8 text-center text-terminal-dim">
                {{ store.loading ? '加载中...' : '暂无持仓，请点击 [+ 调仓] 添加' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ═══ 调仓弹窗 ══════════════════════════════════════════ -->
    <div v-if="showTradeModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div class="bg-terminal-panel border border-gray-600 rounded-xl w-80 p-4 shadow-2xl">
        <div class="text-sm font-bold text-gray-200 mb-3">
          {{ tradeTarget ? '调整持仓' : '新建仓位' }}
        </div>

        <!-- 标的 -->
        <div class="mb-2">
          <label class="text-[10px] text-terminal-dim">股票代码</label>
          <input v-model="tradeForm.symbol" type="text" placeholder="如 600519"
                 class="mt-1 w-full bg-terminal-bg border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 outline-none focus:border-terminal-accent" />
        </div>

        <!-- 股数 -->
        <div class="mb-2">
          <label class="text-[10px] text-terminal-dim">持仓股数（填 0 则清仓）</label>
          <input v-model.number="tradeForm.shares" type="number" min="0" placeholder="0"
                 class="mt-1 w-full bg-terminal-bg border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 outline-none focus:border-terminal-accent" />
        </div>

        <!-- 成本价 -->
        <div class="mb-3">
          <label class="text-[10px] text-terminal-dim">成本价（元）</label>
          <input v-model.number="tradeForm.avg_cost" type="number" min="0" step="0.001" placeholder="0.00"
                 class="mt-1 w-full bg-terminal-bg border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 outline-none focus:border-terminal-accent" />
        </div>

        <div class="flex gap-2 justify-end">
          <button @click="showTradeModal = false"
                  class="px-3 py-1 rounded border border-gray-600 text-xs text-gray-400 hover:text-gray-200 transition">
            取消
          </button>
          <button @click="submitTrade"
                  class="px-3 py-1 rounded bg-terminal-accent/20 border border-terminal-accent/50 text-xs text-terminal-accent hover:bg-terminal-accent/30 transition">
            确认
          </button>
        </div>
      </div>
    </div>

    <!-- ═══ 新建账户弹窗 ══════════════════════════════════════ -->
    <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div class="bg-terminal-panel border border-gray-600 rounded-xl w-72 p-4 shadow-2xl">
        <div class="text-sm font-bold text-gray-200 mb-3">新建账户</div>
        <div class="mb-2">
          <label class="text-[10px] text-terminal-dim">账户名称</label>
          <input v-model="createForm.name" type="text" placeholder="如：教育基金"
                 class="mt-1 w-full bg-terminal-bg border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 outline-none focus:border-terminal-accent" />
        </div>
        <div class="mb-3">
          <label class="text-[10px] text-terminal-dim">账户类型</label>
          <select v-model="createForm.type"
                  class="mt-1 w-full bg-terminal-bg border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 outline-none">
            <option value="main">主账户</option>
            <option value="special_plan">子账户</option>
          </select>
        </div>
        <div class="flex gap-2 justify-end">
          <button @click="showCreateModal = false"
                  class="px-3 py-1 rounded border border-gray-600 text-xs text-gray-400 hover:text-gray-200 transition">取消</button>
          <button @click="submitCreate"
                  class="px-3 py-1 rounded bg-terminal-accent/20 border border-terminal-accent/50 text-xs text-terminal-accent hover:bg-terminal-accent/30 transition">创建</button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { usePortfolioStore } from '../composables/usePortfolioStore.js'

const store = usePortfolioStore()

// ── 状态 ──────────────────────────────────────────────────────
const chartEl      = ref(null)
const sortKey      = ref('pnl_pct')
const sortAsc      = ref(false)
const showTradeModal = ref(false)
const showCreateModal = ref(false)
const tradeTarget  = ref(null)
const chart        = ref(null)

const sortCols = [
  { key: 'symbol',     label: '代码' },
  { key: 'pnl_pct',   label: '盈亏率' },
  { key: 'market_value', label: '市值' },
  { key: 'shares',     label: '股数' },
]

const tradeForm = ref({ symbol: '', shares: 0, avg_cost: 0 })
const createForm = ref({ name: '', type: 'main' })

// ── 排序 ──────────────────────────────────────────────────────
const sortedPositions = computed(() => {
  if (!store.positions.length) return []
  const key = sortKey.value
  const dir = sortAsc.value ? 1 : -1
  return [...store.positions].sort((a, b) => {
    const av = a[key] ?? 0
    const bv = b[key] ?? 0
    return (av < bv ? -1 : av > bv ? 1 : 0) * dir
  })
})

function setSort(key) {
  if (sortKey.value === key) sortAsc.value = !sortAsc.value
  else { sortKey.value = key; sortAsc.value = false }
}

// ── 调仓 ─────────────────────────────────────────────────────
function openTrade(pos) {
  tradeTarget.value = pos
  tradeForm.value = { symbol: pos.symbol, shares: pos.shares, avg_cost: pos.avg_cost }
  showTradeModal.value = true
}

async function submitTrade() {
  if (!tradeForm.value.symbol) return
  await store.upsertPosition(
    store.activePid,
    tradeForm.value.symbol,
    tradeForm.value.shares,
    tradeForm.value.avg_cost,
  )
  showTradeModal.value = false
}

async function submitCreate() {
  if (!createForm.value.name) return
  await store.createPortfolio(createForm.value.name, createForm.value.type)
  showCreateModal.value = false
}

async function handleSwitch(pid) {
  await store.switchAccount(pid)
  await nextTick()
  renderChart()
}

async function handleRefresh() {
  if (store.activePid) await store.fetchAll(store.activePid)
}

// ── ECharts 净值曲线 ──────────────────────────────────────────
function renderChart() {
  if (!chartEl.value || !store.snapshots.length) return
  if (!chart.value) {
    chart.value = echarts.init(chartEl.value, 'dark')
  }
  const dates = store.snapshots.map(s => s.date)
  const assets = store.snapshots.map(s => s.total_asset)
  const costs  = store.snapshots.map(s => s.total_cost)

  chart.value.setOption({
    backgroundColor: 'transparent',
    grid: { top: 8, bottom: 8, left: 48, right: 8 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1e2130',
      borderColor: '#374151',
      textStyle: { color: '#9ca3af', fontSize: 9 },
      formatter: (params) => {
        const d = params[0]
        return `${d.axisValue}<br/>资产: <b>${fmtYuan(d.value)}</b>`
      }
    },
    xAxis: {
      type: 'category', data: dates,
      axisLabel: { color: '#6b7280', fontSize: 8, rotate: 30 },
      axisLine: { lineStyle: { color: '#374151' } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#6b7280', fontSize: 8, formatter: v => (v/1e4).toFixed(0)+'w' },
      splitLine: { lineStyle: { color: '#1f2937' } },
      axisLine: { show: false },
    },
    series: [
      {
        name: '总资产', type: 'line',
        data: assets,
        smooth: true,
        lineStyle: { color: '#60a5fa', width: 1.5 },
        itemStyle: { color: '#60a5fa' },
        areaStyle: { color: new echarts.graphic.LinearGradient(0,0,0,1,[
          { offset: 0, color: 'rgba(96,165,250,0.3)' },
          { offset: 1, color: 'rgba(96,165,250,0)' },
        ])},
        symbol: 'none',
      },
      {
        name: '总成本', type: 'line',
        data: costs,
        smooth: true,
        lineStyle: { color: '#6b7280', width: 1, type: 'dashed' },
        itemStyle: { color: '#6b7280' },
        symbol: 'none',
      },
    ],
  })
}

// ── 工具函数 ─────────────────────────────────────────────────
function fmtYuan(v) {
  if (!v && v !== 0) return '--'
  if (Math.abs(v) >= 1e8) return (v/1e8).toFixed(2) + '亿'
  if (Math.abs(v) >= 1e4) return (v/1e4).toFixed(2) + '万'
  return v.toFixed(2)
}

// ── 生命周期 ─────────────────────────────────────────────────
onMounted(async () => {
  await store.fetchPortfolios()
  if (store.activePid) await store.fetchAll(store.activePid)
  store.startPoll(20_000)  // 每 20 秒刷新 PnL
  await nextTick()
  renderChart()
})

onUnmounted(() => {
  store.stopPoll()
  chart.value?.dispose()
})

// snapshots 变化时重绘图表
watch(() => store.snapshots.length, () => {
  nextTick(renderChart)
})

// 窗口 resize 时重绘
window.addEventListener('resize', () => chart.value?.resize())
</script>
