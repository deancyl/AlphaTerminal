<template>
  <div class="flex flex-col bg-terminal-panel border-t border-theme">
    <!-- Tab 栏 -->
    <div class="relative flex items-center gap-0 px-2 py-0.5 border-b border-theme/30 shrink-0">
      <button
        v-for="tab in tabs" :key="tab"
        class="relative px-2 py-0.5 text-[10px] font-medium tracking-wide transition-colors"
        :class="activeTab === tab
          ? 'text-[var(--color-info)]'
          : 'text-theme-muted hover:text-theme-primary'"
        @click="handleTabClick(tab)"
      >
        {{ tab }}
        <!-- 选中指示条 -->
        <span
          v-if="activeTab === tab"
          class="absolute bottom-0 left-1 right-1 h-0.5 rounded-full bg-blue-400/80"
        ></span>
      </button>

      <!-- 参数设置按钮 -->
      <button
        ref="paramsButtonRef"
        class="ml-2 px-1.5 py-0.5 text-[10px] text-theme-tertiary hover:text-theme-primary border border-transparent hover:border-theme-secondary rounded-sm transition"
        @click="handleSettingsClick"
        title="指标参数设置"
      >⚙️ 设置</button>

      <!-- 参数设置浮窗（桌面端） -->
      <div 
        v-if="showParams && !isMobile" 
        ref="paramsPopupRef"
        class="absolute mt-1 p-3 rounded-sm border border-theme-secondary bg-terminal-panel shadow-sm z-20 w-52"
        :style="popupPos"
      >
        <div class="text-[10px] text-theme-secondary mb-2 uppercase tracking-wider">指标参数</div>
        <!-- MACD -->
        <template v-if="activeTab === 'MACD'">
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-[10px] text-theme-secondary w-10">快线</span>
            <input type="number" :value="params.MACD.fast" min="1"
              class="flex-1 bg-theme-secondary border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[11px] text-theme-primary outline-none w-14"
              @change="handleParamChange('MACD', { ...params.MACD, fast: +$event.target.value })"
            />
          </div>
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-[10px] text-theme-secondary w-10">慢线</span>
            <input type="number" :value="params.MACD.slow" min="1"
              class="flex-1 bg-theme-secondary border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[11px] text-theme-primary outline-none w-14"
              @change="handleParamChange('MACD', { ...params.MACD, slow: +$event.target.value })"
            />
          </div>
          <div class="flex items-center gap-2">
            <span class="text-[10px] text-theme-secondary w-10">信号</span>
            <input type="number" :value="params.MACD.signal" min="1"
              class="flex-1 bg-theme-secondary border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[11px] text-theme-primary outline-none w-14"
              @change="handleParamChange('MACD', { ...params.MACD, signal: +$event.target.value })"
            />
          </div>
        </template>
        <!-- KDJ -->
        <template v-else-if="activeTab === 'KDJ'">
          <div class="flex items-center gap-2">
            <span class="text-[10px] text-theme-secondary w-10">周期</span>
            <input type="number" :value="params.KDJ.n" min="1"
              class="flex-1 bg-theme-secondary border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[11px] text-theme-primary outline-none w-14"
              @change="handleParamChange('KDJ', { ...params.KDJ, n: +$event.target.value })"
            />
          </div>
        </template>
        <!-- RSI -->
        <template v-else-if="activeTab === 'RSI'">
          <div class="flex items-center gap-2">
            <span class="text-[10px] text-theme-secondary w-10">周期</span>
            <input type="number" :value="params.RSI.period" min="1"
              class="flex-1 bg-theme-secondary border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[11px] text-theme-primary outline-none w-14"
              @change="handleParamChange('RSI', { ...params.RSI, period: +$event.target.value })"
            />
          </div>
        </template>
        <!-- BOLL -->
        <template v-else-if="activeTab === 'BOLL'">
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-[10px] text-theme-secondary w-10">周期</span>
            <input type="number" :value="params.BOLL.period" min="1"
              class="flex-1 bg-theme-secondary border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[11px] text-theme-primary outline-none w-14"
              @change="handleParamChange('BOLL', { ...params.BOLL, period: +$event.target.value })"
            />
          </div>
          <div class="flex items-center gap-2">
            <span class="text-[10px] text-theme-secondary w-10">倍</span>
            <input type="number" :value="params.BOLL.stdDev" min="0.1" step="0.1"
              class="flex-1 bg-theme-secondary border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[11px] text-theme-primary outline-none w-14"
              @change="handleParamChange('BOLL', { ...params.BOLL, stdDev: +$event.target.value })"
            />
          </div>
        </template>
      </div>
    </div>

    <!-- 副图内容（固定高度 140px） -->
    <div class="flex-1 min-h-0" ref="chartRef"></div>

    <!-- 移动端 BottomSheet 设置面板 -->
    <BottomSheet
      v-model="showParams"
      title="指标参数设置"
      height="auto"
    >
      <div class="p-4 space-y-4">
        <!-- MACD -->
        <template v-if="activeTab === 'MACD'">
          <div class="flex items-center justify-between">
            <span class="text-sm text-theme-secondary">快线周期</span>
            <input type="number" :value="params.MACD.fast" min="1"
              class="w-20 bg-surface border border-border-base rounded-sm px-3 py-2 text-sm text-primary outline-none focus:border-primary"
              @change="handleParamChange('MACD', { ...params.MACD, fast: +$event.target.value })"
            />
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-theme-secondary">慢线周期</span>
            <input type="number" :value="params.MACD.slow" min="1"
              class="w-20 bg-surface border border-border-base rounded-sm px-3 py-2 text-sm text-primary outline-none focus:border-primary"
              @change="handleParamChange('MACD', { ...params.MACD, slow: +$event.target.value })"
            />
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-theme-secondary">信号周期</span>
            <input type="number" :value="params.MACD.signal" min="1"
              class="w-20 bg-surface border border-border-base rounded-sm px-3 py-2 text-sm text-primary outline-none focus:border-primary"
              @change="handleParamChange('MACD', { ...params.MACD, signal: +$event.target.value })"
            />
          </div>
        </template>
        <!-- KDJ -->
        <template v-else-if="activeTab === 'KDJ'">
          <div class="flex items-center justify-between">
            <span class="text-sm text-theme-secondary">计算周期</span>
            <input type="number" :value="params.KDJ.n" min="1"
              class="w-20 bg-surface border border-border-base rounded-sm px-3 py-2 text-sm text-primary outline-none focus:border-primary"
              @change="handleParamChange('KDJ', { ...params.KDJ, n: +$event.target.value })"
            />
          </div>
        </template>
        <!-- RSI -->
        <template v-else-if="activeTab === 'RSI'">
          <div class="flex items-center justify-between">
            <span class="text-sm text-theme-secondary">计算周期</span>
            <input type="number" :value="params.RSI.period" min="1"
              class="w-20 bg-surface border border-border-base rounded-sm px-3 py-2 text-sm text-primary outline-none focus:border-primary"
              @change="handleParamChange('RSI', { ...params.RSI, period: +$event.target.value })"
            />
          </div>
        </template>
        <!-- BOLL -->
        <template v-else-if="activeTab === 'BOLL'">
          <div class="flex items-center justify-between">
            <span class="text-sm text-theme-secondary">计算周期</span>
            <input type="number" :value="params.BOLL.period" min="1"
              class="w-20 bg-surface border border-border-base rounded-sm px-3 py-2 text-sm text-primary outline-none focus:border-primary"
              @change="handleParamChange('BOLL', { ...params.BOLL, period: +$event.target.value })"
            />
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-theme-secondary">标准差倍数</span>
            <input type="number" :value="params.BOLL.stdDev" min="0.1" step="0.1"
              class="w-20 bg-surface border border-border-base rounded-sm px-3 py-2 text-sm text-primary outline-none focus:border-primary"
              @change="handleParamChange('BOLL', { ...params.BOLL, stdDev: +$event.target.value })"
            />
          </div>
        </template>
      </div>
    </BottomSheet>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useDebounceFn, onClickOutside, useBreakpoints, breakpointsTailwind } from '@vueuse/core'

