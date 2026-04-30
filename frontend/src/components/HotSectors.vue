<template>
  <div class="flex flex-col min-w-0 overflow-hidden" style="height: 100%;">
    <div class="flex items-center justify-between mb-2 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">🔥 行业风口</span>
      <div class="flex items-center gap-2">
        <span class="text-terminal-dim text-[10px]">{{ tsDisplay }}</span>
        <button v-if="sectors.length > 5" @click="showAllSectors = !showAllSectors"
          class="text-[9px] text-cyan-400 hover:text-cyan-300 transition-colors">
          {{ showAllSectors ? '收起' : `更多(${sectors.length})` }}
        </button>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto min-w-0">
      <!-- 响应式网格：根据容器宽度自动调整列数 -->
      <div
        class="grid gap-1 overflow-hidden"
        :style="{ gridTemplateColumns: `repeat(${gridCols}, 1fr)` }"
      >
        <div
          v-for="sec in displaySectors"
          :key="sec.name"
          class="flex flex-col items-center justify-center px-1.5 py-1.5 rounded border cursor-pointer transition-all hover:opacity-80 min-w-0 overflow-hidden"
          :class="(sec.change_pct || 0) >= 0
            ? 'bg-red-500/10 border-red-500/30 hover:border-red-400/60'
            : 'bg-green-500/10 border-green-500/30 hover:border-green-400/60'"
          @click="handleClick(sec)"
          :title="`${sec.name} (点击查看领涨股 ${sec.top_stock?.name || '无'})`"
        >
          <!-- 板块名称：强制截断 -->
          <span
            class="text-[10px] font-medium leading-tight text-center w-full block overflow-hidden whitespace-nowrap text-overflow-ellipsis"
            :class="(sec.change_pct || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
          >
            {{ sec.name }}
          </span>
          <!-- 涨跌幅 -->
          <span
            class="text-[11px] font-mono font-bold leading-none mt-0.5"
            :class="(sec.change_pct || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
          >
            {{ (sec.change_pct || 0) >= 0 ? '+' : '' }}{{ (sec.change_pct || 0).toFixed(2) }}%
          </span>
          <!-- 领涨股 -->
          <span
            v-if="sec.top_stock?.name"
            class="text-[9px] leading-tight mt-0.5 truncate w-full text-center text-theme-tertiary"
          >
            {{ sec.top_stock.name }}
          </span>
        </div>
      </div>

      <!-- 无数据提示 -->
      <div v-if="!sectors.length && !isLoading" class="flex items-center justify-center h-32">
        <span class="text-terminal-dim text-xs">暂无板块数据</span>
      </div>
      
      <!-- 加载中骨架屏 -->
      <div v-if="isLoading" class="grid gap-1" :style="{ gridTemplateColumns: `repeat(${gridCols}, 1fr)` }">
        <div v-for="i in 10" :key="i" class="h-12 rounded border bg-terminal-panel animate-pulse"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useWindowSize } from '@vueuse/core'
import { logger } from '../utils/logger.js'
import { useMarketStore } from '../stores/market.js'
import { apiFetch } from '../utils/api.js'

const emit = defineEmits(['sector-click'])

const { setSymbol } = useMarketStore()
const sectors = ref([])
const isLoading = ref(false)
const tsDisplay = ref('')
const showAllSectors = ref(false)
let refreshTimer = null

// 响应式列数（根据容器宽度估算）
const { width: winWidth } = useWindowSize()
const gridCols = computed(() => {
  if (winWidth.value < 480) return 2   // 手机 < 480px → 2列
  if (winWidth.value < 768) return 3  // 手机 ≥ 480px → 3列
  if (winWidth.value < 1024) return 4 // 平板 → 4列
  return 5  // 桌面 → 5列
})

// 显示所有板块（受 showAllSectors 控制）
const displaySectors = computed(() =>
  showAllSectors.value ? sectors.value : sectors.value.slice(0, 20)
)

async function fetchSectors() {
  isLoading.value = sectors.value.length === 0 // 首次加载显示骨架屏
  try {
    const d = await apiFetch('/api/v1/market/sectors', { timeoutMs: 10000 })
    if (!d) return
    const sectorsList = d.sectors || []
    sectors.value = sectorsList
    // 更新时间戳
    if (d.timestamp) {
      const ts = typeof d.timestamp === 'number' 
        ? new Date(d.timestamp).toLocaleTimeString('zh-CN', { hour12: false })
        : (typeof d.timestamp === 'string' && d.timestamp.includes('T') 
          ? d.timestamp.slice(11, 19) : '')
      tsDisplay.value = ts ? `更新 ${ts}` : ''
    }
  } catch (e) {
    logger.warn('[HotSectors] fetch failed:', e.message)
  } finally {
    isLoading.value = false
  }
}

function handleClick(sec) {
  emit('sector-click', sec)
}

onMounted(() => {
  fetchSectors()
  refreshTimer = setInterval(fetchSectors, 5 * 60 * 1000) // 5分钟刷新
})

onUnmounted(() => {
  clearInterval(refreshTimer)
})
</script>
