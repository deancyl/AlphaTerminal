<template>
  <!-- ━━━ 全屏模式：K线全屏（受Sidebar/TopBar/Copilot边界约束）━━━━━━ -->
  <!-- position:fixed 相对于视口，左侧留240px给Sidebar，顶部留48px给Header -->
  <div v-show="ui.klineFullscreen" class="flex flex-col"
       style="position:fixed;top:48px;left:240px;right:0;bottom:0;z-index:50;background:#0f172a;overflow:hidden;">
    <!-- 全屏顶部栏：指数+周期+指标+退出 -->
    <div class="flex items-center gap-2 px-4 py-2 border-b border-gray-700/50 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">📈 {{ currentSymbolName }} K线</span>
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
              @click="ui.klineFullscreen = false" title="退出全屏（ESC）">✕ 退出全屏</button>
    </div>
    <!-- 全屏图表区域 -->
    <div class="flex-1 min-h-0">
      <AdvancedKlinePanel />
    </div>
  </div>

  <!-- ━━━ 正常网格模式 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
  <div v-show="!ui.klineFullscreen" class="grid-stack" ref="gridRef">

    <!-- ━━━ Widget 1：A股K线（分时/日/周/月 + MACD/BOLL预留）━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="0" gs-y="0" gs-w="8" gs-h="6" gs-min-w="4" gs-min-h="4">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <!-- 标题行（整行可点击进入全屏） -->
        <div class="flex items-center justify-between mb-1 shrink-0"
             style="touch-action: manipulation; cursor: pointer; min-height: 28px;"
             @click.stop="ui.klineFullscreen = true"
             title="点击进入全屏">
          <span class="text-terminal-accent font-bold text-sm">📈 {{ currentIndexOption.name }} K线</span>
          <button
            class="px-2 py-0.5 text-[10px] rounded border border-gray-600 text-gray-400 hover:border-terminal-accent/50 hover:text-terminal-accent transition-colors"
            style="touch-action: manipulation;"
            @click.stop="ui.klineFullscreen = true"
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
        <!-- 周期+指标行 -->
        <div class="flex items-center gap-1 mb-2 shrink-0">
          <button v-for="p in periods" :key="p.key"
                  class="px-2 py-0.5 text-[10px] rounded border transition"
                  :class="selectedPeriod === p.key
                    ? 'bg-blue-500/20 border-blue-500/50 text-blue-400'
                    : 'bg-terminal-bg border-gray-700 text-terminal-dim hover:border-gray-500'"
                  @click="switchPeriod(p.key)">
            {{ p.label }}
          </button>
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

    <!-- ━━━ Widget 2：市场情绪直方图（K线正下方，左侧8列）━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="0" gs-y="6" gs-w="8" gs-h="3" gs-min-w="4" gs-min-h="2">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <div class="flex items-center justify-between mb-2 shrink-0">
          <span class="text-terminal-accent font-bold text-sm">📊 市场情绪</span>
          <div class="flex gap-1">
            <button
              v-for="v in views" :key="v.key"
              class="px-2 py-0.5 text-[10px] rounded border transition"
              :class="view === v.key
                ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent'
                : 'bg-terminal-bg border-gray-700 text-terminal-dim hover:border-gray-500'"
              @click="view = v.key">
              {{ v.label }}
            </button>
          </div>
        </div>
        <div class="flex-1 min-h-0">
          <div v-if="view === 'emotion'" class="w-full h-full">
            <EmotionChart :symbol="currentSymbol" />
          </div>
          <div v-else-if="view === 'heatmap'" class="w-full h-full">
            <SectorHeatmap />
          </div>
          <div v-else class="w-full h-full">
            <AStockStatus />
          </div>
        </div>
      </div>
    </div>

    <!-- ━━━ Widget 3：资讯/快讯 Feed（右侧列）━━━━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="8" gs-y="0" gs-w="4" gs-h="9" gs-min-w="3" gs-min-h="4">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <NewsFeed />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useMarketStore } from '../composables/useMarketStore.js'
