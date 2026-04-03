<template>
  <!-- ━━━ 全屏模式：K线全屏（受Sidebar/TopBar/Copilot边界约束）━━━━━━━━━ -->
  <div v-if="isKlineFullscreen" class="flex flex-col terminal-panel" style="width:100%;z-index:50;display:flex;flex-direction:column;">
    <!-- 全屏顶部栏：指数+周期+指标+退出 -->
    <div class="flex items-center gap-2 px-4 py-2 border-b border-gray-700/50 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">📈 {{ currentIndexOption.name }} K线</span>
      <div class="flex gap-1 ml-2">
        <button v-for="idx in indexOptions" :key="idx.symbol"
                class="px-2 py-0.5 text-[10px] rounded border transition"
                :class="selectedIndex === idx.symbol
                  ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent'
                  : 'bg-terminal-bg border-gray-700 text-terminal-dim hover:border-gray-500'"
                @click="switchIndex(idx)">
          {{ idx.name }}
        </button>
      </div>
      <div class="flex gap-1">
        <button v-for="p in periods" :key="p.key"
                class="px-2 py-0.5 text-[10px] rounded border transition"
                :class="selectedPeriod === p.key
                  ? 'bg-blue-500/20 border-blue-500/50 text-blue-400'
                  : 'bg-terminal-bg border-gray-700 text-terminal-dim hover:border-gray-500'"
                @click="switchPeriod(p.key)">
          {{ p.label }}
        </button>
      </div>
      <span class="ml-2 text-terminal-dim text-[9px]">指标:</span>
      <button v-for="ind in indicators" :key="ind.key"
              class="px-1.5 py-0.5 text-[9px] rounded border transition"
              :class="activeIndicators.includes(ind.key)
                ? 'bg-purple-500/20 border-purple-500/50 text-purple-400'
                : 'bg-terminal-bg border-gray-700 text-terminal-dim hover:border-gray-500'"
              @click="toggleIndicator(ind.key)">
        {{ ind.label }}
      </button>
      <button class="ml-auto shrink-0 px-3 py-1 text-xs rounded border border-gray-600 text-gray-400 hover:border-red-500/50 hover:text-red-400 transition-colors"
              @click="isKlineFullscreen = false" title="退出全屏（ESC）">✕ 退出全屏</button>
    </div>
    <!-- 全屏图表 -->
    <div class="flex-1 min-h-0 p-1">
      <IndexLineChart
        :key="`fullscreen-${selectedIndex}-${selectedPeriod}`"
        :symbol="selectedIndex"
        :name="currentIndexOption.name"
        :color="currentIndexOption.color"
        :url="`/api/v1/market/history/${selectedIndex}?period=${selectedPeriod}`"
        :indicators="activeIndicators"
        @fullscreen-change="isKlineFullscreen = false"
      />
    </div>
  </div>

  <!-- ━━━ 正常网格模式 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
  <div v-show="!isKlineFullscreen" class="grid-stack" ref="gridRef">

    <!-- ━━━ Widget 1：A股K线（分时/日/周/月 + MACD/BOLL预留）━━━━━━━━━━ -->
    <!-- K线主图：左侧 8列，高度6单位 -->
    <div class="grid-stack-item"
         gs-x="0" gs-y="0" gs-w="8" gs-h="6" gs-min-w="4" gs-min-h="4">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <!-- 标题行 -->
        <div class="flex items-center justify-between mb-1 shrink-0">
          <span class="text-terminal-accent font-bold text-sm">📈 {{ currentIndexOption.name }} K线</span>
          <!-- 全屏按钮：独立一行，位于右上角 -->
          <button
            class="px-2 py-0.5 text-[10px] rounded border border-gray-600 text-gray-400 hover:border-terminal-accent/50 hover:text-terminal-accent transition-colors"
            @click="isKlineFullscreen = true"
            title="全屏"
          >⛶ 全屏</button>
        </div>
        <!-- 指数切换行 -->
        <div class="flex items-center gap-1 mb-1 shrink-0">
          <button v-for="idx in indexOptions" :key="idx.symbol"
                  class="px-2 py-0.5 text-[10px] rounded border transition"
                  :class="selectedIndex === idx.symbol
                    ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent'
                    : 'bg-terminal-bg border-gray-700 text-terminal-dim hover:border-gray-500'"
                  @click="switchIndex(idx)">
            {{ idx.name }}
          </button>
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
            @fullscreen-change="isKlineFullscreen = true"
          />
        </div>
      </div>
    </div>

    <!-- ━━━ Widget 2：市场情绪直方图（K线正下方，左侧8列）━━━━━━━━━━━━━ -->
    <!-- 移到K线下方，占据完整8列宽度，让11个柱状图舒展显示 -->
    <div class="grid-stack-item"
         gs-x="0" gs-y="6" gs-w="8" gs-h="5" gs-min-w="4" gs-min-h="4">
      <div class="grid-stack-item-content terminal-panel p-3">
        <SentimentGauge :market-data="marketData" @symbol-click="handleWindClick" />
      </div>
    </div>

    <!-- ━━━ Widget 3：快讯新闻（情绪图下方，左侧8列）━━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="0" gs-y="11" gs-w="8" gs-h="6" gs-min-w="4" gs-min-h="4">
      <div class="grid-stack-item-content terminal-panel p-3">
        <NewsFeed />
      </div>
    </div>

    <!-- ━━━ Widget 4：风向标（右上，右侧4列）━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="8" gs-y="0" gs-w="4" gs-h="6" gs-min-w="3" gs-min-h="3">
      <div class="grid-stack-item-content terminal-panel p-2">
        <!-- Phase 5: 8个风向标（4指数 + 4宏观）两列卡片网格（密度升级：padding 20%） -->
        <div class="text-[10px] text-terminal-dim mb-1 flex items-center justify-between">
          <span>🌐 市场风向标</span>
          <span class="text-[9px] opacity-60">{{ windItems.length }}标的</span>
        </div>
        <!-- 两列卡片网格：消除垂直留白，充分利用右侧宽度（密度升级） -->
        <div class="grid grid-cols-2 gap-1 p-0.5">
          <div
            v-for="item in windItems" :key="item.symbol"
            class="bg-gray-800/50 rounded p-1.5 flex flex-col items-center justify-center cursor-pointer hover:bg-gray-700/50 transition-colors"
            @click="handleWindClick(item)"
          >
            <!-- 标的名称（分类标签） -->
            <div class="flex items-center gap-0.5 mb-0.5">
              <span
                class="text-[7px] px-0.5 rounded border"
                :class="item.category === 'macro' ? 'border-amber-500/40 text-amber-400' : 'border-cyan-500/40 text-cyan-400'"
              >{{ item.category === 'macro' ? '📊' : '📈' }}</span>
              <span class="text-[9px] text-gray-200 truncate max-w-[60px]" :title="item.name">{{ item.name }}</span>
            </div>
            <!-- 最新价 -->
            <div class="text-[10px] font-mono text-gray-100 text-center">
              {{ item.category === 'macro' ? formatMacroPrice(item) : formatPrice(item.price) }}
            </div>
            <!-- 涨跌幅 -->
            <div
              class="text-[10px] font-mono font-bold"
              :class="(item.change_pct || 0) >= 0 ? 'text-red-400' : 'text-green-400'"
            >
              {{ (item.change_pct || 0) >= 0 ? '+' : '' }}{{ (item.change_pct || 0).toFixed(2) }}%
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ━━━ Widget 5：行业与资金风口（右侧4列，中间）━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="8" gs-y="6" gs-w="4" gs-h="6" gs-min-w="3" gs-min-h="4">
      <div class="grid-stack-item-content terminal-panel p-2">
        <HotSectors @sector-click="handleSectorClick" />
      </div>
    </div>

    <!-- ━━━ Widget 6：国内市场指数（右侧4列，下方）━━━━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="8" gs-y="12" gs-w="4" gs-h="5" gs-min-w="3" gs-min-h="3">
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
                  class="border-b border-gray-800 hover:bg-white/5 cursor-pointer transition-colors"
                  @click="handleChinaClick(item)">
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

    <!-- ━━━ Widget 7：全市场个股透视看板（底部全宽12列）━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="0" gs-y="17" gs-w="12" gs-h="8" gs-min-w="6" gs-min-h="5">
      <div class="grid-stack-item-content terminal-panel p-3">
        <StockScreener />
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import IndexLineChart from './IndexLineChart.vue'
import NewsFeed from './NewsFeed.vue'
import SentimentGauge from './SentimentGauge.vue'
import HotSectors from './HotSectors.vue'
import StockScreener from './StockScreener.vue'
import { useMarketStore } from '../composables/useMarketStore.js'

