<template>
  <div class="flex flex-col h-full">

    <!-- ── Header ─────────────────────────────────────────────── -->
    <div class="flex items-center justify-between mb-1 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">🔍 全市场个股</span>
      <div class="flex items-center gap-2">
        <input v-model="searchQuery" type="text" placeholder="搜索代码/名称"
               class="w-24 bg-terminal-bg border border-theme rounded px-2 py-0.5 text-[9px] text-theme-primary placeholder:text-theme-muted focus:border-terminal-accent outline-none" />
        <span class="text-terminal-dim text-[10px]">{{ filteredStocks.length }} 只</span>
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
                {{ allStocks.length === 0 ? '数据加载中...' : '无符合条件的数据' }}
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
                  :class="stock.chg_pct >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ fmtPct(stock.chg_pct) }}
              </td>
              <td class="py-0.5 px-0.5 text-right font-mono text-[9px] w-14"
                  :class="stock.chg >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ fmtChg(stock.chg) }}
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
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useVirtualList } from '@vueuse/core'
import { logger } from '../utils/logger.js'
import { useMarketStore } from '../composables/useMarketStore.js'
import { normalizeFields } from '../utils/api.js'
import { fmtPrice, fmtPct, fmtChg, fmtTurnover } from '../utils/formatters.js'

const { setSymbol } = useMarketStore()

// ── 数据状态 ─────────────────────────────────────────────────────
const allStocks = ref([])   // 全量股票（一次加载）
const loading    = ref(false)
const searchQuery = ref('')   // 全市场搜索
const sortBy     = ref('chg_pct')
const asc        = ref(false)

// ── 过滤条件 ─────────────────────────────────────────────────────
const flt = ref({
  change_pct: { min: null, max: null },
  turnover:    { min: null, max: null },
  amount:     { min: null, max: null },   // 单位：亿元（前端输入），转元后比较
  price:      { min: null, max: null },
  pe:         { min: null, max: null },   // 市盈率
  pb:         { min: null, max: null },   // 市净率
})

const filterActive = computed(() =>
  Object.values(flt.value).some(v => v.min !== null || v.max !== null)
)

// ── 过滤（排序职责已剥离到 filteredWithSeq）──────────────────────
const filteredStocks = computed(() => {
  let list = allStocks.value

  // 价格过滤
  if (flt.value.price.min !== null && flt.value.price.min !== '')
    list = list.filter(s => s.price >= flt.value.price.min)
  if (flt.value.price.max !== null && flt.value.price.max !== '')
    list = list.filter(s => s.price <= flt.value.price.max)

  // 涨跌幅过滤
  if (flt.value.change_pct.min !== null && flt.value.change_pct.min !== '')
    list = list.filter(s => s.chg_pct >= flt.value.change_pct.min)
  if (flt.value.change_pct.max !== null && flt.value.change_pct.max !== '')
    list = list.filter(s => s.chg_pct <= flt.value.change_pct.max)

  // 换手率过滤（%）
  if (flt.value.turnover.min !== null && flt.value.turnover.min !== '')
    list = list.filter(s => s.turnover >= flt.value.turnover.min)
  if (flt.value.turnover.max !== null && flt.value.turnover.max !== '')
    list = list.filter(s => s.turnover <= flt.value.turnover.max)

  // 成交额过滤（输入为亿元，转元比较）
  if (flt.value.amount.min !== null && flt.value.amount.min !== '')
    list = list.filter(s => s.amount >= flt.value.amount.min * 1e8)
  if (flt.value.amount.max !== null && flt.value.amount.max !== '')
    list = list.filter(s => s.amount <= flt.value.amount.max * 1e8)

  // 市盈率 PE 过滤
  if (flt.value.pe.min !== null && flt.value.pe.min !== '')
    list = list.filter(s => (s.pe || 0) >= flt.value.pe.min)
  if (flt.value.pe.max !== null && flt.value.pe.max !== '')
    list = list.filter(s => (s.pe || 0) <= flt.value.pe.max)

  // 市净率 PB 过滤
  if (flt.value.pb.min !== null && flt.value.pb.min !== '')
    list = list.filter(s => (s.pb || 0) >= flt.value.pb.min)
  if (flt.value.pb.max !== null && flt.value.pb.max !== '')
    list = list.filter(s => (s.pb || 0) <= flt.value.pb.max)

  return list
})

