<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center justify-between mb-2 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">🔥 行业风口</span>
      <span class="text-terminal-dim text-[10px]">{{ tsDisplay }}</span>
    </div>

    <!-- Phase 4: 热力色块矩阵（flex-wrap pill cards） -->
    <!-- max-h 约束：确保 Top 15 在 GridStack 固定格内可滚动 -->
    <div class="flex-1" style="max-height: 300px; overflow-y: auto;">
      <div class="flex flex-wrap gap-1.5">
        <div
          v-for="sec in sectors"
          :key="sec.name"
          class="flex flex-col items-center justify-center px-2.5 py-1.5 rounded-lg border cursor-pointer transition-all hover:opacity-80 min-w-[72px]"
          :class="(sec.change_pct || 0) >= 0
            ? 'bg-red-500/10 border-red-500/30 hover:border-red-400/60'
            : 'bg-green-500/10 border-green-500/30 hover:border-green-400/60'"
          @click="handleClick(sec)"
        >
          <!-- 行业名称 -->
          <span
            class="text-[10px] font-medium leading-tight text-center"
            :class="(sec.change_pct || 0) >= 0 ? 'text-red-300' : 'text-green-300'"
          >
            {{ sec.name }}
          </span>
          <!-- 涨跌幅 -->
          <span
            class="text-[11px] font-mono font-bold mt-0.5"
            :class="(sec.change_pct || 0) >= 0 ? 'text-red-400' : 'text-green-400'"
          >
            {{ (sec.change_pct || 0) >= 0 ? '+' : '' }}{{ (sec.change_pct || 0).toFixed(2) }}%
          </span>
          <!-- 领涨股（如果有） -->
          <span
            v-if="sec.top_stock"
            class="text-[8px] mt-0.5"
            :class="(sec.top_stock.change_pct || 0) >= 0 ? 'text-red-500/60' : 'text-green-500/60'"
          >
            {{ sec.top_stock.name }}
          </span>
        </div>
      </div>

      <div v-if="!sectors.length" class="flex-1 flex items-center justify-center mt-4">
        <span class="text-terminal-dim text-xs">暂无板块数据</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useMarketStore } from '../composables/useMarketStore.js'

const emit = defineEmits(['sector-click'])

const { setSymbol } = useMarketStore()
const sectors = ref([])
const tsDisplay = ref('')
let refreshTimer = null

async function fetchSectors() {
  try {
    const res = await fetch('/api/v1/market/sectors')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const d = await res.json()
    sectors.value = d.sectors || []
    if (d.timestamp) {
      // 提取时分秒
      const t = d.timestamp.slice ? d.timestamp.slice(11, 19) : ''
      tsDisplay.value = t ? `更新 ${t}` : ''
    }
  } catch (e) {
    console.warn('[HotSectors] fetch failed:', e.message)
  }
}

function handleClick(sec) {
  emit('sector-click', sec)
}

onMounted(() => {
  fetchSectors()
  refreshTimer = setInterval(fetchSectors, 5 * 60 * 1000)
})

onUnmounted(() => {
  clearInterval(refreshTimer)
})
</script>
