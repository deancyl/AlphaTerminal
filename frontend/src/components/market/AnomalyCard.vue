<template>
  <div
    class="bg-surface rounded-lg p-4 border border-border-base transition-all"
    :class="{ 'hover:border-border-hover': true }"
  >
    <div class="flex items-center justify-between mb-3">
      <h4 class="font-semibold text-primary" :title="getAnomalyDescription(anomaly.type)">{{ anomaly.title }}</h4>
      <span class="text-xs text-secondary px-2 py-1 rounded bg-surface-hover">TOP 10</span>
    </div>

    <div class="space-y-2">
      <div
        v-for="(stock, index) in anomaly.stocks.slice(0, 5)"
        :key="stock.symbol"
        class="flex items-center justify-between p-2 rounded hover:bg-surface-hover cursor-pointer transition-colors"
        tabindex="0"
        @click="$emit('stock-click', stock)"
        @keydown.enter="$emit('stock-click', stock)"
        @keydown.space.prevent="$emit('stock-click', stock)"
      >
        <div class="flex items-center gap-2">
          <span class="text-xs text-muted w-4 tabular-nums">{{ index + 1 }}</span>
          <span class="font-medium text-primary">{{ stock.name }}</span>
          <span class="text-xs text-muted">{{ stock.symbol }}</span>
        </div>
        <span
          :class="getValueClass(stock.value)"
          class="font-data text-sm tabular-nums"
        >
          {{ formatValue(stock.value, anomaly.type) }}
        </span>
      </div>

      <!-- Show more button if there are more than 5 -->
      <button
        v-if="anomaly.stocks.length > 5"
        @click="showMore = !showMore"
        class="text-xs text-primary hover:text-primary-hover transition-colors w-full text-left py-1"
      >
        {{ showMore ? '收起' : '查看更多' }}
      </button>

      <!-- Show remaining stocks -->
      <div
        v-if="showMore"
        v-for="(stock, index) in anomaly.stocks.slice(5)"
        :key="stock.symbol"
        class="flex items-center justify-between p-2 rounded hover:bg-surface-hover cursor-pointer transition-colors"
        tabindex="0"
        @click="$emit('stock-click', stock)"
        @keydown.enter="$emit('stock-click', stock)"
        @keydown.space.prevent="$emit('stock-click', stock)"
      >
        <div class="flex items-center gap-2">
          <span class="text-xs text-muted w-4 tabular-nums">{{ index + 6 }}</span>
          <span class="font-medium text-primary">{{ stock.name }}</span>
          <span class="text-xs text-muted">{{ stock.symbol }}</span>
        </div>
        <span
          :class="getValueClass(stock.value)"
          class="font-data text-sm tabular-nums"
        >
          {{ formatValue(stock.value, anomaly.type) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  anomaly: {
    type: Object,
    required: true,
    validator: (val) => {
      return val.title && val.type && Array.isArray(val.stocks)
    }
  }
})

defineEmits(['stock-click'])

const showMore = ref(false)

const ANOMALY_DESCRIPTIONS = {
  volatility: '振幅异常：当日最高价与最低价之差占昨收的比例',
  capital_outflow: '资金流出：主力资金净流出占成交额比例',
  institution_research: '机构调研：近30日机构调研次数',
  new_high: '创新高：股价创近60日新高',
  volume_surge: '放量突破：成交量较5日均量放大超过50%'
}

function getAnomalyDescription(type) {
  return ANOMALY_DESCRIPTIONS[type] || ''
}

function getValueClass(value) {
  if (value > 0) return 'text-bull'
  if (value < 0) return 'text-bear'
  return 'text-primary'
}

function formatValue(value, type) {
  if (value === null || value === undefined) return '--'

  switch (type) {
    case 'volatility':
      return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
    case 'capital_outflow':
      return `${value >= 0 ? '+' : ''}${value.toFixed(2)}亿`
    case 'institution_research':
      return `${value}次`
    case 'new_high':
      return `${value.toFixed(1)}周`
    case 'volume_surge':
      return `${value.toFixed(1)}倍`
    case 'limit_up':
      return `${value.toFixed(2)}%`
    case 'limit_down':
      return `${value.toFixed(2)}%`
    case 'turnover_rate':
      return `${value.toFixed(2)}%`
    default:
      return typeof value === 'number' ? value.toFixed(2) : String(value)
  }
}
</script>