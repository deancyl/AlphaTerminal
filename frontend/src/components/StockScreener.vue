<template>
  <div class="flex flex-col h-full">

    <!-- ── Header ─────────────────────────────────────────────── -->
    <div class="flex items-center justify-between mb-1 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">🔍 全市场个股</span>
      <div class="flex items-center gap-2">
        <input v-model="searchQuery" type="text" placeholder="搜索代码/名称"
               class="w-24 bg-terminal-bg border border-gray-700 rounded px-2 py-0.5 text-[9px] text-gray-200 placeholder:text-gray-600 focus:border-terminal-accent outline-none" />
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
                 class="w-full bg-terminal-bg border border-gray-700 rounded px-1 py-0.5 text-[9px] text-gray-200 focus:border-terminal-accent outline-none placeholder:text-gray-600" />
          <span class="text-terminal-dim">~</span>
          <input v-model.number="flt.change_pct.max" type="number"
                 placeholder="max" step="0.1"
                 class="w-full bg-terminal-bg border border-gray-700 rounded px-1 py-0.5 text-[9px] text-gray-200 focus:border-terminal-accent outline-none placeholder:text-gray-600" />
        </div>
      </div>

      <!-- 换手率 % -->
      <div class="flex flex-col">
        <span class="text-terminal-dim mb-0.5">换手率</span>
        <div class="flex items-center gap-0.5">
          <input v-model.number="flt.turnover.min" type="number"
                 placeholder="min" step="0.1"
                 class="w-full bg-terminal-bg border border-gray-700 rounded px-1 py-0.5 text-[9px] text-gray-200 focus:border-terminal-accent outline-none placeholder:text-gray-600" />
          <span class="text-terminal-dim">~</span>
          <input v-model.number="flt.turnover.max" type="number"
                 placeholder="max" step="0.1"
                 class="w-full bg-terminal-bg border border-gray-700 rounded px-1 py-0.5 text-[9px] text-gray-200 focus:border-terminal-accent outline-none placeholder:text-gray-600" />
        </div>
      </div>

      <!-- 成交额（元） -->
      <div class="flex flex-col">
        <span class="text-terminal-dim mb-0.5">成交额</span>
        <div class="flex items-center gap-0.5">
          <input v-model.number="flt.amount.min" type="number"
                 placeholder="亿" step="1"
                 class="w-full bg-terminal-bg border border-gray-700 rounded px-1 py-0.5 text-[9px] text-gray-200 focus:border-terminal-accent outline-none placeholder:text-gray-600" />
          <span class="text-terminal-dim">~</span>
          <input v-model.number="flt.amount.max" type="number"
                 placeholder="亿" step="1"
                 class="w-full bg-terminal-bg border border-gray-700 rounded px-1 py-0.5 text-[9px] text-gray-200 focus:border-terminal-accent outline-none placeholder:text-gray-600" />
        </div>
      </div>

      <!-- 最新价 -->
      <div class="flex flex-col">
        <span class="text-terminal-dim mb-0.5">最新价</span>
        <div class="flex items-center gap-0.5">
          <input v-model.number="flt.price.min" type="number"
                 placeholder="min" step="0.01"
                 class="w-full bg-terminal-bg border border-gray-700 rounded px-1 py-0.5 text-[9px] text-gray-200 focus:border-terminal-accent outline-none placeholder:text-gray-600" />
          <span class="text-terminal-dim">~</span>
          <input v-model.number="flt.price.max" type="number"
                 placeholder="max" step="0.01"
                 class="w-full bg-terminal-bg border border-gray-700 rounded px-1 py-0.5 text-[9px] text-gray-200 focus:border-terminal-accent outline-none placeholder:text-gray-600" />
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="flex flex-col justify-end">
        <div class="flex gap-1">
          <button @click="resetFilter"
                  class="px-2 py-0.5 text-[9px] rounded border border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200 transition shrink-0">
            重置
          </button>
          <button @click="toggleFilterPanel"
                  class="px-2 py-0.5 text-[9px] rounded border transition shrink-0"
                  :class="filterActive ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent' : 'border-gray-700 text-gray-400 hover:border-gray-500'">
            {{ filterActive ? '过滤中' : '筛选' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── 表头（可排序列）────────────────────────────────── -->
    <div class="overflow-x-auto overflow-y-auto flex-1 min-h-0">
      <table class="w-full text-xs whitespace-nowrap">
        <thead class="sticky top-0 z-10 bg-terminal-panel">
          <tr class="text-terminal-dim border-b border-gray-700">
            <th class="text-left py-0.5 px-0.5 cursor-pointer hover:text-gray-200 w-8"
                @click="setSort('seq')">#</th>
            <th class="text-left py-0.5 px-0.5 cursor-pointer hover:text-gray-200 min-w-[60px]"
                @click="setSort('name')">名称</th>
            <th class="text-left py-0.5 px-0.5 cursor-pointer hover:text-gray-200 w-16"
                @click="setSort('code')">代码</th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-gray-200 w-16"
                @click="setSort('price')">最新价</th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-gray-200 w-16"
                @click="setSort('chg_pct')">
              <span :class="sortClass('chg_pct')">涨跌幅 ↕</span>
            </th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-gray-200 w-14"
                @click="setSort('chg')">涨跌</th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-gray-200 w-12"
                @click="setSort('turnover')">
              <span :class="sortClass('turnover')">换手率</span>
            </th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-gray-200 w-16"
                @click="setSort('amount')">
              <span :class="sortClass('amount')">成交额</span>
            </th>
          </tr>
        </thead>
        <tbody class="overflow-y-auto">
          <tr v-for="stock in pageStocks" :key="stock.code"
              class="border-b border-gray-800 hover:bg-white/5 cursor-pointer transition-colors"
              @click="handleClick(stock)">
            <td class="py-0.5 px-0.5 text-terminal-dim text-[9px]">{{ stock.seq }}</td>
            <td class="py-0.5 px-0.5 text-gray-200 text-[10px] max-w-[80px] truncate" :title="stock.name">{{ stock.name }}</td>
            <td class="py-0.5 px-0.5 text-terminal-dim text-[9px] w-[60px]">{{ stock.code }}</td>
            <td class="py-0.5 px-0.5 text-right font-mono text-[10px]">{{ stock.price }}</td>
            <td class="py-0.5 px-0.5 text-right font-mono text-[10px]"
                :class="stock.chg_pct >= 0 ? 'text-red-400' : 'text-green-400'">
              {{ stock.chg_pct >= 0 ? '+' : '' }}{{ stock.chg_pct }}%
            </td>
            <td class="py-0.5 px-0.5 text-right font-mono text-[9px]"
                :class="stock.chg >= 0 ? 'text-red-400' : 'text-green-400'">
              {{ stock.chg >= 0 ? '+' : '' }}{{ stock.chg }}
            </td>
            <td class="py-0.5 px-0.5 text-right font-mono text-[9px]"
                :class="stock.turnover > 5 ? 'text-yellow-400' : 'text-terminal-dim'">
              {{ stock.turnover }}%
            </td>
            <td class="py-0.5 px-0.5 text-right font-mono text-[9px] text-terminal-dim">
              {{ formatAmt(stock.amount) }}
            </td>
          </tr>
          <tr v-if="!pageStocks.length && !loading">
            <td colspan="8" class="py-8 text-center text-terminal-dim text-xs">
              {{ allStocks.length === 0 ? '数据加载中（约30秒后可用）...' : '无符合条件的数据' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── 分页控制器 ─────────────────────────────────────── -->
    <div v-if="pages > 1" class="flex items-center justify-between mt-1 shrink-0">
      <span class="text-[10px] text-terminal-dim">
        第 {{ page }} / {{ pages }} 页
      </span>
      <div class="flex items-center gap-1">
        <button class="px-2 py-0.5 text-[10px] rounded border transition"
                :class="page === 1 ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-terminal-bg border-gray-600 text-gray-300 hover:border-terminal-accent/50'"
                :disabled="page === 1" @click="prevPage">‹</button>

        <button v-for="p in visiblePages" :key="p"
                class="px-2 py-0.5 text-[10px] rounded border transition"
                :class="p === page ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent' : 'bg-terminal-bg border-gray-600 text-gray-300 hover:border-terminal-accent/50'"
                @click="goPage(p)">{{ p }}</button>

        <button class="px-2 py-0.5 text-[10px] rounded border transition"
                :class="page === pages ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-terminal-bg border-gray-600 text-gray-300 hover:border-terminal-accent/50'"
                :disabled="page === pages" @click="nextPage">›</button>
      </div>
      <span class="text-[10px] text-terminal-dim">{{ pageSize }}条/页</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useMarketStore } from '../composables/useMarketStore.js'

const { setSymbol } = useMarketStore()

// ── 数据状态 ─────────────────────────────────────────────────────
const allStocks = ref([])   // 全量股票（一次加载，分页在前端）
const loading    = ref(false)
const page       = ref(1)
const pageSize   = ref(50)   // 前端分页粒度
const searchQuery = ref('')   // 全市场搜索
const sortBy     = ref('chg_pct')
const asc        = ref(false)

// ── 过滤条件 ─────────────────────────────────────────────────────
const flt = ref({
  change_pct: { min: null, max: null },
  turnover:    { min: null, max: null },
  amount:     { min: null, max: null },   // 单位：亿元（前端输入），转元后比较
  price:      { min: null, max: null },
})

const filterActive = computed(() =>
  Object.values(flt.value).some(v => v.min !== null || v.max !== null)
)

// ── 过滤 + 排序（computed，filters 变化自动重算）────────────────
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

  // 排序
  const key = sortBy.value
  const dir = asc.value ? 1 : -1
  list = [...list].sort((a, b) => {
    const av = a[key] ?? 0
    const bv = b[key] ?? 0
    return (av < bv ? -1 : av > bv ? 1 : 0) * dir
  })

  // 重排序号
  list.forEach((s, i) => { s.seq = i + 1 })
  return list
})

// ── 前端分页 ─────────────────────────────────────────────────────
const pages = computed(() =>
  Math.max(1, Math.ceil(filteredStocks.value.length / pageSize.value))
)
const pageStocks = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredStocks.value.slice(start, start + pageSize.value)
})

