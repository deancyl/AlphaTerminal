<template>
  <div class="grid-stack" ref="gridRef">

    <!-- ━━━ Widget 1：A股K线（分时/日/周/月 + MACD/BOLL预留）━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="0" gs-y="0" gs-w="8" gs-h="6" gs-min-w="4" gs-min-h="4">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <div class="flex items-center justify-between mb-2 shrink-0">
          <span class="text-terminal-accent font-bold text-sm">📈 {{ currentIndexOption.name }} K线</span>
          <div class="flex gap-1">
            <button v-for="idx in indexOptions" :key="idx.symbol"
                    class="px-2 py-0.5 text-[10px] rounded border transition"
                    :class="selectedIndex === idx.symbol
                      ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent'
                      : 'bg-terminal-bg border-gray-700 text-terminal-dim hover:border-gray-500'"
                    @click="switchIndex(idx)">
              {{ idx.name }}
            </button>
          </div>
        </div>
        <!-- Period selector -->
        <div class="flex items-center gap-1 mb-2 shrink-0">
          <button v-for="p in periods" :key="p.key"
                  class="px-2 py-0.5 text-[10px] rounded border transition"
                  :class="selectedPeriod === p.key
                    ? 'bg-blue-500/20 border-blue-500/50 text-blue-400'
                    : 'bg-terminal-bg border-gray-700 text-terminal-dim hover:border-gray-500'"
                  @click="switchPeriod(p.key)">
            {{ p.label }}
          </button>
          <!-- Indicator toggles -->
          <span class="ml-2 text-terminal-dim text-[9px]">指标:</span>
          <button v-for="ind in indicators" :key="ind.key"
                  class="px-1.5 py-0.5 text-[9px] rounded border transition"
                  :class="activeIndicators.includes(ind.key)
                    ? 'bg-purple-500/20 border-purple-500/50 text-purple-400'
                    : 'bg-terminal-bg border-gray-700 text-terminal-dim hover:border-gray-500'"
                  @click="toggleIndicator(ind.key)">
            {{ ind.label }}
          </button>
        </div>
        <div class="flex-1 min-h-0">
          <IndexLineChart
            :key="`${selectedIndex}-${selectedPeriod}`"
            :symbol="selectedIndex"
            :name="currentIndexOption.name"
            :color="currentIndexOption.color"
            :url="`/api/v1/market/history/${selectedIndex}?period=${selectedPeriod}`"
            :indicators="activeIndicators"
          />
        </div>
      </div>
    </div>

    <!-- ━━━ Widget 2：市场风向标（精简：上证·沪深300·恒生·纳斯达克）━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="8" gs-y="0" gs-w="4" gs-h="6" gs-min-w="3" gs-min-h="3">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <div class="flex items-center justify-between mb-2 shrink-0">
          <span class="text-terminal-accent font-bold text-sm">🎯 市场风向标</span>
          <span class="text-terminal-dim text-[10px]">{{ tsDisplay }}</span>
        </div>
        <div class="flex-1 overflow-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="text-terminal-dim border-b border-gray-700">
                <th class="text-left py-1">指数</th>
                <th class="text-right py-1">最新价</th>
                <th class="text-right py-1">涨跌幅</th>
                <th class="text-right py-1">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, key) in windItems" :key="key"
                  class="border-b border-gray-800 hover:bg-white/5">
                <td class="py-1.5 text-gray-300">{{ item.name }}</td>
                <td class="py-1.5 text-right font-mono">{{ formatPrice(item.index) }}</td>
                <td class="py-1.5 text-right font-mono"
                    :class="(item.change_pct || 0) >= 0 ? 'text-red-400' : 'text-green-400'">
                  {{ (item.change_pct || 0) >= 0 ? '+' : '' }}{{ (item.change_pct || 0).toFixed(2) }}%
                </td>
                <td class="py-1.5 text-right">
                  <span class="px-1 py-0.5 rounded text-[9px]"
                        :class="item.status === '交易中' ? 'bg-green-500/20 text-green-400' : 'bg-gray-600/30 text-gray-400'">
                    {{ item.status }}
                  </span>
                </td>
              </tr>
              <tr v-if="!windItems.length">
                <td colspan="4" class="py-4 text-center text-terminal-dim text-xs">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ━━━ Widget 3：全球市场（扩容至5个指数）━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="0" gs-y="6" gs-w="4" gs-h="6" gs-min-w="3" gs-min-h="3">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <div class="flex items-center justify-between mb-2 shrink-0">
          <span class="text-terminal-accent font-bold text-sm">🌐 全球市场</span>
          <span class="text-terminal-dim text-[10px]">{{ tsDisplay }}</span>
        </div>
        <div class="flex-1 overflow-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="text-terminal-dim border-b border-gray-700">
                <th class="text-left py-1">指数</th>
                <th class="text-right py-1">最新价</th>
                <th class="text-right py-1">涨跌幅</th>
                <th class="text-right py-1">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in globalItems" :key="item.symbol"
                  class="border-b border-gray-800 hover:bg-white/5">
                <td class="py-1 text-gray-300 text-[11px]">{{ item.name }}</td>
                <td class="py-1 text-right font-mono text-[11px]">{{ formatPrice(item.price) }}</td>
                <td class="py-1 text-right font-mono text-[11px]"
                    :class="(item.change_pct || 0) >= 0 ? 'text-red-400' : 'text-green-400'">
                  {{ (item.change_pct || 0) >= 0 ? '+' : '' }}{{ (item.change_pct || 0).toFixed(2) }}%
                </td>
                <td class="py-1 text-right">
                  <span class="px-1 py-0.5 rounded text-[9px]"
                        :class="item.status === '交易中' ? 'bg-green-500/20 text-green-400' : 'bg-gray-600/30 text-gray-400'">
                    {{ item.status }}
                  </span>
                </td>
              </tr>
              <tr v-if="!globalItems.length">
                <td colspan="4" class="py-4 text-center text-terminal-dim text-xs">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ━━━ Widget 4：国内市场10+指数（新卡片）━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="4" gs-y="6" gs-w="4" gs-h="6" gs-min-w="3" gs-min-h="3">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <div class="flex items-center justify-between mb-2 shrink-0">
          <span class="text-terminal-accent font-bold text-sm">🇨🇳 国内指数</span>
          <span class="text-terminal-dim text-[10px]">{{ tsDisplay }}</span>
        </div>
        <div class="flex-1 overflow-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="text-terminal-dim border-b border-gray-700">
                <th class="text-left py-1">指数</th>
                <th class="text-right py-1">最新价</th>
                <th class="text-right py-1">涨跌幅</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in chinaAllItems" :key="item.symbol"
                  class="border-b border-gray-800 hover:bg-white/5">
                <td class="py-1 text-gray-300 text-[11px]">{{ item.name }}</td>
                <td class="py-1 text-right font-mono text-[11px]">{{ formatPrice(item.price) }}</td>
                <td class="py-1 text-right font-mono text-[11px]"
                    :class="(item.change_pct || 0) >= 0 ? 'text-red-400' : 'text-green-400'">
                  {{ (item.change_pct || 0) >= 0 ? '+' : '' }}{{ (item.change_pct || 0).toFixed(2) }}%
                </td>
              </tr>
              <tr v-if="!chinaAllItems.length">
                <td colspan="3" class="py-4 text-center text-terminal-dim text-xs">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ━━━ Widget 5：板块与商品（Tab 切换）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="8" gs-y="6" gs-w="4" gs-h="6" gs-min-w="3" gs-min-h="3">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <div class="flex items-center justify-between mb-2 shrink-0">
          <span class="text-terminal-accent font-bold text-sm">🔥 板块与商品</span>
          <div class="flex gap-1 text-[10px]">
            <button
              class="px-1.5 py-0.5 rounded border transition"
              :class="commodityTab === 'sectors'
                ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent'
                : 'bg-terminal-bg border-gray-700 text-terminal-dim hover:border-gray-500'"
              @click="commodityTab = 'sectors'">
              板块
            </button>
            <button
              class="px-1.5 py-0.5 rounded border transition"
              :class="commodityTab === 'derivatives'
                ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent'
                : 'bg-terminal-bg border-gray-700 text-terminal-dim hover:border-gray-500'"
              @click="commodityTab = 'derivatives'">
              商品
            </button>
          </div>
        </div>

        <!-- 行业板块视图 -->
        <div v-if="commodityTab === 'sectors'" class="flex-1 overflow-auto">
          <div v-if="sectorsItems.length" class="space-y-1">
            <div v-for="(sec, i) in sectorsItems" :key="sec.name"
                 class="flex items-center justify-between bg-terminal-bg rounded px-2 py-1.5 border border-gray-700">
              <div class="flex items-center gap-1.5">
                <span class="text-terminal-dim text-[10px] w-3">{{ i + 1 }}</span>
                <span class="text-gray-200 text-[11px]">{{ sec.name }}</span>
              </div>
              <span class="font-mono text-[11px]"
                    :class="(sec.change_pct || 0) >= 0 ? 'text-red-400' : 'text-green-400'">
                {{ (sec.change_pct || 0) >= 0 ? '+' : '' }}{{ (sec.change_pct || 0).toFixed(2) }}%
              </span>
            </div>
          </div>
          <div v-else class="flex-1 flex items-center justify-center text-terminal-dim text-xs">
            暂无板块数据
          </div>
        </div>

        <!-- 大宗商品视图 -->
        <div v-if="commodityTab === 'derivatives'" class="flex-1 overflow-auto">
          <table v-if="derivativesItems.length" class="w-full text-xs">
            <thead>
              <tr class="text-terminal-dim border-b border-gray-700">
                <th class="text-left py-1">品种</th>
                <th class="text-right py-1">最新价</th>
                <th class="text-right py-1">涨跌</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in derivativesItems" :key="item.symbol"
                  class="border-b border-gray-800 hover:bg-white/5">
                <td class="py-1 text-gray-300 text-[11px]">{{ item.name }}</td>
                <td class="py-1 text-right font-mono text-[11px]">{{ formatPrice(item.price) }}</td>
                <td class="py-1 text-right font-mono text-[11px]"
                    :class="(item.change_pct || 0) >= 0 ? 'text-red-400' : 'text-green-400'">
                  {{ (item.change_pct || 0) >= 0 ? '+' : '' }}{{ (item.change_pct || 0).toFixed(2) }}%
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="flex-1 flex items-center justify-center text-terminal-dim text-xs">
            暂无商品数据
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import IndexLineChart from './IndexLineChart.vue'
import NewsFeed from './NewsFeed.vue'

