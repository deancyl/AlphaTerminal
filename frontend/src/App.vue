<template>
  <!-- Teleport 全屏到 body，脱离主界面 DOM 树，强制 100vw/100vh -->
  <Teleport to="body">
    <div
      v-if="ui.klineFullscreen"
      class="fixed inset-0 w-screen h-screen bg-terminal-bg flex flex-col overflow-hidden"
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
  <div v-if="hasError" class="fixed inset-0 z-[99999] flex items-center justify-center bg-terminal-bg">
    <div class="text-center p-8">
      <div class="text-6xl mb-4">⚠️</div>
      <h1 class="text-xl text-terminal-accent mb-2">应用出现错误</h1>
      <p class="text-terminal-dim text-sm mb-4 max-w-md">{{ errorMessage }}</p>
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

    <!-- ━━━ 移动端 Sidebar 遮罩层 ━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <div v-if="isMobile && isSidebarOpen" class="fixed inset-0 bg-black/50 z-[9999]" @click="isSidebarOpen = false" />

    <!-- ━━━ 左侧 Sidebar（Phase 5 新增）━━━━━━━━━━━━━━━━━━━━━ -->
    <!-- 桌面端：直接渲染 | 移动端：固定定位 overlay -->
    <div v-if="!isMobile" class="flex-shrink-0">
      <Sidebar
        :is-open="isSidebarOpen"
        :active-id="currentView"
        @navigate="handleSidebarNavigate"
        @close="isSidebarOpen = false"
      />
    </div>
    <!-- 移动端：固定定位 sidebar -->
    <div v-else class="fixed left-0 top-0 h-full z-[10000] transition-transform bg-theme-panel" :style="{ transform: isSidebarOpen ? 'translateX(0)' : 'translateX(-100%)', width: '224px' }">
      <Sidebar
        :is-open="isSidebarOpen"
        :active-id="currentView"
        @navigate="handleSidebarNavigate; isSidebarOpen = false"
        @close="isSidebarOpen = false"
      />
    </div>

    <!-- ━━━ 左侧主体：网格 Dashboard ━━━━━━━━━━━━━━━━━━━━━━━ -->
    <main
      class="flex-1 flex flex-col transition-all duration-300 ease-in-out"
      style="overflow-y:auto;overflow-x:hidden"
      :style="{ width: isMobile ? '100%' : (isCopilotOpen ? 'calc(100% - 340px)' : '100%') }"
    >
      <!-- 顶部状态栏 -->
      <header class="h-12 flex items-center justify-between px-4 border-b border-theme-secondary bg-terminal-panel/80 shrink-0">
        <div class="flex items-center gap-3">
          <!-- ☰ 侧边栏展开按钮 -->
          <button
            class="w-7 h-7 flex items-center justify-center rounded text-terminal-dim hover:text-terminal-accent transition-colors text-lg"
            @click="isSidebarOpen = !isSidebarOpen"
            title="切换侧边栏"
          >
            ☰
          </button>
          <span class="text-terminal-accent font-bold text-base">📊 AlphaTerminal</span>
        </div>
        <div class="flex items-center gap-3 text-xs text-terminal-dim">
          <!-- 仅桌面端显示时钟 -->
          <span v-if="!isMobile" id="clock" class="font-mono">{{ currentTime }}</span>
          <span class="px-2 py-0.5 rounded bg-terminal-accent/10 text-terminal-accent border border-terminal-accent/30">
            ● LIVE
          </span>
          <!-- 仅桌面端显示锁定按钮（手机端不需要拖拽） -->
          <button
            v-if="!isMobile"
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
      <div class="flex-1 overflow-auto p-4 relative">
        <!-- F1修复: 骨架屏加载状态 -->
        <div v-if="isInitialLoading" class="absolute inset-0 z-10 bg-terminal-bg/95 flex flex-col gap-3 p-4 animate-pulse">
          <!-- 风向标骨架 -->
          <div class="grid grid-cols-4 gap-2">
            <div v-for="i in 4" :key="i" class="h-16 rounded bg-terminal-panel border border-theme"></div>
          </div>
          <!-- 新闻/板块骨架 -->
          <div class="grid grid-cols-2 gap-2">
            <div class="h-32 rounded bg-terminal-panel border border-theme"></div>
            <div class="h-32 rounded bg-terminal-panel border border-theme"></div>
          </div>
          <!-- K线骨架 -->
          <div class="h-48 rounded bg-terminal-panel border border-theme"></div>
          <div class="text-terminal-dim text-xs text-center">正在加载市场数据...</div>
        </div>

        <!-- F2修复: 加载错误提示 -->
        <div v-if="loadError && !isInitialLoading" 
             class="mb-2 px-3 py-2 rounded border border-bullish/40 bg-bullish/15 text-bullish text-xs flex items-center justify-between">
          <span>⚠️ 数据加载失败: {{ loadError }}</span>
          <button @click="fetchMarketData" class="px-2 py-0.5 bg-bullish/30 rounded text-bullish-light hover:bg-bullish/40">重试</button>
        </div>

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
        <!-- 买卖盘口 -->
        <SimpleQuotePanel v-else-if="currentView === 'simplequote'" :symbol="currentSymbol || 'sh600519'" />
        <!-- 回测实验室 -->
        <BacktestDashboard v-else-if="currentView === 'backtest'" />
        <!-- 系统管理 -->
        <AdminDashboard v-else-if="currentView === 'admin'" />
      </div>
    </main>

    <!-- ━━━ Copilot 抽屉 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <!-- 桌面端：右侧 sidebar | 移动端：底部抽屉 (bottom sheet) -->
    <aside
      v-show="isCopilotOpen"
      :class="isMobile 
        ? 'fixed bottom-0 left-0 right-0 z-[9998] max-h-[80vh] rounded-t-2xl border-t-2 border-theme' 
        : 'flex-shrink-0 flex flex-col bg-terminal-panel border-l border-theme-secondary transition-all duration-300 ease-in-out overflow-hidden'"
      :style="isMobile ? { width: '100%', maxWidth: '100%' } : { width: '340px', maxWidth: '340px' }"
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
import { ref, onMounted, onUnmounted, onErrorCaptured, watch, computed } from 'vue'
import { useDocumentVisibility, useIntervalFn, useBreakpoints, breakpointsTailwind } from '@vueuse/core'
import Sidebar       from './components/Sidebar.vue'
import DashboardGrid from './components/DashboardGrid.vue'
import BondDashboard   from './components/BondDashboard.vue'
import FuturesDashboard from './components/FuturesDashboard.vue'
import PortfolioDashboard from './components/PortfolioDashboard.vue'
import SimpleQuotePanel from './components/SimpleQuotePanel.vue'
import BacktestDashboard from './components/BacktestDashboard.vue'
import FuturesPanel       from './components/FuturesPanel.vue'
import CopilotSidebar from './components/CopilotSidebar.vue'
import AdminDashboard  from './components/AdminDashboard.vue'
import FullscreenKline from './components/FullscreenKline.vue'
import { useUiStore } from './composables/useUiStore.js'
import { useMarketStore } from './stores/market.js'
import { useTheme } from './composables/useTheme.js'
import { fetchApiBatch } from './utils/api.js'
import { logger } from './utils/logger.js'

