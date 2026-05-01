<template>
  <!-- ━━━ 移动端：单列垂直流式布局 (< 768px) ━━━━━━━━━━━━━━━ -->
  <div v-if="isMobile" class="flex flex-col gap-3 px-4 py-3 overflow-y-auto min-w-0" style="height: 100dvh; padding-bottom: 80px;">

    <!-- 快捷导航胶囊 -->
    <div class="flex gap-2 overflow-x-auto pb-1 scrollbar-hide shrink-0">
      <button v-for="anchor in mobileAnchors" :key="anchor.id"
        :href="`#${anchor.id}`"
        class="shrink-0 px-2 py-0 rounded-full text-xs border transition-colors h-5 flex items-center"
        :class="'bg-terminal-accent/10 border-terminal-accent/30 text-terminal-accent hover:bg-terminal-accent/20'"
        @click.prevent="scrollToMobileSection(anchor.id)">
        {{ anchor.label }}
      </button>
    </div>

    <!-- K线图：自适应高度，内部图表自适应 -->
    <div id="section-chart" class="terminal-panel p-4 rounded-xl shadow-lg border border-theme/10 shrink-0" style="min-height: 240px;">
      <div class="flex items-center justify-between mb-2 shrink-0">
        <span class="text-terminal-accent font-bold text-sm">📈 指标图表</span>
      </div>
      <IndexLineChart :symbol="selectedIndex" :period="selectedPeriod" class="w-full" style="height: 180px;" />
    </div>

    <!-- A股监测：自适应高度，内部滚动 -->
    <div id="section-screener" class="terminal-panel p-4 rounded-xl shadow-lg border border-theme/10 shrink-0" style="min-height: 300px; max-height: 50vh; overflow: hidden;">
      <div class="text-terminal-accent font-bold text-sm mb-2 shrink-0">📊 A股监测</div>
      <div class="w-full overflow-y-auto" style="height: calc(100% - 32px);">
        <StockScreener :data="globalItems" @symbol-click="handleScreenerClick" />
      </div>
    </div>

    <!-- 市场情绪 -->
    <div id="section-sentiment" class="terminal-panel p-4 rounded-xl shadow-lg border border-theme/10 shrink-0" style="min-height: 180px;">
      <SentimentGauge :market-data="{ indices: indices }" :macro-data="macroData" @symbol-click="handleWindClick" class="w-full" />
    </div>

    <!-- 板块热度：自适应高度，内部滚动 -->
    <div id="section-sectors" class="terminal-panel p-4 rounded-xl shadow-lg border border-theme/10 shrink-0" style="min-height: 280px; max-height: 45vh; overflow: hidden;">
      <HotSectors :data="sectors" class="w-full" />
    </div>

    <!-- 新闻快讯：自适应高度，内部滚动 -->
    <div id="section-news" class="terminal-panel p-4 rounded-xl shadow-lg border border-theme/10 shrink-0" style="min-height: 300px; max-height: 50vh; overflow: hidden;">
      <NewsFeed class="w-full" />
    </div>
  </div>

  <!-- ━━━ 桌面端：GridStack 网格布局 (≥ 768px) ━━━━━━━━━━━━ -->
  <div v-else class="grid-stack" ref="gridRef">

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
            class="px-2 py-0.5 text-[10px] rounded border border-theme-secondary text-theme-secondary hover:border-terminal-accent/50 hover:text-terminal-accent transition-colors"
            @click="handleFullscreenClick()"
            title="全屏"
          >⛶ 全屏</button>
        </div>
        <!-- 指数切换行 -->
        <div class="flex items-center gap-1 mb-1 shrink-0">
          <button v-for="idx in indexOptions" :key="idx.symbol"
                  class="px-2 py-0.5 text-[10px] rounded border transition"
                  :class="selectedIndex === idx.symbol
                    ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent'
                    : 'bg-terminal-bg border-theme text-theme-tertiary hover:border-gray-500'"
                  @click="switchIndex(idx)">
            {{ idx.name }}
          </button>
        </div>
        <!-- Period selector -->
        <div class="flex items-center gap-1 mb-2 shrink-0">
          <button v-for="p in periods" :key="p.key"
                  class="px-2 py-0.5 text-[10px] rounded border transition"
                  :class="selectedPeriod === p.key
                    ? 'bg-[var(--color-info-bg)] border-blue-500/50 text-[var(--color-info)]'
                    : 'bg-terminal-bg border-theme text-theme-tertiary hover:border-gray-500'"
                  @click="switchPeriod(p.key)">
            {{ p.label }}
          </button>
          <!-- Indicator toggles -->
          <span class="ml-2 text-theme-tertiary text-[9px]">指标:</span>
          <button v-for="ind in indicators" :key="ind.key"
                  class="px-1.5 py-0.5 text-[9px] rounded border transition"
                  :class="activeIndicators.includes(ind.key)
                    ? 'bg-[var(--color-primary-bg)] border-purple-500/50 text-[var(--color-primary)]'
                    : 'bg-terminal-bg border-theme text-theme-tertiary hover:border-gray-500'"
                  @click="toggleIndicator(ind.key)">
            {{ ind.label }}
          </button>
        </div>
        <div class="flex-1 min-h-0">
          <!-- IndexLineChart 内部已显示名称，这里不再重复显示 -->
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
    <!-- 情绪面板扩展至 10 单位高度（800px），彻底消除滚动条 -->
    <div class="grid-stack-item"
         gs-x="0" gs-y="6" gs-w="8" gs-h="10" gs-min-w="4" gs-min-h="8">
      <div class="grid-stack-item-content terminal-panel p-3">
        <SentimentGauge :market-data="marketData" :macro-data="macroData" @symbol-click="handleWindClick" />
      </div>
    </div>

    <!-- ━━━ Widget 3：快讯新闻（情绪图下方，16起）━━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="0" gs-y="16" gs-w="8" gs-h="6" gs-min-w="4" gs-min-h="4">
      <div class="grid-stack-item-content terminal-panel p-3">
        <NewsFeed />
      </div>
    </div>

    <!-- ━━━ Widget 4：风向标（右上，右侧4列）━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="8" gs-y="0" gs-w="4" gs-h="6" gs-min-w="3" gs-min-h="3">
      <div class="grid-stack-item-content terminal-panel p-2">
        <!-- Phase 5: 8个风向标（4指数 + 4宏观）两列卡片网格（密度升级：padding 20%） -->
        <div class="text-[10px] text-theme-tertiary mb-1 flex items-center justify-between">
          <span>🌐 市场风向标</span>
          <span class="text-[9px] opacity-60">{{ windItems.length }}标的</span>
        </div>
        <!-- 两列卡片网格：消除垂直留白，充分利用右侧宽度（密度升级） -->
        <div class="grid grid-cols-2 gap-1 p-0.5">
          <div
            v-for="item in windItems" :key="item.symbol"
            class="bg-theme-secondary/50 rounded p-1.5 flex flex-col items-center justify-center cursor-pointer hover:bg-theme-tertiary/50 transition-colors min-w-0 overflow-hidden"
            @click="handleWindClick(item)"
          >
            <!-- 标的名称（分类标签） -->
            <div class="flex items-center gap-0.5 mb-0.5">
              <span
                class="text-[7px] px-0.5 rounded border"
                :class="item.category === 'macro' ? 'border-[var(--color-warning-border)] text-[var(--color-warning)]' : 'border-[var(--color-info-border)] text-[var(--color-info)]'"
              >{{ item.category === 'macro' ? '📊' : '📈' }}</span>
              <span class="text-[9px] text-theme-primary truncate max-w-[60px]" :title="item.name">{{ item.name }}</span>
            </div>
            <!-- 最新价（右对齐） -->
            <div class="text-[10px] font-mono text-theme-primary text-right w-full">
              {{ item.category === 'macro' ? formatMacroPrice(item) : formatPrice(item.price) }}
            </div>
            <!-- 涨跌幅（右对齐） -->
            <div
              class="text-[10px] font-mono font-bold text-right w-full"
              :class="(item.change_pct || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
            >
              {{ (item.change_pct || 0) >= 0 ? '+' : '' }}{{ (item.change_pct || 0).toFixed(2) }}%
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ━━━ Widget 5：资金流向（独立，右侧4列，6起）━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="8" gs-y="6" gs-w="4" gs-h="5" gs-min-w="3" gs-min-h="4">
      <div class="grid-stack-item-content terminal-panel p-2">
        <FundFlowPanel />
      </div>
    </div>

    <!-- ━━━ Widget 5.1：行业风口（独立，右侧4列，11起）━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="8" gs-y="11" gs-w="4" gs-h="5" gs-min-w="3" gs-min-h="4">
      <div class="grid-stack-item-content terminal-panel p-2">
        <HotSectors @sector-click="handleSectorClick" />
      </div>
    </div>

    <!-- ━━━ Widget 6：国内市场指数（右侧4列，16起，填补Y=16空挡）━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="8" gs-y="16" gs-w="4" gs-h="5" gs-min-w="3" gs-min-h="3">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <div class="flex items-center justify-between mb-2 shrink-0">
          <span class="text-terminal-accent font-bold text-sm">🇨🇳 国内指数</span>
          <span class="text-theme-tertiary text-[10px]">{{ tsDisplay }}</span>
        </div>
        <div class="flex-1 overflow-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="text-theme-tertiary border-b border-theme">
                <th class="text-left py-1">指数</th>
                <th class="text-right py-1">最新价</th>
                <th class="text-right py-1">涨跌幅</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in chinaAllItems" :key="item.symbol"
                  class="border-b border-theme-secondary hover:bg-white/5 cursor-pointer transition-colors"
                  @click="handleChinaClick(item)">
                <td class="py-1 text-theme-primary text-[11px]">{{ item.name }}</td>
                <td class="py-1 text-right font-mono text-[11px]">{{ formatPrice(item.price) }}</td>
                <td class="py-1 text-right font-mono text-[11px]"
                    :class="(item.change_pct || 0) >= 0 ? 'text-bullish' : 'text-bearish'">
                  {{ (item.change_pct || 0) >= 0 ? '+' : '' }}{{ (item.change_pct || 0).toFixed(2) }}%
                </td>
              </tr>
              <tr v-if="!chinaAllItems.length">
                <td colspan="3" class="py-4 text-center text-theme-tertiary text-xs">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ━━━ Widget 7：全市场个股透视看板（底部全宽12列，21起）━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="0" gs-y="21" gs-w="12" gs-h="8" gs-min-w="6" gs-min-h="5">
      <div class="grid-stack-item-content terminal-panel p-3">
        <StockScreener @symbol-click="handleScreenerClick" />
      </div>
    </div>

    <!-- ━━━ Widget 8：价格预警管理（右侧3列，15起）━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="9" gs-y="15" gs-w="3" gs-h="6" gs-min-w="2" gs-min-h="4">
      <div class="grid-stack-item-content terminal-panel p-3">
        <AlertManager />
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useBreakpoints, breakpointsTailwind, useIntervalFn, useDocumentVisibility, useDebounceFn } from '@vueuse/core'
import { apiFetch } from '../utils/api.js'
import { useMarketStore } from '../stores/market.js'
import IndexLineChart    from './IndexLineChart.vue'
import NewsFeed          from './NewsFeed.vue'
import SentimentGauge    from './SentimentGauge.vue'
import HotSectors        from './HotSectors.vue'
import FundFlowPanel     from './FundFlowPanel.vue'
import StockScreener     from './StockScreener.vue'
import AlertManager      from './AlertManager.vue'

