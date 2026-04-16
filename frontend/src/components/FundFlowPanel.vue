<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center justify-between mb-2 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">💰 资金流向</span>
      <span class="text-terminal-dim text-[10px]">{{ tsDisplay }}</span>
    </div>

    <!-- 主力净流入趋势 -->
    <div v-if="latestData" class="mb-2 p-2 rounded border"
         :class="latestData.main_net >= 0 ? 'bg-red-500/10 border-red-500/30' : 'bg-green-500/10 border-green-500/30'">
      <div class="flex items-center justify-between">
        <span class="text-[10px] text-theme-tertiary">主力净流入</span>
        <span class="text-[12px] font-mono font-bold"
              :class="latestData.main_net >= 0 ? 'text-bullish' : 'text-bearish'">
          {{ formatYuan(latestData.main_net) }}
        </span>
      </div>
      <div class="flex items-center justify-between mt-1">
        <span class="text-[10px] text-theme-tertiary">净占比</span>
        <span class="text-[11px] font-mono"
              :class="latestData.main_pct >= 0 ? 'text-bullish' : 'text-bearish'">
          {{ latestData.main_pct >= 0 ? '+' : '' }}{{ latestData.main_pct.toFixed(2) }}%
        </span>
      </div>
    </div>

    <!-- 大单/小单对比 -->
    <div v-if="latestData" class="grid grid-cols-2 gap-1 mb-2">
      <div class="p-1.5 rounded border border-theme bg-terminal-panel/50">
        <div class="text-[9px] text-theme-tertiary">大单</div>
        <div class="text-[10px] font-mono" :class="latestData.large_net >= 0 ? 'text-bullish' : 'text-bearish'">
          {{ formatYuan(latestData.large_net) }}
        </div>
      </div>
      <div class="p-1.5 rounded border border-theme bg-terminal-panel/50">
        <div class="text-[9px] text-theme-tertiary">小单</div>
        <div class="text-[10px] font-mono" :class="latestData.small_net >= 0 ? 'text-bullish' : 'text-bearish'">
          {{ formatYuan(latestData.small_net) }}
        </div>
      </div>
    </div>

    <!-- 7天趋势图（简易版） -->
    <div class="flex-1 min-h-0">
      <div class="text-[9px] text-theme-tertiary mb-1">近7日主力净流入(亿)</div>
      <div class="h-16 flex items-end gap-0.5">
        <div v-for="(item, idx) in weekData" :key="idx"
             class="flex-1 flex flex-col items-center"
             :title="`${item.date}: ${(item.main_net/1e8).toFixed(1)}亿`">
          <!-- 柱子 -->
          <div class="w-full rounded-sm transition-all hover:opacity-80"
               :class="item.main_net >= 0 ? 'bg-red-500/60' : 'bg-green-500/60'"
               :style="{ height: getBarHeight(item.main_net) + '%' }"></div>
          <!-- 数值 -->
          <span class="text-[8px] text-theme-tertiary mt-0.5">{{ (item.main_net/1e8).toFixed(0) }}</span>
        </div>
      </div>
    </div>

    <!-- 无数据 -->
    <div v-if="!latestData && !isLoading" class="flex-1 flex items-center justify-center">
      <span class="text-terminal-dim text-xs">非交易时段，暂无最新数据</span>
    </div>

    <!-- 加载中 -->
    <div v-if="isLoading" class="flex-1 flex items-center justify-center">
      <span class="text-terminal-dim text-xs animate-pulse">加载中...</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { apiFetch } from '../utils/api.js'

const fundFlowData = ref([])
const isLoading = ref(false)
const tsDisplay = ref('')
let refreshTimer = null

// 最新一天数据
const latestData = computed(() => fundFlowData.value[0] || null)

// 最近7天数据
const weekData = computed(() => fundFlowData.value.slice(0, 7))

// 格式化金额
function formatYuan(val) {
  if (!val) return '0'
  const abs = Math.abs(val)
  if (abs >= 1e8) return (val / 1e8).toFixed(1) + '亿'
  if (abs >= 1e4) return (val / 1e4).toFixed(0) + '万'
  return val.toFixed(0)
}

// 计算柱子高度（相对于最大绝对值）
function getBarHeight(val) {
  const maxAbs = Math.max(...weekData.value.map(d => Math.abs(d.main_net || 0)), 1)
  return Math.max(5, (Math.abs(val) / maxAbs) * 80)
}

async function fetchFundFlow() {
  isLoading.value = fundFlowData.value.length === 0
  try {
    const d = await apiFetch('/api/v1/market/fund_flow', { timeoutMs: 15000 })
    if (!d || d.code !== 0) return
    
    fundFlowData.value = d.data?.items || []
    
    // 更新时间戳
    if (fundFlowData.value.length > 0) {
      const latest = fundFlowData.value[0]
      if (latest.date) {
        tsDisplay.value = latest.date
      }
    }
  } catch (e) {
    console.error('fetchFundFlow error:', e)
  } finally {
    // 确保无论成功或失败都释放加载状态
    isLoading.value = false
  }
}

onMounted(() => {
  fetchFundFlow()
  // 每5分钟刷新
  refreshTimer = setInterval(fetchFundFlow, 5 * 60 * 1000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>