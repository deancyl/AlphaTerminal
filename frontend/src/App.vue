<template>
  <div class="flex h-screen bg-terminal-bg overflow-hidden">

    <!-- ━━━ 左侧 Sidebar（Phase 5 新增）━━━━━━━━━━━━━━━━━━━━━ -->
    <Sidebar
      :is-open="isSidebarOpen"
      :active-id="currentView"
      @navigate="handleSidebarNavigate"
      @close="isSidebarOpen = false"
    />

    <!-- ━━━ 左侧主体：网格 Dashboard ━━━━━━━━━━━━━━━━━━━━━━━ -->
    <main
      class="flex-1 flex flex-col overflow-hidden transition-all duration-300 ease-in-out"
      :style="{ width: isCopilotOpen ? 'calc(100% - 340px)' : '100%' }"
    >
      <!-- 顶部状态栏 -->
      <header class="h-12 flex items-center justify-between px-4 border-b border-gray-800 bg-terminal-panel/80 shrink-0">
        <div class="flex items-center gap-3">
          <!-- ☰ 侧边栏展开按钮 -->
          <button
            class="w-7 h-7 flex items-center justify-center rounded text-gray-400 hover:text-terminal-accent transition-colors text-lg"
            @click="isSidebarOpen = !isSidebarOpen"
            title="切换侧边栏"
          >
            ☰
          </button>
          <span class="text-terminal-accent font-bold text-base">📊 AlphaTerminal</span>
          <span class="text-terminal-dim text-xs">Phase 7 · 全球市场 · K线</span>
        </div>
        <div class="flex items-center gap-3 text-xs text-terminal-dim">
          <span id="clock" class="font-mono">{{ currentTime }}</span>
          <span class="px-2 py-0.5 rounded bg-terminal-accent/10 text-terminal-accent border border-terminal-accent/30">
            ● LIVE
          </span>
          <!-- 🔒 锁定/解锁按钮 -->
          <button
            class="flex items-center gap-1 px-2.5 py-1 rounded border text-xs transition"
            :class="isLocked
              ? 'border-amber-500/30 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20'
              : 'border-green-500/30 bg-green-500/10 text-green-400 hover:bg-green-500/20'"
            @click="toggleLock"
            :title="isLocked ? '点击解锁网格（允许拖拽）' : '点击锁定网格（禁止拖拽）'"
          >
            <span v-if="isLocked">🔒</span>
            <span v-else>🔓</span>
            {{ isLocked ? '已锁定' : '可拖拽' }}
          </button>
          <!-- Copilot 唤醒按钮 -->
          <button
            class="flex items-center gap-1 px-2 py-1 rounded border border-purple-500/30 bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 hover:border-purple-500/50 transition-all text-xs"
            @click="toggleCopilot"
          >
            <span v-if="isCopilotOpen">⏭ 收起 AI 助理</span>
            <span v-else>🤖 展开 AI 助理</span>
          </button>
          <!-- 全屏按钮 -->
          <button
            class="px-2 py-1 rounded border border-gray-600 text-gray-400 hover:border-terminal-accent/50 hover:text-terminal-accent transition-colors text-xs"
            @click="ui.klineFullscreen = !ui.klineFullscreen"
            title="K线全屏"
          >
            {{ ui.klineFullscreen ? '✕ 退出全屏' : '⛶ 全屏' }}
          </button>
        </div>
      </header>

      <!-- 主视图区域（Phase 5 视图切换） -->
      <div class="flex-1 overflow-auto p-4">
        <!-- 股票行情（默认） -->
        <DashboardGrid
          v-if="currentView === 'stock'"
          :market-data="marketOverview"
          :macro-data="macroData"
          :rates-data="ratesData"
          :global-data="globalData"
          :china-all-data="chinaAllData"
          :sectors-data="sectorsData"
          :derivatives-data="derivativesData"
          :is-locked="isLocked"
          @toggle-lock="toggleLock"
        />
        <!-- 债券行情 -->
        <BondDashboard v-else-if="currentView === 'bond'" />
        <!-- 期货行情 -->
        <FuturesDashboard v-else-if="currentView === 'futures'" />
      </div>
    </main>

    <!-- ━━━ 右侧 Copilot 抽屉 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <aside
      v-show="isCopilotOpen"
      class="flex-shrink-0 flex flex-col bg-terminal-panel border-l border-gray-800 transition-all duration-300 ease-in-out overflow-hidden"
      style="width: 340px; max-width: 340px;"
    >
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
import Sidebar       from './components/Sidebar.vue'
import DashboardGrid from './components/DashboardGrid.vue'
import BondDashboard  from './components/BondDashboard.vue'
import FuturesDashboard from './components/FuturesDashboard.vue'
import CopilotSidebar from './components/CopilotSidebar.vue'
import { useUiStore } from './composables/useUiStore.js'

const { ui } = useUiStore()

// Phase 5: 侧边栏与视图切换状态
const isSidebarOpen = ref(false)   // 侧边栏默认收起
const currentView   = ref('stock') // 默认视图：stock / bond / futures

function handleSidebarNavigate(viewId) {
  currentView.value = viewId
}

const isCopilotOpen = ref(false) // 默认收起 AI 助理
const isLocked = ref(true)     // 网格默认锁定

function toggleLock() {
  isLocked.value = !isLocked.value
}

function toggleCopilot() {
  isCopilotOpen.value = !isCopilotOpen.value
}

const marketOverview  = ref(null)
const macroData      = ref([])   // Phase 5: USD/CNH · 黄金 · WTI · VIX
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
    const [ov, mc, rt, nv, gl, ca, sc, dr] = await Promise.all([
      fetch('/api/v1/market/overview').then(r => r.ok ? r.json() : null),
      fetch('/api/v1/market/macro').then(r => r.ok ? r.json().then(d => d.macro || []) : []),
      fetch('/api/v1/market/rates').then(r => r.ok ? r.json().then(d => d.rates || []) : []),
      fetch('/api/v1/news/flash').then(r => r.ok ? r.json().then(d => d.news || []) : []),
      fetch('/api/v1/market/global').then(r => r.ok ? r.json().then(d => d.global || []) : []),
      fetch('/api/v1/market/china_all').then(r => r.ok ? r.json().then(d => d.china_all || []) : []),
      fetch('/api/v1/market/sectors').then(r => r.ok ? r.json().then(d => d.sectors || []) : []),
      fetch('/api/v1/market/derivatives').then(r => r.ok ? r.json().then(d => d.derivatives || []) : []),
    ])
    marketOverview.value  = ov
    macroData.value       = mc
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

// 每 30 秒静默刷新（不影响用户操作）
let refreshTimer = null
function startRefresh() {
  refreshTimer = setInterval(fetchMarketData, 30_000)
}

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  fetchMarketData()
  startRefresh()
})

onUnmounted(() => {
  clearInterval(clockTimer)
  clearInterval(refreshTimer)
})
</script>