import { calcMA, calcBOLL, calcMACD, calcKDJ, calcRSI } from '../utils/indicators.js'
import { buildXAxisLabels } from '../utils/symbols.js'
import { UP, DOWN } from '../utils/indicators.js'
import { createResizeObserver } from '../utils/lazyEcharts.js'
import { safeDispose } from '../utils/chartManager.js'
import BottomSheet from './BottomSheet.vue'
import { useHaptic } from '../composables/useHaptic.js'

const { light, selection } = useHaptic()
const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('md')



const props = defineProps({
  hist:          { type: Array,  default: () => [] },
  activeTab:     { type: String, default: 'VOL' },
  indicatorParams: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['tab-change', 'params-change'])

const tabs = ['VOL', 'MACD', 'KDJ', 'RSI', 'BOLL']
const showParams = ref(false)
const chartRef = ref(null)
const paramsButtonRef = ref(null)
const paramsPopupRef = ref(null)
const params = computed(() => ({
  MACD:  { fast: 12, slow: 26, signal: 9, ...(props.indicatorParams?.MACD || {}) },
  KDJ:   { n: 9,    ...(props.indicatorParams?.KDJ  || {}) },
  RSI:   { period: 14, ...(props.indicatorParams?.RSI || {}) },
  BOLL:  { period: 20, stdDev: 2, ...(props.indicatorParams?.BOLL || {}) },
}))

function handleTabClick(tab) {
  selection()
  emit('tab-change', tab)
}

function handleSettingsClick() {
  light()
  showParams.value = !showParams.value
}

function handleParamChange(indicator, newParams) {
  light()
  emit('params-change', { [indicator]: newParams })
}

// Dynamic popup position based on viewport boundaries
const popupPos = computed(() => {
  if (!showParams.value || !paramsButtonRef.value) {
    return { top: '100%', left: '0' }
  }
  
  const rect = paramsButtonRef.value.getBoundingClientRect()
  const popupWidth = 208 // w-52 = 13rem = 208px
  const isRightOverflow = rect.left + popupWidth > window.innerWidth
  const isBottomOverflow = rect.bottom + 200 > window.innerHeight // approximate popup height
  
  return {
    top: isBottomOverflow ? 'auto' : '100%',
    bottom: isBottomOverflow ? '100%' : 'auto',
    left: isRightOverflow ? 'auto' : '0',
    right: isRightOverflow ? '0' : 'auto'
  }
})

let chartInstance = null
let resizeObserver = null

function buildOption() {
  const hist = props.hist
  if (!hist.length) return {}
  const times   = buildXAxisLabels(hist, 'daily')
  const closes  = hist.map(h => h.close)
  const volumes = hist.map(h => h.volume)
  const tab = props.activeTab

  const yAxisCfg = {
    type: 'value', position: 'right',
    axisLine: { lineStyle: { color: '#374151' } },
    splitLine: { show: false },
    axisLabel: { color: '#6b7280', fontSize: 9 },
  }

  if (tab === 'VOL') {
    return {
      grid: { top: 8, right: 55, left: 55, bottom: 4, containLabel: false },
      xAxis: { type: 'category', data: times, boundaryGap: true, axisLine: { lineStyle: { color: '#374151' } }, splitLine: { show: false }, axisLabel: { show: false } },
      yAxis: { ...yAxisCfg, axisLabel: { formatter: v => (v / 1e8).toFixed(0) + '亿', color: '#6b7280', fontSize: 9 } },
      series: [{
        name: 'VOL', type: 'bar',
        data: hist.map(h => ({ value: h.volume, itemStyle: { color: h.close >= h.open ? UP + '44' : DOWN + '44' } })),
        barMaxWidth: 4,
      }],
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (params) => {
        const p = params[0]
        const h = hist[p.dataIndex]
        return `<b>${p.axisValue}</b><br/>VOL: ${(h.volume / 1e8).toFixed(2)}亿股`
      }},
    }
  }

  const gridInd = 0
  if (tab === 'MACD') {
    const p = params.value.MACD || {}
    const { dif, dea, macd } = calcMACD(closes, p.fast || 12, p.slow || 26, p.signal || 9)
    return {
      grid: { top: 8, right: 55, left: 55, bottom: 4, containLabel: false },
      xAxis: { type: 'category', data: times, boundaryGap: true, axisLine: { lineStyle: { color: '#374151' } }, splitLine: { show: false }, axisLabel: { show: false } },
      yAxis: yAxisCfg,
      series: [
        { name: 'DIF', type: 'line', data: dif, smooth: false, symbol: 'none', lineStyle: { color: '#60a5fa', width: 1.2 } },
        { name: 'DEA', type: 'line', data: dea, smooth: false, symbol: 'none', lineStyle: { color: '#f87171', width: 1.2 } },
        { name: 'MACD', type: 'bar',
          data: macd.map(v => ({ value: Math.abs(v), itemStyle: { color: v >= 0 ? UP : DOWN } })),
          barMaxWidth: 3 },
      ],
      tooltip: { trigger: 'axis' },
    }
  }

  if (tab === 'KDJ') {
    const p = params.value.KDJ || {}
    const { k, d, j } = calcKDJ(closes, hist.map(h => h.high), hist.map(h => h.low), p.n || 9)
    return {
      grid: { top: 8, right: 55, left: 55, bottom: 4, containLabel: false },
      xAxis: { type: 'category', data: times, boundaryGap: true, axisLine: { lineStyle: { color: '#374151' } }, splitLine: { show: false }, axisLabel: { show: false } },
      yAxis: yAxisCfg,
      series: [
        { name: 'K', type: 'line', data: k, smooth: false, symbol: 'none', lineStyle: { color: '#f87171', width: 1.2 } },
        { name: 'D', type: 'line', data: d, smooth: false, symbol: 'none', lineStyle: { color: '#60a5fa', width: 1.2 } },
        { name: 'J', type: 'line', data: j, smooth: false, symbol: 'none', lineStyle: { color: '#fbbf24', width: 1.2 } },
      ],
      tooltip: { trigger: 'axis' },
    }
  }

  if (tab === 'RSI') {
    const p = params.value.RSI || {}
    const rsi = calcRSI(closes, p.period || 14)
    return {
      grid: { top: 8, right: 55, left: 55, bottom: 4, containLabel: false },
      xAxis: { type: 'category', data: times, boundaryGap: true, axisLine: { lineStyle: { color: '#374151' } }, splitLine: { show: false }, axisLabel: { show: false } },
      yAxis: { ...yAxisCfg, max: 100, min: 0 },
      series: [{ name: 'RSI', type: 'line', data: rsi, smooth: false, symbol: 'none', lineStyle: { color: '#34d399', width: 1.5 } }],
      tooltip: { trigger: 'axis' },
    }
  }

  if (tab === 'BOLL') {
    const p = params.value.BOLL || {}
    const { mid, upper, lower } = calcBOLL(closes, p.period || 20, p.stdDev || 2)
    return {
      grid: { top: 8, right: 55, left: 55, bottom: 4, containLabel: false },
      xAxis: { type: 'category', data: times, boundaryGap: true, axisLine: { lineStyle: { color: '#374151' } }, splitLine: { show: false }, axisLabel: { show: false } },
      yAxis: yAxisCfg,
      series: [
        { name: 'BOLL-M', type: 'line', data: mid, smooth: false, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1.2 } },
        { name: 'BOLL-U', type: 'line', data: upper, smooth: false, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1, type: 'dashed' } },
        { name: 'BOLL-L', type: 'line', data: lower, smooth: false, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1, type: 'dashed' } },
      ],
      tooltip: { trigger: 'axis' },
    }
  }

  return {}
}

