<template>
  <!-- 数据盘口 + 图表控制台 -->
  <div class="flex flex-col gap-1 px-2 py-1.5 border-b border-gray-700/50 bg-terminal-panel/80 shrink-0">

    <!-- 第一行：实时快照 -->
    <div class="flex items-center gap-3 text-[11px]">
      <!-- 标的名称 -->
      <span class="font-bold text-gray-100 whitespace-nowrap">{{ name }}</span>
      <span class="text-gray-500 font-mono">{{ code }}</span>

      <!-- 分隔线 -->
      <span class="text-gray-700">|</span>

      <!-- 最新价 -->
      <span class="font-mono font-medium text-gray-100">{{ quote.price ?? '--' }}</span>

      <!-- 涨跌额 -->
      <span class="font-mono" :class="quote.change >= 0 ? 'text-red-400' : 'text-green-400'">
        {{ quote.change >= 0 ? '+' : '' }}{{ quote.change != null ? quote.change.toFixed(2) : '--' }}
      </span>

      <!-- 涨跌幅 -->
      <span class="font-mono px-1.5 py-0.5 rounded text-[10px]"
        :class="quote.change_pct >= 0 ? 'bg-red-500/15 text-red-400' : 'bg-green-500/15 text-green-400'"
      >
        {{ quote.change_pct >= 0 ? '+' : '' }}{{ quote.change_pct != null ? quote.change_pct.toFixed(2) : '--' }}%
      </span>

      <!-- 分隔线 -->
      <span class="text-gray-700">|</span>

      <!-- 成交量 -->
      <span class="text-gray-400">成交量 <span class="text-gray-200 font-mono">{{ formatVolume(quote.volume) }}</span></span>

      <!-- 成交额 -->
      <span class="text-gray-400">成交额 <span class="text-gray-200 font-mono">{{ formatAmount(quote.amount) }}</span></span>

      <!-- 振幅 -->
      <span class="text-gray-400">振幅 <span class="text-gray-200 font-mono">{{ quote.amplitude != null ? quote.amplitude.toFixed(2) + '%' : '--' }}</span></span>

      <!-- 换手率 -->
      <span class="text-gray-400">换手率 <span class="text-gray-200 font-mono">{{ quote.turnover_rate != null ? quote.turnover_rate.toFixed(2) + '%' : '--' }}</span></span>
    </div>

    <!-- 第二行：周期 + 复权 + Y轴 + 导出 -->
    <div class="flex items-center gap-2 flex-wrap">

      <!-- 周期切换 -->
      <div class="flex items-center gap-0.5">
        <button
          v-for="p in periods"
          :key="p.key"
          class="px-1.5 py-0.5 text-[10px] rounded border transition"
          :class="period === p.key
            ? 'bg-blue-500/20 border-blue-500/50 text-blue-400'
            : 'border-gray-700 text-gray-400 hover:border-gray-500'"
          @click="emit('period-change', p.key)"
        >{{ p.label }}</button>
      </div>

      <!-- 分隔 -->
      <span class="text-gray-700">|</span>

      <!-- 复权切换 -->
      <div class="flex items-center gap-0.5">
        <button
          v-for="adj in adjustments"
          :key="adj.key"
          class="px-1.5 py-0.5 text-[10px] rounded border transition"
          :class="adjustment === adj.key
            ? 'bg-amber-500/20 border-amber-500/50 text-amber-400'
            : 'border-gray-700 text-gray-400 hover:border-gray-500'"
          @click="emit('adjustment-change', adj.key)"
        >{{ adj.label }}</button>
      </div>

      <!-- 分隔 -->
      <span class="text-gray-700">|</span>

      <!-- Y轴切换 -->
      <button
        class="px-1.5 py-0.5 text-[10px] rounded border transition"
        :class="yAxisType === 'log'
          ? 'bg-purple-500/20 border-purple-500/50 text-purple-400'
          : 'border-gray-700 text-gray-400 hover:border-gray-500'"
        @click="emit('yaxis-change', yAxisType === 'linear' ? 'log' : 'linear')"
        title="Y轴刻度切换"
      >{{ yAxisType === 'log' ? '对数' : '线性' }}</button>

      <!-- 叠加标的 -->
      <button
        class="px-1.5 py-0.5 text-[10px] rounded border transition"
        :class="overlaySymbol
          ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400'
          : 'border-gray-700 text-gray-400 hover:border-gray-500'"
        @click="selectOverlay"
        title="叠加其他标的"
      >{{ overlaySymbol ? '➕ ' + overlaySymbolName : '叠加' }}</button>

      <!-- 分隔 -->
      <span class="text-gray-700">|</span>

      <!-- 导出按钮 -->
      <button
        class="px-1.5 py-0.5 text-[10px] rounded border border-gray-700 text-gray-400 hover:border-gray-500 transition"
        @click="showExportMenu = !showExportMenu"
      >📤 导出</button>

      <!-- 导出菜单 -->
      <div v-if="showExportMenu" class="absolute mt-8 rounded border border-gray-600 bg-terminal-panel shadow-xl z-10 overflow-hidden">
        <button class="block w-full px-3 py-1.5 text-[11px] text-gray-300 hover:bg-gray-700/50 text-left"
          @click="exportCSV('visible')">📄 导出可视数据 (.csv)</button>
        <button class="block w-full px-3 py-1.5 text-[11px] text-gray-300 hover:bg-gray-700/50 text-left"
          @click="exportCSV('all')">📄 导出全部数据 (.csv)</button>
        <button class="block w-full px-3 py-1.5 text-[11px] text-gray-300 hover:bg-gray-700/50 text-left"
          @click="exportPNG">🖼️ 导出 PNG 图片</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { exportCSV as utilExportCSV } from '../utils/symbols.js'

