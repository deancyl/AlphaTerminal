<template>
  <div class="flex flex-col h-full bg-terminal-bg text-terminal-fg font-mono" role="region" aria-label="股票筛选器">
    <div class="flex flex-wrap items-center justify-between p-2 gap-2 border-b border-theme-secondary shrink-0">
      <div class="flex items-center gap-4 text-xs">
        <span class="text-terminal-accent font-bold">全市场个股</span>
        <div class="flex items-center gap-1">
          <label for="stock-search" class="sr-only">搜索股票</label>
          <input id="stock-search" type="text" v-model="searchQuery" placeholder="输入拼音/代码/名称"
             class="bg-terminal-bg border border-theme-secondary rounded-sm px-2 py-1 focus:border-terminal-accent outline-none w-32" />
        </div>
      </div>
      <!-- 电脑端：显示所有筛选条件 -->
      <div class="hidden md:flex items-center gap-3 flex-wrap" role="group" aria-label="筛选条件">
        <div class="flex items-center gap-1 text-xs">
          <label for="filter-change" class="text-terminal-dim">涨跌幅 ></label>
          <input id="filter-change" type="number" v-model="flt.change_pct.min" class="w-12 bg-terminal-bg border border-theme-secondary rounded-sm px-1 outline-none focus:border-theme-accent" aria-describedby="filter-change-unit" />
          <span id="filter-change-unit" class="text-terminal-dim">%</span>
        </div>
        <div class="flex items-center gap-1 text-xs">
          <label for="filter-turnover" class="text-terminal-dim">换手率 ></label>
          <input id="filter-turnover" type="number" v-model="flt.turnover.min" class="w-12 bg-terminal-bg border border-theme-secondary rounded-sm px-1 outline-none focus:border-theme-accent" aria-describedby="filter-turnover-unit" />
          <span id="filter-turnover-unit" class="text-terminal-dim">%</span>
        </div>
        <div class="flex items-center gap-1 text-xs">
          <label for="filter-pe" class="text-terminal-dim">PE <</label>
          <input id="filter-pe" type="number" v-model="flt.pe.max" class="w-12 bg-terminal-bg border border-theme-secondary rounded-sm px-1 outline-none focus:border-theme-accent" />
        </div>
        <div class="flex items-center gap-1 text-xs">
          <label for="filter-pb" class="text-terminal-dim">PB <</label>
          <input id="filter-pb" type="number" v-model="flt.pb.max" class="w-12 bg-terminal-bg border border-theme-secondary rounded-sm px-1 outline-none focus:border-theme-accent" />
        </div>
        <div class="flex items-center gap-1 text-xs">
          <span class="text-terminal-dim">价格区间</span>
          <label for="filter-price-min" class="sr-only">最低价格</label>
          <input id="filter-price-min" type="number" v-model="flt.price.min" placeholder="低" class="w-12 bg-terminal-bg border border-theme-secondary rounded-sm px-1 outline-none focus:border-theme-accent" />
          <span class="text-terminal-dim">~</span>
          <label for="filter-price-max" class="sr-only">最高价格</label>
          <input id="filter-price-max" type="number" v-model="flt.price.max" placeholder="高" class="w-12 bg-terminal-bg border border-theme-secondary rounded-sm px-1 outline-none focus:border-theme-accent" />
        </div>
        <div class="flex items-center gap-1 text-xs">
          <span class="text-terminal-dim">市值(亿)</span>
          <label for="filter-mktcap-min" class="sr-only">最小市值</label>
          <input id="filter-mktcap-min" type="number" v-model="flt.mktcap.min" placeholder="低" class="w-12 bg-terminal-bg border border-theme-secondary rounded-sm px-1 outline-none focus:border-theme-accent" />
          <span class="text-terminal-dim">~</span>
          <label for="filter-mktcap-max" class="sr-only">最大市值</label>
          <input id="filter-mktcap-max" type="number" v-model="flt.mktcap.max" placeholder="高" class="w-12 bg-terminal-bg border border-theme-secondary rounded-sm px-1 outline-none focus:border-theme-accent" />
        </div>
      </div>
      <!-- 移动端：简化筛选 -->
      <div class="flex md:hidden items-center gap-2">
        <button @click="showMobileFilter = !showMobileFilter" class="px-2 py-0.5 text-[10px] border border-theme-secondary rounded-sm text-terminal-dim hover:border-theme-accent"
          :aria-expanded="showMobileFilter"
          aria-label="筛选条件"
          type="button"
        >
          筛选
        </button>
      </div>
    </div>
    
    <!-- 移动端筛选面板 -->
    <div v-if="showMobileFilter" class="md:hidden px-2 py-1 border-b border-theme-secondary bg-terminal-panel">
      <div class="grid grid-cols-3 gap-1">
        <div class="flex items-center gap-0.5 text-[10px]">
          <span class="text-terminal-dim">涨幅></span>
          <input type="number" v-model="flt.change_pct.min" class="w-8 bg-terminal-bg border border-theme-secondary rounded-sm px-0.5 outline-none" />
        </div>
        <div class="flex items-center gap-0.5 text-[10px]">
          <span class="text-terminal-dim">换手></span>
          <input type="number" v-model="flt.turnover.min" class="w-8 bg-terminal-bg border border-theme-secondary rounded-sm px-0.5 outline-none" />
        </div>
        <div class="flex items-center gap-0.5 text-[10px]">
          <span class="text-terminal-dim">PE<</span>
          <input type="number" v-model="flt.pe.max" class="w-8 bg-terminal-bg border border-theme-secondary rounded-sm px-0.5 outline-none" />
        </div>
      </div>
    </div>

