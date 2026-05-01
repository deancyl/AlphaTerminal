<template>
  <!-- 双层布局：上面盘口行 + 下面控制行 -->
  <div class="flex flex-col shrink-0 border-b border-theme bg-terminal-panel/90">

    <!-- 盘口行：标的+价格+MA+OHLCV（紧凑单行） -->
    <div class="flex items-center gap-x-2 px-2 py-0.5 overflow-x-auto text-[10px]">
      <!-- 标的+代码（固定） -->
      <div class="flex items-center gap-1 shrink-0">
        <span class="font-bold text-theme-primary whitespace-nowrap">{{ name }}</span>
        <span class="text-theme-tertiary font-mono">{{ code }}</span>
      </div>

      <span class="text-theme-tertiary shrink-0">|</span>

      <!-- 最新价 -->
      <span class="font-mono font-medium text-theme-primary shrink-0">{{ quote.price != null ? quote.price.toFixed(2) : '--' }}</span>

      <!-- 涨跌额/涨跌幅 -->
      <span class="shrink-0" :class="(quote.change ?? 0) >= 0 ? 'text-bullish' : 'text-bearish'">
        {{ (quote.change ?? 0) >= 0 ? '+' : '' }}{{ quote.change != null ? quote.change.toFixed(2) : '--' }}
      </span>
      <span class="shrink-0 px-1 py-0 rounded-sm text-[10px]"
        :class="(quote.change_pct ?? 0) >= 0 ? 'bg-[var(--color-up-bg)] text-bullish' : 'bg-[var(--color-down-bg)] text-bearish'">
        {{ (quote.change_pct ?? 0) >= 0 ? '+' : '' }}{{ quote.change_pct != null ? quote.change_pct.toFixed(2) : '--' }}%
      </span>

      <!-- MA 数值 -->
      <template v-for="ma in maDisplays" :key="ma.period">
        <span class="shrink-0 font-mono text-[10px]" :style="{ color: ma.color }">
          MA{{ ma.period }}<span class="text-theme-primary ml-0.5">{{ ma.value != null ? ma.value.toFixed(2) : '--' }}</span>
        </span>
      </template>

      <!-- 十字光标 OHLCV 数据（hover时显示在同一行，不遮挡图表） -->
      <template v-if="hoverData && Object.keys(hoverData).length">
        <span class="text-theme-tertiary shrink-0">|</span>
        <span class="shrink-0 text-theme-secondary font-mono text-[10px]">{{ hoverData.date || hoverData.time }}</span>
        <span class="shrink-0 text-theme-secondary font-mono text-[10px]">开<span class="text-theme-primary ml-0.5">{{ hoverData.open?.toFixed(2) }}</span></span>
        <span class="shrink-0 text-theme-secondary font-mono text-[10px]">高<span class="text-[var(--color-danger-light)] ml-0.5">{{ hoverData.high?.toFixed(2) }}</span></span>
        <span class="shrink-0 text-theme-secondary font-mono text-[10px]">低<span class="text-[var(--color-success-light)] ml-0.5">{{ hoverData.low?.toFixed(2) }}</span></span>
        <span class="shrink-0 text-theme-secondary font-mono text-[10px]">收<span class="text-theme-primary ml-0.5">{{ hoverData.close?.toFixed(2) }}</span></span>
        <span class="shrink-0 text-theme-secondary font-mono text-[10px]">量<span class="text-theme-primary ml-0.5">{{ hoverData.volume != null ? (hoverData.volume / 1e8).toFixed(2)+'亿股' : '' }}</span></span>
      </template>

      <!-- 基础行情（无hover时） -->
      <template v-if="!hoverData || !Object.keys(hoverData).length">
        <span class="text-theme-tertiary shrink-0">|</span>
        <span class="text-theme-secondary shrink-0 text-[10px]">量<span class="text-theme-primary font-mono ml-0.5">{{ fmtVol(quote.volume) }}</span></span>
        <span class="text-theme-secondary shrink-0 text-[10px]">额<span class="text-theme-primary font-mono ml-0.5">{{ fmtAmt(quote.amount) }}</span></span>
        <span class="text-theme-secondary shrink-0 text-[10px]">振<span class="text-theme-primary font-mono ml-0.5">{{ quote.amplitude != null ? quote.amplitude.toFixed(2)+'%' : '--' }}</span></span>
        <span class="text-theme-secondary shrink-0 text-[10px]">换<span class="text-theme-primary font-mono ml-0.5">{{ quote.turnover_rate != null ? quote.turnover_rate.toFixed(2)+'%' : '--' }}</span></span>
      </template>
    </div>

    <!-- 控制行：周期切换 | 图标按钮（右对齐） -->
    <div class="flex items-center gap-1 px-2 py-0.5 border-t border-theme/20">

      <!-- 周期切换（紧凑 icon + tooltip） -->
      <div class="flex items-center gap-0.5 shrink-0">
        <button
          v-for="p in periods" :key="p.key"
          class="w-5 h-5 flex items-center justify-center rounded-sm text-[10px] font-mono transition-colors"
          :class="period === p.key
            ? 'bg-[var(--color-info-bg)] text-[var(--color-info)]'
            : 'text-theme-muted hover:text-theme-primary'"
          :title="p.label"
          @click="emit('period-change', p.key)"
        >{{ p.label }}</button>
      </div>

      <span class="text-theme-tertiary mx-1 shrink-0">|</span>

      <!-- 右侧图标按钮组 -->
      <div class="flex items-center gap-1 ml-auto shrink-0">

        <!-- 复权 -->
        <div class="relative group">
          <button
            class="w-5 h-5 flex items-center justify-center rounded-sm transition-colors"
            :class="adjustment === 'qfq'
              ? 'text-[var(--color-warning)]'
              : 'text-theme-muted hover:text-theme-primary'"
            title="复权"
            @click="emit('adjustment-change', adjustment === 'qfq' ? 'none' : 'qfq')"
          >
            <!-- Wave icon -->
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
              <path d="M1 6c1-2 2-3 3-3s2 1 3 3 2 3 3 3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
            </svg>
          </button>
          <div class="absolute right-0 top-full mt-1 hidden group-hover:flex z-50 pointer-events-none">
            <div class="bg-theme-secondary border border-theme-secondary rounded-sm px-2 py-1 shadow-sm whitespace-nowrap">
              <span class="text-[10px] text-theme-primary">{{ adjustment === 'qfq' ? '前复权 ✓' : '前复权' }}</span>
            </div>
          </div>
        </div>

        <!-- Y轴类型 -->
        <div class="relative group">
          <button
            class="w-5 h-5 flex items-center justify-center rounded-sm transition-colors"
            :class="yAxisType === 'log'
              ? 'text-[var(--color-primary)]'
              : 'text-theme-muted hover:text-theme-primary'"
            title="Y轴坐标系"
            @click="emit('yaxis-change', yAxisType === 'linear' ? 'log' : 'linear')"
          >
            <!-- Axis icon -->
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
              <path d="M2 10V2M2 10h8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
            </svg>
          </button>
          <div class="absolute right-0 top-full mt-1 hidden group-hover:flex z-50 pointer-events-none">
            <div class="bg-theme-secondary border border-theme-secondary rounded-sm px-2 py-1 shadow-sm whitespace-nowrap">
              <span class="text-[10px] text-theme-primary">{{ yAxisType === 'log' ? '对数坐标' : '线性坐标' }}</span>
            </div>
          </div>
        </div>

        <div class="relative group">
          <button
            class="w-5 h-5 flex items-center justify-center rounded-sm transition-colors"
            :class="overlaySymbol
              ? 'text-[var(--color-info)]'
              : 'text-theme-muted hover:text-theme-primary'"
            title="叠加标的"
            @click.stop="showOverlayPanel = !showOverlayPanel"
          >
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
              <path d="M6 2v8M2 6h8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
            </svg>
          </button>

          <!-- 叠加搜索面板 -->
          <div
            v-if="showOverlayPanel"
            class="absolute right-0 top-full mt-1 z-50 w-64 rounded-sm border border-theme-secondary bg-terminal-panel shadow-sm"
            @click.stop
          >
            <div class="p-2 border-b border-theme/30">
              <input
                ref="overlaySearchInput"
                v-model="overlaySearchQuery"
                type="text"
                placeholder="搜索股票代码/名称..."
                class="w-full bg-theme-tertiary/30 border border-theme rounded-sm px-2 py-1 text-[10px] text-theme-primary placeholder-theme-muted focus:outline-none focus:border-[var(--color-info)]/60"
                @keydown.enter="applyOverlaySearch"
                @keydown.esc="showOverlayPanel = false; overlaySearchQuery = ''"
              />
            </div>
            <div v-if="overlaySearchResults.length > 0" class="max-h-40 overflow-y-auto">
              <button
                v-for="item in overlaySearchResults"
                :key="item.symbol"
                class="w-full px-3 py-1.5 text-left text-[10px] hover:bg-theme-tertiary/50 flex items-center gap-2"
                @click="selectOverlayItem(item)"
              >
                <span class="font-mono text-[var(--color-info)] w-16 shrink-0">{{ item.symbol.toUpperCase() }}</span>
                <span class="text-theme-primary truncate">{{ item.name }}</span>
              </button>
            </div>
            <div v-else-if="overlaySearchQuery.length > 0" class="px-3 py-2 text-[10px] text-theme-muted">
              无结果，请尝试输入如 sh000300
            </div>

        <!-- 导出 -->
        <div class="relative" v-click-outside="() => showExport = false">
          <button
            class="w-5 h-5 flex items-center justify-center rounded-sm text-theme-muted hover:text-theme-primary transition-colors"
            title="导出"
            @click="showExport = !showExport"
          >
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
              <path d="M6 2v6M3.5 5.5 6 8l2.5-2.5M2 10h8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
          <div v-if="showExport"
            class="absolute right-0 mt-1 w-36 rounded-sm border border-theme-secondary bg-terminal-panel shadow-sm z-50 py-1">
            <button class="w-full px-3 py-1 text-left text-theme-primary hover:bg-theme-tertiary/60 text-[10px] flex items-center gap-2"
              @click="doExport('visible'); showExport=false">
              <span class="text-[10px]">📊</span>导出可视范围
            </button>
            <button class="w-full px-3 py-1 text-left text-theme-primary hover:bg-theme-tertiary/60 text-[10px] flex items-center gap-2"
              @click="doExport('all'); showExport=false">
              <span class="text-[10px]">📋</span>导出全部数据
            </button>
            <button class="w-full px-3 py-1 text-left text-theme-primary hover:bg-theme-tertiary/60 text-[10px] flex items-center gap-2"
              @click="emit('export-png'); showExport=false">
              <span class="text-[10px]">🖼</span>导出 PNG
            </button>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { exportCSV as utilExportCSV } from '../utils/symbols.js'

