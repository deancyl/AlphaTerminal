<template>
  <div class="flex flex-col h-full">

    <!-- ── Header ─────────────────────────────────────────────── -->
    <div class="flex items-center justify-between mb-1 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">🔍 全市场个股</span>
      <div class="flex items-center gap-2">
        <span class="text-terminal-dim text-[10px]">{{ total.toLocaleString() }} 只</span>
        <span class="w-1.5 h-1.5 rounded-full"
              :class="loading ? 'bg-yellow-400 animate-pulse' : 'bg-green-400'"></span>
      </div>
    </div>

    <!-- ── 表头（可排序列）────────────────────────────────── -->
    <div class="overflow-x-auto flex-1 min-h-0">
      <table class="w-full text-xs whitespace-nowrap">
        <thead class="sticky top-0 z-10 bg-terminal-panel">
          <tr class="text-terminal-dim border-b border-gray-700">
            <th class="text-left py-0.5 px-0.5 cursor-pointer hover:text-gray-200 w-8"
                @click="toggleSort('seq')">#</th>
            <th class="text-left py-0.5 px-0.5 cursor-pointer hover:text-gray-200 min-w-[60px]"
                @click="toggleSort('name')">名称</th>
            <th class="text-left py-0.5 px-0.5 cursor-pointer hover:text-gray-200 w-16"
                @click="toggleSort('code')">代码</th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-gray-200 w-16"
                @click="toggleSort('price')">最新价</th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-gray-200 w-16"
                @click="toggleSort('chg_pct')">
              <span :class="sortClass('chg_pct')">涨跌幅 ↕</span>
            </th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-gray-200 w-14"
                @click="toggleSort('chg')">涨跌</th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-gray-200 w-12"
                @click="toggleSort('turnover')">换手率</th>
            <th class="text-right py-0.5 px-0.5 cursor-pointer hover:text-gray-200 w-16"
                @click="toggleSort('amount')">成交额</th>
          </tr>
        </thead>
        <tbody class="overflow-y-auto">
          <tr v-for="stock in stocks" :key="stock.code"
              class="border-b border-gray-800 hover:bg-white/5 cursor-pointer transition-colors"
              @click="handleClick(stock)">
            <td class="py-0.5 px-0.5 text-terminal-dim text-[9px]">{{ stock.seq }}</td>
            <td class="py-0.5 px-0.5 text-gray-200 text-[10px]">{{ stock.name }}</td>
            <td class="py-0.5 px-0.5 text-terminal-dim text-[9px]">{{ stock.code }}</td>
            <td class="py-0.5 px-0.5 text-right font-mono text-[10px]">{{ stock.price }}</td>
            <td class="py-0.5 px-0.5 text-right font-mono text-[10px]"
                :class="stock.chg_pct >= 0 ? 'text-red-400' : 'text-green-400'">
              {{ stock.chg_pct >= 0 ? '+' : '' }}{{ stock.chg_pct }}%
            </td>
            <td class="py-0.5 px-0.5 text-right font-mono text-[9px]"
                :class="stock.chg >= 0 ? 'text-red-400' : 'text-green-400'">
              {{ stock.chg >= 0 ? '+' : '' }}{{ stock.chg }}
            </td>
            <td class="py-0.5 px-0.5 text-right font-mono text-[9px] text-terminal-dim">
              {{ stock.turnover }}%
            </td>
            <td class="py-0.5 px-0.5 text-right font-mono text-[9px] text-terminal-dim">
              {{ formatAmt(stock.amount) }}
            </td>
          </tr>
          <tr v-if="!stocks.length && !loading">
            <td colspan="8" class="py-8 text-center text-terminal-dim text-xs">
              {{ total === 0 ? '数据加载中（约30秒后可用）...' : '暂无数据' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── 分页控制器 ─────────────────────────────────────── -->
    <div v-if="pages > 1" class="flex items-center justify-between mt-2 shrink-0">
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
      <span class="text-[10px] text-terminal-dim">
        {{ pageSize }}条/页
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMarketStore } from '../composables/useMarketStore.js'

const { setSymbol } = useMarketStore()

const stocks     = ref([])
const total       = ref(0)
const page        = ref(1)
const pages       = ref(1)
const pageSize    = ref(20)
const sortBy      = ref('change_pct')
const asc         = ref(false)
const loading     = ref(false)

const visiblePages = computed(() => {
  const p = pages.value
  if (p <= 5) return Array.from({ length: p }, (_, i) => i + 1)
  const cur = page.value
  if (cur <= 3) return [1, 2, 3, 4, 5]
  if (cur >= p - 2) return [p - 4, p - 3, p - 2, p - 1, p]
  return [cur - 2, cur - 1, cur, cur + 1, cur + 2]
})

function sortClass(col) {
  return sortBy.value === col ? 'text-terminal-accent' : ''
}

function toggleSort(col) {
  if (sortBy.value === col) {
    asc.value = !asc.value
  } else {
    sortBy.value = col
    asc.value = false
  }
  page.value = 1
  fetchStocks()
}

async function fetchStocks() {
  loading.value = true
  try {
    const url = `/api/v1/market/stocks?page=${page.value}&page_size=${pageSize.value}&sort_by=${sortBy.value}&asc=${asc.value}`
    const res = await fetch(url)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const d = await res.json()
    stocks.value = d.stocks || []
    total.value = d.total || 0
    pages.value  = d.pages  || 1
  } catch (e) {
    console.warn('[StockScreener] fetch failed:', e.message)
  } finally {
    loading.value = false
  }
}

function handleClick(stock) {
  // 点击个股 → 切换主图 K 线
  // 注意：这里 setSymbol 用 code 作为 symbol
  setSymbol(stock.code, stock.name, stock.chg_pct >= 0 ? '#ef232a' : '#14b143')
}

function formatAmt(v) {
  if (!v) return '--'
  if (v >= 1e8) return (v / 1e8).toFixed(1) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(0) + '万'
  return v.toFixed(0)
}

function goPage(p) {
  if (p < 1 || p > pages.value || p === page.value) return
  page.value = p
  fetchStocks()
}
function prevPage() { goPage(page.value - 1) }
function nextPage() { goPage(page.value + 1) }

onMounted(fetchStocks)
</script>
