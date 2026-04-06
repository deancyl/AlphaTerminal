<template>
  <!-- ━━━ 正常网格模式 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
  <div class="grid-stack" ref="gridRef">

    <!-- ━━━ Widget 1：A股K线（分时/日/周/月 + MACD/BOLL预留）━━━━━━━━━━ -->
    <!-- K线主图：左侧 8列，高度6单位 -->
    <div class="grid-stack-item"
         gs-x="0" gs-y="0" gs-w="8" gs-h="6" gs-min-w="4" gs-min-h="4">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <!-- 标题行 -->
        <div class="flex items-center justify-between mb-1 shrink-0">
          <span class="text-terminal-accent font-bold text-sm">📈 指标图表</span>
          <!-- 全屏按钮：独立一行，位于右上角 -->
          <button
            class="px-2 py-0.5 text-[10px] rounded border border-gray-600 text-gray-400 hover:border-terminal-accent/50 hover:text-terminal-accent transition-colors"
            @click="emit('open-fullscreen', { symbol: selectedIndex, name: currentIndexName })"
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
          <!-- 选中的指数名称 -->
          <div class="text-xs text-gray-400 mb-1 px-1">
            {{ currentIndexName }}
          </div>
          <IndexLineChart
            :key="`${selectedIndex}-${selectedPeriod}`"
            :symbol="selectedIndex"
            :name="currentIndexName"
            :color="currentIndexOption.color"
            :url="`/api/v1/market/history/${selectedIndex}?period=${selectedPeriod}`"
            :indicators="activeIndicators"

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
            <!-- 最新价（右对齐） -->
            <div class="text-[10px] font-mono text-gray-100 text-right w-full">
              {{ item.category === 'macro' ? formatMacroPrice(item) : formatPrice(item.price) }}
            </div>
            <!-- 涨跌幅（右对齐） -->
            <div
              class="text-[10px] font-mono font-bold text-right w-full"
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
import IndexLineChart    from './IndexLineChart.vue'
import NewsFeed from './NewsFeed.vue'
import SentimentGauge from './SentimentGauge.vue'
import HotSectors from './HotSectors.vue'
import StockScreener from './StockScreener.vue'
import { useMarketStore } from '../composables/useMarketStore.js'

const { currentSymbol, currentSymbolName, currentColor, setSymbol, normalizeSymbol } = useMarketStore()
const currentIndexName = ref('上证指数')

const props = defineProps({
  marketData:     { type: Object, default: null },
  macroData:      { type: Array,  default: () => [] },
  ratesData:      { type: Array,  default: () => [] },
  globalData:     { type: Array,  default: () => [] },
  chinaAllData:   { type: Array,  default: () => [] },
  sectorsData:    { type: Array,  default: () => [] },
  derivativesData:{ type: Array,  default: () => [] },
  isLocked:       { type: Boolean, default: true },
})

const emit = defineEmits(['toggle-lock', 'open-fullscreen'])

const gridRef          = ref(null)
const selectedIndex    = ref(currentSymbol.value)
const selectedPeriod   = ref('daily')
const activeIndicators = ref([])

// ── 列表点击联动 ─────────────────────────────────────────────────
// 宏观品种名称 → symbol 映射（windItems 的宏观行没有 symbol 字段）
const _MACRO_NAME_MAP = {
  '黄金': 'GOLD', '黄金(美元)': 'GOLD', 'XAU': 'GOLD', 'GLD': 'GOLD',
  'WTI原油': 'WTI', 'WTI': 'WTI', 'NYMEX_WTI': 'WTI',
  'VIX': 'VIX', '恐慌指数': 'VIX', '波动率指数': 'VIX',
  'USD/CNH': 'CNHUSD', 'CNHUSD': 'CNHUSD', '离岸人民币': 'CNHUSD',
  'DXY': 'DXY', '美元指数': 'DXY',
  '恒指波幅': 'VHSI', 'VHKS': 'VHSI',
  '日经225': 'N225', '日经': 'N225',
}