const props = defineProps({
  marketData:       { type: Object, default: null },
  ratesData:        { type: Array,  default: () => [] },
  globalData:       { type: Array,  default: () => [] },
  chinaAllData:     { type: Array,  default: () => [] },
  sectorsData:      { type: Array,  default: () => [] },
  derivativesData:   { type: Array,  default: () => [] },
})

const gridRef          = ref(null)
const selectedIndex    = ref('000001')
const selectedPeriod   = ref('daily')
const commodityTab     = ref('sectors')
const activeIndicators = ref([])

let grid = null

// ── 指数选项（K线切换）──────────────────────────────────────────
const indexOptions = [
  { symbol: '000001', name: '上证',   color: '#f87171' },
  { symbol: '000300', name: '沪深300', color: '#60a5fa' },
  { symbol: '399001', name: '深证',   color: '#fbbf24' },
  { symbol: '399006', name: '创业板',  color: '#a78bfa' },
]
const currentIndexOption = computed(() =>
  indexOptions.find(i => i.symbol === selectedIndex.value) || indexOptions[0]
)

// ── Period 选项（Task 1: K线时间维度）────────────────────────────
const periods = [
  { key: 'realtime', label: '分时' },
  { key: 'daily',    label: '日K' },
  { key: 'weekly',   label: '周K' },
  { key: 'monthly',  label: '月K' },
]

