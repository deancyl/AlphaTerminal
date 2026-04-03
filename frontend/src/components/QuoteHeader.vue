<template>
  <!-- 紧凑型盘口+控制条：单行高密度 -->
  <div class="flex items-center gap-x-2 gap-y-0 px-2 py-0.5 border-b border-gray-700/50 bg-terminal-panel/90 shrink-0 overflow-x-auto text-[9px]">

    <!-- 标的+快照（固定左侧） -->
    <div class="flex items-center gap-1.5 shrink-0">
      <span class="font-bold text-gray-100 whitespace-nowrap">{{ name }}</span>
      <span class="text-gray-500 font-mono">{{ code }}</span>
    </div>

    <span class="text-gray-700 shrink-0">|</span>

    <!-- 最新价 -->
    <span class="font-mono font-medium text-gray-100 shrink-0">{{ quote.price != null ? quote.price.toFixed(2) : '--' }}</span>

    <!-- 涨跌额/涨跌幅 -->
    <span class="shrink-0" :class="(quote.change ?? 0) >= 0 ? 'text-red-400' : 'text-green-400'">
      {{ (quote.change ?? 0) >= 0 ? '+' : '' }}{{ quote.change != null ? quote.change.toFixed(2) : '--' }}
    </span>
    <span class="shrink-0 px-1 py-0 rounded"
      :class="(quote.change_pct ?? 0) >= 0 ? 'bg-red-500/15 text-red-400' : 'bg-green-500/15 text-green-400'">
      {{ (quote.change_pct ?? 0) >= 0 ? '+' : '' }}{{ quote.change_pct != null ? quote.change_pct.toFixed(2) : '--' }}%
    </span>

    <!-- MA 数值（当前可视最新值） -->
    <template v-for="ma in maDisplays" :key="ma.period">
      <span class="shrink-0 font-mono text-[9px]" :style="{ color: ma.color }">
        MA{{ ma.period }}<span class="text-gray-200 ml-0.5">{{ ma.value != null ? ma.value.toFixed(2) : '--' }}</span>
      </span>
    </template>

    <!-- 十字光标悬浮数据（当hover时显示在右侧） -->
    <template v-if="hoverData && Object.keys(hoverData).length">
      <span class="text-gray-700 shrink-0 ml-1">|</span>
      <span class="shrink-0 text-gray-400 font-mono text-[9px]">{{ hoverData.date || hoverData.time }}</span>
      <span class="shrink-0 text-gray-400 font-mono text-[9px]">开<span class="text-gray-200">{{ hoverData.open?.toFixed(2) }}</span></span>
      <span class="shrink-0 text-gray-400 font-mono text-[9px]">高<span class="text-red-300">{{ hoverData.high?.toFixed(2) }}</span></span>
      <span class="shrink-0 text-gray-400 font-mono text-[9px]">低<span class="text-green-300">{{ hoverData.low?.toFixed(2) }}</span></span>
      <span class="shrink-0 text-gray-400 font-mono text-[9px]">收<span class="text-gray-200">{{ hoverData.close?.toFixed(2) }}</span></span>
      <span class="shrink-0 text-gray-400 font-mono text-[9px]">量<span class="text-gray-200">{{ hoverData.volume != null ? (hoverData.volume / 1e8).toFixed(2)+'亿' : '' }}</span></span>
    </template>

    <!-- 成交量/额/振幅/换手率（一行缩写） -->
    <template v-if="!hoverData || !Object.keys(hoverData).length">
      <span class="text-gray-700 shrink-0">|</span>
      <span class="text-gray-400 shrink-0 text-[9px]">量<span class="text-gray-200 font-mono">{{ fmtVol(quote.volume) }}</span></span>
      <span class="text-gray-400 shrink-0 text-[9px]">额<span class="text-gray-200 font-mono">{{ fmtAmt(quote.amount) }}</span></span>
      <span class="text-gray-400 shrink-0 text-[9px]">振<span class="text-gray-200 font-mono">{{ quote.amplitude != null ? quote.amplitude.toFixed(2)+'%' : '--' }}</span></span>
      <span class="text-gray-400 shrink-0 text-[9px]">换<span class="text-gray-200 font-mono">{{ quote.turnover_rate != null ? quote.turnover_rate.toFixed(2)+'%' : '--' }}</span></span>
    </template>

    <span class="text-gray-700 shrink-0">|</span>

    <!-- 周期切换（紧凑 pill） -->
    <div class="flex items-center gap-0.5 shrink-0">
      <button
        v-for="p in periods" :key="p.key"
        class="px-1 py-0 rounded border transition-colors leading-none"
        :class="period === p.key
          ? 'bg-blue-500/20 border-blue-500/50 text-blue-400'
          : 'border-gray-700 text-gray-500 hover:border-gray-500 hover:text-gray-300'"
        @click="emit('period-change', p.key)"
      >{{ p.label }}</button>
    </div>

    <!-- 复权（紧凑） -->
    <button
      class="px-1 py-0 rounded border transition-colors leading-none shrink-0"
      :class="adjustment === 'qfq'
        ? 'bg-amber-500/20 border-amber-500/50 text-amber-400'
        : 'border-gray-700 text-gray-500 hover:border-gray-500'"
      @click="emit('adjustment-change', adjustment === 'qfq' ? 'none' : 'qfq')"
      title="前复权"
    >复权</button>

    <!-- Y轴 -->
    <button
      class="px-1 py-0 rounded border transition-colors leading-none shrink-0"
      :class="yAxisType === 'log'
        ? 'bg-purple-500/20 border-purple-500/50 text-purple-400'
        : 'border-gray-700 text-gray-500 hover:border-gray-500'"
      @click="emit('yaxis-change', yAxisType === 'linear' ? 'log' : 'linear')"
      title="Y轴: {{ yAxisType === 'log' ? '对数' : '线性' }}"
    >{{ yAxisType === 'log' ? 'LOG' : 'LIN' }}</button>

    <!-- 叠加 -->
    <button
      class="px-1 py-0 rounded border transition-colors leading-none shrink-0"
      :class="overlaySymbol
        ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400'
        : 'border-gray-700 text-gray-500 hover:border-gray-500'"
      @click="selectOverlay"
      title="叠加标的"
    >+{{ overlaySymbol ? overlaySymbolName || overlaySymbol : '叠加' }}</button>

    <!-- 导出 -->
    <div class="relative shrink-0" v-click-outside="() => showExport = false">
      <button
        class="flex items-center gap-1 px-1 py-0 rounded border border-gray-700 text-gray-500 hover:border-gray-500 transition-colors leading-none"
        @click="showExport = !showExport"
        title="导出"
      >
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M5 1v6M2.5 4.5 5 7l2.5-2.5M1 9h8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
      <div v-if="showExport"
        class="absolute right-0 mt-1 w-36 rounded border border-gray-600 bg-terminal-panel shadow-xl z-50 py-1">
        <button class="w-full px-3 py-1 text-left text-gray-300 hover:bg-gray-700/60 text-[10px]"
          @click="doExport('visible'); showExport=false">📄 导出可视范围</button>
        <button class="w-full px-3 py-1 text-left text-gray-300 hover:bg-gray-700/60 text-[10px]"
          @click="doExport('all'); showExport=false">📄 导出全部数据</button>
        <button class="w-full px-3 py-1 text-left text-gray-300 hover:bg-gray-700/60 text-[10px]"
          @click="emit('export-png'); showExport=false">🖼️ 导出 PNG</button>
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
  { key: 'quarterly',label: 'Q' },
  { key: 'yearly',   label: 'Y' },
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

function selectOverlay() {
  if (props.overlaySymbol) {
    emit('overlay-change', '')
    return
  }
  const input = prompt('输入叠加标的 Symbol（如 sh000300）：', 'sh000300')
  if (input?.trim()) emit('overlay-change', { symbol: input.trim(), name: '' })
}

function doExport(mode) {
  const hist = mode === 'visible' ? props.visibleHist : props.fullHist
  utilExportCSV(hist, props.indicators, `${props.name || props.symbol}_${props.period}.csv`)
}

// Click outside directive (simple implementation)
const vClickOutside = {
  mounted(el, binding) {
    el._clickOutsideHandler = (e) => { if (!el.contains(e.target)) binding.value(e) }
    document.addEventListener('click', el._clickOutsideHandler)
  },
  unmounted(el) { document.removeEventListener('click', el._clickOutsideHandler) },
}
</script>
