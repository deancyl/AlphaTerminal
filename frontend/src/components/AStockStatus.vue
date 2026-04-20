<template>
  <div class="flex flex-col h-full min-h-0 md:min-h-0 bg-terminal-bg">
    <!-- 标题栏 -->
    <div class="flex items-center justify-between mb-2 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">📊 A股监测</span>
      <span class="text-terminal-dim text-[10px]">{{ total }} 只</span>
    </div>
    <!-- 搜索过滤栏 -->
    <div class="flex items-center gap-2 mb-2 shrink-0">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="代码/名称"
        class="flex-1 min-w-0 bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-[11px] text-theme-primary outline-none focus:border-terminal-accent/60"
      />
    </div>
    <!-- 列表：flex-1 min-h-0 确保填满剩余高度且可滚动 -->
    <div class="flex-1 min-h-0 overflow-y-auto">
      <table class="w-full text-xs whitespace-nowrap">
        <thead class="bg-terminal-panel sticky top-0 z-10">
          <tr class="text-terminal-dim border-b border-theme">
            <th class="px-1.5 py-1 text-left font-normal w-8">#</th>
            <th class="px-1.5 py-1 text-left font-normal min-w-0 truncate">名称</th>
            <th class="px-1.5 py-1 text-right font-normal">最新价</th>
            <th class="px-1.5 py-1 text-right font-normal">涨跌幅</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(item, idx) in displayedItems"
            :key="item.symbol || idx"
            class="border-b border-theme-secondary/30 hover:bg-white/5 transition-colors"
          >
            <td class="px-1.5 py-1 text-terminal-dim text-[10px]">{{ (currentPage - 1) * pageSize + idx + 1 }}</td>
            <td class="px-1.5 py-1 min-w-0 truncate text-theme-primary text-[11px]">{{ item.name || item.symbol }}</td>
            <td class="px-1.5 py-1 text-right font-mono text-[11px] text-theme-primary">{{ item.price != null ? Number(item.price).toFixed(2) : '--' }}</td>
            <td
              class="px-1.5 py-1 text-right font-mono text-[11px]"
              :class="(item.change_pct || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
            >
              {{ (item.change_pct || 0) >= 0 ? '+' : '' }}{{ (item.change_pct || 0).toFixed(2) }}%
            </td>
          </tr>
          <tr v-if="!displayedItems.length">
            <td colspan="4" class="px-1.5 py-4 text-center text-terminal-dim text-xs">暂无数据</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页控制器：shrink-0 确保不被挤压出可视区 -->
    <div v-if="totalPages > 1" class="shrink-0 bg-theme-panel pb-2 flex items-center justify-center gap-1 mt-1">
      <button class="px-1.5 py-0.5 text-[10px] rounded border border-theme-secondary text-terminal-dim hover:border-terminal-accent/50 disabled:opacity-30" :disabled="currentPage === 1" @click="currentPage--">‹</button>
      <span class="text-[9px] text-terminal-dim px-1">{{ currentPage }}/{{ totalPages }}</span>
      <button class="px-1.5 py-0.5 text-[10px] rounded border border-theme-secondary text-terminal-dim hover:border-terminal-accent/50 disabled:opacity-30" :disabled="currentPage === totalPages" @click="currentPage++">›</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] }
})

const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = 20

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
