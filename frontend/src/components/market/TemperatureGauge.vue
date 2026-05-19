<template>
  <div class="bg-surface rounded-lg p-4 border border-border-base">
    <div class="flex items-center justify-between mb-3">
      <h4 class="font-semibold text-primary">市场温度</h4>
      <span 
        class="text-xs px-2 py-1 rounded"
        :style="{ backgroundColor: temperature.color + '20', color: temperature.color }"
      >
        {{ temperature.label }}
      </span>
    </div>
    
    <div 
      ref="gaugeContainer" 
      class="w-full"
      style="height: 180px;"
      tabindex="0"
      role="img"
      :aria-label="`市场温度: ${temperature.score}分, ${temperature.label}`"
    />
    
    <div class="grid grid-cols-2 gap-2 mt-3 text-xs">
      <div class="flex items-center justify-between p-2 rounded bg-surface-hover">
        <span class="text-secondary">涨停</span>
        <span class="text-bull font-data tabular-nums">{{ temperature.limit_up }}</span>
      </div>
      <div class="flex items-center justify-between p-2 rounded bg-surface-hover">
        <span class="text-secondary">跌停</span>
        <span class="text-bear font-data tabular-nums">{{ temperature.limit_down }}</span>
      </div>
      <div class="flex items-center justify-between p-2 rounded bg-surface-hover">
        <span class="text-secondary">上涨</span>
        <span class="text-bull font-data tabular-nums">{{ temperature.advance }}</span>
      </div>
      <div class="flex items-center justify-between p-2 rounded bg-surface-hover">
        <span class="text-secondary">下跌</span>
        <span class="text-bear font-data tabular-nums">{{ temperature.decline }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useECharts } from '@/composables/useECharts.js'
import { getDynamicThemeColors } from '@/utils/echartsTheme.js'
import { onThemeChange } from '@/composables/useTheme.js'

const props = defineProps({
  temperature: {
    type: Object,
    required: true,
    validator: (val) => {
      return typeof val.score === 'number'
    }
  }
})

const gaugeContainer = ref(null)
const { initChart, setOption, dispose, isReady } = useECharts(gaugeContainer, {
  theme: 'dark',
  autoResize: true,
  resizeDelay: 100
})

let chartInstance = ref(null)

const gaugeOption = computed(() => {
  const themeColors = getDynamicThemeColors()
  const score = props.temperature.score || 50
  
  return {
    backgroundColor: 'transparent',
    series: [{
      type: 'gauge',
      center: ['50%', '60%'],
      radius: '85%',
      min: 0,
      max: 100,
      splitNumber: 5,
      startAngle: 200,
      endAngle: -20,
      axisLine: {
        lineStyle: {
          width: 20,
          color: [
            [0.2, '#3b82f6'],
            [0.4, '#06b6d4'],
            [0.6, '#fbbf24'],
            [0.8, '#f97316'],
            [1, '#ef4444']
          ]
        }
      },
      pointer: {
        icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
        length: '60%',
        width: 8,
        offsetCenter: [0, '-10%'],
        itemStyle: {
          color: themeColors.textPrimary
        }
      },
      axisTick: {
        length: 6,
        lineStyle: {
          color: 'auto',
          width: 1
        }
      },
      splitLine: {
        length: 12,
        lineStyle: {
          color: 'auto',
          width: 2
        }
      },
      axisLabel: {
        color: themeColors.textSecondary,
        fontSize: 10,
        distance: -35,
        formatter: (value) => {
          if (value === 0) return '冰点'
          if (value === 20) return '偏冷'
          if (value === 40) return '中性'
          if (value === 60) return '偏热'
          if (value === 80) return '过热'
          if (value === 100) return '极热'
          return ''
        }
      },
      title: {
        offsetCenter: [0, '40%'],
        fontSize: 12,
        color: themeColors.textSecondary
      },
      detail: {
        fontSize: 28,
        fontFamily: 'var(--font-data)',
        offsetCenter: [0, '5%'],
        valueAnimation: true,
        formatter: (value) => value.toFixed(0),
        color: props.temperature.color || themeColors.textPrimary,
        fontWeight: 'bold'
      },
      data: [{
        value: score,
        name: '市场温度'
      }]
    }]
  }
})

function updateChart() {
  if (isReady.value) {
    setOption(gaugeOption.value, true)
  }
}

watch(() => props.temperature, () => {
  updateChart()
}, { deep: true })

onThemeChange(() => {
  updateChart()
})

onMounted(async () => {
  const chart = await initChart()
  chartInstance.value = chart
})

onBeforeUnmount(() => {
  if (chartInstance.value) {
    chartInstance.value.off('click')
  }
  dispose()
})
</script>
