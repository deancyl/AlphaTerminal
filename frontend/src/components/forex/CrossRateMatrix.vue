<template>
  <div class="bg-surface rounded-lg border border-theme-secondary p-4" role="region" aria-label="交叉汇率矩阵">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-bold text-terminal-accent">📊 交叉汇率矩阵</h3>
      <div class="flex items-center gap-2">
        <span v-if="lastUpdate" class="text-xs text-terminal-dim font-mono tabular-nums">最后更新: {{ lastUpdate }}</span>
        <button 
          v-if="error"
          @click="$emit('retry')"
          class="px-2 py-1 bg-bearish/20 text-bearish rounded-sm text-xs hover:bg-bearish/30 transition"
          type="button"
        >
          重试
        </button>
      </div>
    </div>
    
    <div v-if="error" class="mb-3 p-2 bg-bearish/10 border border-bearish/30 rounded-sm flex items-center gap-2">
      <span class="text-bearish text-xs">⚠️ {{ error }}</span>
    </div>
    
    <div v-if="loading && matrix.length === 0" class="grid grid-cols-4 gap-2">
      <div v-for="i in 16" :key="i" class="animate-pulse">
        <div class="h-4 bg-terminal-bg/30 rounded w-full"></div>
      </div>
    </div>
    
    <div v-else-if="matrix.length > 0" class="overflow-x-auto" aria-live="polite" aria-atomic="true">
      <table class="w-full border-collapse" role="grid" :aria-label="`${currencies.length}x${currencies.length} 交叉汇率矩阵`">
        <thead>
          <tr>
            <th class="sticky left-0 bg-surface z-10 p-2 text-xs text-terminal-dim font-medium border border-theme-secondary"></th>
            <th 
              v-for="(currency, colIdx) in currencies" 
              :key="colIdx"
              class="p-2 text-xs text-terminal-dim font-medium border border-theme-secondary min-w-[70px]"
              :class="{ 'bg-terminal-accent/20': hoveredCol === colIdx }"
            >
              {{ currency }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, rowIdx) in matrix" :key="rowIdx">
            <td 
              class="sticky left-0 bg-surface z-10 p-2 text-xs font-bold text-terminal-accent border border-theme-secondary"
              :class="{ 'bg-terminal-accent/20': hoveredRow === rowIdx }"
            >
              {{ row.base_currency }}
            </td>
            <td 
              v-for="(cell, colIdx) in row.rates" 
              :key="colIdx"
              class="p-2 text-xs border border-theme-secondary text-center transition-colors duration-150"
              :class="getCellClass(cell, rowIdx, colIdx)"
              @mouseenter="hoveredRow = rowIdx; hoveredCol = colIdx"
              @mouseleave="hoveredRow = null; hoveredCol = null"
              role="gridcell"
              :aria-label="getCellAriaLabel(row.base_currency, currencies[colIdx], cell)"
            >
              <span v-if="cell.is_base" class="text-terminal-dim">—</span>
              <span v-else-if="cell.rate !== null" class="font-mono tabular-nums">
                {{ formatRate(cell.rate) }}
                <span v-if="cell.is_calculated" class="text-[8px] text-terminal-dim ml-0.5">*</span>
              </span>
              <span v-else class="text-terminal-dim">N/A</span>
            </td>
          </tr>
        </tbody>
      </table>
      
      <div class="mt-3 text-[10px] text-terminal-dim flex items-center gap-4">
        <span>* 通过USD三角套利计算</span>
      </div>
    </div>
    
    <div v-else class="flex flex-col items-center justify-center h-32 text-terminal-dim">
      <span class="text-2xl mb-2">📊</span>
      <p class="text-xs">暂无交叉汇率数据</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  currencies: {
    type: Array,
    default: () => ['USD', 'EUR', 'GBP', 'JPY', 'CNY', 'AUD', 'CAD', 'CHF']
  },
  matrix: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: null
  },
  lastUpdate: {
    type: String,
    default: ''
  }
})

defineEmits(['retry'])

const hoveredRow = ref(null)
const hoveredCol = ref(null)

function getCellClass(cell, rowIdx, colIdx) {
  const classes = []
  
  if (cell.is_base) {
    classes.push('bg-terminal-bg/30')
  } else if (cell.rate !== null) {
    if (hoveredRow.value === rowIdx || hoveredCol.value === colIdx) {
      classes.push('bg-terminal-accent/10')
    }
  }
  
  if (hoveredRow.value === rowIdx && hoveredCol.value === colIdx && !cell.is_base) {
    classes.push('ring-1', 'ring-terminal-accent/50')
  }
  
  return classes
}

function getCellAriaLabel(baseCurrency, quoteCurrency, cell) {
  if (cell.is_base) {
    return `${baseCurrency} 对 ${quoteCurrency}: 对角线`
  }
  if (cell.rate !== null) {
    const calculated = cell.is_calculated ? '(计算得出)' : ''
    return `${baseCurrency}/${quoteCurrency} = ${cell.rate.toFixed(6)} ${calculated}`
  }
  return `${baseCurrency} 对 ${quoteCurrency}: 无数据`
}

function formatRate(rate) {
  if (rate >= 100) return rate.toFixed(2)
  if (rate >= 10) return rate.toFixed(4)
  if (rate >= 1) return rate.toFixed(4)
  return rate.toFixed(6)
}
</script>

<style scoped>
.bg-surface {
  background: var(--bg-surface, #1e1e1e);
}

.bg-terminal-bg {
  background: var(--bg-base, #121212);
}

.text-terminal-accent {
  color: var(--color-primary, #0F52BA);
}

.text-terminal-dim {
  color: var(--text-secondary, #C9D1D9);
}

.text-bearish {
  color: var(--color-bear, #1A936F);
}

.border-theme-secondary {
  border-color: var(--border-base, #30363D);
}

.ring-terminal-accent {
  --tw-ring-color: var(--color-primary, #0F52BA);
}

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.tabular-nums {
  font-variant-numeric: tabular-nums;
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>