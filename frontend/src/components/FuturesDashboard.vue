<template>
  <div class="flex flex-col h-full overflow-auto gap-3 p-4">

    <!-- Loading State with Fade Transition -->
    <Transition name="fade" mode="out-in">
      <div v-if="isLoading" class="flex items-center justify-center py-8">
        <LoadingSpinner text="加载期货数据..." />
      </div>

      <!-- Error State -->
      <div v-else-if="hasError" class="flex-1 flex flex-col items-center justify-center py-8">
        <div class="text-3xl mb-3">⚠️</div>
        <div class="text-sm text-terminal-dim mb-3">{{ errorMessage }}</div>
        <button
          @click="fetchFuturesData"
          class="px-3 py-1 text-xs rounded-sm bg-terminal-accent hover:opacity-80"
        >
          重试
        </button>
      </div>

      <!-- Content (only show when not loading and no error) -->
      <div v-else class="flex flex-col gap-3 flex-1">
        <!-- 顶部核心卡片：股指期货主力 -->
        <!-- 移动端：水平滚动，桌面端：等分布局 -->
        <div class="flex gap-2 md:gap-3 shrink-0 overflow-x-auto pb-1 md:pb-0 scrollbar-hide">
          <div
            v-for="card in futuresCards"
            :key="card.symbol"
            class="flex-1 min-w-[100px] md:min-w-0 terminal-panel border border-theme-secondary rounded-sm px-2 md:px-4 py-2 md:py-3 flex flex-col gap-1 cursor-pointer hover:border-terminal-accent/40 transition"
            @click="openFuturesCard(card)"
          >
            <div class="flex items-center justify-between">
              <span class="text-[10px] md:text-[10px] text-terminal-dim uppercase tracking-wider">{{ card.name }}</span>
              <span
                class="text-[10px] md:text-[10px] px-1 py-0.5 rounded-sm border"
                :class="card.change_pct >= 0
                  ? 'border-bullish/30 text-bullish'
                  : 'border-bearish/30 text-bearish'"
              >{{ card.change_pct >= 0 ? '多' : '空' }}</span>
            </div>
            <div class="flex items-end gap-1 md:gap-2">
              <span class="text-base md:text-lg font-mono text-theme-primary">{{ card.price }}</span>
              <span
                class="text-[10px] md:text-xs font-mono"
                :class="card.change_pct >= 0 ? 'text-bullish' : 'text-bearish'"
              >{{ card.change_pct >= 0 ? '+' : '' }}{{ card.change_pct?.toFixed(2) }}%</span>
            </div>
            <div class="text-[10px] md:text-[10px] text-terminal-dim flex justify-between">
              <span>持仓: {{ card.position || '--' }}</span>
              <span class="hidden md:inline">{{ card.note || '' }}</span>
            </div>
          </div>
        </div>

        <!-- 主体：上方大宗商品热力图 + 下方主力合约图表 -->
        <div class="flex flex-col gap-3 flex-1 min-h-0">

          <!-- 大宗商品板块分组热力图 -->
          <div class="terminal-panel border border-theme-secondary rounded-sm p-4">
            <div class="flex items-center justify-between mb-3">
              <span class="text-xs text-terminal-dim">🛢️ 国内大宗商品主力合约</span>
              <span class="text-[10px] text-terminal-dim">{{ commodityUpdateTime || '...' }}</span>
            </div>

            <!-- Skeleton while loading -->
            <div v-if="commoditySectors.length === 0" class="grid grid-cols-3 md:grid-cols-5 gap-2">
              <div v-for="i in 15" :key="i" class="skeleton h-10 rounded-sm"></div>
            </div>

            <!-- 按板块分组渲染 -->
            <div v-for="sector in commoditySectors" :key="sector.name" class="mb-4 last:mb-0">
              <!-- 板块头：名称 + 加权平均涨跌幅 -->
              <div class="flex items-center gap-2 mb-1.5">
                <span class="text-[10px]">{{ sector.emoji }} {{ sector.name }}</span>
                <span
                  class="text-[10px] font-mono px-1.5 py-0.5 rounded-sm"
                  :class="sector.avgChange >= 0 ? 'bg-red-900/40 text-bullish' : 'bg-green-900/40 text-bearish'"
                >
                  {{ sector.avgChange >= 0 ? '+' : '' }}{{ sector.avgChange.toFixed(2) }}%
                </span>
              </div>
              <!-- 板块内商品方块（移动端2-3列，桌面端3-6列） -->
              <div class="grid gap-1.5 md:gap-2"
                   :class="[
                     sector.items.length > 4 ? 'grid-cols-3 md:grid-cols-6' : 'grid-cols-2 md:grid-cols-3',
                     sector.items.length > 6 ? 'grid-cols-4 md:grid-cols-6' : ''
                   ]">
                <div
                  v-for="item in sector.items"
                  :key="item.symbol"
                  class="rounded-sm border flex flex-col items-center justify-center py-1.5 md:py-2 px-1 cursor-pointer hover:brightness-125 hover:scale-[1.02] transition-all"
                  style="min-height: 44px;"
                  :style="{
                    borderColor: (item.change_pct || 0) >= 0
                      ? 'rgba(239,68,68,0.35)'
                      : 'rgba(34,197,94,0.35)',
                    background: (item.change_pct || 0) >= 0
                      ? 'rgba(239,68,68,0.08)'
                      : 'rgba(34,197,94,0.08)',
                  }"
                  @click="openCommodity(item)"
                >
                  <span class="text-[10px] md:text-[10px] text-theme-primary truncate w-full text-center">{{ item.name }}</span>
                  <span
                    class="text-[10px] md:text-xs font-mono mt-0.5"
                    :class="(item.change_pct || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
                  >{{ (item.change_pct || 0) >= 0 ? '+' : '' }}{{ (item.change_pct ?? 0).toFixed(2) }}%</span>
                </div>
              </div>
            </div>
            <div v-if="commodityBlocks.length > 0 && commoditySectors.length === 0"
                 class="text-center text-terminal-dim text-xs py-4">
              暂无数据
            </div>
          </div>


          <!-- 下方：主力合约走势图（真实图表） -->
          <div class="flex-1 terminal-panel border border-theme-secondary rounded-sm p-2 md:p-4 flex flex-col">
            <div class="text-xs text-terminal-dim mb-1 md:mb-2">📈 期货指数走势（IF · IC · IM）</div>
            <div class="flex-1 min-h-0 overflow-hidden relative" style="min-height: 120px;">
              <FuturesMainChart
                v-if="futuresCards.length > 0"
                :futures-data="futuresCards"
              />
              <div v-else class="w-full h-full flex flex-col p-3 gap-2">
                <div class="skeleton h-3 w-24 rounded-sm"></div>
                <div class="flex-1 skeleton rounded-sm"></div>
                <div class="flex gap-2">
                  <div class="skeleton h-2 w-12 rounded-sm"></div>
                  <div class="skeleton h-2 w-12 rounded-sm"></div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { logger } from '../utils/logger.js'