const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('md')  // < 768px is mobile

const { currentSymbol, currentSymbolName, currentColor, setSymbol, normalizeSymbol, indices } = useMarketStore()
const currentIndexName = ref('上证指数')

const props = defineProps({
  marketData:     { type: Object, default: null },
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
  let sym = item.symbol || item.key || ''
  const LOWER_MACRO_MAP = {
    '黄金': 'GOLD', 'xau': 'GOLD', 'gld': 'GOLD',
    'wti原油': 'WTI', 'wti': 'WTI', '原油': 'WTI', 'wtic': 'WTI',
    'vix': 'VIX', '恐慌指数': 'VIX', '波幅': 'VIX',
    'usd/cnh': 'CNHUSD', '离岸人民币': 'CNHUSD', '人民币': 'CNHUSD',
    'dxy': 'DXY', '美元指数': 'DXY',
    '恒指波幅': 'VHSI', 'vhsi': 'VHSI',
    '日经225': 'N225', '日经': 'N225',
    // 扩展：无括号的标准名称
    'gold': 'GOLD', 'wti': 'WTI', 'vix': 'VIX', 'cnhusd': 'CNHUSD',
    'dji': 'DJI', 'spx': 'SPX', 'ndx': 'NDX',
  }

  // 名称特征匹配：macro 品种只有 name（中文/英文），没有标准 symbol
  if (!/^[A-Za-z]{2,6}$/.test(sym)) {
    // 去掉括号及其内容（如 "(美元)" "(VHSI)"），再匹配
    const cleaned = sym.replace(/\([^)]*\)/g, '').trim()
    const lower = cleaned.toLowerCase()
    if (LOWER_MACRO_MAP[lower] || LOWER_MACRO_MAP[cleaned]) {
      sym = LOWER_MACRO_MAP[cleaned] || LOWER_MACRO_MAP[lower]
    } else {
      // 兜底：去掉非字母数字后取前6字符 normalize（仅保留英文和数字）
      const stripped = cleaned.replace(/[^a-zA-Z0-9]/g, '').slice(0, 6)
      sym = LOWER_MACRO_MAP[stripped] || normalizeSymbol(stripped)
    }
  }

  const norm = normalizeSymbol(sym)
  setSymbol(norm, item.name || sym, '#f87171')
  queueMicrotask(() => {
    selectedIndex.value = norm
    currentIndexName.value = item.name || norm
  })
}

