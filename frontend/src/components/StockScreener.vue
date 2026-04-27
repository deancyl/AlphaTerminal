<template>
  <div class="flex flex-col h-full bg-terminal-bg text-terminal-fg font-mono">
    <div class="flex flex-wrap items-center justify-between px-2 py-1 gap-1 border-b border-theme-secondary shrink-0">
      <div class="flex items-center gap-2 text-xs">
        <span class="text-theme-accent font-bold">全市场个股</span>
        <input type="text" v-model="searchQuery" placeholder="搜索代码/名称"
          class="bg-terminal-bg border border-theme-secondary rounded px-2 py-0.5 text-[11px] focus:border-theme-accent outline-none w-28 h-5" />
        <button @click="showFilter = !showFilter" class="px-1.5 py-0.5 text-[10px] border border-theme-secondary rounded text-terminal-dim hover:border-theme-accent">
          筛选
        </button>
      </div>
      <!-- 可折叠的筛选条件 -->
      <div v-if="showFilter" class="flex items-center gap-2 flex-wrap">
        <div class="flex items-center gap-1 text-[10px]">
          <span class="text-terminal-dim">涨幅></span>
          <input type="number" v-model="flt.change_pct.min" class="w-10 bg-terminal-bg border border-theme-secondary rounded px-1 outline-none text-[10px]" />
        </div>
        <div class="flex items-center gap-1 text-[10px]">
          <span class="text-terminal-dim">换手></span>
          <input type="number" v-model="flt.turnover.min" class="w-10 bg-terminal-bg border border-theme-secondary rounded px-1 outline-none text-[10px]" />
        </div>
        <div class="flex items-center gap-1 text-[10px]">
          <span class="text-terminal-dim">PE<</span>
          <input type="number" v-model="flt.pe.max" class="w-10 bg-terminal-bg border border-theme-secondary rounded px-1 outline-none text-[10px]" />
        </div>
      </div>
    </div>

    <!-- 表头 -->
    <div class="flex items-center px-2 py-0.5 bg-terminal-panel border-b border-theme text-[10px] text-terminal-dim shrink-0">
      <div class="w-5 text-left" @click="setSort('seq')">#</div>
      <div class="w-16 text-left" @click="setSort('name')">名称</div>
      <div class="w-12 text-left" @click="setSort('code')">代码</div>
      <div class="w-12 text-right" @click="setSort('price')">最新</div>
      <div class="w-12 text-right" @click="setSort('change_pct')">涨跌%</div>
      <div class="w-10 text-right" @click="setSort('turnover')">换手</div>
    </div>
    
    <!-- 列表 -->
    <div class="flex-1 overflow-y-auto">
      <div
        v-for="(stock, index) in stocks" 
        :key="stock.code + '-' + index"
        class="flex items-center px-2 py-0.5 border-b border-theme-secondary/20 hover:bg-white/5 transition-colors text-[11px]"
        :class="index % 2 === 0 ? 'bg-terminal-bg' : 'bg-terminal-panel/30'"
        @click="handleClick(stock)"
      >
        <div class="w-5 text-left text-[10px] text-terminal-dim">{{ stock.seq || (currentPage-1)*pageSize + index + 1 }}</div>
        <div class="w-16 text-left truncate text-theme-primary font-medium">{{ stock.name }}</div>
        <div class="w-12 text-left text-[10px] text-terminal-dim">{{ stock.code }}</div>
        <div class="w-12 text-right font-mono" :class="getColor(stock.change_pct)">{{ stock.price?.toFixed(2) }}</div>
        <div class="w-12 text-right font-mono" :class="getColor(stock.change_pct)">
          <span v-if="stock.change_pct > 0">+</span>{{ stock.change_pct?.toFixed(2) }}%
        </div>
        <div class="w-10 text-right text-[10px]">{{ stock.turnover ? stock.turnover.toFixed(1) : '-' }}</div>
      </div>
      <div v-if="!stocks.length" class="px-2 py-4 text-center text-terminal-dim text-xs">
        暂无数据
      </div>
      <div ref="sentinelEl" class="h-px w-full"></div>
    </div>

    <!-- 分页控制栏（固定在底部） -->
    <div class="flex items-center justify-between px-2 py-0.5 text-[10px] border-t border-theme-secondary shrink-0 bg-terminal-panel">
      <button
        class="px-1.5 py-0 border border-theme-secondary rounded hover:bg-theme-secondary/50 disabled:opacity-30 disabled:cursor-not-allowed"
        :disabled="currentPage === 1"
        @click="goPage(currentPage - 1)">‹</button>
      <div class="text-terminal-dim">
        {{ currentPage }} / {{ totalPages }}
      </div>
      <button
        class="px-1.5 py-0 border border-theme-secondary rounded hover:bg-theme-secondary/50 disabled:opacity-30 disabled:cursor-not-allowed"
        :disabled="currentPage >= totalPages"
        @click="goPage(currentPage + 1)">›</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { logger } from '../utils/logger.js'
import { useMarketStore } from '../stores/market.js'
import { fmtPrice, fmtPct, fmtChg, fmtTurnover } from '../utils/formatters.js'
import { apiFetch } from '../utils/api.js'

const emit = defineEmits(['symbol-click'])
const { setSymbol } = useMarketStore()

// ── 服务端分页数据状态 ─────────────────────────────────────────────
const stocks       = ref([])
const total        = ref(0)
const currentPage  = ref(1)
const pageSize     = ref(10)  // 移动端每页10个
const totalPages  = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

// ── 本地 UI 状态 ─────────────────────────────────────────────────────
const loading     = ref(false)
const sentinelEl  = ref(null)
const searchQuery = ref('')
const showFilter  = ref(false)  // 筛选面板显示状态
const sortBy      = ref('change_pct')
const sortDir     = ref('desc')