const { currentSymbol, currentSymbolName, currentColor, setSymbol } = useMarketStore()

const props = defineProps({
  marketData:   { type: Object, default: null },
  macroData:    { type: Array,  default: () => [] },  // Phase 5: USD/CNH · GOLD · WTI · VIX
  ratesData:    { type: Array,  default: () => [] },
  globalData:   { type: Array,  default: () => [] },
  chinaAllData: { type: Array,  default: () => [] },
  isLocked:     { type: Boolean, default: true },
})

const emit = defineEmits(['toggle-lock'])

const gridRef          = ref(null)
const selectedIndex    = ref(currentSymbol.value)
const selectedPeriod   = ref('daily')
const activeIndicators = ref([])

// ━━━ 全屏模式 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const isKlineFullscreen = ref(false)

function onKeyDown(e) {
  if (e.key === 'Escape' && isKlineFullscreen.value) {
    isKlineFullscreen.value = false
  }
}

// ── 全局状态同步 ─────────────────────────────────────────────────
watch(currentSymbol, (sym) => {
  selectedIndex.value = sym
})

// ── 列表点击联动 ─────────────────────────────────────────────────
function handleGlobalClick(item) {
  const symbolMap = {
    'NDX': 'ndx', 'SPX': 'spx', 'DJI': 'dji', 'HSI': 'hsi', 'N225': 'nikkei',
    'ndx': 'ndx', 'spx': 'spx', 'dji': 'dji', 'hsi': 'hsi', 'nikkei': 'nikkei',
  }
  const sym = symbolMap[item.symbol?.toLowerCase()] || item.symbol
  const opt = { symbol: sym, name: item.name, color: '#60a5fa' }
  setSymbol(opt.symbol, opt.name, opt.color)
  selectedIndex.value = opt.symbol
}