function handleGlobalClick(item) {
  // globalItems 可能有 usIXIC / usNDX / hkHSI 等前缀
  const norm = normalizeSymbol(item.symbol || item.name || item.key || '')
  setSymbol(norm, item.name || norm, '#60a5fa')
  // 同步更新本地 selectedIndex
  queueMicrotask(() => {
    selectedIndex.value = norm
    currentIndexName.value = item.name || norm
  })
}

function handleChinaClick(item) {
  const norm = normalizeSymbol(item.symbol)
  setSymbol(norm, item.name, '#f87171')
  // 同步更新本地 selectedIndex
  queueMicrotask(() => {
    selectedIndex.value = norm
    currentIndexName.value = item.name || item.symbol
  })
}

function handleSectorClick(sec) {
  // 板块无独立K线，使用板块的领涨股代码替代
  const rawCode = sec.top_stock?.code || ''
  const topName = sec.top_stock?.name || ''

  // 统一用 normalizeSymbol 处理：自动添加 sh/sz 前缀（兼容纯数字码）
  // normalizeSymbol 规则：6/9/000开头→sh；其余(0/2/3)→sz
  const code = rawCode ? normalizeSymbol(rawCode) : 'sh000001'
  const displayName = topName ? `${sec.name}-${topName}` : sec.name
  setSymbol(code, displayName, '#fbbf24')
  queueMicrotask(() => {
    selectedIndex.value = code
    currentIndexName.value = displayName
  })
}