const props = defineProps({
  name:         { type: String,  default: '' },
  symbol:       { type: String,  default: '' },
  quote:        { type: Object,  default: () => ({}) },  // { price, change, change_pct, volume, amount, amplitude, turnover_rate }
  period:       { type: String,  default: 'daily' },
  adjustment:   { type: String,  default: 'none' },      // none | qfq | hfq
  yAxisType:    { type: String,  default: 'linear' },     // linear | log
  overlaySymbol:{ type: String,  default: '' },
  overlayName:  { type: String,  default: '' },
  // 用于导出
  visibleHist:  { type: Array,   default: () => [] },
  fullHist:     { type: Array,   default: () => [] },
  indicators:   { type: Object,  default: () => ({}) },
})

const emit = defineEmits([
  'period-change',
  'adjustment-change',
  'yaxis-change',
  'overlay-change',
  'export-png',
])

const showExportMenu = ref(false)

// ── 周期选项 ───────────────────────────────────────────────────
const periods = [
  { key: 'minutely', label: '分时' },
  { key: '1min',      label: '1分' },
  { key: '5min',      label: '5分' },
  { key: '15min',     label: '15分' },
  { key: '30min',     label: '30分' },
  { key: '60min',     label: '60分' },
  { key: 'daily',     label: '日K' },
  { key: 'weekly',    label: '周K' },
  { key: 'monthly',   label: '月K' },
  { key: 'quarterly', label: '季K' },
  { key: 'yearly',    label: '年K' },
]

// ── 复权选项 ───────────────────────────────────────────────────
const adjustments = [
  { key: 'none', label: '不复权' },
  { key: 'qfq',  label: '前复权' },
  { key: 'hfq',  label: '后复权' },
]

// ── 计算属性 ───────────────────────────────────────────────────
const code = computed(() => {
  return props.symbol.replace(/^(sh|sz|us|hk|jp)/i, '').toUpperCase()
})

const overlaySymbolName = computed(() => props.overlayName || props.overlaySymbol)

// ── 格式化 ────────────────────────────────────────────────────
function formatVolume(v) {
  if (v == null) return '--'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(2)
}

function formatAmount(a) {
  if (a == null) return '--'
  if (a >= 1e8) return (a / 1e8).toFixed(2) + '亿'
  if (a >= 1e4) return (a / 1e4).toFixed(2) + '万'
  return a.toFixed(2)
}

// ── 叠加 ──────────────────────────────────────────────────────
function toggleOverlay() {
  if (props.overlaySymbol) {
    emit('overlay-change', '')
  } else {
    selectOverlay()
  }
}

function selectOverlay() {
  const input = prompt('输入叠加标的的 Symbol（如 sh000300 沪深300, usNDX 纳指）：', 'sh000300')
  if (!input) return
  const sym = input.trim()
  if (!sym) return
  emit('overlay-change', { symbol: sym, name: '' })
}

// ── 导出 ──────────────────────────────────────────────────────
function exportCSV(mode) {
  showExportMenu.value = false
  const hist = mode === 'visible' ? props.visibleHist : props.fullHist
  const filename = `${props.name || props.symbol}_${props.period}_${mode}.csv`
  utilExportCSV(hist, props.indicators, filename)
}

function exportPNG() {
  showExportMenu.value = false
  emit('export-png')
}

// 点击外部关闭导出菜单
if (typeof window !== 'undefined') {
  window.addEventListener('click', () => { showExportMenu.value = false })
}
</script>
