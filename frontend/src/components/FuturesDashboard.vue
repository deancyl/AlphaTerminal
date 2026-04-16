<template>
  <div class="flex flex-col h-full overflow-auto gap-3 p-4">

    <!-- 顶部核心卡片：股指期货主力 -->
    <div class="flex gap-3 shrink-0">
      <div
        v-for="card in futuresCards"
        :key="card.symbol"
        class="flex-1 terminal-panel border border-theme-secondary rounded px-4 py-3 flex flex-col gap-1 cursor-pointer hover:border-terminal-accent/40 transition"
        @click="openFuturesCard(card)"
      >
        <div class="flex items-center justify-between">
          <span class="text-[10px] text-terminal-dim uppercase tracking-wider">{{ card.name }}</span>
          <span
            class="text-[9px] px-1 py-0.5 rounded border"
            :class="card.change_pct >= 0
              ? 'border-red-500/30 text-bullish'
              : 'border-green-500/30 text-bearish'"
          >{{ card.change_pct >= 0 ? '多' : '空' }}</span>
        </div>
        <div class="flex items-end gap-2">
          <span class="text-lg font-mono text-theme-primary">{{ card.price }}</span>
          <span
            class="text-xs font-mono"
            :class="card.change_pct >= 0 ? 'text-bullish' : 'text-bearish'"
          >{{ card.change_pct >= 0 ? '+' : '' }}{{ card.change_pct?.toFixed(2) }}%</span>
        </div>
        <div class="text-[9px] text-terminal-dim flex justify-between">
          <span>持仓: {{ card.position || '--' }}</span>
          <span>{{ card.note || '' }}</span>
        </div>
      </div>
    </div>

    <!-- 主体：上方大宗商品热力图 + 下方主力合约图表 -->
    <div class="flex flex-col gap-3 flex-1 min-h-0">

      <!-- 大宗商品板块分组热力图 -->
      <div class="terminal-panel border border-theme-secondary rounded p-4">
        <div class="flex items-center justify-between mb-3">
          <span class="text-xs text-terminal-dim">🛢️ 国内大宗商品主力合约</span>
          <span class="text-[9px] text-terminal-dim">{{ commodityUpdateTime || '...' }}</span>
        </div>

        <!-- 按板块分组渲染 -->
        <div v-for="sector in commoditySectors" :key="sector.name" class="mb-4 last:mb-0">
          <!-- 板块头：名称 + 加权平均涨跌幅 -->
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-[10px]">{{ sector.emoji }} {{ sector.name }}</span>
            <span
              class="text-[10px] font-mono px-1.5 py-0.5 rounded"
              :class="sector.avgChange >= 0 ? 'bg-red-900/40 text-bullish' : 'bg-green-900/40 text-bearish'"
            >
              {{ sector.avgChange >= 0 ? '+' : '' }}{{ sector.avgChange.toFixed(2) }}%
            </span>
          </div>
          <!-- 板块内商品方块（超过4个用6列，否则3列） -->
          <div class="grid gap-2" :class="sector.items.length > 4 ? 'grid-cols-6' : 'grid-cols-3'">
            <div
              v-for="item in sector.items"
              :key="item.symbol"
              class="rounded border flex flex-col items-center justify-center py-2 px-1 cursor-default transition-all hover:brightness-125"
              style="min-height: 52px;"
              :style="{
                borderColor: (item.change_pct || 0) >= 0
                  ? 'rgba(239,68,68,0.35)'
                  : 'rgba(34,197,94,0.35)',
                background: (item.change_pct || 0) >= 0
                  ? 'rgba(239,68,68,0.08)'
                  : 'rgba(34,197,94,0.08)',
              }"
            >
              <span class="text-[10px] text-theme-primary truncate w-full text-center">{{ item.name }}</span>
              <span
                class="text-xs font-mono mt-0.5"
                :class="(item.change_pct || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
              >{{ (item.change_pct || 0) >= 0 ? '+' : '' }}{{ (item.change_pct ?? 0).toFixed(2) }}%</span>
            </div>
          </div>
        </div>
        <div v-if="!commodityBlocks || commodityBlocks.length === 0"
             class="text-center text-terminal-dim text-xs py-4">
          暂无数据
        </div>
      </div>


      <!-- 下方：主力合约走势图（真实图表） -->
      <div class="flex-1 terminal-panel border border-theme-secondary rounded p-4 flex flex-col">
        <div class="text-xs text-terminal-dim mb-2">📈 期货指数走势（IF · IC · IM）</div>
        <div class="flex-1 min-h-0 overflow-hidden relative" style="min-height: 160px;">
          <FuturesMainChart
            v-if="futuresCards.length > 0"
            :futures-data="futuresCards"
          />
          <div v-else class="w-full h-full flex items-center justify-center">
            <span class="text-terminal-dim text-xs">加载中...</span>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { logger } from '../utils/logger.js'
import FuturesMainChart from './FuturesMainChart.vue'
import { logger } from '../utils/logger.js'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'

const emit = defineEmits(['open-futures'])

const futuresCards     = ref([])
const commodityBlocks  = ref([])
const commodityUpdateTime = ref('')

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

async function fetchFuturesData() {
  try {
    const [mi, mc] = await Promise.all([
      apiFetch('/api/v1/futures/main_indexes'),
      apiFetch('/api/v1/futures/commodities'),
    ])

    if (mi) {
      futuresCards.value = mi.index_futures || []
    }

    if (mc) {
      const commodities = mc.commodities || []
      commodityBlocks.value = commodities
      commodityUpdateTime.value = mc.update_time || ''
    }
  } catch (e) {
    logger.warn('[FuturesDashboard] fetch failed:', e)
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
