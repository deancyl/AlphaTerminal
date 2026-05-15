<template>
  <div class="bg-surface rounded-lg border border-theme-secondary p-4" role="region" aria-label="外汇报价面板">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-bold text-terminal-accent">💱 实时报价</h3>
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
    
    <div v-if="loading && quotes.length === 0" class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div v-for="i in 8" :key="i" class="bg-terminal-bg/50 rounded-lg p-3 animate-pulse">
        <div class="h-3 w-16 bg-terminal-bg/30 rounded mb-2"></div>
        <div class="h-5 w-20 bg-terminal-bg/30 rounded"></div>
      </div>
    </div>
    
    <div 
      v-else-if="quotes.length > 0" 
      class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3"
      tabindex="0"
      @keydown.down="focusNext"
      @keydown.up="focusPrev"
      @keydown.enter="selectCurrent"
      @keydown.space.prevent="selectCurrent"
      role="listbox"
      aria-label="货币对列表"
      aria-live="polite"
      aria-atomic="true"
    >
      <div 
        v-for="(quote, index) in quotes" 
        :key="quote.symbol"
        class="bg-terminal-bg/30 rounded-lg p-3 border border-theme-secondary hover:border-terminal-accent/50 transition-colors cursor-pointer"
        :class="{ 'ring-1 ring-terminal-accent': selectedSymbol === quote.symbol }"
        @click="$emit('select', quote)"
        role="option"
        :aria-selected="selectedSymbol === quote.symbol"
        :aria-label="`${quote.name || quote.symbol} 报价卡片`"
        :tabindex="focusedIndex === index ? 0 : -1"
      >
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-bold text-terminal-accent truncate">{{ quote.symbol }}</span>
          <span class="text-[10px] text-terminal-dim">{{ quote.name || '' }}</span>
        </div>
        
        <div class="flex items-baseline gap-1 mb-1">
          <span class="text-lg font-bold text-terminal-primary font-mono tabular-nums">
            {{ formatPrice(quote.latest) }}
          </span>
        </div>
        
        <div class="flex items-center gap-2 text-xs">
          <span 
            class="font-mono tabular-nums"
            :class="quote.change_pct >= 0 ? 'text-bull' : 'text-bear'"
          >
            {{ quote.change_pct >= 0 ? '+' : '' }}{{ quote.change_pct?.toFixed(2) || '0.00' }}%
          </span>
          <span class="text-terminal-dim font-mono tabular-nums">
            {{ quote.change >= 0 ? '+' : '' }}{{ quote.change?.toFixed(4) || '0.0000' }}
          </span>
        </div>
        
        <div class="mt-2 flex justify-between text-[10px] text-terminal-dim">
          <span class="font-mono tabular-nums">买: {{ formatPrice(quote.bid) }}</span>
          <span class="font-mono tabular-nums">卖: {{ formatPrice(quote.ask) }}</span>
        </div>
        
        <div class="mt-1 text-[10px] text-terminal-dim font-mono tabular-nums">
          点差: {{ quote.spread?.toFixed(6) || '--' }}
        </div>
      </div>
    </div>
    
    <div v-else class="flex flex-col items-center justify-center h-24 text-terminal-dim">
      <span class="text-xl mb-2">💱</span>
      <p class="text-xs">暂无报价数据</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  quotes: {
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
  },
  selectedSymbol: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['select', 'retry'])

const focusedIndex = ref(0)

function focusNext() {
  focusedIndex.value = Math.min(focusedIndex.value + 1, props.quotes.length - 1)
}

function focusPrev() {
  focusedIndex.value = Math.max(focusedIndex.value - 1, 0)
}

function selectCurrent() {
  if (props.quotes[focusedIndex.value]) {
    emit('select', props.quotes[focusedIndex.value])
  }
}

function formatPrice(val) {
  if (val === null || val === undefined) return '--'
  if (val >= 100) return val.toFixed(2)
  if (val >= 10) return val.toFixed(3)
  if (val >= 1) return val.toFixed(4)
  return val.toFixed(6)
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

.text-terminal-primary {
  color: var(--text-primary, #F0F6FC);
}

.text-terminal-dim {
  color: var(--text-secondary, #C9D1D9);
}

.text-bull {
  color: var(--color-bull, #E63946);
}

.text-bear {
  color: var(--color-bear, #1A936F);
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