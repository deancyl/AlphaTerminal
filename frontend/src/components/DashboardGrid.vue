<template>
  <div class="grid-stack" ref="gridRef">

    <!-- ━━━ Widget 1：A 股指数 ECharts 折线图 ━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="0" gs-y="0" gs-w="6" gs-h="5" gs-min-w="3" gs-min-h="3">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <div class="flex items-center justify-between mb-2 shrink-0">
          <span class="text-terminal-accent font-bold text-sm">📈 A股指数走势</span>
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
        <div class="flex-1 min-h-0">
          <IndexLineChart
            :key="selectedIndex"
            :symbol="selectedIndex"
            :name="currentIndexOption.name"
            :color="currentIndexOption.color"
            :url="`/api/v1/market/history/${selectedIndex}`"
          />
        </div>
      </div>
    </div>

    <!-- ━━━ Widget 2：市场总览表格 ━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="6" gs-y="0" gs-w="6" gs-h="5" gs-min-w="3" gs-min-h="3">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <div class="flex items-center justify-between mb-2 shrink-0">
          <span class="text-terminal-accent font-bold text-sm">🌏 市场总览</span>
          <span class="text-terminal-dim text-[10px]">{{ tsDisplay }}</span>
        </div>
        <div class="flex-1 overflow-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="text-terminal-dim border-b border-gray-700">
                <th class="text-left py-1">名称</th>
                <th class="text-right py-1">最新价</th>
                <th class="text-right py-1">涨跌幅</th>
                <th class="text-right py-1">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(m, key) in marketMarkets" :key="key"
                  class="border-b border-gray-800 hover:bg-white/5">
                <td class="py-1.5 text-gray-300">{{ m.name || key }}</td>
                <td class="py-1.5 text-right font-mono">{{ m.index ? m.index.toLocaleString('en-US', {maximumFractionDigits:2}) : (m.rate ?? '--') }}</td>
                <td class="py-1.5 text-right font-mono"
                    :class="(m.change_pct || 0) >= 0 ? 'text-red-400' : 'text-green-400'">
                  {{ (m.change_pct || 0) >= 0 ? '+' : '' }}{{ (m.change_pct || 0).toFixed(2) }}%
                </td>
                <td class="py-1.5 text-right">
                  <span class="px-1.5 py-0.5 rounded text-[10px]"
                        :class="m.status === '交易中' ? 'bg-green-500/20 text-green-400' : 'bg-gray-600/30 text-gray-400'">
                    {{ m.status }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ━━━ Widget 3：SHIBOR 利率柱状图 ━━━━━━━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="0" gs-y="5" gs-w="6" gs-h="5" gs-min-w="3" gs-min-h="3">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <div class="flex items-center justify-between mb-2 shrink-0">
          <span class="text-terminal-accent font-bold text-sm">💰 SHIBOR 利率</span>
          <span class="text-terminal-dim text-[10px]">银行间质押式回购</span>
        </div>
        <div class="flex-1 min-h-0">
          <div ref="shiborChartRef" class="w-full h-full"></div>
        </div>
      </div>
    </div>

    <!-- ━━━ Widget 4：快讯资讯流 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="0" gs-y="10" gs-w="6" gs-h="6" gs-min-w="3" gs-min-h="3">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <NewsFeed />
      </div>
    </div>

    <!-- ━━━ Widget 5：系统状态 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         gs-x="6" gs-y="5" gs-w="6" gs-h="5" gs-min-w="3" gs-min-h="3">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <div class="flex items-center justify-between mb-2 shrink-0">
          <span class="text-terminal-accent font-bold text-sm">🕐 系统状态</span>
          <span class="text-green-400 text-xs">● 运行中</span>
        </div>
        <div class="flex-1 flex flex-col justify-center items-center">
          <div class="text-3xl font-mono font-bold text-gray-100">{{ currentTime }}</div>
          <div class="text-terminal-dim text-xs mt-1">{{ currentDate }}</div>

          <div class="mt-4 w-full grid grid-cols-2 gap-2">
            <div class="bg-terminal-bg rounded p-2 border border-gray-700 text-center">
              <div class="text-terminal-dim text-[9px]">后端连接</div>
              <div class="text-xs mt-0.5" :class="backendConnected ? 'text-green-400' : 'text-red-400'">
                {{ backendConnected ? '● 已连接' : '○ 未连接' }}
              </div>
            </div>
            <div class="bg-terminal-bg rounded p-2 border border-gray-700 text-center">
              <div class="text-terminal-dim text-[9px]">数据源</div>
              <div class="text-xs mt-0.5 text-gray-300">Sina HQ + AkShare</div>
            </div>
            <div class="bg-terminal-bg rounded p-2 border border-gray-700 text-center">
              <div class="text-terminal-dim text-[9px]">数据时间</div>
              <div class="text-xs mt-0.5 text-gray-300">{{ tsDisplay }}</div>
            </div>
            <div class="bg-terminal-bg rounded p-2 border border-gray-700 text-center">
              <div class="text-terminal-dim text-[9px]">DB 写入</div>
              <div class="text-xs mt-0.5 text-gray-300">WAL · 每10s flush</div>
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import IndexLineChart from './IndexLineChart.vue'
import NewsFeed from './NewsFeed.vue'

const props = defineProps({
  marketData: { type: Object, default: null },
  ratesData:  { type: Array,  default: () => [] },
})

const gridRef      = ref(null)
const shiborChartRef = ref(null)
const currentTime  = ref('')
const currentDate  = ref('')
const backendConnected = ref(false)
const selectedIndex    = ref('000001')
let clockTimer  = null
let grid        = null
let shiborChart = null
let resizeObserver = null

const indexOptions = [
  { symbol: '000001', name: '上证',  color: '#f87171' },
  { symbol: '000300', name: '沪深300', color: '#60a5fa' },
  { symbol: '399001', name: '深证',  color: '#fbbf24' },
  { symbol: '399006', name: '创业板', color: '#a78bfa' },
]
const currentIndexOption = computed(() =>
  indexOptions.find(i => i.symbol === selectedIndex.value) || indexOptions[0]
)

const timestamp   = computed(() => props.marketData?.timestamp || '')
const tsDisplay   = computed(() => timestamp.value.slice(11, 19) || '')
const marketMarkets = computed(() => props.marketData?.markets || {})

function switchIndex(idx) {
  selectedIndex.value = idx.symbol
}

function updateClock() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour12: false })
  currentDate.value = now.toLocaleDateString('zh-CN', { weekday: 'short', year: 'numeric', month: '2-digit', day: '2-digit' })
}