function handleScreenerClick({ symbol, name }) {
  const norm = normalizeSymbol(symbol)
  setSymbol(norm, name || symbol, '#00ff88')
  queueMicrotask(() => {
    selectedIndex.value = norm
    currentIndexName.value = name || symbol
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
  { key: 'BOLL',  label: 'BOLL' },
  { key: 'KDJ',  label: 'KDJ' },
  { key: 'RSI',  label: 'RSI' },
  { key: 'WR',   label: 'WR' },
  { key: 'OBV',  label: 'OBV' },
  { key: 'DMI',  label: 'DMI' },
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

function handleFullscreenClick() {
  // selectedIndex 是 Vue ref，模板中需加 .value 才能取到字符串值；
  // 使用 indexOptions[0].symbol 作为兜底，确保永远有有效 symbol
  let raw = selectedIndex.value || indexOptions[0]?.symbol || 'sh000001'
  let finalSymbol = String(raw)

  // ── 硬编码前缀修复（v0.5.106）：后端 WS 要求带 sh/sz 前缀，纯数字码直接硬塞 ──
  if (/^\d{6}$/.test(finalSymbol)) {
    if (finalSymbol.startsWith('6') || finalSymbol.startsWith('0000')) {
      finalSymbol = 'sh' + finalSymbol
    } else {
      finalSymbol = 'sz' + finalSymbol
    }
  }

  const name = currentIndexName.value || indexOptions[0]?.name || '上证指数'
  console.log('[DashboardGrid] 最终修正并发送的参数:', { symbol: finalSymbol, name, raw })
  emit('open-fullscreen', { symbol: finalSymbol, name })
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
  // 修复: marketData 从 App.vue 传来时已经是 wind 对象本身（不是 {wind: {...}}）
  const indices = props.marketData || {}
  const macros  = macroData.value || []

  // 指数行（实时 Sina 数据：item.price 是当前价）
  const indexRows = Object.entries(indices).map(([sym, item]) => ({
    symbol:     sym,
    name:       item.name,
    price:      item.price ?? item.index ?? 0,  // 兼容新旧格式
    change_pct: item.change_pct ?? 0,
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
const globalItems = computed(() => globalData.value || [])
const chinaAllItems = computed(() => props.chinaAllData || [])
const sectors = computed(() => props.sectorsData || [])

const mobileAnchors = [
  { id: 'section-chart',     label: '📈 图表' },
  { id: 'section-screener',  label: '📊 监测' },
  { id: 'section-sentiment', label: '🌡️ 情绪' },
  { id: 'section-sectors',   label: '🔥 板块' },
  { id: 'section-news',      label: '📰 快讯' },
]

function scrollToMobileSection(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// ── 低频数据自持（宏观/利率/海外，5分钟轮询）────────────────────────
const macroData  = ref([])
const ratesData  = ref([])
const globalData = ref([])

async function fetchLowFreq() {
  try {
    const d = await apiFetch('/api/v1/market/macro')
    macroData.value = d?.macro || d?.data?.macro || d || []
  } catch { /* silent */ }
  try {
    const d = await apiFetch('/api/v1/market/rates')
    ratesData.value = d?.rates || d?.data?.rates || d || []
  } catch { /* silent */ }
  try {
    const d = await apiFetch('/api/v1/market/global')
    globalData.value = d?.global || d?.data?.global || d || []
  } catch { /* silent */ }
}

const { pause: pauseLow, resume: resumeLow } = useIntervalFn(fetchLowFreq, 300_000, { immediate: false })
const visibility = useDocumentVisibility()

watch(visibility, (v) => {
  if (v === 'visible') { resumeLow(); fetchLowFreq() }
  else { pauseLow() }
})

onMounted(async () => {
  fetchLowFreq()
  await nextTick()
  if (!isMobile.value && typeof window !== 'undefined' && window.GridStack && document.querySelector('.grid-stack')) {
    grid = GridStack.init({
      column: 12,
      cellHeight: 80,
      float: true,
      margin: 8,
      disableDrag: isMobile.value,   // 手机端禁止拖拽
      disableResize: isMobile.value, // 手机端禁止缩放
    })
    grid.setStatic(props.isLocked)
  }
})

onUnmounted(() => {
  grid?.destroy(false)
  pauseLow()
})

function formatPrice(v) {
  if (v == null || isNaN(v)) return '--'
  return Number(v).toLocaleString('en-US', { maximumFractionDigits: 2 })
}

// Phase 5: 格式化宏观价格（带单位）
function formatMacroPrice(item) {
  const p = formatPrice(item.price)
  return item.unit ? `${p} ${item.unit}` : p
}

// ── StockScreener / Copilot 等外部改变了 currentSymbol 时同步 selectedIndex ──
// 防抖版：避免 rapid setSymbol 调用导致频繁更新
let syncIndexTimer = null
watch(() => currentSymbol.value, (sym) => {
  clearTimeout(syncIndexTimer)
  syncIndexTimer = setTimeout(() => {
    if (sym && sym !== selectedIndex.value) {
      selectedIndex.value = sym
    }
    currentIndexName.value = currentSymbolName.value || currentIndexName.value
  }, 50)
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
function toggleLock() {
  emit('toggle-lock')
}
</script>

<style>
.grid-stack { width: 100%; height: 100%; overflow: hidden; }
.grid-stack-item-content { inset: 4px; overflow: hidden; border-radius: 8px; display: flex; flex-direction: column; }
.scrollbar-hide::-webkit-scrollbar { display: none; }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
</style>
