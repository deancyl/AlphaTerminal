<template>
  <div class="flex flex-col h-full">

    <!-- ── Header ─────────────────────────────────────────────── -->
    <div class="flex items-center justify-between mb-1 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">🔍 全市场个股</span>
      <div class="flex items-center gap-2">
        <input v-model="searchQuery" type="text" placeholder="搜索代码/名称"
               class="w-24 bg-terminal-bg border border-theme rounded px-2 py-0.5 text-[9px] text-theme-primary placeholder:text-theme-muted focus:border-terminal-accent outline-none" />
        <span class="text-terminal-dim text-[10px]">{{ total }} 只</span>
        <span class="w-1.5 h-1.5 rounded-full"
              :class="loading ? 'bg-yellow-400 animate-pulse' : 'bg-green-400'"></span>
      </div>
    </div>

    <!-- ── 过滤控制栏 ─────────────────────────────────────────── -->
    <div class="grid grid-cols-5 gap-x-1 gap-y-0.5 mb-1 shrink-0 text-[9px]">

      <!-- 涨跌幅 % -->
      <div class="flex flex-col">
        <span class="text-terminal-dim mb-0.5">涨跌幅</span>
        <div class="flex items-center gap-0.5">
          <input v-model.number="flt.change_pct.min" type="number"
                 placeholder="min" step="0.1"
                 class="w-full bg-terminal-bg border border-theme rounded px-1 py-0.5 text-[9px] text-theme-primary focus:border-terminal-accent outline-none placeholder:text-theme-muted" />
          <span class="text-terminal-dim">~</span>
          <input v-model.number="flt.change_pct.max" type="number"
                 placeholder="max" step="0.1"
                 class="w-full bg-terminal-bg border border-theme rounded px-1 py-0.5 text-[9px] text-theme-primary focus:border-terminal-accent outline-none placeholder:text-theme-muted" />
        </div>
      </div>

      <!-- 换手率 % -->
      <div class="flex flex-col">
        <span class="text-terminal-dim mb-0.5">换手率</span>
        <div class="flex items-center gap-0.5">
          <input v-model.number="flt.turnover.min" type="number"
                 placeholder="min" step="0.1"
                 class="w-full bg-terminal-bg border border-theme rounded px-1 py-0.5 text-[9px] text-theme-primary focus:border-terminal-accent outline-none placeholder:text-theme-muted" />
          <span class="text-terminal-dim">~</span>
          <input v-model.number="flt.turnover.max" type="number"
                 placeholder="max" step="0.1"
                 class="w-full bg-terminal-bg border border-theme rounded px-1 py-0.5 text-[9px] text-theme-primary focus:border-terminal-accent outline-none placeholder:text-theme-muted" />
        </div>
      </div>

      <!-- 成交额（元） -->
      <div class="flex flex-col">
        <span class="text-terminal-dim mb-0.5">成交额</span>
        <div class="flex items-center gap-0.5">
          <input v-model.number="flt.amount.min" type="number"
                 placeholder="亿" step="1"
                 class="w-full bg-terminal-bg border border-theme rounded px-1 py-0.5 text-[9px] text-theme-primary focus:border-terminal-accent outline-none placeholder:text-theme-muted" />
          <span class="text-terminal-dim">~</span>
          <input v-model.number="flt.amount.max" type="number"
                 placeholder="亿" step="1"
                 class="w-full bg-terminal-bg border border-theme rounded px-1 py-0.5 text-[9px] text-theme-primary focus:border-terminal-accent outline-none placeholder:text-theme-muted" />
        </div>
      </div>

      <!-- 最新价 -->
      <div class="flex flex-col">
        <span class="text-terminal-dim mb-0.5">最新价</span>
        <div class="flex items-center gap-0.5">
          <input v-model.number="flt.price.min" type="number"
                 placeholder="min" step="0.01"
                 class="w-full bg-terminal-bg border border-theme rounded px-1 py-0.5 text-[9px] text-theme-primary focus:border-terminal-accent outline-none placeholder:text-theme-muted" />
          <span class="text-terminal-dim">~</span>
          <input v-model.number="flt.price.max" type="number"
                 placeholder="max" step="0.01"
                 class="w-full bg-terminal-bg border border-theme rounded px-1 py-0.5 text-[9px] text-theme-primary focus:border-terminal-accent outline-none placeholder:text-theme-muted" />
        </div>
      </div>

      <!-- 市盈率 PE -->
      <div class="flex flex-col">
        <span class="text-terminal-dim mb-0.5">市盈率</span>
        <div class="flex items-center gap-0.5">
          <input v-model.number="flt.pe.min" type="number"
                 placeholder="min" step="0.1"
                 class="w-full bg-terminal-bg border border-theme rounded px-1 py-0.5 text-[9px] text-theme-primary focus:border-terminal-accent outline-none placeholder:text-theme-muted" />
          <span class="text-terminal-dim">~</span>
          <input v-model.number="flt.pe.max" type="number"
                 placeholder="max" step="0.1"
                 class="w-full bg-terminal-bg border border-theme rounded px-1 py-0.5 text-[9px] text-theme-primary focus:border-terminal-accent outline-none placeholder:text-theme-muted" />
        </div>
      </div>

      <!-- 市净率 PB -->
      <div class="flex flex-col">
        <span class="text-terminal-dim mb-0.5">市净率</span>
        <div class="flex items-center gap-0.5">
          <input v-model.number="flt.pb.min" type="number"
                 placeholder="min" step="0.01"
                 class="w-full bg-terminal-bg border border-theme rounded px-1 py-0.5 text-[9px] text-theme-primary focus:border-terminal-accent outline-none placeholder:text-theme-muted" />
          <span class="text-terminal-dim">~</span>
          <input v-model.number="flt.pb.max" type="number"
                 placeholder="max" step="0.01"
                 class="w-full bg-terminal-bg border border-theme rounded px-1 py-0.5 text-[9px] text-theme-primary focus:border-terminal-accent outline-none placeholder:text-theme-muted" />
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="flex flex-col justify-end">
        <div class="flex gap-1">
          <button @click="resetFilter"
                  class="px-2 py-0.5 text-[9px] rounded border border-theme text-theme-secondary hover:border-gray-500 hover:text-theme-primary transition shrink-0">
            重置
          </button>
          <button @click="toggleFilterPanel"
                  class="px-2 py-0.5 text-[9px] rounded border transition shrink-0"
                  :class="filterActive ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent' : 'border-theme text-theme-secondary hover:border-gray-500'">
            {{ filterActive ? '过滤中' : '筛选' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── 表头（可排序列）────────────────────────────────── -->
    <div class="overflow-x-auto flex-none">
      <table class="w-full text-xs whitespace-nowrap">
        <thead class="bg-terminal-panel">
          <tr class="text-terminal-dim border-b border-theme">
            <th class="text-left py-0.5 px-0.5 cursor-pointer hover:text-theme-primary w-8"
                @click="setSort('seq')">#</th>
            <th class="text-left py-0.5 px-0.5 cursor-pointer hover:text-theme-primary w-[72px] shrink-0"
                @click="setSort('name')">名称</th>
            <th class="text-left py-0.5 px-0.5 cursor-pointer hover:text-theme-primary w-16"
                @click="setSort('code')">代码</th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-theme-primary w-16"
                @click="setSort('price')">最新价</th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-theme-primary w-16"
                @click="setSort('chg_pct')">
              <span :class="sortClass('chg_pct')">涨跌幅 ↕</span>
            </th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-theme-primary w-14"
                @click="setSort('chg')">涨跌</th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-theme-primary w-12"
                @click="setSort('turnover')">
              <span :class="sortClass('turnover')">换手率</span>
            </th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-theme-primary w-16"
                @click="setSort('amount')">
              <span :class="sortClass('amount')">成交额</span>
            </th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-theme-primary w-12"
                @click="setSort('pe')">
              <span :class="sortClass('pe')">PE</span>
            </th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-theme-primary w-12"
                @click="setSort('pb')">
              <span :class="sortClass('pb')">PB</span>
            </th>
          </tr>
        </thead>
      </table>
    </div>

    <!-- ── 虚拟滚动列表（仅渲染可见行）────────────────── -->
    <div v-bind="containerProps" class="flex-1 min-h-0 overflow-y-auto">
      <div v-bind="wrapperProps">
        <table class="w-full text-xs whitespace-nowrap">
          <tbody>
            <!-- 骨架屏（加载中） -->
            <tr v-if="loading && !virtualRows.length">
              <td colspan="10" class="py-1">
                <div class="space-y-1 animate-pulse">
                  <div v-for="i in 8" :key="i" class="flex gap-1">
                    <div class="h-3 rounded bg-terminal-panel w-8"></div>
                    <div class="h-3 rounded bg-terminal-panel w-16 shrink-0"></div>
                    <div class="h-3 rounded bg-terminal-panel w-14"></div>
                    <div class="flex-1 h-3 rounded bg-terminal-panel"></div>
                    <div class="h-3 rounded bg-terminal-panel w-14"></div>
                    <div class="h-3 rounded bg-terminal-panel w-12"></div>
                    <div class="h-3 rounded bg-terminal-panel w-12"></div>
                    <div class="h-3 rounded bg-terminal-panel w-14"></div>
                    <div class="h-3 rounded bg-terminal-panel w-10"></div>
                    <div class="h-3 rounded bg-terminal-panel w-10"></div>
                  </div>
                </div>
              </td>
            </tr>
            <!-- 空状态 -->
            <tr v-else-if="!virtualRows.length">
              <td colspan="10" class="py-8 text-center text-terminal-dim text-xs">
                {{ stocks.length === 0 && !loading ? '无符合条件的数据' : '数据加载中...' }}
              </td>
            </tr>
            <!-- 虚拟行 -->
            <tr v-for="{ data: stock, index } in virtualRows" :key="stock.code + '-' + index"
                class="border-b border-theme-secondary hover:bg-white/5 cursor-pointer transition-colors"
                @click="handleClick(stock)">
              <td class="py-0.5 px-0.5 text-terminal-dim text-[9px] w-8">{{ stock.seq }}</td>
              <td class="py-0.5 px-0.5 text-theme-primary text-[10px] max-w-[70px] truncate w-[72px] shrink-0" :title="stock.name">{{ stock.name }}</td>
              <td class="py-0.5 px-0.5 text-terminal-dim text-[9px] w-14">{{ stock.code }}</td>
              <td class="py-0.5 px-0.5 text-right font-mono text-[10px] w-16">{{ fmtPrice(stock.price) }}</td>
              <td class="py-0.5 px-0.5 text-right font-mono text-[10px] w-16"
                  :class="stock.change_pct >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ fmtPct(stock.change_pct) }}
              </td>
              <td class="py-0.5 px-0.5 text-right font-mono text-[9px] w-14"
                  :class="stock.change >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ fmtChg(stock.change) }}
              </td>
              <td class="py-0.5 px-0.5 text-right font-mono text-[9px] w-12"
                  :class="stock.turnover > 5 ? 'text-yellow-400' : 'text-terminal-dim'">
                {{ fmtTurnover(stock.turnover) }}
              </td>
              <td class="py-0.5 px-0.5 text-right font-mono text-[9px] w-16 text-terminal-dim">
                {{ formatAmt(stock.amount) }}
              </td>
              <td class="py-0.5 px-0.5 text-right font-mono text-[9px] w-12"
                  :class="(stock.pe || 0) <= 0 ? 'text-terminal-dim' : ((stock.pe || 0) < 15 ? 'text-bullish' : ((stock.pe || 0) > 60 ? 'text-bearish' : 'text-theme-primary'))">
                {{ stock.pe ? stock.pe.toFixed(1) : '-' }}
              </td>
              <td class="py-0.5 px-0.5 text-right font-mono text-[9px] w-12"
                  :class="(stock.pb || 0) <= 0 ? 'text-terminal-dim' : ((stock.pb || 0) < 1 ? 'text-bullish' : ((stock.pb || 0) > 5 ? 'text-bearish' : 'text-theme-primary'))">
                {{ stock.pb ? stock.pb.toFixed(2) : '-' }}
              </td>
            </tr>
          </tbody>
        </table>
        <!-- 触底无限滚动触发器 -->
        <div ref="loadMoreTrigger" class="h-1 w-full" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useVirtualList, useDebounceFn, useIntersectionObserver } from '@vueuse/core'
import { logger } from '../utils/logger.js'
import { useMarketStore } from '../stores/market.js'
import { fmtPrice, fmtPct, fmtChg, fmtTurnover } from '../utils/formatters.js'
import { apiFetch } from '../utils/api.js'

// ── 服务端分页数据状态（替代全量 allStocks）────────────────────
const stocks       = ref([])      // 当前页数据
const total        = ref(0)       // 符合条件总数
const currentPage  = ref(1)
const pageSize      = ref(50)
const totalPages   = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

// ── 本地 UI 状态 ─────────────────────────────────────────────────
const loading      = ref(false)
const searchQuery   = ref('')
const sortBy        = ref('change_pct')
const sortDir       = ref('desc')
const loadMoreTrigger = ref(null)   // 触底无限滚动触发器

// ── 过滤条件 ─────────────────────────────────────────────────────
const flt = ref({
  change_pct: { min: null, max: null },
  turnover:    { min: null, max: null },
  amount:     { min: null, max: null },
  price:      { min: null, max: null },
  pe:         { min: null, max: null },
  pb:         { min: null, max: null },
})

const filterActive = computed(() =>
  Object.values(flt.value).some(v => v.min !== null || v.max !== null)
)

// ── 虚拟滚动（渲染当前页数据，行高固定）────────────────────────
const ROW_HEIGHT = 32

const { list: virtualRows, containerProps, wrapperProps } =
  useVirtualList(computed(() => stocks.value), {
    itemHeight: ROW_HEIGHT,
    overshoot: 8,
  })

// ── 核心：服务端搜索（防抖 300ms）───────────────────────────────
async function fetchStocks() {
  loading.value = true
  try {
    const params = new URLSearchParams()

    if (searchQuery.value.trim()) params.set('keyword', searchQuery.value.trim())
    if (flt.value.change_pct.min != null) params.set('min_pct_chg', flt.value.change_pct.min)
    if (flt.value.change_pct.max != null) params.set('max_pct_chg', flt.value.change_pct.max)
    if (flt.value.turnover.min   != null) params.set('min_turnover', flt.value.turnover.min)
    if (flt.value.turnover.max   != null) params.set('max_turnover', flt.value.turnover.max)
    if (flt.value.amount.min     != null) params.set('min_amount',   flt.value.amount.min * 1e8)
    if (flt.value.amount.max     != null) params.set('max_amount',   flt.value.amount.max * 1e8)
    if (flt.value.pe.min         != null) params.set('min_pe',       flt.value.pe.min)
    if (flt.value.pe.max         != null) params.set('max_pe',       flt.value.pe.max)
    if (flt.value.pb.min         != null) params.set('min_pb',       flt.value.pb.min)
    if (flt.value.pb.max         != null) params.set('max_pb',       flt.value.pb.max)

    params.set('sort_by',   sortBy.value)
    params.set('sort_dir',  sortDir.value)
    params.set('page',      String(currentPage.value))
    params.set('page_size', String(pageSize.value))

    const d = await apiFetch(`/api/v1/market/stocks/search?${params}`)
    const payload = d?.data || d || {}
    const newData = (payload.stocks || []).map((s, i) => ({
      ...s,
      seq: (currentPage.value - 1) * pageSize.value + i + 1,
    }))

    // 第一页替换，后续页追加（支持无限滚动）
    if (currentPage.value === 1) {
      stocks.value = newData
    } else {
      stocks.value.push(...newData)
    }
    total.value  = payload.total || 0
  } catch (e) {
    logger.warn('[StockScreener] fetchStocks failed:', e.message)
  } finally {
    loading.value = false
  }
}

// 防抖包装（搜索框/滑块/排序触发）
const debouncedFetch = useDebounceFn(fetchStocks, 300)

// ── 触底无限滚动（useIntersectionObserver）──────────────────────
function onLoadMoreVisible() {
  if (loading.value) return
  if (currentPage.value >= totalPages.value) return
  currentPage.value++
  fetchStocks()   // 无防抖，直接拉下一页
}

const { stop: stopObserver } = useIntersectionObserver(
  loadMoreTrigger,
  ([{ isIntersecting }]) => {
    if (isIntersecting) onLoadMoreVisible()
  },
  { threshold: 0.1 }
)

// ── 排序控制 ─────────────────────────────────────────────────────
function sortClass(col) {
  return sortBy.value === col ? 'text-terminal-accent' : ''
}
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

// ── 分页控制 ─────────────────────────────────────────────────────
function goPage(p) {
  currentPage.value = Math.max(1, Math.min(p, totalPages.value))
  debouncedFetch()
}

// ── 搜索/过滤变化 → 重置到第1页并触发搜索 ───────────────────
watch(searchQuery, () => { currentPage.value = 1; debouncedFetch() })

// ── 重置过滤 ─────────────────────────────────────────────────────
function resetFilter() {
  flt.value = { change_pct: { min: null, max: null }, turnover: { min: null, max: null },
                amount: { min: null, max: null }, price: { min: null, max: null },
                pe: { min: null, max: null }, pb: { min: null, max: null } }
  currentPage.value = 1
  debouncedFetch()
}

// ── 点击个股 ─────────────────────────────────────────────────────
function handleClick(stock) {
  setSymbol(stock.code, stock.name, stock.change_pct >= 0 ? '#ef232a' : '#14b143')
}

// ── 格式化成交额 ────────────────────────────────────────────────
function formatAmt(v) { return fmtTurnover(v) }

// ── 空操作 ──────────────────────────────────────────────────────
function toggleFilterPanel() {}

onMounted(debouncedFetch)
</script>
