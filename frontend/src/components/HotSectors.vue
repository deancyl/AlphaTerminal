<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center justify-between mb-2 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">🔥 行业风口</span>
      <span class="text-terminal-dim text-[10px]">{{ tsDisplay }}</span>
    </div>

    <div class="flex-1 overflow-auto space-y-1">
      <div
        v-for="(sec, i) in sectors"
        :key="sec.name"
        class="bg-terminal-bg rounded border border-gray-700 p-2 hover:border-terminal-accent/40 transition-colors cursor-pointer"
        @click="handleClick(sec)"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-[10px] text-terminal-dim w-3">{{ i + 1 }}</span>
            <span class="text-xs text-gray-200 font-medium">{{ sec.name }}</span>
          </div>
          <span
            class="text-[11px] font-mono font-bold"
            :class="(sec.change_pct || 0) >= 0 ? 'text-red-400' : 'text-green-400'"
          >
            {{ (sec.change_pct || 0) >= 0 ? '+' : '' }}{{ (sec.change_pct || 0).toFixed(2) }}%
          </span>
        </div>

        <!-- 领涨股 -->
        <div v-if="sec.top_stock" class="flex items-center gap-2 mt-1 pl-5">
          <span class="text-[9px] text-terminal-dim">领涨</span>
          <span class="text-[10px] text-gray-300">{{ sec.top_stock.name }}</span>
          <span
            class="text-[10px] font-mono"
            :class="(sec.top_stock.change_pct || 0) >= 0 ? 'text-red-400' : 'text-green-400'"
          >
            {{ (sec.top_stock.change_pct || 0) >= 0 ? '+' : '' }}{{ (sec.top_stock.change_pct || 0).toFixed(2) }}%
          </span>
        </div>
      </div>

      <div v-if="!sectors.length" class="flex-1 flex items-center justify-center">
        <span class="text-terminal-dim text-xs">暂无数据</span>
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