<!-- 单表结构：Sticky 表头 + 虚拟化滚动 tbody + 固定分页栏 -->
    <div class="flex-1 min-h-0 overflow-hidden relative">
      <!-- Sticky 表头 -->
      <div class="shrink-0 overflow-x-auto scrollbar-hide bg-terminal-panel sticky top-0 z-10 shadow-sm">
        <div class="flex items-center text-xs whitespace-nowrap text-terminal-dim border-b border-theme">
          <div class="px-2 py-1.5 w-12 shrink-0">#</div>
          <div class="px-2 py-1.5 shrink-0 cursor-pointer" @click="setSort('name')">名称</div>
          <div class="px-2 py-1.5 shrink-0 cursor-pointer" @click="setSort('code')">代码</div>
          <div class="px-2 py-1.5 shrink-0 text-right cursor-pointer" @click="setSort('price')">最新价</div>
          <div class="px-2 py-1.5 shrink-0 text-right cursor-pointer" @click="setSort('change_pct')">涨跌幅</div>
          <!-- 电脑端显示 -->
          <div class="hidden md:block px-2 py-1.5 shrink-0 text-right cursor-pointer" @click="setSort('change')">涨跌</div>
          <div class="px-2 py-1.5 shrink-0 text-right cursor-pointer" @click="setSort('turnover')">换手率</div>
          <div class="hidden md:block px-2 py-1.5 shrink-0 text-right cursor-pointer" @click="setSort('amount')">成交额</div>
          <div class="hidden md:block px-2 py-1.5 shrink-0 text-right cursor-pointer" @click="setSort('pe')">PE</div>
          <div class="hidden md:block px-2 py-1.5 shrink-0 text-right cursor-pointer" @click="setSort('pb')">PB</div>
        </div>
      </div>

      <!-- 虚拟化滚动列表 -->
      <RecycleScroller
        ref="scrollerRef"
        class="h-full overflow-x-auto scrollbar-hide"
        :items="virtualizedStocks"
        :item-size="32"
        key-field="id"
        :buffer="300"
        v-slot="{ item, index }"
      >
        <div
          :class="[
            'flex items-center text-xs whitespace-nowrap border-b border-theme-secondary/30 hover:bg-theme-secondary/20 transition-colors group cursor-pointer',
            { 'bg-terminal-accent/20 ring-1 ring-terminal-accent ring-inset': focusedRowIndex === index }
          ]"
          :aria-selected="focusedRowIndex === index"
          role="option"
          @click="handleClick(item)"
          @contextmenu.prevent="handleContextMenu($event, item)"
        >
          <div class="px-2 py-1.5 w-12 shrink-0 text-terminal-dim">{{ item.seq || (currentPage-1)*pageSize + index + 1 }}</div>
          <div class="px-2 py-1.5 shrink-0">
            <div class="font-medium group-hover:text-theme-accent transition-colors">{{ item.name }}</div>
          </div>
          <div class="px-2 py-1.5 shrink-0 text-terminal-dim">{{ item.code }}</div>
          <div class="px-2 py-1.5 shrink-0 text-right" :class="getColor(item.change_pct)">{{ item.price?.toFixed(2) }}</div>
          <div class="px-2 py-1.5 shrink-0 text-right" :class="getColor(item.change_pct)">
            <span v-if="item.change_pct > 0">+</span>{{ item.change_pct?.toFixed(2) }}%
          </div>
          <!-- 电脑端显示 -->
          <div class="hidden md:block px-2 py-1.5 shrink-0 text-right" :class="getColor(item.change)">
            <span v-if="item.change > 0">+</span>{{ item.change?.toFixed(2) }}
          </div>
          <div class="px-2 py-1.5 shrink-0 text-right">{{ item.turnover ? item.turnover.toFixed(2) + '%' : '-' }}</div>
          <div class="hidden md:block px-2 py-1.5 shrink-0 text-right">{{ formatAmount(item.amount) }}</div>
          <div class="hidden md:block px-2 py-1.5 shrink-0 text-right">{{ item.pe ? item.pe.toFixed(1) : '-' }}</div>
          <div class="hidden md:block px-2 py-1.5 shrink-0 text-right">{{ item.pb ? item.pb.toFixed(2) : '-' }}</div>
        </div>
      </RecycleScroller>

      <!-- 加载中遮罩 -->
      <div v-if="loading" class="absolute inset-0 bg-terminal-bg/50 backdrop-blur-sm flex items-center justify-center z-20">
        <div class="space-y-2 w-full max-w-md px-4">
          <div class="skeleton h-4 w-3/4 rounded-sm"></div>
          <div class="skeleton h-4 w-1/2 rounded-sm"></div>
          <div class="skeleton h-4 w-2/3 rounded-sm"></div>
          <div class="text-theme-accent text-xs text-center mt-2">检索中...</div>
        </div>
      </div>
    </div>

    <!-- 分页控制栏（固定在底部） -->
    <div class="flex items-center justify-between p-2 text-xs border-t border-theme-secondary shrink-0 bg-terminal-panel">
      <button
        class="px-3 py-1 border border-theme-secondary rounded-sm hover:bg-theme-secondary/50 disabled:opacity-30 disabled:cursor-not-allowed"
        :disabled="currentPage === 1"
        @click="goPage(currentPage - 1)">上一页</button>
      <div class="text-terminal-dim">
        第 <span class="text-terminal-fg font-bold">{{ currentPage }}</span> / {{ totalPages }} 页
      </div>
      <button
        class="px-3 py-1 border border-theme-secondary rounded-sm hover:bg-theme-secondary/50 disabled:opacity-30 disabled:cursor-not-allowed"
        :disabled="currentPage >= totalPages"
        @click="goPage(currentPage + 1)">下一页</button>
    </div>
  <!-- 右键菜单 -->
  <ContextMenu
    :visible="contextMenu.visible"
    :x="contextMenu.x"
    :y="contextMenu.y"
    :items="contextMenuItems"
    @select="handleMenuSelect"
    @close="contextMenu.visible = false"
  />