import { useUiStore } from '../composables/useUiStore.js'
import IndexLineChart  from './IndexLineChart.vue'
import EmotionChart    from './EmotionChart.vue'
import SectorHeatmap   from './SectorHeatmap.vue'
import AStockStatus    from './AStockStatus.vue'
import NewsFeed       from './NewsFeed.vue'
import AdvancedKlinePanel from './AdvancedKlinePanel.vue'

const { currentSymbol, currentSymbolName } = useMarketStore()
const { ui } = useUiStore()

const gridRef       = ref(null)
const selectedIndex  = ref(currentSymbol.value)
const selectedPeriod = ref('daily')
const activeIndicators = ref([])
const view = ref('emotion')

const indexOptions = [
  { symbol: 'sh000001', name: '上证',   color: '#f87171', type: 'index' },
  { symbol: 'sh000300', name: '沪深300', color: '#60a5fa', type: 'index' },
  { symbol: 'sz399001', name: '深证',   color: '#fbbf24', type: 'index' },
  { symbol: 'sz399006', name: '创业板', color: '#a78bfa', type: 'index' },
]

const currentIndexOption = computed(() =>
  indexOptions.find(o => o.symbol === selectedIndex.value) || indexOptions[0]
)

const SYMBOL_OPTIONS = [
  { symbol: 'sh000001', name: '上证指数',    color: '#f87171' },
  { symbol: 'sh000300', name: '沪深300',    color: '#60a5fa' },
  { symbol: 'sz399001', name: '深证成指',   color: '#fbbf24' },
  { symbol: 'sz399006', name: '创业板指',   color: '#a78bfa' },
  { symbol: 'sh000688', name: '科创50',     color: '#34d399' },
]

const periods = [
  { key: 'minutely', label: '分时' },
  { key: 'daily',     label: '日K'  },
  { key: 'weekly',    label: '周K'  },
  { key: 'monthly',   label: '月K'  },
]

const indicators = [
  { key: 'MA5',   label: 'MA5'  },
  { key: 'MA10',  label: 'MA10' },
  { key: 'MA20',  label: 'MA20' },
  { key: 'BOLL',  label: 'BOLL' },
]

const views = [
  { key: 'emotion',  label: '情绪'  },
  { key: 'heatmap',  label: '板块'  },
  { key: 'astock',   label: 'A股'   },
]

function getSymbolOption(symbol) {
  return SYMBOL_OPTIONS.find(o => o.symbol === symbol) || SYMBOL_OPTIONS[0]
}

function switchIndex(idx) {
  selectedIndex.value  = idx.symbol
  currentSymbol.value = idx.symbol
  currentIndexOption.value = idx
}

function switchPeriod(p) {
  selectedPeriod.value = p
}

function toggleIndicator(key) {
  const idx = activeIndicators.value.indexOf(key)
  if (idx >= 0) activeIndicators.value.splice(idx, 1)
  else activeIndicators.value.push(key)
}

// ── GridStack 初始化 ─────────────────────────────────────────
let grid = null

function initGrid() {
  if (typeof window === 'undefined' || !window.GridStack) return
  grid = window.GridStack.init({ column: 12, cellHeight: 80, float: true, margin: 8 })
  grid.setStatic(props.isLocked)
}

// ── 键盘ESC退出全屏 ───────────────────────────────────────────
function onKeyDown(e) {
  if (e.key === 'Escape' && ui.klineFullscreen) {
    ui.klineFullscreen = false
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  nextTick(initGrid)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  grid?.destroy(false)
})

// ── props ────────────────────────────────────────────────────
const props = defineProps({
  isLocked: { type: Boolean, default: false },
})

watch(() => props.isLocked, (v) => {
  grid?.setStatic(v)
})
</script>
