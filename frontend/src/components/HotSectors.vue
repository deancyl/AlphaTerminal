<template>
  <div class="flex flex-col min-w-0 overflow-hidden" style="height: 100%;">
    <div class="flex items-center justify-between mb-2 shrink-0">
      <div class="flex items-center gap-1.5">
        <span class="text-terminal-accent font-bold text-sm">🔥 行业风口</span>
        <button v-if="isRefreshing" class="text-[9px] text-terminal-dim animate-spin">⟳</button>
        <span v-else @click="refreshSectors" class="text-[9px] text-terminal-dim/50 hover:text-terminal-dim cursor-pointer transition-colors" title="点击刷新">↻</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-terminal-dim text-[10px]">{{ tsDisplay }}</span>
        <button v-if="sectors.length > 12" @click="showAllSectors = !showAllSectors"
          class="text-[10px] text-[var(--color-info)] hover:text-[var(--color-info-light)] transition-colors">
          {{ showAllSectors ? '收起' : '展开全部' }}
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
          class="flex flex-col items-center justify-center px-1.5 py-1.5 rounded-sm border cursor-pointer transition-all hover:opacity-80 min-w-0 overflow-hidden"
          :class="(sec.change_pct || 0) >= 0
            ? 'bg-[var(--color-danger-bg)] border-[var(--color-danger-border)] hover:border-bullish/60'
            : 'bg-[var(--color-success-bg)] border-[var(--color-success-border)] hover:border-bearish/60'"
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
            class="text-[10px] leading-tight mt-0.5 truncate w-full text-center text-theme-tertiary"
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
        <div v-for="i in 10" :key="i" class="h-12 rounded-sm border bg-terminal-panel animate-pulse"></div>
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
const isRefreshing = ref(false)
const tsDisplay = ref('')
const showAllSectors = ref(false)
const cacheAge = ref(0) // seconds
let refreshTimer = null

// 响应式列数（根据容器宽度估算）
const { width: winWidth } = useWindowSize()
const gridCols = computed(() => {
  if (winWidth.value < 480) return 3   // 手机 < 480px → 3列（默认12个板块）
  if (winWidth.value < 768) return 4  // 手机 ≥ 480px → 4列
  if (winWidth.value < 1024) return 5 // 平板 → 5列
  return 6  // 桌面 → 6列
})

// 显示所有板块（受 showAllSectors 控制）
const displaySectors = computed(() =>
  showAllSectors.value ? sectors.value : sectors.value.slice(0, 12)
)

async function fetchSectors() {
  isLoading.value = sectors.value.length === 0 // 首次加载显示骨架屏
  try {
    const d = await apiFetch('/api/v1/market/sectors', { timeoutMs: 10000 })
    if (!d) return
    const sectorsList = d.sectors || []
    sectors.value = sectorsList
    // 更新时间戳（缓存时间）
    if (d.cache_age_seconds !== undefined) {
      cacheAge.value = d.cache_age_seconds
      tsDisplay.value = cacheAge.value < 60
        ? `${cacheAge.value}秒前`
        : `${Math.floor(cacheAge.value / 60)}分前`
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

async function refreshSectors() {
  if (isRefreshing.value) return
  isRefreshing.value = true
  try {
    const d = await apiFetch('/api/v1/market/sectors/refresh', { method: 'POST' })
    if (d?.sectors) {
      sectors.value = d.sectors
      if (d.cache_age_seconds !== undefined) {
        cacheAge.value = d.cache_age_seconds
        tsDisplay.value = cacheAge.value < 60
          ? `${cacheAge.value}秒前`
          : `${Math.floor(cacheAge.value / 60)}分前`
      }
    }
  } catch (e) {
    logger.warn('[HotSectors] refresh failed:', e.message)
  } finally {
    isRefreshing.value = false
  }
}

onMounted(() => {
  fetchSectors()
  refreshTimer = setInterval(fetchSectors, 5 * 60 * 1000) // 5分钟刷新
})

onUnmounted(() => {
  clearInterval(refreshTimer)
})
</script>