function handleWindClick(item) {
  // 宏观大宗（黄金/WTI/VIX/外汇）无 K 线数据，跳过图表切换
  if (item.category === 'macro') {
    setSymbol('GOLD', item.name || 'GOLD', '#fbbf24')
    return
  }

  // 指数类：有独立 K 线，直接用 symbol
  let sym = item.symbol || item.key || ''

  // 名称特征匹配（宏观大宗没有 symbol 字段，只有全名）
  if (!/^[A-Za-z]{2,6}$/.test(sym)) {
    const lower = sym.toLowerCase()
    if (lower.includes('黄金') || lower.includes('xau') || lower.includes('gld')) {
      sym = 'GOLD'
    } else if (lower.includes('wti') || lower.includes('原油')) {
      sym = 'WTI'
    } else if (lower.includes('vix') || lower.includes('波幅') || lower.includes('vhsi')) {
      sym = 'VIX'
    } else if (lower.includes('人民币') || lower.includes('cny') || lower.includes('cny')) {
      sym = 'CNH'
    } else if (lower.includes('美元') && !lower.includes('原油')) {
      sym = 'DXY'
    } else {
      // 兜底：去掉数字和特殊字符后 normalize
      sym = normalizeSymbol(sym.replace(/[^\w]/g, ''))
    }
  }

  const norm = normalizeSymbol(sym)
  setSymbol(norm, item.name || sym, '#f87171')
  currentIndexName.value = item.name || norm
}

function handleGlobalClick(item) {
  // globalItems 可能有 usIXIC / usNDX / hkHSI 等前缀
  const norm = normalizeSymbol(item.symbol || item.name || item.key || '')
  setSymbol(norm, item.name || norm, '#60a5fa')
  currentIndexName.value = item.name || norm
}

function handleChinaClick(item) {
  setSymbol(item.symbol, item.name, '#f87171')
  // currentIndexName 同步（selectedIndex 由 watch(currentSymbol) 统一处理）
  currentIndexName.value = item.name || item.symbol
}

function handleSectorClick(sec) {
  // 板块无独立K线，使用板块的领涨股代码替代
  const code = sec.top_stock?.code || '000001'
  const topName = sec.top_stock?.name || ''
  const displayName = topName ? `${sec.name}-${topName}` : sec.name
  setSymbol(code, displayName, '#fbbf24')
  queueMicrotask(() => {
    selectedIndex.value = code
    currentIndexName.value = displayName
  })
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

function switchIndex(idx) {
  setSymbol(idx.symbol, idx.name, idx.color)
  queueMicrotask(() => {
    selectedIndex.value = idx.symbol
    currentIndexName.value = idx.name || idx.symbol
  })
}
function onFullscreenSymbolChange({ symbol, name }) {
  switchIndex({ symbol, name })
}
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
// ── 标的切换时自动回退不支持的周期 ────────────────────────────────
// ── StockScreener / Copilot 等外部改变了 currentSymbol 时同步 selectedIndex ──
watch(currentSymbol, (sym) => {
  if (sym && sym !== selectedIndex.value) {
    selectedIndex.value = sym
  }
  // 同步名称（StockScreener 等外部组件通过 store.setSymbol 更新了 currentSymbolName）
  currentIndexName.value = currentSymbolName.value || currentIndexName.value
})

// ── 标的切换时自动回退不支持的周期 ────────────────────────────────
watch(selectedIndex, (sym) => {
  // 分钟系（分时/1min/5min...）仅支持 _MIN_KLINE_SUPPORTED 中的5只A股指数
  const MIN_SUPPORTED = new Set(['000001', '000300', '399001', '399006', '000688'])
  const MIN_PERIODS  = new Set(['minutely', '1min', '5min', '15min', '30min', '60min'])
  if (!MIN_SUPPORTED.has(sym) && MIN_PERIODS.has(selectedPeriod.value)) {
    selectedPeriod.value = 'daily'
  }
})

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
  await nextTick()
  if (typeof window !== 'undefined' && window.GridStack) {
    grid = GridStack.init({ column: 12, cellHeight: 80, float: true, margin: 8 })
    grid.setStatic(props.isLocked)  // 跟随 props 初始状态
  }
})

onUnmounted(() => {
  grid?.destroy(false)
})
</script>

<style>
.grid-stack { width: 100%; height: 100%; overflow: hidden; }
.grid-stack-item-content { inset: 4px; overflow: hidden; border-radius: 8px; display: flex; flex-direction: column; }
</style>
