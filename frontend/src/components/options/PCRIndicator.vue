<template>
  <div class="pcr-indicator flex flex-col items-center p-4 bg-surface rounded-sm">
    <div class="flex items-center gap-2 mb-2">
      <span class="text-xs text-secondary">市场情绪指标</span>
      <EducationalTooltip term="pcr" />
    </div>
    
    <div class="gauge-container w-[120px] h-[80px] relative">
      <svg viewBox="0 0 120 80" class="w-full h-full">
        <path
          d="M 10 70 A 50 50 0 0 1 110 70"
          fill="none"
          stroke="#30363d"
          stroke-width="8"
        />
        <path
          d="M 10 70 A 50 50 0 0 1 35 30"
          fill="none"
          :class="segmentClass"
          stroke-width="8"
        />
        <line
          x1="60" y1="70"
          :x2="needleX" :y2="needleY"
          stroke="#fbbf24"
          stroke-width="2"
        />
        <circle cx="60" cy="70" r="4" fill="#fbbf24" />
      </svg>
    </div>
    
    <div class="text-lg font-mono font-bold mt-2" :class="valueClass">
      {{ pcrDisplay }}
    </div>
    
    <div class="text-xs mt-1" :class="sentimentClass">
      {{ sentimentText }}
    </div>
    
    <div class="text-[10px] text-secondary mt-2 px-2 py-1 rounded bg-primary/10">
      {{ interpretation }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import EducationalTooltip from './EducationalTooltip.vue'

const props = defineProps({
  pcr: { type: Number, default: null },
  sentiment: { type: String, default: 'unknown' }
})

const pcrDisplay = computed(() => 
  props.pcr === null ? '--' : props.pcr.toFixed(2)
)

const valueClass = computed(() => {
  if (props.pcr === null) return 'text-secondary'
  if (props.pcr < 0.8) return 'text-bullish'
  if (props.pcr > 1.2) return 'text-bearish'
  return 'text-primary'
})

const sentimentClass = computed(() => {
  switch (props.sentiment) {
    case 'bullish': return 'text-bullish'
    case 'bearish': return 'text-bearish'
    default: return 'text-secondary'
  }
})

const sentimentText = computed(() => {
  switch (props.sentiment) {
    case 'bullish': return '看涨情绪'
    case 'bearish': return '看跌情绪'
    case 'neutral': return '中性'
    default: return '未知'
  }
})

const interpretation = computed(() => {
  if (props.pcr === null) return '暂无数据'
  if (props.pcr < 0.6) return '极度乐观'
  if (props.pcr < 0.8) return '乐观情绪'
  if (props.pcr < 1.2) return '市场中性'
  if (props.pcr < 1.5) return '悲观情绪'
  return '极度悲观'
})

const needleX = computed(() => {
  if (props.pcr === null) return 60
  const ratio = Math.min(Math.max(props.pcr, 0.5), 2.0)
  const angle = Math.PI - (ratio - 0.5) / 1.5 * Math.PI
  return 60 + 50 * Math.cos(angle)
})

const needleY = computed(() => {
  if (props.pcr === null) return 70
  const ratio = Math.min(Math.max(props.pcr, 0.5), 2.0)
  const angle = Math.PI - (ratio - 0.5) / 1.5 * Math.PI
  return 70 - 50 * Math.sin(angle)
})

const segmentClass = computed(() => {
  if (props.pcr === null) return 'gauge-neutral'
  if (props.pcr < 0.8) return 'gauge-bullish'
  if (props.pcr > 1.2) return 'gauge-bearish'
  return 'gauge-neutral'
})
</script>

<style scoped>
.text-bullish { color: var(--color-bull, #ef4444); }
.text-bearish { color: var(--color-bear, #22c55e); }
.text-primary { color: var(--text-primary, #f0f6fc); }
.text-secondary { color: var(--text-secondary, #9ca3af); }
.bg-surface { background: var(--bg-surface, #1e1e1e); }
.bg-primary\/10 { background: rgba(15, 82, 186, 0.1); }

.gauge-bullish { stroke: #ef4444; }
.gauge-bearish { stroke: #22c55e; }
.gauge-neutral { stroke: #fbbf24; }
</style>