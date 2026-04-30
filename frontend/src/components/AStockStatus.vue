<template>
  <div class="flex flex-col h-full min-h-0 bg-terminal-bg">
    <!-- 标题栏 -->
    <div class="flex items-center justify-between mb-1 shrink-0 px-2 py-1">
      <span class="text-terminal-accent font-bold text-xs">📊 A股监测</span>
      <span class="text-terminal-dim text-[10px]">{{ total }} 只</span>
    </div>
    
    <!-- 搜索过滤栏 -->
    <div class="flex items-center gap-1 mb-1 shrink-0 px-2">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜索代码/名称"
        class="flex-1 min-w-0 bg-terminal-bg border border-theme-secondary rounded-sm px-2 py-0.5 text-[11px] text-theme-primary outline-none focus:border-terminal-accent/60 h-5"
      />
    </div>
    
    <!-- 表头 -->
    <div class="flex items-center px-2 py-0.5 bg-terminal-panel border-b border-theme text-[10px] text-terminal-dim shrink-0">
      <div class="w-5 text-left">#</div>
      <div class="flex-1 min-w-0 truncate">名称</div>
      <div class="w-12 text-right">最新价</div>
      <div class="w-10 text-right">涨跌幅</div>
    </div>
    
    <!-- 列表：确保能显示10个个股 -->
    <div class="flex-1 overflow-y-auto">
      <div
        v-for="(item, idx) in displayedItems"
        :key="item.symbol || idx"
        class="flex items-center px-2 py-0.5 border-b border-theme-secondary/20 hover:bg-theme-hover transition-colors text-[11px]"
        :class="idx % 2 === 0 ? 'bg-terminal-bg' : 'bg-terminal-panel/30'"
      >
        <div class="w-5 text-left text-[10px] text-terminal-dim">{{ (currentPage - 1) * pageSize + idx + 1 }}</div>
        <div class="flex-1 min-w-0 truncate text-theme-primary">{{ item.name || item.symbol }}</div>
        <div class="w-12 text-right font-mono text-theme-primary" :class="getFlashClass(item.symbol)">{{ item.price != null ? Number(item.price).toFixed(2) : '--' }}</div>
        <div
          class="w-10 text-right font-mono"
          :class="(item.change_pct || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
        >
          {{ (item.change_pct || 0) >= 0 ? '+' : '' }}{{ (item.change_pct || 0).toFixed(2) }}%
        </div>
      </div>
      <div v-if="!displayedItems.length" class="px-2 py-4 text-center text-terminal-dim text-xs">
        暂无数据
      </div>
    </div>

    <!-- 分页控制器 -->
    <div v-if="totalPages > 1" class="shrink-0 bg-terminal-panel flex items-center justify-center gap-1 py-0.5">
      <button 
        class="px-1.5 py-0 text-[10px] rounded-sm border border-theme-secondary text-terminal-dim hover:border-terminal-accent/50 disabled:opacity-30" 
        :disabled="currentPage === 1" 
        @click="currentPage--"
      >‹</button>
      <span class="text-[10px] text-terminal-dim">{{ currentPage }}/{{ totalPages }}</span>
      <button 
        class="px-1.5 py-0 text-[10px] rounded-sm border border-theme-secondary text-terminal-dim hover:border-terminal-accent/50 disabled:opacity-30" 
        :disabled="currentPage === totalPages" 
        @click="currentPage++"
      >›</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { usePriceFlashMap } from '../composables/usePriceFlashMap.js'

const props = defineProps({
  data: { type: Array, default: () => [] }
})

const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = 10  // 每页10个，确保默认能看到10个

const { getFlashClass, updatePrice } = usePriceFlashMap()

// 监听数据变化，更新价格闪烁
watch(() => props.data, (newData) => {
  newData.forEach(item => {
    if (item.symbol && item.price !== undefined) {
      updatePrice(item.symbol, item.price)
    }
  })
}, { deep: true })

const filtered = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return props.data
  return props.data.filter(i => {
    const sym = (i.symbol || '').toLowerCase()
    const name = (i.name || '').toLowerCase()
    return sym.includes(q) || name.includes(q)
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize)))

const displayedItems = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filtered.value.slice(start, start + pageSize)
})

const total = computed(() => props.data.length)
</script>