// ── 过滤结果排序后附加 seq（不污染原始数据）────────────────────
const filteredWithSeq = computed(() => {
  const key = sortBy.value
  const dir = asc.value ? 1 : -1
  const list = [...filteredStocks.value].sort((a, b) => {
    const av = a[key] ?? 0
    const bv = b[key] ?? 0
    return (av < bv ? -1 : av > bv ? 1 : 0) * dir
  })
  list.forEach((s, i) => { s.seq = i + 1 })
  return list
})

// ── 虚拟滚动（替代前端分页，只渲染可见行）────────────────────────
const ROW_HEIGHT = 32   // 每行固定高度（px）
const LIST_HEIGHT = 400  // 虚拟列表可视区高度

const { list: virtualRows, containerProps, wrapperProps } =
  useVirtualList(filteredWithSeq, {
    itemHeight: ROW_HEIGHT,
    overshoot: 8,
  })

// 过滤条件变化时自动滚动到顶部
watch(filteredWithSeq, () => {
  if (containerProps?.ref?.value) {
    containerProps.ref.value.scrollTop = 0
  }
})

// 搜索防抖（300ms后触发API搜索）
let searchTimer = null
watch(searchQuery, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    fetchAllStocks()  // 新API支持服务端搜索
  }, 300)
})

// ── 加载数据（从全市场缓存 API 加载，支持搜索）────────────────
async function fetchAllStocks() {
  loading.value = true
  try {
    // 无搜索条件时：使用一次性轻量接口（快）
    if (!searchQuery.value.trim()) {
      const res = await fetch('/api/v1/market/all_stocks_lite')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const d = await res.json()
      const payload = d.data || d
      const stocks = payload.stocks || []
      allStocks.value = stocks.map((s, i) => ({
        ...normalizeFields(s),
        seq: i + 1,
      }))
      // logger.log(`[StockScreener] Lite 加载完成: ${stocks.length} 只`)
      return
    }
    
    // 有搜索条件时：使用分页接口
    const pageSize = 200
    let page = 1
    let allFetched = []
    
    while (true) {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(Math.min(pageSize, 200)),
        search: searchQuery.value.trim(),
      })
      
      const res = await fetch(`/api/v1/market/all_stocks?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const d = await res.json()
      const payload = d.data || d
      const stocks = payload.stocks || []
      
      if (!stocks.length) break
      
      allFetched = allFetched.concat(stocks.map((s, i) => ({
        ...normalizeFields(s),
        seq: allFetched.length + i + 1,
      })))
      
      if (payload.total && allFetched.length >= payload.total) break
      if (stocks.length < pageSize) break
      if (page >= 30) break
      page++
      await new Promise(r => setTimeout(r, 50))
    }
    
    allStocks.value = allFetched
    logger.log(`[StockScreener] 搜索加载完成: ${allFetched.length} 只`)
  } catch (e) {
    logger.warn('[StockScreener] fetch failed:', e.message)
  } finally {
    loading.value = false
  }
}

// ── 排序 ─────────────────────────────────────────────────────────
function sortClass(col) {
  return sortBy.value === col ? 'text-terminal-accent' : ''
}
function setSort(col) {
  if (sortBy.value === col) {
    asc.value = !asc.value
  } else {
    sortBy.value = col
    asc.value = false
  }
}

// ── 重置过滤 ─────────────────────────────────────────────────────
function resetFilter() {
  flt.value = {
    change_pct: { min: null, max: null },
    turnover:    { min: null, max: null },
    amount:     { min: null, max: null },
    price:      { min: null, max: null },
  }
}

// ── 点击个股 ─────────────────────────────────────────────────────
function handleClick(stock) {
  setSymbol(stock.code, stock.name, stock.chg_pct >= 0 ? '#ef232a' : '#14b143')
}

// ── 格式化成交额 ────────────────────────────────────────────────
function formatAmt(v) {
  if (!v) return '--'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return Number(v).toFixed(2)
}

// ── 空操作（保留扩展）────────────────────────────────────────────
function toggleFilterPanel() {}

onMounted(fetchAllStocks)
</script>
