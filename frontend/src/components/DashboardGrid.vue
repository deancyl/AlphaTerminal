<template>
  <div class="grid-stack" ref="gridRef">

    <!-- Widget 1：市场总览 -->
    <div class="grid-stack-item" gs-x="0" gs-y="0" gs-w="4" gs-h="3" gs-min-w="2" gs-min-h="2">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <div class="flex items-center justify-between mb-3">
          <span class="text-terminal-accent font-bold text-sm">📈 市场总览</span>
          <span class="text-terminal-dim text-xs">{{ timestamp || '加载中...' }}</span>
        </div>
        <div class="flex-1 overflow-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="text-terminal-dim border-b border-gray-700">
                <th class="text-left py-1">市场</th>
                <th class="text-right py-1">指数</th>
                <th class="text-right py-1">涨跌幅</th>
                <th class="text-right py-1">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(m, key) in marketMarkets" :key="key"
                  class="border-b border-gray-800 hover:bg-white/5">
                <td class="py-1.5 text-gray-300">{{ m.name }}</td>
                <td class="py-1.5 text-right font-mono">{{ formatIndex(m.index) }}</td>
                <td class="py-1.5 text-right font-mono"
                    :class="m.change_pct >= 0 ? 'text-red-400' : 'text-green-400'">
                  {{ m.change_pct >= 0 ? '+' : '' }}{{ m.change_pct.toFixed(2) }}%
                </td>
                <td class="py-1.5 text-right">
                  <span class="px-1.5 py-0.5 rounded text-[10px]"
                        :class="m.status === '交易中' ? 'bg-green-500/20 text-green-400' : 'bg-gray-600/30 text-gray-400'">
                    {{ m.status }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Widget 2：资金面指标 -->
    <div class="grid-stack-item" gs-x="4" gs-y="0" gs-w="4" gs-h="3" gs-min-w="2" gs-min-h="2">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <div class="flex items-center justify-between mb-3">
          <span class="text-terminal-accent font-bold text-sm">💰 资金面</span>
        </div>
        <div class="flex-1 grid grid-cols-2 gap-3 content-start">
          <div v-for="(val, key) in fundamentals" :key="key"
               class="bg-terminal-bg rounded p-2 border border-gray-700">
            <div class="text-terminal-dim text-[10px] uppercase">{{ key }}</div>
            <div class="text-gray-100 font-mono text-sm mt-0.5">{{ val }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Widget 3：实时时钟 + 系统状态 -->
    <div class="grid-stack-item" gs-x="8" gs-y="0" gs-w="4" gs-h="3" gs-min-w="2" gs-min-h="2">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <div class="flex items-center justify-between mb-3">
          <span class="text-terminal-accent font-bold text-sm">🕐 系统状态</span>
          <span class="text-green-400 text-xs">● 运行中</span>
        </div>
        <div class="flex-1 flex flex-col justify-center items-center">
          <div class="text-4xl font-mono font-bold text-gray-100">{{ currentTime }}</div>
          <div class="text-terminal-dim text-xs mt-2">{{ currentDate }}</div>
          <div class="mt-4 text-center">
            <div class="text-terminal-dim text-xs">数据源</div>
            <div class="text-gray-300 text-xs mt-1">AKShare · yfinance · CoinGecko</div>
          </div>
          <div class="mt-3 text-center">
            <div class="text-terminal-dim text-xs">后端状态</div>
            <div class="text-xs mt-1" :class="backendConnected ? 'text-green-400' : 'text-red-400'">
              {{ backendConnected ? '● 已连接 localhost:8002' : '○ 未连接' }}
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
// gridstack 通过 index.html CDN 全局加载，无需 import

const props = defineProps({
  marketData: {
    type: Object,
    default: null
  }
})

const gridRef = ref(null)
const currentTime = ref('')
const currentDate = ref('')
const backendConnected = ref(false)
let clockTimer = null
let grid = null

const timestamp = computed(() => props.marketData?.timestamp?.slice(11, 19) ?? '')
const marketMarkets = computed(() => props.marketData?.markets ?? {})
const fundamentals = computed(() => {
  const f = props.marketData?.fundamentals ?? {}
  return {
    'Shibor 1W': f.shibor_1w ?? '--',
    'Shibor 1Y': f.shibor_1y ?? '--',
    'USD/CNY': f.usd_cny ?? '--',
    'USD Index': f.usd_index ?? '--',
    '黄金 USD': f.gold_usd ?? '--',
    'WTI 原油': f.wti_oil ?? '--',
  }
})

function formatIndex(v) {
  if (v === undefined || v === null) return '--'
  if (v > 10000) return v.toLocaleString('en-US', { maximumFractionDigits: 2 })
  return v.toFixed(2)
}

function updateClock() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour12: false })
  currentDate.value = now.toLocaleDateString('zh-CN', { weekday: 'short', year: 'numeric', month: '2-digit', day: '2-digit' })
}

onMounted(async () => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)

  // 检查后端连通性
  try {
    const res = await fetch('http://localhost:8002/health')
    backendConnected.value = res.ok
  } catch {
    backendConnected.value = false
  }

  // 初始化 gridstack
  if (typeof window !== 'undefined' && window.GridStack) {
    grid = GridStack.init({
      column: 12,
      cellHeight: 80,
      float: true,
      margin: 8,
    })
  }
})

onUnmounted(() => {
  clearInterval(clockTimer)
  grid?.destroy(false)
})
</script>

<style>
.grid-stack {
  width: 100%;
}
.grid-stack-item-content {
  inset: 4px;
  overflow: hidden;
  border-radius: 8px;
}
.grid-stack > .grid-stack-item > .grid-stack-item-content {
  bottom: auto !important;
}
</style>