// ── Indicator 选项（Task 1: MACD/BOLL 预留）────────────────────
const indicators = [
  { key: 'MACD',  label: 'MACD' },
  { key: 'BOLL', label: 'BOLL' },
  { key: 'KDJ',  label: 'KDJ' },
]

function switchIndex(idx) { selectedIndex.value = idx.symbol }
function switchPeriod(p)   { selectedPeriod.value = p }
function toggleIndicator(k) {
  const idx = activeIndicators.value.indexOf(k)
  if (idx >= 0) activeIndicators.value.splice(idx, 1)
  else activeIndicators.value.push(k)
}

// ── 数据计算属性 ────────────────────────────────────────────────
const timestamp = computed(() => props.marketData?.timestamp || '')
const tsDisplay  = computed(() => timestamp.value.slice(11, 19) || '')

const windItems = computed(() => {
  const w = props.marketData?.wind || {}
  return Object.values(w)
})

const globalItems = computed(() => props.globalData || [])
const chinaAllItems = computed(() => props.chinaAllData || [])

const sectorsItems = computed(() => {
  if (!props.sectorsData || !props.sectorsData.length) return []
  if (typeof props.sectorsData === 'string') {
    try { return JSON.parse(props.sectorsData) } catch { return [] }
  }
  return props.sectorsData
})

const derivativesItems = computed(() => props.derivativesData || [])

function formatPrice(v) {
  if (v == null || isNaN(v)) return '--'
  return Number(v).toLocaleString('en-US', { maximumFractionDigits: 2 })
}

onMounted(async () => {
  await nextTick()
  if (typeof window !== 'undefined' && window.GridStack) {
    grid = GridStack.init({ column: 12, cellHeight: 80, float: true, margin: 8 })
  }
})

onUnmounted(() => {
  grid?.destroy(false)
})
</script>

<style>
.grid-stack { width: 100%; }
.grid-stack-item-content { inset: 4px; overflow: hidden; border-radius: 8px; }
</style>
