<template>
  <!-- Teleport 全屏到 body，脱离主界面 DOM 树，强制 100vw/100vh -->
  <Teleport to="body">
    <div
      v-if="ui.klineFullscreen"
      class="fixed inset-0 w-screen h-screen bg-[#0a0e17] flex flex-col overflow-hidden"
      style="z-index: 99999 !important;"
    >
      <FullscreenKline
        v-if="!futuresFullscreen"
        :symbol="fullscreenSymbol"
        :name="fullscreenName"
        :isFull="true"
        @close="() => { ui.klineFullscreen = false }"
        @symbol-change="openFullscreenKline"
      />
      <FuturesPanel
        v-if="futuresFullscreen"
        :symbol="futuresFullscreenSymbol"
        @close="() => { futuresFullscreen = false; ui.klineFullscreen = false }"
      />
    </div>
  </Teleport>

  <!-- 全局错误遮罩 -->
  <div v-if="hasError" class="fixed inset-0 z-[99999] flex items-center justify-center bg-[#0a0e17]">
    <div class="text-center p-8">
      <div class="text-6xl mb-4">⚠️</div>
      <h1 class="text-xl text-red-400 mb-2">应用出现错误</h1>
      <p class="text-gray-400 text-sm mb-4 max-w-md">{{ errorMessage }}</p>
      <button 
        class="px-6 py-2 bg-terminal-accent text-white rounded hover:bg-terminal-accent/80 transition"
        @click="clearError"
      >
        重试
      </button>
    </div>
  </div>

  <!-- 主内容区（overflow:visible，允许position:fixed正确工作） -->
  <div class="flex h-screen bg-terminal-bg" style="overflow:visible">

    <!-- ━━━ 左侧 Sidebar（Phase 5 新增）━━━━━━━━━━━━━━━━━━━━━ -->
    <Sidebar
      :is-open="isSidebarOpen"
      :active-id="currentView"
      @navigate="handleSidebarNavigate"
      @close="isSidebarOpen = false"
    />

    <!-- ━━━ 左侧主体：网格 Dashboard ━━━━━━━━━━━━━━━━━━━━━━━ -->
    <main
      class="flex-1 flex flex-col transition-all duration-300 ease-in-out"
      style="overflow-y:auto;overflow-x:hidden"
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
          @open-fullscreen="openFullscreenKline"
        />
        <!-- 债券行情 -->
        <BondDashboard v-else-if="currentView === 'bond'" />
        <!-- 投资组合 -->
        <PortfolioDashboard v-else-if="currentView === 'portfolio'" />
        <!-- 期货行情 -->
        <FuturesDashboard v-else-if="currentView === 'futures'" @open-futures="openFuturesFullscreen" />
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
        :watch-list="watchList"
        @open-chart="openFullscreenKline"
        @show-north-flow="showNorthFlow"
        @show-limit-up="showLimitUp"
        @show-limit-down="showLimitDown"
        @show-unusual="showUnusual"
        @show-watchlist="currentView = 'stock'"
      />
    </aside>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, onErrorCaptured } from 'vue'
import Sidebar       from './components/Sidebar.vue'
import DashboardGrid from './components/DashboardGrid.vue'
import BondDashboard   from './components/BondDashboard.vue'
import FuturesDashboard from './components/FuturesDashboard.vue'
import PortfolioDashboard from './components/PortfolioDashboard.vue'
import FuturesPanel       from './components/FuturesPanel.vue'
import CopilotSidebar from './components/CopilotSidebar.vue'
import FullscreenKline from './components/FullscreenKline.vue'
import { useUiStore } from './composables/useUiStore.js'
import { fetchApiBatch } from './utils/apiClient.js'

const { ui } = useUiStore()

// 全局错误处理
const hasError = ref(false)
const errorMessage = ref('')

function clearError() {
  hasError.value = false
  errorMessage.value = ''
  window.location.reload()
}

onErrorCaptured((err, instance, info) => {
  console.error('[App] 捕获到错误:', err)
  console.error('[App] 组件:', instance)
  console.error('[App] 信息:', info)
  hasError.value = true
  errorMessage.value = err.message || '未知错误'
  return false // 阻止错误继续传播
})

// Phase 5: 侧边栏与视图切换状态
const isSidebarOpen = ref(false)   // 侧边栏默认收起
const currentView   = ref('stock') // 默认视图：stock / bond / futures
const futuresFullscreen = ref(false)
const futuresFullscreenSymbol = ref('IF0')

function handleSidebarNavigate(viewId) {
  currentView.value = viewId
}

function openFuturesFullscreen({ symbol }) {
  futuresFullscreenSymbol.value = symbol || 'IF0'
  futuresFullscreen.value = true
  ui.klineFullscreen = true
}

const isCopilotOpen = ref(false) // 默认收起 AI 助理
const isLocked = ref(true)     // 网格默认锁定

