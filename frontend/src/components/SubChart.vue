<template>
  <div class="flex flex-col bg-terminal-panel border-t border-gray-700/50">
    <!-- Tab 栏 -->
    <div class="relative flex items-center gap-0.5 px-2 py-1 border-b border-gray-700/30 shrink-0">
      <button
        v-for="tab in tabs" :key="tab"
        class="px-2 py-0.5 text-[10px] rounded transition"
        :class="activeTab === tab
          ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40'
          : 'text-gray-500 hover:text-gray-300 border border-transparent'"
        @click="emit('tab-change', tab)"
      >{{ tab }}</button>

      <!-- 参数设置按钮 -->
      <button
        class="ml-2 px-1.5 py-0.5 text-[10px] text-gray-500 hover:text-gray-300 border border-transparent hover:border-gray-600 rounded transition"
        @click="showParams = !showParams"
        title="指标参数设置"
      >⚙️ 设置</button>

      <!-- 参数设置浮窗 -->
      <div v-if="showParams" class="absolute top-full left-0 mt-1 p-3 rounded border border-gray-600 bg-terminal-panel shadow-xl z-20 w-52">
        <div class="text-[10px] text-gray-400 mb-2 uppercase tracking-wider">指标参数</div>
        <!-- MACD -->
        <template v-if="activeTab === 'MACD'">
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-[10px] text-gray-400 w-10">快线</span>
            <input type="number" :value="params.MACD.fast" min="1"
              class="flex-1 bg-gray-800 border border-gray-600 rounded px-1.5 py-0.5 text-[11px] text-gray-200 outline-none w-14"
              @change="e => emit('params-change', { MACD: { ...params.MACD, fast: +e.target.value } })"
            />
          </div>
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-[10px] text-gray-400 w-10">慢线</span>
            <input type="number" :value="params.MACD.slow" min="1"
              class="flex-1 bg-gray-800 border border-gray-600 rounded px-1.5 py-0.5 text-[11px] text-gray-200 outline-none w-14"
              @change="e => emit('params-change', { MACD: { ...params.MACD, slow: +e.target.value } })"
            />
          </div>
          <div class="flex items-center gap-2">
            <span class="text-[10px] text-gray-400 w-10">信号</span>
            <input type="number" :value="params.MACD.signal" min="1"
              class="flex-1 bg-gray-800 border border-gray-600 rounded px-1.5 py-0.5 text-[11px] text-gray-200 outline-none w-14"
              @change="e => emit('params-change', { MACD: { ...params.MACD, signal: +e.target.value } })"
            />
          </div>
        </template>
        <!-- KDJ -->
        <template v-else-if="activeTab === 'KDJ'">
          <div class="flex items-center gap-2">
            <span class="text-[10px] text-gray-400 w-10">周期</span>
            <input type="number" :value="params.KDJ.n" min="1"
              class="flex-1 bg-gray-800 border border-gray-600 rounded px-1.5 py-0.5 text-[11px] text-gray-200 outline-none w-14"
              @change="e => emit('params-change', { KDJ: { ...params.KDJ, n: +e.target.value } })"
            />
          </div>
        </template>
        <!-- RSI -->
        <template v-else-if="activeTab === 'RSI'">
          <div class="flex items-center gap-2">
            <span class="text-[10px] text-gray-400 w-10">周期</span>
            <input type="number" :value="params.RSI.period" min="1"
              class="flex-1 bg-gray-800 border border-gray-600 rounded px-1.5 py-0.5 text-[11px] text-gray-200 outline-none w-14"
              @change="e => emit('params-change', { RSI: { ...params.RSI, period: +e.target.value } })"
            />
          </div>
        </template>
        <!-- BOLL -->
        <template v-else-if="activeTab === 'BOLL'">
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-[10px] text-gray-400 w-10">周期</span>
            <input type="number" :value="params.BOLL.period" min="1"
              class="flex-1 bg-gray-800 border border-gray-600 rounded px-1.5 py-0.5 text-[11px] text-gray-200 outline-none w-14"
              @change="e => emit('params-change', { BOLL: { ...params.BOLL, period: +e.target.value } })"
            />
          </div>
          <div class="flex items-center gap-2">
            <span class="text-[10px] text-gray-400 w-10">倍</span>
            <input type="number" :value="params.BOLL.stdDev" min="0.1" step="0.1"
              class="flex-1 bg-gray-800 border border-gray-600 rounded px-1.5 py-0.5 text-[11px] text-gray-200 outline-none w-14"
              @change="e => emit('params-change', { BOLL: { ...params.BOLL, stdDev: +e.target.value } })"
            />
          </div>
        </template>
      </div>
    </div>

    <!-- 副图内容（固定高度 140px） -->
    <div class="flex-1 min-h-0" ref="chartRef"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { calcMA, calcBOLL, calcMACD, calcKDJ, calcRSI } from '../utils/indicators.js'
import { buildXAxisLabels } from '../utils/symbols.js'
import { UP, DOWN } from '../utils/indicators.js'

echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  hist:          { type: Array,  default: () => [] },
  activeTab:     { type: String, default: 'VOL' },
  indicatorParams: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['tab-change', 'params-change'])

const tabs = ['VOL', 'MACD', 'KDJ', 'RSI', 'BOLL']
const showParams = ref(false)
const chartRef = ref(null)
const params = computed(() => ({
  MACD:  { fast: 12, slow: 26, signal: 9, ...(props.indicatorParams?.MACD || {}) },
  KDJ:   { n: 9,    ...(props.indicatorParams?.KDJ  || {}) },
  RSI:   { period: 14, ...(props.indicatorParams?.RSI || {}) },
  BOLL:  { period: 20, stdDev: 2, ...(props.indicatorParams?.BOLL || {}) },
}))

let chartInstance = null

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
    axisLabel: { textStyle: { color: '#6b7280', fontSize: 9 } },
  }

  if (tab === 'VOL') {
    return {
      grid: { top: 8, right: 55, left: 55, bottom: 4, containLabel: false },
      xAxis: { type: 'category', data: times, boundaryGap: true, axisLine: { lineStyle: { color: '#374151' } }, splitLine: { show: false }, axisLabel: { show: false } },
      yAxis: { ...yAxisCfg, axisLabel: { formatter: v => (v / 1e8).toFixed(0) + '亿', textStyle: { color: '#6b7280', fontSize: 9 } } },
      series: [{
        name: 'VOL', type: 'bar',
        data: hist.map(h => ({ value: h.volume, itemStyle: { color: h.close >= h.open ? UP + '44' : DOWN + '44' } })),
        barMaxWidth: 4,
      }],
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (params) => {
        const p = params[0]
        const h = hist[p.dataIndex]
        return `<b>${p.axisValue}</b><br/>VOL: ${(h.volume / 1e8).toFixed(2)}亿`
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
  chartInstance.setOption(buildOption(), true)
}

onMounted(() => {
  chartInstance = echarts.init(chartRef.value, null, { renderer: 'canvas' })
  render()
})

onUnmounted(() => {
  chartInstance?.dispose()
})

watch(() => [props.hist, props.activeTab, props.indicatorParams], () => nextTick(render), { deep: true })
</script>
