<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center justify-between mb-2 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">🔥 行业风口</span>
      <span class="text-terminal-dim text-[10px]">{{ tsDisplay }}</span>
    </div>

    <!-- 矩阵卡片流：一屏 Top 20，5列×4行紧凑网格 -->
    <!-- 替代 flex-wrap 瀑布流，充分利用 GridStack 固定格宽度 -->
    <div class="flex-1" style="max-height: 360px; overflow-y: auto;">
      <!-- 5列矩阵网格 -->
      <div class="grid gap-1" style="grid-template-columns: repeat(5, 1fr);">
        <div
          v-for="sec in topSectors"
          :key="sec.name"
          class="flex flex-col items-center justify-center px-1 py-1 rounded border cursor-pointer transition-all hover:opacity-80"
          :class="(sec.change_pct || 0) >= 0
            ? 'bg-red-500/10 border-red-500/30 hover:border-red-400/60'
            : 'bg-green-500/10 border-green-500/30 hover:border-green-400/60'"
          @click="handleClick(sec)"
        >
          <!-- 板块名称（超长截断） -->
          <span
            class="text-[9px] font-medium leading-tight text-center w-full truncate"
            :class="(sec.change_pct || 0) >= 0 ? 'text-red-300' : 'text-green-300'"
            :title="sec.name"
          >
            {{ sec.name }}
          </span>
          <!-- 涨跌幅（金融红绿） -->
          <span
            class="text-[10px] font-mono font-bold leading-none mt-0.5"
            :class="(sec.change_pct || 0) >= 0 ? 'text-red-400' : 'text-green-400'"
          >
            {{ (sec.change_pct || 0) >= 0 ? '+' : '' }}{{ (sec.change_pct || 0).toFixed(2) }}%
          </span>
          <!-- 领涨股 -->
          <span
            v-if="sec.top_stock?.name"
            class="text-[8px] leading-tight mt-0.5 truncate w-full text-center"
            :class="(sec.top_stock.change_pct || 0) >= 0 ? 'text-red-500/60' : 'text-green-500/60'"
          >
            {{ sec.top_stock.name }}
          </span>
        </div>
      </div>

      <!-- 剩余板块（如果有超过20个） -->
      <div v-if="sectors.length > 20" class="mt-1">
        <div class="grid gap-1" style="grid-template-columns: repeat(5, 1fr);">
          <div
            v-for="sec in sectors.slice(20)"
            :key="sec.name"
            class="flex flex-col items-center justify-center px-1 py-1 rounded border cursor-pointer transition-all hover:opacity-80"
            :class="(sec.change_pct || 0) >= 0
              ? 'bg-red-500/5 border-red-500/20'
              : 'bg-green-500/5 border-green-500/20'"
            @click="handleClick(sec)"
          >
            <span class="text-[9px] text-gray-400 truncate w-full text-center">{{ sec.name }}</span>
            <span
              class="text-[10px] font-mono font-bold"
              :class="(sec.change_pct || 0) >= 0 ? 'text-red-400/80' : 'text-green-400/80'"
            >
              {{ (sec.change_pct || 0) >= 0 ? '+' : '' }}{{ (sec.change_pct || 0).toFixed(2) }}%
            </span>
          </div>
        </div>
      </div>

      <div v-if="!sectors.length" class="flex-1 flex items-center justify-center mt-3">
        <span class="text-terminal-dim text-xs">暂无板块数据</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useMarketStore } from '../composables/useMarketStore.js'

const emit = defineEmits(['sector-click'])

const { setSymbol } = useMarketStore()
const sectors = ref([])
const topSectors = computed(() => sectors.value.slice(0, 20))
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