// 全屏 K 线状态（提升到 App 根级别，脱离 stacking context 约束）
const fullscreenSymbol = ref('sh000001')
const fullscreenName   = ref('上证指数')

function openFullscreenKline({ symbol, name }) {
  console.log('[DEBUG] openFullscreenKline called', { symbol, name, klineFullscreenBefore: ui.klineFullscreen })
  fullscreenSymbol.value = symbol || 'sh000001'
  fullscreenName.value  = name  || '上证指数'
  ui.klineFullscreen = true
  console.log('[DEBUG] ui.klineFullscreen set to', ui.klineFullscreen, '| fullscreenSymbol:', fullscreenSymbol.value)
}

function toggleLock() {
  isLocked.value = !isLocked.value
}

function toggleCopilot() {
  isCopilotOpen.value = !isCopilotOpen.value
}

// Copilot 事件处理
function showNorthFlow() {
  console.log('[Copilot] 北向资金')
  // 可以在此打开北向资金面板
}

function showLimitUp() {
  console.log('[Copilot] 涨停板')
  // 可以在此打开涨停板面板
}

function showLimitDown() {
  console.log('[Copilot] 跌停板')
  // 可以在此打开跌停板面板
}

function showUnusual() {
  console.log('[Copilot] 盘中异动')
  // 可以在此打开异动面板
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
const watchList       = ref([])   // 自选股列表

let clockTimer = null

function updateClock() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour12: false }) + ' CST'
}

async function fetchMarketData() {
  try {
    const results = await fetchApiBatch([
      { url: '/api/v1/market/overview', key: 'overview', default: null },
      { url: '/api/v1/market/macro', key: 'macro', default: [] },
      { url: '/api/v1/market/rates', key: 'rates', default: [] },
      { url: '/api/v1/news/flash', key: 'news', default: [] },
      { url: '/api/v1/market/global', key: 'global', default: [] },
      { url: '/api/v1/market/china_all', key: 'china_all', default: [] },
      { url: '/api/v1/market/sectors', key: 'sectors', default: [] },
      { url: '/api/v1/market/derivatives', key: 'derivatives', default: [] },
    ])
    
    // 修复: market_overview 现在直接返回 Sina 实时数据（无 data.wind 包装）
    // 兼容: results.overview={wind:{...}} 和 results.overview={...}（扁平）
    marketOverview.value  = results.overview?.wind || results.overview || null
    macroData.value       = results.macro?.macro || results.macro?.data?.macro || results.macro || []
    ratesData.value       = results.rates?.rates || results.rates?.data?.rates || results.rates || []
    // 修复: news/flash 新格式 {code, data: {news:[...]}} → results.news = {news:[...]}
    // 兼容旧格式 news:[...] 直接返回（Array.isArray 判断）
    newsData.value        = results.news?.news || results.news?.data?.news || (Array.isArray(results.news) ? results.news : [])
    globalData.value      = results.global?.global || results.global?.data?.global || results.global || []
    // 修复: china_all 新格式 {code, data: {china_all:[...]}} → results.china_all = {china_all:[...]}
    // 兼容旧格式 china_all:[...] 直接返回
    // 注意: 必须用括号包裹三元运算，避免优先级问题
    chinaAllData.value    = results.china_all?.china_all || results.china_all?.data?.china_all || (Array.isArray(results.china_all) ? results.china_all : [])
    // 修复: sectors 新格式 {code, data: {sectors:[...]}} → results.sectors = {sectors:[...]}
    sectorsData.value     = results.sectors?.sectors || results.sectors?.data?.sectors || (Array.isArray(results.sectors) ? results.sectors : [])
    derivativesData.value = results.derivatives?.derivatives || results.derivatives?.data?.derivatives || results.derivatives || []
  } catch (e) {
    console.error('[App] fetchMarketData error:', e)
  }
}

let refreshTimer = null

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  fetchMarketData()
  refreshTimer = setInterval(fetchMarketData, 30000)
})

onUnmounted(() => {
  clearInterval(clockTimer)
  clearInterval(refreshTimer)
})
</script>

<style>
/* 错误遮罩样式 */
.error-overlay {
  position: fixed;
  inset: 0;
  z-index: 99999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0a0e17;
}
.error-content {
  text-align: center;
  padding: 2rem;
}
.error-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}
.error-title {
  font-size: 1.25rem;
  color: #ef4444;
  margin-bottom: 0.5rem;
}
.error-message {
  color: #9ca3af;
  font-size: 0.875rem;
  margin-bottom: 1.5rem;
  max-width: 400px;
}
.error-retry {
  padding: 0.5rem 1.5rem;
  background: #fbbf24;
  color: #000;
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: opacity 0.2s;
}
.error-retry:hover {
  opacity: 0.9;
}
</style>