</div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick, shallowRef } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { logger } from '../utils/logger.js'
import { useMarketStore } from '../stores/market.js'
import { fmtPrice, fmtPct, fmtChg, fmtTurnover, formatAmount } from '../utils/formatters.js'
import { apiFetch } from '../utils/api.js'
import ContextMenu from './ContextMenu.vue'
import { useToast } from '../composables/useToast.js'

const emit = defineEmits(['symbol-click'])
const { setSymbol } = useMarketStore()
const { success: toastSuccess, info: toastInfo } = useToast()

// ── 右键菜单状态 ───────────────────────────────────────────────────
const contextMenu = ref({ visible: false, x: 0, y: 0, stock: null })

const contextMenuItems = [
  { id: 'copy', label: '复制代码', icon: '📋', shortcut: 'Ctrl+C' },
  { id: 'f9', label: 'F9 深度资料', icon: '📊', shortcut: 'F9' },
  { id: 'watchlist', label: '加入自选', icon: '⭐', shortcut: '' },
  { id: 'kline', label: '打开K线', icon: '📈', shortcut: '' },
]

function handleContextMenu(event, stock) {
  contextMenu.value = {
    visible: true,
    x: event.clientX,
    y: event.clientY,
    stock
  }
}

function handleMenuSelect(item) {
  const stock = contextMenu.value.stock
  if (!stock) return

  switch (item.id) {
    case 'copy':
      navigator.clipboard.writeText(stock.code).then(() => {
        toastSuccess('已复制', `股票代码 ${stock.code} 已复制到剪贴板`)
      }).catch(() => {
        toastInfo('复制代码', stock.code)
      })
      break
    case 'f9':
      emit('symbol-click', { symbol: stock.code, name: stock.name, action: 'f9' })
      break
    case 'watchlist':
      toastSuccess('加入自选', `${stock.name} (${stock.code}) 已添加到自选股`)
      break
    case 'kline':
      emit('symbol-click', { symbol: stock.code, name: stock.name, action: 'kline' })
      break
  }
  contextMenu.value.visible = false
}

