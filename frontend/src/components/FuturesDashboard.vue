<template>
  <div class="flex flex-col h-full overflow-auto gap-3 p-4">

    <!-- 顶部核心卡片：股指期货主力 -->
    <div class="flex gap-3 shrink-0">
      <div
        v-for="card in futuresCards"
        :key="card.symbol"
        class="flex-1 terminal-panel border border-gray-800 rounded px-4 py-3 flex flex-col gap-1"
      >
        <div class="flex items-center justify-between">
          <span class="text-[10px] text-terminal-dim uppercase tracking-wider">{{ card.name }}</span>
          <span
            class="text-[9px] px-1 py-0.5 rounded border"
            :class="card.change_pct >= 0
              ? 'border-red-500/30 text-red-400'
              : 'border-green-500/30 text-green-400'"
          >{{ card.change_pct >= 0 ? '多' : '空' }}</span>
        </div>
        <div class="flex items-end gap-2">
          <span class="text-lg font-mono text-gray-100">{{ card.price }}</span>
          <span
            class="text-xs font-mono"
            :class="card.change_pct >= 0 ? 'text-red-400' : 'text-green-400'"
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

      <!-- 大宗商品涨跌方块阵列（热力图风格） -->
      <div class="terminal-panel border border-gray-800 rounded p-4">
        <div class="flex items-center justify-between mb-3">
          <span class="text-xs text-terminal-dim">🛢️ 国内大宗商品主力合约</span>
          <span class="text-[9px] text-terminal-dim">{{ commodityUpdateTime || '...' }}</span>
        </div>
        <div class="grid grid-cols-6 gap-2">
          <div
            v-for="item in commodityBlocks"
            v-if="item && item.symbol"
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
            <span class="text-[10px] text-gray-300 truncate w-full text-center">{{ item.name || item.symbol }}</span>
            <span
              class="text-xs font-mono mt-0.5"
              :class="(item.change_pct || 0) >= 0 ? 'text-red-400' : 'text-green-400'"
            >{{ (item.change_pct || 0) >= 0 ? '+' : '' }}{{ (item.change_pct ?? 0).toFixed(2) }}%</span>
          </div>
          <div v-if="!commodityBlocks || commodityBlocks.length === 0"
               class="col-span-6 text-center text-terminal-dim text-xs py-4">
            暂无数据
          </div>
        </div>
      </div>

      <!-- 下方：主力合约走势图（真实图表） -->
      <div class="flex-1 terminal-panel border border-gray-800 rounded p-4 flex flex-col">
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
import { ref, onMounted } from 'vue'
import FuturesMainChart from './FuturesMainChart.vue'

const futuresCards     = ref([])
const commodityBlocks  = ref([])
const commodityUpdateTime = ref('')

async function fetchFuturesData() {
  try {
    const [mi, mc] = await Promise.all([
      fetch('/api/v1/futures/main_indexes').then(r => r.ok ? r.json() : null),
      fetch('/api/v1/futures/commodities').then(r => r.ok ? r.json() : null),
    ])

    if (mi) {
      futuresCards.value = mi.index_futures || []
    }

    if (mc) {
      const commodities = mc.commodities || []
      commodityBlocks.value = commodities.slice(0, 12)
      commodityUpdateTime.value = mc.update_time || ''
    }
  } catch (e) {
    console.warn('[FuturesDashboard] fetch failed:', e)
  }
}

onMounted(() => {
  fetchFuturesData()
  setInterval(fetchFuturesData, 180_000)  // 每3分钟刷新
})
</script>