function buildShiborChart(rates) {
  if (!shiborChartRef.value || typeof window === 'undefined' || !window.echarts) return
  const labels = rates.map(r => r.name.replace('SHIBOR ', ''))
  const values = rates.map(r => r.rate)
  const colors = values.map(v => v >= 1.5 ? '#f87171' : v >= 1.0 ? '#fbbf24' : '#4ade80')

  const option = {
    backgroundColor: 'transparent',
    grid: { top: 8, right: 16, bottom: 24, left: 50, containLabel: false },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1a1e2e',
      borderColor: '#374151',
      textStyle: { color: '#9ca3af', fontSize: 11 },
      formatter: params => {
        const p = params[0]
        return `<span style="color:#6b7280;font-size:10px">${p.axisValue}</span><br/>`
          + `<span style="color:#e5e7eb;font-size:12px">${p.value.toFixed(3)}%</span>`
      },
    },
    xAxis: {
      type: 'category', data: labels,
      axisLine: { lineStyle: { color: '#2d3748' } },
      axisLabel: { color: '#6b7280', fontSize: 9 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      position: 'left',
      axisLine: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 9, formatter: v => v.toFixed(2) },
      splitLine: { lineStyle: { color: '#1f2937', type: 'dashed' } },
      min: v => (v.min - 0.1).toFixed(3),
    },
    series: [{
      type: 'bar',
      data: values,
      itemStyle: { color: v => colors[v.dataIndex], borderRadius: [2, 2, 0, 0] },
      barMaxWidth: 36,
    }],
  }
  if (shiborChart) {
    shiborChart.setOption(option)
  }
}

async function checkBackend() {
  try {
    const res = await fetch('http://localhost:8002/health')
    backendConnected.value = res.ok
  } catch {
    backendConnected.value = false
  }
}

async function initShiborChart() {
  await nextTick()
  if (!shiborChartRef.value) return
  if (typeof window !== 'undefined' && window.echarts) {
    shiborChart = window.echarts.init(shiborChartRef.value, null, { renderer: 'canvas' })
    buildShiborChart(props.ratesData.length ? props.ratesData : [])
  }
}

// ratesData 到达后更新图表
watch(() => props.ratesData, (newRates) => {
  if (newRates && newRates.length > 0) {
    buildShiborChart(newRates)
  }
}, { deep: true })

onMounted(async () => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  await checkBackend()

  // 等待 DOM 渲染后初始化 gridstack
  await nextTick()
  if (typeof window !== 'undefined' && window.GridStack) {
    grid = GridStack.init({ column: 12, cellHeight: 80, float: true, margin: 8 })
  }

  await initShiborChart()
  resizeObserver = new ResizeObserver(() => {
    shiborChart?.resize()
  })
  if (shiborChartRef.value) resizeObserver.observe(shiborChartRef.value)
})

onUnmounted(() => {
  clearInterval(clockTimer)
  grid?.destroy(false)
  shiborChart?.dispose()
  resizeObserver?.disconnect()
})
</script>

<style>
.grid-stack { width: 100%; }
.grid-stack-item-content { inset: 4px; overflow: hidden; border-radius: 8px; }
</style>