const props = defineProps({
  name:          { type: String,  default: '' },
  symbol:        { type: String,  default: '' },
  quote:         { type: Object,  default: () => ({}) },
  period:        { type: String,  default: 'daily' },
  adjustment:    { type: String,  default: 'none' },
  yAxisType:     { type: String,  default: 'linear' },
  overlaySymbol:  { type: String,  default: '' },
  overlayName:    { type: String,  default: '' },
  visibleHist:    { type: Array,   default: () => [] },
  fullHist:       { type: Array,   default: () => [] },
  indicators:     { type: Object,  default: () => ({}) },
  maDisplays:     { type: Array,   default: () => [] },
  hoverData:      { type: Object,  default: () => ({}) },
})

const emit = defineEmits([
  'period-change', 'adjustment-change', 'yaxis-change',
  'overlay-change', 'export-png',
])

const showExport = ref(false)
const showOverlayPanel = ref(false)
const overlaySearchQuery = ref('')
const overlaySearchResults = ref([])
const overlaySearchCache = ref({})

const periods = [
  { key: 'minutely', label: 'T' },
  { key: '1min',     label: '1' },
  { key: '5min',     label: '5' },
  { key: '15min',    label: '15' },
  { key: '30min',    label: '30' },
  { key: '60min',    label: '60' },
  { key: 'daily',    label: 'D' },
  { key: 'weekly',   label: 'W' },
  { key: 'monthly',  label: 'M' },
]