function render() {
  if (!chartInstance) return
  chartInstance.clear()
  // v0.6.66: 使用增量更新避免全量重绘
  chartInstance.setOption(buildOption(), { replaceMerge: ['series'], lazyUpdate: true })
}

onMounted(() => {
  if (!chartRef.value || !window.echarts) return
  chartInstance = window.echarts.init(chartRef.value, null, { renderer: 'canvas' })
  resizeObserver = createResizeObserver(chartInstance)
  resizeObserver.observe(chartRef.value)
  render()
})

// Click-away handler - set up when popup becomes visible
watch(showParams, (visible) => {
  if (visible) {
    nextTick(() => {
      if (paramsPopupRef.value) {
        onClickOutside(paramsPopupRef, () => {
          showParams.value = false
        })
      }
    })
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  if (chartInstance && !chartInstance.isDisposed()) {
    chartInstance.dispose()
    chartInstance = null
  }
})

const debouncedRender = useDebounceFn(() => nextTick(render), 150)

// Watch for indicator tab changes - clear chart before switching
watch(() => props.activeTab, (newTab, oldTab) => {
  if (chartInstance && newTab !== oldTab) {
    chartInstance.clear()
  }
  debouncedRender()
})

// Watch for data and params changes
watch(() => [props.hist, props.indicatorParams], () => { debouncedRender() }, { deep: true })
</script>
