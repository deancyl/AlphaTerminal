<template>
  <div class="flex flex-col h-full bg-terminal-bg text-terminal-fg font-mono">
    <div class="flex flex-wrap items-center justify-between p-2 gap-2 border-b border-theme-secondary shrink-0">
      <div class="flex items-center gap-4 text-xs">
        <span class="text-theme-accent font-bold">全市场个股</span>
        <div class="flex items-center gap-1">
          <input type="text" v-model="searchQuery" placeholder="输入拼音/代码/名称"
            class="bg-terminal-bg border border-theme-secondary rounded px-2 py-1 focus:border-theme-accent outline-none w-32" />
        </div>
      </div>
      <div class="flex items-center gap-3 flex-wrap">
        <div class="flex items-center gap-1 text-xs">
          <span class="text-terminal-dim">涨跌幅 ></span>
          <input type="number" v-model="flt.change_pct.min" class="w-12 bg-terminal-bg border border-theme-secondary rounded px-1 outline-none focus:border-theme-accent" />
          <span class="text-terminal-dim">%</span>
        </div>
        <div class="flex items-center gap-1 text-xs">
          <span class="text-terminal-dim">换手率 ></span>
          <input type="number" v-model="flt.turnover.min" class="w-12 bg-terminal-bg border border-theme-secondary rounded px-1 outline-none focus:border-theme-accent" />
          <span class="text-terminal-dim">%</span>
        </div>
        <div class="flex items-center gap-1 text-xs">
          <span class="text-terminal-dim">PE <</span>
          <input type="number" v-model="flt.pe.max" class="w-12 bg-terminal-bg border border-theme-secondary rounded px-1 outline-none focus:border-theme-accent" />
        </div>
        <div class="flex items-center gap-1 text-xs">
          <span class="text-terminal-dim">PB <</span>
          <input type="number" v-model="flt.pb.max" class="w-12 bg-terminal-bg border border-theme-secondary rounded px-1 outline-none focus:border-theme-accent" />
        </div>
        <div class="flex items-center gap-1 text-xs">
          <span class="text-terminal-dim">价格区间</span>
          <input type="number" v-model="flt.price.min" placeholder="低" class="w-12 bg-terminal-bg border border-theme-secondary rounded px-1 outline-none focus:border-theme-accent" />
          <span class="text-terminal-dim">~</span>
          <input type="number" v-model="flt.price.max" placeholder="高" class="w-12 bg-terminal-bg border border-theme-secondary rounded px-1 outline-none focus:border-theme-accent" />
        </div>
        <div class="flex items-center gap-1 text-xs">
          <span class="text-terminal-dim">市值(亿)</span>
          <input type="number" v-model="flt.mktcap.min" placeholder="低" class="w-12 bg-terminal-bg border border-theme-secondary rounded px-1 outline-none focus:border-theme-accent" />
          <span class="text-terminal-dim">~</span>
          <input type="number" v-model="flt.mktcap.max" placeholder="高" class="w-12 bg-terminal-bg border border-theme-secondary rounded px-1 outline-none focus:border-theme-accent" />
        </div>
      </div>
    </div>

    <!-- 单表结构：Sticky 表头 + 滚动 tbody + 固定分页栏 -->
    <div class="flex-1 min-h-0 overflow-y-auto relative">
      <table class="w-full text-xs whitespace-nowrap">
        <thead class="bg-terminal-panel sticky top-0 z-10 shadow-sm">
          <tr class="text-terminal-dim border-b border-theme">
            <th class="px-2 py-1.5 text-left font-normal w-12">#</th>
            <th class="px-2 py-1.5 text-left font-normal cursor-pointer" @click="setSort('name')">名称</th>
            <th class="px-2 py-1.5 text-left font-normal cursor-pointer" @click="setSort('code')">代码</th>
            <th class="px-2 py-1.5 text-right font-normal cursor-pointer" @click="setSort('price')">最新价</th>
            <th class="px-2 py-1.5 text-right font-normal cursor-pointer" @click="setSort('change_pct')">涨跌幅</th>
            <th class="px-2 py-1.5 text-right font-normal cursor-pointer" @click="setSort('change')">涨跌</th>
            <th class="px-2 py-1.5 text-right font-normal cursor-pointer" @click="setSort('turnover')">换手率</th>
            <th class="px-2 py-1.5 text-right font-normal cursor-pointer" @click="setSort('amount')">成交额</th>
            <th class="px-2 py-1.5 text-right font-normal cursor-pointer" @click="setSort('pe')">PE</th>
            <th class="px-2 py-1.5 text-right font-normal cursor-pointer" @click="setSort('pb')">PB</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(stock, index) in stocks" :key="stock.code + '-' + index"
              class="border-b border-theme-secondary/30 hover:bg-theme-secondary/20 transition-colors group">
            <td class="px-2 py-1.5 text-terminal-dim">{{ stock.seq || (currentPage-1)*pageSize + index + 1 }}</td>
            <td class="px-2 py-1.5">
              <div class="font-medium group-hover:text-theme-accent transition-colors">{{ stock.name }}</div>
            </td>
            <td class="px-2 py-1.5 text-terminal-dim">{{ stock.code }}</td>
            <td class="px-2 py-1.5 text-right" :class="getColor(stock.change_pct)">{{ stock.price?.toFixed(2) }}</td>
            <td class="px-2 py-1.5 text-right" :class="getColor(stock.change_pct)">
              <span v-if="stock.change_pct > 0">+</span>{{ stock.change_pct?.toFixed(2) }}%
            </td>
            <td class="px-2 py-1.5 text-right" :class="getColor(stock.change)">
              <span v-if="stock.change > 0">+</span>{{ stock.change?.toFixed(2) }}
            </td>
            <td class="px-2 py-1.5 text-right">{{ stock.turnover ? stock.turnover.toFixed(2) + '%' : '-' }}</td>
            <td class="px-2 py-1.5 text-right">{{ formatAmount(stock.amount) }}</td>
            <td class="px-2 py-1.5 text-right">{{ stock.pe ? stock.pe.toFixed(1) : '-' }}</td>
            <td class="px-2 py-1.5 text-right">{{ stock.pb ? stock.pb.toFixed(2) : '-' }}</td>
          </tr>
        </tbody>
      </table>

      <!-- Sentinel for infinite scroll trigger -->
      <div ref="sentinelEl" class="h-px w-full"></div>

      <!-- 加载中遮罩 -->
      <div v-if="loading" class="absolute inset-0 bg-terminal-bg/50 backdrop-blur-sm flex items-center justify-center z-20">
        <span class="text-theme-accent">检索中...</span>
      </div>
    </div>

    <!-- 分页控制栏（固定在底部） -->
    <div class="flex items-center justify-between p-2 text-xs border-t border-theme-secondary shrink-0 bg-terminal-panel">
      <button
        class="px-3 py-1 border border-theme-secondary rounded hover:bg-theme-secondary/50 disabled:opacity-30 disabled:cursor-not-allowed"
        :disabled="currentPage === 1"
        @click="goPage(currentPage - 1)">上一页</button>
      <div class="text-terminal-dim">
        第 <span class="text-terminal-fg font-bold">{{ currentPage }}</span> / {{ totalPages }} 页
      </div>
      <button
        class="px-3 py-1 border border-theme-secondary rounded hover:bg-theme-secondary/50 disabled:opacity-30 disabled:cursor-not-allowed"
        :disabled="currentPage >= totalPages"
        @click="goPage(currentPage + 1)">下一页</button>
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