const code = computed(() => props.symbol.replace(/^(sh|sz|us|hk|jp)/i, '').toUpperCase())

function fmtVol(v) {
  if (v == null) return '--'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(0)
}

function fmtAmt(a) {
  if (a == null) return '--'
  if (a >= 1e8) return (a / 1e8).toFixed(2) + '亿'
  if (a >= 1e4) return (a / 1e4).toFixed(2) + '万'
  return a.toFixed(0)
}

function selectOverlayItem(item) {
  showOverlayPanel.value = false
  overlaySearchQuery.value = ''
  overlaySearchResults.value = []
  emit('overlay-change', { symbol: item.symbol, name: item.name || item.symbol })
}

async function applyOverlaySearch() {
  const q = overlaySearchQuery.value.trim()
  if (!q) return
  // 优先从本地缓存搜索（全市场A股）
  if (overlaySearchCache.value._symbols) {
    const lower = q.toLowerCase()
    overlaySearchResults.value = overlaySearchCache.value._symbols
      .filter(s => s.symbol.toLowerCase().includes(lower) || (s.name || '').toLowerCase().includes(lower))
      .slice(0, 20)
    if (overlaySearchResults.value.length > 0) return
  }
  // 兜底：直接使用输入的 symbol（兼容用户直接输入 sh000300 格式）
  overlaySearchResults.value = [{ symbol: q, name: q }]
}

// 点击外部关闭面板
const vClickOutsideOverlay = {
  mounted(el, binding) {
    el._ovClickOutside = (e) => {
      if (!el.closest('.relative')?.contains(e.target) && !el.querySelector('.absolute')?.contains(e.target)) {
        binding.value(e)
      }
    }
    setTimeout(() => document.addEventListener('click', el._ovClickOutside), 0)
  },
  unmounted(el) { document.removeEventListener('click', el._ovClickOutside) },
}

// 加载全市场A股符号缓存（搜索用）
async function loadOverlaySymbolCache() {
  if (overlaySearchCache.value._symbols) return
  try {
    const resp = await fetch('/api/v1/market/symbols')
    const json = await resp.json()
    if (json?.data?.symbols) {
      overlaySearchCache.value._symbols = json.data.symbols
    }
  } catch { /* silent */ }
}

// 面板打开时加载缓存
watch(showOverlayPanel, (v) => {
  if (v) loadOverlaySymbolCache()
})

function doExport(mode) {
  const hist = mode === 'visible' ? props.visibleHist : props.fullHist
  utilExportCSV(hist, props.indicators, `${props.name || props.symbol}_${props.period}.csv`)
}

// Click outside directive
const vClickOutside = {
  mounted(el, binding) {
    el._clickOutsideHandler = (e) => { if (!el.contains(e.target)) binding.value(e) }
    document.addEventListener('click', el._clickOutsideHandler)
  },
  unmounted(el) { document.removeEventListener('click', el._clickOutsideHandler) },
}
</script>