const { ui } = useUiStore()
const { currentSymbol } = useMarketStore()

// 初始化主题系统（必须在组件挂载前调用）
const { theme: currentTheme, isDark } = useTheme()

// 全局错误处理
const hasError = ref(false)
const errorMessage = ref('')
const isInitialLoading = ref(true)  // 初始加载骨架屏
const loadError = ref(null)          // 加载错误信息

function clearError() {
  hasError.value = false
  errorMessage.value = ''
  // 避免window.location.reload()丢失所有内存状态
  // 通过重置组件key来重建有问题的组件
  errorComponentKey.value++
}

const errorComponentKey = ref(0)

onErrorCaptured((err, instance, info) => {
  logger.error('[App] 捕获到错误:', err)
  logger.error('[App] 组件:', instance?.type?.name || instance)
  logger.error('[App] 信息:', info)
  hasError.value = true
  errorMessage.value = err.message || err.toString() || '未知错误'
  // 仅标记错误，不刷新整个页面，保持其他组件状态
  return false // 阻止错误继续传播
})

// Phase 5: 侧边栏与视图切换状态
const isSidebarOpen = ref(false)   // 侧边栏默认收起（桌面+手机）
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
const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('md')  // < 768px is mobile

// 全屏 K 线状态（提升到 App 根级别，脱离 stacking context 约束）
const fullscreenSymbol = ref('sh000001')
const fullscreenName   = ref('上证指数')

function openFullscreenKline({ symbol, name }) {
  logger.log('[DEBUG] openFullscreenKline called', { symbol, name, klineFullscreenBefore: ui.klineFullscreen })
  fullscreenSymbol.value = symbol || 'sh000001'
  fullscreenName.value  = name  || '上证指数'
  ui.klineFullscreen = true
  logger.log('[DEBUG] ui.klineFullscreen set to', ui.klineFullscreen, '| fullscreenSymbol:', fullscreenSymbol.value)
}

function toggleLock() {
  isLocked.value = !isLocked.value
}

function toggleCopilot() {
  isCopilotOpen.value = !isCopilotOpen.value
}

// Copilot 事件处理
function showNorthFlow() {
  logger.log('[Copilot] 北向资金')
  // 可以在此打开北向资金面板
}

function showLimitUp() {
  logger.log('[Copilot] 涨停板')
  // 可以在此打开涨停板面板
}

function showLimitDown() {
  logger.log('[Copilot] 跌停板')
  // 可以在此打开跌停板面板
}

function showUnusual() {
  logger.log('[Copilot] 盘中异动')
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
    
    // 数据加载完成，关闭骨架屏
    isInitialLoading.value = false
    loadError.value = null
  } catch (e) {
    logger.error('[App] fetchMarketData error:', e)
    // 加载失败，显示错误提示
    loadError.value = e.message || '数据加载失败'
    isInitialLoading.value = false
  }
}

let refreshTimer = null

// 页面可见性控制 - 页面隐藏时暂停轮询，节省资源
const visibility = useDocumentVisibility()

// 监听可见性变化，页面隐藏时暂停轮询
watch(visibility, (v) => {
  if (v === 'visible') {
    logger.log('[App] 页面可见，恢复轮询')
    fetchMarketData()  // 立即刷新一次
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = setInterval(fetchMarketData, 30000)
    }
  } else {
    logger.log('[App] 页面隐藏，暂停轮询')
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }
})

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  // 仅在页面可见时启动轮询
  if (visibility.value === 'visible') {
    fetchMarketData()
    refreshTimer = setInterval(fetchMarketData, 30000)
  }
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
  background: var(--bg-primary);
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
  color: var(--accent-primary);
  margin-bottom: 0.5rem;
}
.error-message {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-bottom: 1.5rem;
  max-width: 400px;
}
.error-retry {
  padding: 0.5rem 1.5rem;
  background: var(--accent-primary);
  color: var(--bg-primary);
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
