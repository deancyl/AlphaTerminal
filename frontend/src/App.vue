<template>
  <div class="flex h-screen bg-terminal-bg overflow-hidden">

    <!-- ━━━ 左侧主体：网格 Dashboard ━━━━━━━━━━━━━━━━━━━━━━━ -->
    <main class="flex-1 flex flex-col overflow-hidden">
      <!-- 顶部状态栏 -->
      <header class="h-12 flex items-center justify-between px-4 border-b border-gray-800 bg-terminal-panel/80">
        <div class="flex items-center gap-3">
          <span class="text-terminal-accent font-bold text-base">📊 AlphaTerminal</span>
          <span class="text-terminal-dim text-xs">Phase 7 · 全球市场 · K线</span>
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
        <DashboardGrid
          :market-data="marketOverview"
          :rates-data="ratesData"
          :global-data="globalData"
          :china-all-data="chinaAllData"
          :sectors-data="sectorsData"
          :derivatives-data="derivativesData"
        />
      </div>
    </main>

    <!-- ━━━ 右侧边栏：AI Copilot（Task 5: 吸附右侧）━━━━━━━━━━ -->
    <aside class="w-[340px] flex-shrink-0 flex flex-col bg-terminal-panel border-l border-gray-800">
      <CopilotSidebar
        :market-overview="marketOverview"
        :global-data="globalData"
        :china-all-data="chinaAllData"
        :sectors-data="sectorsData"
        :derivatives-data="derivativesData"
        :rates-data="ratesData"
        :news-data="newsData"
      />
    </aside>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import CopilotSidebar from './components/CopilotSidebar.vue'
import DashboardGrid  from './components/DashboardGrid.vue'

const marketOverview  = ref(null)
const ratesData       = ref([])
const newsData        = ref([])
const globalData      = ref([])
const chinaAllData    = ref([])
const sectorsData     = ref([])
const derivativesData = ref([])
const currentTime     = ref('')

let clockTimer = null

function updateClock() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour12: false }) + ' CST'
}

async function fetchMarketData() {
  try {
    const [ov, rt, nv, gl, ca, sc, dr] = await Promise.all([
      fetch('/api/v1/market/overview').then(r => r.ok ? r.json() : null),
      fetch('/api/v1/market/rates').then(r => r.ok ? r.json().then(d => d.rates || []) : []),
      fetch('/api/v1/news/flash').then(r => r.ok ? r.json().then(d => d.news || []) : []),
      fetch('/api/v1/market/global').then(r => r.ok ? r.json().then(d => d.global || []) : []),
      fetch('/api/v1/market/china_all').then(r => r.ok ? r.json().then(d => d.china_all || []) : []),
      fetch('/api/v1/market/sectors').then(r => r.ok ? r.json().then(d => d.sectors || []) : []),
      fetch('/api/v1/market/derivatives').then(r => r.ok ? r.json().then(d => d.derivatives || []) : []),
    ])
    marketOverview.value  = ov
    ratesData.value       = rt
    newsData.value        = nv
    globalData.value      = gl
    chinaAllData.value    = ca
    sectorsData.value     = sc
    derivativesData.value = dr
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