// ── 过滤条件 ─────────────────────────────────────────────────────────
const flt = ref({
  change_pct: { min: null, max: null },
  turnover:   { min: null, max: null },
  pe:         { min: null, max: null },
})

// ── 核心：服务端搜索（防抖 300ms）────────────────────────────────────
async function fetchStocks() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (searchQuery.value.trim()) params.set('keyword', searchQuery.value.trim())
    if (flt.value.change_pct.min != null) params.set('min_pct_chg', flt.value.change_pct.min)
    if (flt.value.turnover.min   != null) params.set('min_turnover', flt.value.turnover.min)
    if (flt.value.pe.max         != null) params.set('max_pe',       flt.value.pe.max)
    params.set('sort_by',   sortBy.value)
    params.set('sort_dir',  sortDir.value)
    params.set('page',      String(currentPage.value))
    params.set('page_size', String(pageSize.value))

    const d = await apiFetch(`/api/v1/market/stocks/search?${params}`)
    const payload = d?.data || d || {}
    stocks.value = (payload.stocks || []).map((s, i) => ({ ...s, seq: (currentPage.value - 1) * pageSize.value + i + 1 }))
    total.value  = payload.total || 0
  } catch (e) {
    logger.warn('[StockScreener] fetchStocks failed:', e.message)
  } finally {
    loading.value = false
  }
}

const debouncedFetch = useDebounceFn(fetchStocks, 300)

// ── 辅助 ──────────────────────────────────────────────────────────────
function getColor(val) {
  if (!val && val !== 0) return ''
  return val >= 0 ? 'text-bullish' : 'text-bearish'
}

function formatAmount(v) {
  if (!v) return '--'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return Number(v).toFixed(2)
}

function sortClass(col) {
  return sortBy.value === col ? 'text-theme-accent' : ''
}

// ── 排序控制 ──────────────────────────────────────────────────────────
function setSort(col) {
  if (sortBy.value === col) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = col
    sortDir.value = 'desc'
  }
  currentPage.value = 1
  debouncedFetch()
}

// ── 分页控制 ──────────────────────────────────────────────────────────
function goPage(p) {
  currentPage.value = Math.max(1, Math.min(p, totalPages.value))
  debouncedFetch()
}

// ── 搜索/过滤变化 → 重置到第1页，深度监听所有筛框 ─────────────────────
watch(flt, () => { currentPage.value = 1; debouncedFetch() }, { deep: true })

// ── 点击个股 ──────────────────────────────────────────────────────────
function handleClick(stock) {
  // 确保数字代码加上 sh/sz 前缀（normalizeSymbol 依赖 registry 加载，
  // 可能未就绪，所以手动处理常见情况）
  let sym = stock.code
  if (/^\d{6}$/.test(sym)) {
    const prefix = sym.startsWith('6') || sym.startsWith('9') || sym.startsWith('000') ? 'sh' : 'sz'
    sym = prefix + sym
  }
  setSymbol(sym, stock.name, (stock.change_pct || 0) >= 0 ? '#ef232a' : '#14b143')
  // 同步 selectedIndex，触发 IndexLineChart 刷新（通过 emit 通知父组件）
  emit('symbol-click', { symbol: sym, name: stock.name })
}

// ── 重置过滤 ───────────────────────────────────────────────────────────
function resetFilter() {
  flt.value = { change_pct: { min: null, max: null }, turnover: { min: null, max: null },
                amount: { min: null, max: null }, price: { min: null, max: null },
                pe: { min: null, max: null }, pb: { min: null, max: null } }
  currentPage.value = 1
  debouncedFetch()
}

// ── 空操作 ─────────────────────────────────────────────────────────────
function toggleFilterPanel() {}

onMounted(debouncedFetch)

// ── 无限滚动触底触发（双重保险：IntersectionObserver + scroll 兜底）────────
let _observer = null
let _scrollHandler = null

function tryAutoNextPage() {
  if (loading.value) return
  if (currentPage.value >= totalPages.value) return
  goPage(currentPage.value + 1)
}

function setupSentinel(scrollContainer) {
  // 防御：sentinelEl 尚未挂载时等待下一帧
  if (!sentinelEl.value) {
    const ro = new ResizeObserver(() => {
      if (sentinelEl.value) {
        ro.disconnect()
        setupSentinel(scrollContainer)
      }
    })
    ro.observe(scrollContainer)
    return
  }

  // IntersectionObserver：sentinel 进入视口 → 自动加载下一页
  _observer = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting) tryAutoNextPage()
    },
    { root: scrollContainer, threshold: 0 }
  )
  _observer.observe(sentinelEl.value)

  // Scroll 兜底：滚动速度过快时 IntersectionObserver 可能漏触发
  _scrollHandler = () => {
    const el = scrollContainer
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 200) {
      tryAutoNextPage()
    }
  }
  scrollContainer.addEventListener('scroll', _scrollHandler, { passive: true })
}

onMounted(() => {
  debouncedFetch()
  // 等待表格渲染后以 .closest() 找最近的滚动父容器
  const tableWrapper = sentinelEl.value?.closest('.overflow-y-auto')
  if (tableWrapper) {
    // 表格高度可能为 0（数据未加载），等数据渲染后再初始化
    const ro = new ResizeObserver(() => {
      if (tableWrapper.clientHeight > 0) {
        ro.disconnect()
        setupSentinel(tableWrapper)
      }
    })
    ro.observe(tableWrapper)
  }
})

onUnmounted(() => {
  _observer?.disconnect()
  const tableWrapper = sentinelEl.value?.closest('.overflow-y-auto')
  if (tableWrapper && _scrollHandler) {
    tableWrapper.removeEventListener('scroll', _scrollHandler)
  }
})
</script>