import FuturesMainChart from './FuturesMainChart.vue'
import LoadingSpinner from './f9/LoadingSpinner.vue'
import { apiFetch } from '../utils/api.js'

const emit = defineEmits(['open-futures'])

const futuresCards     = ref([])
const commodityBlocks  = ref([])
const commodityUpdateTime = ref('')
const isLoading = ref(false)
const hasError = ref(false)
const errorMessage = ref('')

// 板块分组 + 板块平均涨跌幅
const commoditySectors = computed(() => {
  const map = {}
  for (const item of (commodityBlocks.value || [])) {
    const s = item.sector || '其他'
    if (!map[s]) map[s] = { name: s, emoji: item.sector_emoji || '📦', items: [], total: 0, count: 0 }
    map[s].items.push(item)
    map[s].total += (item.change_pct || 0)
    map[s].count += 1
  }
  return Object.values(map).map(g => ({
    ...g,
    avgChange: g.count > 0 ? g.total / g.count : 0,
  }))
})

function openFuturesCard(card) {
  emit('open-futures', { symbol: card.symbol || card.name })
}

function openCommodity(item) {
  emit('open-futures', { symbol: item.symbol })
}

let fetchRequestId = 0

async function fetchFuturesData() {
  const currentRequestId = ++fetchRequestId
  isLoading.value = true
  hasError.value = false
  errorMessage.value = ''

  try {
    const [mi, mc] = await Promise.all([
      apiFetch('/api/v1/futures/main_indexes'),
      apiFetch('/api/v1/futures/commodities'),
    ])

    if (currentRequestId !== fetchRequestId) return

    if (mi) {
      const indexFutures = mi.index_futures || []
      
      const historyPromises = indexFutures.map(fut => {
        const symbol = fut.symbol || ''
        const baseSymbol = symbol.replace(/\d+$/, '')
        return apiFetch(`/api/v1/futures/index_history?symbol=${baseSymbol}&limit=20`)
          .then(res => ({ symbol: fut.symbol, history: res?.history || [] }))
          .catch(() => ({ symbol: fut.symbol, history: [] }))
      })
      
      const historyResults = await Promise.all(historyPromises)
      
      if (currentRequestId !== fetchRequestId) return
      
      const historyMap = Object.fromEntries(historyResults.map(r => [r.symbol, r.history]))
      
      futuresCards.value = indexFutures.map(fut => ({
        ...fut,
        history: historyMap[fut.symbol] || []
      }))
    }

    if (mc) {
      const commodities = mc.commodities || []
      commodityBlocks.value = commodities
      commodityUpdateTime.value = mc.update_time || ''
    }
  } catch (e) {
    if (currentRequestId !== fetchRequestId) return
    logger.warn('[FuturesDashboard] fetch failed:', e)
    hasError.value = true
    errorMessage.value = '加载失败，请点击重试'
  } finally {
    if (currentRequestId === fetchRequestId) {
      isLoading.value = false
    }
  }
}

let timer = null

onMounted(() => {
  fetchFuturesData()
  timer = setInterval(fetchFuturesData, 180_000)  // 每3分钟刷新
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
