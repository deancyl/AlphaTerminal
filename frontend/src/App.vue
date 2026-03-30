<template>
  <div class="flex h-screen bg-terminal-bg overflow-hidden">

    <!-- ━━━ 左侧边栏：AI Copilot ━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <aside class="w-[320px] flex-shrink-0 flex flex-col bg-terminal-panel border-r border-gray-800">
      <CopilotSidebar
        :market-overview="marketOverview"
        :rates-data="ratesData"
        :news-data="newsData"
      />
    </aside>

    <!-- ━━━ 右侧主体：网格 Dashboard ━━━━━━━━━━━━━━━━━━━━━━━ -->
    <main class="flex-1 flex flex-col overflow-hidden">
      <!-- 顶部状态栏 -->
      <header class="h-12 flex items-center justify-between px-4 border-b border-gray-800 bg-terminal-panel/80">
        <div class="flex items-center gap-3">
          <span class="text-terminal-accent font-bold text-base">📊 AlphaTerminal</span>
          <span class="text-terminal-dim text-xs">Phase 4 · AI Copilot + 资讯流</span>
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
import CopilotSidebar from './components/CopilotSidebar.vue'
import DashboardGrid  from './components/DashboardGrid.vue'

const marketOverview = ref(null)
const ratesData      = ref([])
const newsData       = ref([])
const currentTime    = ref('')

let clockTimer = null

function updateClock() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour12: false }) + ' CST'
}

async function fetchMarketData() {
  try {
    const [ov, rt, nv] = await Promise.all([
      fetch('/api/v1/market/overview').then(r => r.ok ? r.json() : null),
      fetch('/api/v1/market/rates').then(r => r.ok ? r.json().then(d => d.rates || []) : []),
      fetch('/api/v1/news/flash').then(r => r.ok ? r.json().then(d => d.news || []) : []),
    ])
    marketOverview.value = ov
    ratesData.value      = rt
    newsData.value       = nv
  } catch (e) {
    console.warn('[AlphaTerminal] 后端未启动:', e.message)
  }
}

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  fetchMarketData()
})

onUnmounted(() => clearInterval(clockTimer))
</script>