function handleChinaClick(item) {
  setSymbol(item.symbol, item.name, '#f87171')
  selectedIndex.value = item.symbol
}

function handleWindClick(item) {
  const sym = item.symbol || item.key
  setSymbol(sym, item.name, '#f87171')
  selectedIndex.value = sym
}

function handleSectorClick(sec) {
  setSymbol('000001', sec.name, '#fbbf24')
  selectedIndex.value = '000001'
}

let grid = null

// ── 指数选项（K线切换）──────────────────────────────────────────
const indexOptions = [
  { symbol: '000001', name: '上证',   color: '#f87171' },
  { symbol: '000300', name: '沪深300', color: '#60a5fa' },
  { symbol: '399001', name: '深证',   color: '#fbbf24' },
  { symbol: '399006', name: '创业板',  color: '#a78bfa' },
]
// 注意：必须从本地 selectedIndex 查找，不能用 currentSymbol（全局面经 store）
// 否则切换 K 线组件指数时 name 不跟随 selectedIndex 更新
const currentIndexOption = computed(() => {
  const opt = indexOptions.find(o => o.symbol === selectedIndex.value) || indexOptions[0]
  return opt
})

const periods = [
  { key: 'minutely', label: '分时' },
  { key: 'daily',    label: '日K' },
  { key: 'weekly',   label: '周K' },
  { key: 'monthly',  label: '月K' },
]

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

// Phase 5: 合并4大指数 + 4大宏观 = 8个风向标
const windItems = computed(() => {
  const indices = props.marketData?.wind || {}
  const macros  = props.macroData  || []

  // 指数行（保留原有结构）
  const indexRows = Object.entries(indices).map(([sym, item]) => ({
    symbol:     sym,
    name:       item.name,
    price:      item.index,
    change_pct: item.change_pct,
    status:     item.status,
    category:   'index',   // 指数
  }))

  // 宏观行（USD/CNH · 黄金 · WTI · VIX）
  const macroRows = macros.map(m => ({
    symbol:     m.name,      // 展示用名称作 key
    name:       m.name,
    price:      m.price,
    change_pct: m.change_pct,
    unit:       m.unit || '',
    status:     m.timestamp || '',
    category:   'macro',    // 宏观大宗
  }))

  return [...indexRows, ...macroRows]
})
const globalItems = computed(() => props.globalData || [])
const chinaAllItems = computed(() => props.chinaAllData || [])

function formatPrice(v) {
  if (v == null || isNaN(v)) return '--'
  return Number(v).toLocaleString('en-US', { maximumFractionDigits: 2 })
}

// Phase 5: 格式化宏观价格（带单位）
function formatMacroPrice(item) {
  const p = formatPrice(item.price)
  return item.unit ? `${p} ${item.unit}` : p
}

// ── GridStack 锁定 ─────────────────────────────────────────────
// ── GridStack 锁定：响应 props.isLocked 变化 ────────────────────
watch(() => props.isLocked, (locked) => {
  if (grid) {
    grid.setStatic(locked)
  }
}, { immediate: true })

function toggleLock() {
  emit('toggle-lock')
}

onMounted(async () => {
  window.addEventListener('keydown', onKeyDown)
  await nextTick()
  if (typeof window !== 'undefined' && window.GridStack) {
    grid = GridStack.init({ column: 12, cellHeight: 80, float: true, margin: 8 })
    grid.setStatic(props.isLocked)  // 跟随 props 初始状态
  }
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  grid?.destroy(false)
})
</script>

<style>
.grid-stack { width: 100%; }
.grid-stack-item-content { inset: 4px; overflow: hidden; border-radius: 8px; }
</style>