// 点击其他地方关闭右键菜单
function handleClickOutside(event) {
  if (contextMenu.value.visible) {
    contextMenu.value.visible = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

// ── 服务端分页数据状态 ─────────────────────────────────────────────
const stocks       = ref([])
const total        = ref(0)
const currentPage  = ref(1)
const pageSize     = ref(50)
const totalPages  = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const scrollerRef  = ref(null)

// ── 虚拟化股票列表 ─────────────────────────────────────────────────
const virtualizedStocks = computed(() => {
  return stocks.value.map((s, i) => ({
    ...s,
    id: s.code || `stock-${i}`,
  }))
})

// ── 本地 UI 状态 ─────────────────────────────────────────────────────
const loading     = ref(false)
const sentinelEl  = ref(null)
const searchQuery = ref('')
const showMobileFilter = ref(false)  // 移动端筛选面板显示状态
const sortBy      = ref('change_pct')
const sortDir     = ref('desc')
const focusedRowIndex = ref(-1)  // 键盘导航：当前聚焦行索引
const tableBody   = ref(null)    // tbody ref for focus management
const rowRefs     = shallowRef([])      // row element refs for scrolling

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

// ── 数据变化时重置键盘导航焦点和行 refs ────────────────────────────────
watch(stocks, (newStocks) => {
  focusedRowIndex.value = -1
  rowRefs.value = new Array(newStocks.length).fill(null)
}, { immediate: false })

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

// ── 键盘导航 ──────────────────────────────────────────────────────────
function handleKeydown(event) {
  const stockCount = stocks.value.length
  if (stockCount === 0) return

  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      focusedRowIndex.value = Math.min(focusedRowIndex.value + 1, stockCount - 1)
      scrollFocusedRowIntoView()
      break
    case 'ArrowUp':
      event.preventDefault()
      focusedRowIndex.value = Math.max(focusedRowIndex.value - 1, 0)
      scrollFocusedRowIntoView()
      break
    case 'Enter':
      event.preventDefault()
      if (focusedRowIndex.value >= 0 && focusedRowIndex.value < stockCount) {
        handleClick(stocks.value[focusedRowIndex.value])
      }
      break
    case 'Escape':
      focusedRowIndex.value = -1
      break
  }
}

function handleTableFocus() {
  // When table receives focus, select first row if none selected
  if (focusedRowIndex.value < 0 && stocks.value.length > 0) {
    focusedRowIndex.value = 0
  }
}

function scrollFocusedRowIntoView() {
  // Use nextTick to ensure DOM is updated
  nextTick(() => {
    const row = rowRefs.value[focusedRowIndex.value]
    if (row && row.scrollIntoView) {
      row.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }
  })
}

// Set row ref for keyboard navigation scrolling
function setRowRef(el, index) {
  if (el) {
    rowRefs.value[index] = el
  }
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
let _tableResizeObserver = null
let _sentinelResizeObserver = null

function tryAutoNextPage() {
  if (loading.value) return
  if (currentPage.value >= totalPages.value) return
  goPage(currentPage.value + 1)
}

function setupSentinel(scrollContainer) {
  // 防御：sentinelEl 尚未挂载时等待下一帧
  if (!sentinelEl.value) {
    _sentinelResizeObserver = new ResizeObserver(() => {
      if (sentinelEl.value) {
        _sentinelResizeObserver.disconnect()
        setupSentinel(scrollContainer)
      }
    })
    _sentinelResizeObserver.observe(scrollContainer)
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
    _tableResizeObserver = new ResizeObserver(() => {
      if (tableWrapper.clientHeight > 0) {
        _tableResizeObserver.disconnect()
        setupSentinel(tableWrapper)
      }
    })
    _tableResizeObserver.observe(tableWrapper)
  }
})

onUnmounted(() => {
  _observer?.disconnect()
  _tableResizeObserver?.disconnect()
  _sentinelResizeObserver?.disconnect()
  const tableWrapper = sentinelEl.value?.closest('.overflow-y-auto')
  if (tableWrapper && _scrollHandler) {
    tableWrapper.removeEventListener('scroll', _scrollHandler)
  }
})
</script>