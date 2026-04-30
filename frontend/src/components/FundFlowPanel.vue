<script setup>
import { ref, onMounted, onUnmounted, shallowRef, nextTick } from 'vue'
// ECharts 通过 CDN 加载，使用全局变量（延迟取值，避免模块加载时 CDN 尚未就绪）
const getEcharts = () => window.echarts
import { useResizeObserver } from '@vueuse/core'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'

const chartRef = ref(null)
const chartInstance = shallowRef(null)
const isLoading = ref(true)
const hasData = ref(false)
let timer = null

// ── 渲染入口：永远在 nextTick + DOM 尺寸已就绪后执行 ──────────────────────
const renderChart = async (dataList) => {
  if (!chartRef.value || !dataList?.length) return

  // 等待 DOM 尺寸计算完成（GridStack 拖拽后 / 首次挂载时必须）
  await nextTick()

  // 双重保险：DOM 若仍无物理尺寸，等下一帧
  await new Promise(resolve => requestAnimationFrame(resolve))

  if (!chartRef.value || !chartRef.value.clientWidth) {
    logger.warn('[FundFlow] DOM has zero dimensions, retrying...')
    await new Promise(resolve => requestAnimationFrame(resolve))
  }

  const echarts = getEcharts()
  if (!echarts) {
    logger.warn('[FundFlow] ECharts CDN 未加载，跳过渲染')
    return
  }
  if (!chartInstance.value) {
    chartInstance.value = echarts.init(chartRef.value, 'dark')
  }

  const dates = dataList.map(item => item.date)
  const values = dataList.map(item => (item.main_net || 0) / 100000000)
  const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { top: '15%', right: '5%', bottom: '15%', left: '15%' },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 9, color: '#94a3b8' } },
    yAxis: { type: 'value', axisLabel: { fontSize: 9, color: '#94a3b8' }, splitLine: { lineStyle: { color: '#334155' } } },
    series: [{
      name: '主力净额(亿)',
      type: 'bar',
      data: values,
      itemStyle: { color: (p) => p.value > 0 ? '#ef4444' : '#22c55e' }
    }]
  }
  chartInstance.value.setOption(option)
  chartInstance.value.resize()
}

// ── 数据获取 ────────────────────────────────────────────────────────────
const loadData = async () => {
  try {
    const res = await apiFetch('/api/v1/market/fund_flow')
    const items = res?.items || res?.data?.items || (Array.isArray(res) ? res : [])
    if (items.length > 0) {
      hasData.value = true
      // 数据就绪后调用渲染，此时 DOM 条件渲染刚切换完毕
      renderChart(items)
    } else {
      hasData.value = false
    }
  } catch (e) {
    logger.error('[FundFlow] Fetch failed', e)
    hasData.value = false
  } finally {
    isLoading.value = false
  }
}

// ── 专属 ResizeObserver：监听 chartRef DOM 节点尺寸变化 ─────────────────
useResizeObserver(chartRef, (entries) => {
  if (!chartInstance.value) return
  const { width, height } = entries[0].contentRect
  if (width > 0 && height > 0) {
    chartInstance.value.resize()
  }
})

onMounted(() => {
  loadData()
  timer = setInterval(loadData, 300000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (chartInstance.value) {
    chartInstance.value.dispose()
    chartInstance.value = null
  }
})
</script>

<template>
  <div class="flex flex-col h-full bg-terminal-panel">
    <div class="p-2 text-xs font-bold text-theme-accent border-b border-theme-secondary shrink-0">资金流向 (近30日)</div>
    <!-- Loading 骨架屏：v-show 保持 DOM 存在 -->
    <div v-show="isLoading" class="flex-1 p-3 space-y-3">
      <div class="skeleton h-4 w-3/4 rounded-sm"></div>
      <div class="skeleton h-32 rounded-sm"></div>
      <div class="flex gap-2">
        <div class="skeleton h-3 w-16 rounded-sm"></div>
        <div class="skeleton h-3 w-12 rounded-sm"></div>
        <div class="skeleton h-3 w-20 rounded-sm"></div>
      </div>
    </div>
    <!-- 空状态：也用 v-show，不销毁图表宿主 DOM -->
    <div v-show="!isLoading && !hasData" class="flex-1 flex items-center justify-center text-xs text-[var(--color-danger)]">⚠️ 接口数据为空</div>
    <!-- 图表容器：始终存在于文档树（v-show 控制显隐），不被 v-if 销毁 -->
    <div v-show="hasData" ref="chartRef" class="flex-1 w-full" style="min-height: 150px;"></div>
  </div>
</template>