const { setSymbol } = useMarketStore()

// ── 服务端分页数据状态 ─────────────────────────────────────────────
const stocks       = ref([])
const total        = ref(0)
const currentPage  = ref(1)
const pageSize     = ref(50)
const totalPages  = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

// ── 本地 UI 状态 ─────────────────────────────────────────────────────
const loading     = ref(false)
const sentinelEl  = ref(null)
const searchQuery = ref('')
const sortBy      = ref('change_pct')
const sortDir     = ref('desc')

// ── 过滤条件 ─────────────────────────────────────────────────────────
const flt = ref({
  change_pct: { min: null, max: null },
  turnover:   { min: null, max: null },
  amount:     { min: null, max: null },
  price:      { min: null, max: null },
  pe:         { min: null, max: null },
  pb:         { min: null, max: null },
  mktcap:     { min: null, max: null },  // 市值（亿元）
})

// ── 核心：服务端搜索（防抖 300ms）────────────────────────────────────
async function fetchStocks() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (searchQuery.value.trim()) params.set('keyword', searchQuery.value.trim())
    if (flt.value.change_pct.min != null) params.set('min_pct_chg', flt.value.change_pct.min)
    if (flt.value.change_pct.max != null) params.set('max_pct_chg', flt.value.change_pct.max)
    if (flt.value.turnover.min   != null) params.set('min_turnover', flt.value.turnover.min)
    if (flt.value.turnover.max   != null) params.set('max_turnover', flt.value.turnover.max)
    if (flt.value.pe.min         != null) params.set('min_pe',       flt.value.pe.min)
    if (flt.value.pe.max         != null) params.set('max_pe',       flt.value.pe.max)
    if (flt.value.pb.min         != null) params.set('min_pb',       flt.value.pb.min)
    if (flt.value.pb.max         != null) params.set('max_pb',       flt.value.pb.max)
    params.set('sort_by',   sortBy.value)
    params.set('sort_dir',  sortDir.value)
    params.set('page',      String(currentPage.value))
    params.set('page_size', String(pageSize.value))

    if (flt.value.price.min != null) params.set('min_price', flt.value.price.min)
    if (flt.value.price.max != null) params.set('max_price', flt.value.price.max)
    if (flt.value.mktcap.min != null) params.set('min_mktcap', flt.value.mktcap.min)
    if (flt.value.mktcap.max != null) params.set('max_mktcap', flt.value.mktcap.max)

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
  setSymbol(stock.code, stock.name, (stock.change_pct || 0) >= 0 ? '#ef232a' : '#14b143')
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