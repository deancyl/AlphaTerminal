<template>
  <div class="flex h-screen bg-terminal-bg overflow-hidden">

    <!-- ━━━ 左侧边栏：AI 投研大脑 ━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <aside class="w-[300px] flex-shrink-0 flex flex-col bg-terminal-panel border-r border-gray-800">
      <div class="p-4 border-b border-gray-800">
        <h2 class="text-terminal-accent font-bold text-lg flex items-center gap-2">
          🧠 AlphaTerminal Copilot
        </h2>
        <p class="text-terminal-dim text-xs mt-1">由 OpenClaw 驱动的智能投研助手</p>
      </div>

      <!-- 对话占位 -->
      <div class="flex-1 p-4 overflow-y-auto">
        <div class="bg-terminal-bg rounded-lg p-3 border border-gray-700">
          <p class="text-terminal-dim text-sm">💬 AI 助手已就绪</p>
          <p class="text-terminal-dim text-xs mt-1">Phase 2 阶段：对话框占位，后续接入 Copilot 逻辑</p>
        </div>
      </div>

      <!-- 输入框占位 -->
      <div class="p-4 border-t border-gray-800">
        <textarea
          class="w-full bg-terminal-bg border border-gray-700 rounded px-3 py-2 text-sm text-gray-100 resize-none focus:outline-none focus:border-terminal-accent"
          rows="3"
          placeholder="输入投研问题..."
          disabled
        ></textarea>
        <button class="mt-2 w-full bg-terminal-accent/10 border border-terminal-accent/40 text-terminal-accent text-sm rounded py-1.5 hover:bg-terminal-accent/20 transition cursor-not-allowed" disabled>
          发送 (Phase 3)
        </button>
      </div>
    </aside>

    <!-- ━━━ 右侧主体：网格 Dashboard ━━━━━━━━━━━━━━━━━━━━━ -->
    <main class="flex-1 flex flex-col overflow-hidden">
      <!-- 顶部状态栏 -->
      <header class="h-12 flex items-center justify-between px-4 border-b border-gray-800 bg-terminal-panel/80">
        <div class="flex items-center gap-3">
          <span class="text-terminal-accent font-bold text-base">📊 AlphaTerminal</span>
          <span class="text-terminal-dim text-xs">Phase 2 · Dashboard 骨架</span>
        </div>
        <div class="flex items-center gap-4 text-xs text-terminal-dim">
          <span id="clock" class="font-mono">{{ currentTime }}</span>
          <span class="px-2 py-0.5 rounded bg-terminal-accent/10 text-terminal-accent border border-terminal-accent/30">
            ● LIVE
          </span>
        </div>
      </header>

      <!-- Dashboard 网格区域 -->
      <div class="flex-1 overflow-auto p-4">
        <DashboardGrid :market-data="marketOverview" :rates-data="ratesData" />
      </div>
    </main>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import DashboardGrid from './components/DashboardGrid.vue'

const marketOverview = ref(null)
const ratesData      = ref([])
const currentTime = ref('')

let clockTimer = null

function updateClock() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour12: false }) + ' CST'
}

async function fetchMarketData() {
  try {
    const [ov, rt] = await Promise.all([
      fetch('http://localhost:8002/api/v1/market/overview').then(r => r.ok ? r.json() : null),
      fetch('http://localhost:8002/api/v1/market/rates').then(r => r.ok ? r.json().then(d => d.rates || []) : []),
    ])
    marketOverview.value = ov
    ratesData.value      = rt
    console.log('[AlphaTerminal] 市场数据已加载，利率 ', rt.length, ' 条')
  } catch (e) {
    console.warn('[AlphaTerminal] 后端未启动或请求失败:', e.message)
  }
}

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  fetchMarketData()
})

onUnmounted(() => {
  clearInterval(clockTimer)
})
</script>