// 过滤条件变化时自动归位第1页
watch(filteredStocks, () => { page.value = 1 })

// 搜索防抖（300ms后触发API搜索）
let searchTimer = null
watch(searchQuery, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    fetchAllStocks()  // 新API支持服务端搜索
  }, 300)
})

// ── 可见页码 ─────────────────────────────────────────────────────
const visiblePages = computed(() => {
  const p = pages.value
  if (p <= 5) return Array.from({ length: p }, (_, i) => i + 1)
  const cur = page.value
  if (cur <= 3) return [1, 2, 3, 4, 5]
  if (cur >= p - 2) return [p - 4, p - 3, p - 2, p - 1, p]
  return [cur - 2, cur - 1, cur, cur + 1, cur + 2]
});

// ── 加载数据（从全市场缓存 API 加载，支持搜索）────────────────
async function fetchAllStocks() {
  loading.value = true
  try {
    // 调用新的全市场个股 API (支持搜索、分页)
    // 先尝试获取全量数据（用于前端过滤），若搜索则用 API 搜索
    const pageSize = 200  // 每页获取量
    let page = 1
    let allFetched = []
    
    while (true) {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      })
      if (searchQuery.value.trim()) {
        params.set('search', searchQuery.value.trim())
      }
      
      const res = await fetch(`/api/v1/market/all_stocks?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const d = await res.json()
      const payload = d.data || d
      const stocks = payload.stocks || []
      
      if (!stocks.length) break
      
      allFetched = allFetched.concat(stocks.map((s, i) => ({
        ...s,
        seq: allFetched.length + i + 1,
        // 统一字段名（兼容表格渲染）
        price: parseFloat(s.trade) || 0,
        chg_pct: parseFloat(s.changepercent) || 0,
        chg: parseFloat(s.change) || 0,
        turnover: parseFloat(s.turnoverratio) || 0,
        amount: parseFloat(s.amount) || 0,
        per: s.per !== null && s.per !== undefined && s.per !== '-' ? parseFloat(s.per) : null,
        pb:  s.pb  !== null && s.pb  !== undefined && s.pb  !== '-' ? parseFloat(s.pb)  : null,
        volume: parseFloat(s.volume) || 0,
        mktcap: parseFloat(s.mktcap) || 0,
      })))
      
      if (!searchQuery.value.trim() && payload.total && allFetched.length >= payload.total) {
        break  // 全量获取完成
      }
      if (stocks.length < pageSize) break  // 最后一页
      if (page >= 5) break  // 最多获取5页（1000条），防止搜索过多
      page++
      
      // 避免请求过快
      await new Promise(r => setTimeout(r, 50))
    }
    
    allStocks.value = allFetched
    console.log(`[StockScreener] 加载完成: ${allFetched.length} 只`)
  } catch (e) {
    console.warn('[StockScreener] fetch failed:', e.message)
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
  page.value = 1
}

// ── 分页 ─────────────────────────────────────────────────────────
function goPage(p) {
  if (p < 1 || p > pages.value || p === page.value) return
  page.value = p
}
function prevPage() { goPage(page.value - 1) }
function nextPage() { goPage(page.value + 1) }

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
  if (v >= 1e8) return (v / 1e8).toFixed(1) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(0) + '万'
  return v.toFixed(0)
}

// ── 空操作（保留扩展）────────────────────────────────────────────
function toggleFilterPanel() {}

onMounted(fetchAllStocks)
</script>
