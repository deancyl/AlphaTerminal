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
        :symbol="ui.fullscreenSymbol"
        :name="ui.fullscreenName"
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

  <!-- ━━━ Toast 通知容器 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
  <ToastContainer />

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

    <!-- ━━━ 桌面端 Sidebar（默认隐藏，点击☰展开）━━━━━━━━━━━━━━ -->
    <template v-if="!isMobile">
      <!-- 遮罩层 -->
      <div v-if="isSidebarOpen" class="fixed inset-0 bg-black/30 z-[9998]" @click="isSidebarOpen = false" />
      <!-- 侧边栏 -->
      <div v-show="isSidebarOpen" class="flex-shrink-0 z-[9999]">
        <Sidebar
          :is-open="isSidebarOpen"
          :active-id="currentView"
          @navigate="handleSidebarNavigate"
          @close="isSidebarOpen = false"
        />
      </div>
    </template>

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
            class="w-10 h-10 min-w-[44px] min-h-[44px] flex items-center justify-center rounded text-terminal-dim hover:text-terminal-accent transition-colors text-lg"
            @click="isSidebarOpen = !isSidebarOpen"
            title="切换侧边栏"
          >
            ☰
          </button>
          <span class="text-terminal-accent font-bold text-base">📊 AlphaTerminal</span>
        </div>
        <div class="flex items-center gap-3 text-xs text-terminal-dim flex-nowrap overflow-x-auto scrollbar-hide max-w-full">
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
            class="flex items-center gap-1 px-1.5 py-0 rounded border border-purple-500/30 bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 hover:border-purple-500/50 transition-all text-xs h-5 leading-none relative"
            @click="toggleCopilot"
          >
            <span v-if="isCopilotOpen">⏭ 收起</span>
            <span v-else>🤖 AI</span>
            <!-- 未读消息指示器 -->
            <span v-if="!isCopilotOpen && copilotUnreadCount > 0" class="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full text-[9px] text-white flex items-center justify-center animate-pulse">
              {{ copilotUnreadCount > 9 ? '9+' : copilotUnreadCount }}
            </span>
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

        <!-- F2修复: 加载错误提示（增强：显示重试次数 + apiErrorState） -->
        <div v-if="loadError && !isInitialLoading"
             class="mb-2 px-3 py-2 rounded border border-bullish/40 bg-bullish/15 text-bullish text-xs flex items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <span>⚠️ {{ loadError }}</span>
            <span v-if="apiErrorState.failedCount > 1" class="text-bullish/70 text-[10px]">
              （第 {{ apiErrorState.failedCount }} 次失败，自动重试中...）
            </span>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <button @click="Promise.all([fetchHighFreq(), fetchMedFreq(), fetchLowFreq()])" class="px-2 py-0.5 bg-bullish/30 rounded text-bullish-light hover:bg-bullish/40 text-[10px]">立即重试</button>
            <button v-if="apiErrorState.isDegraded" @click="apiErrorState.isDegraded = false; loadError = null" class="px-2 py-0.5 bg-terminal-panel rounded text-theme-secondary hover:text-theme-primary text-[10px]">忽略</button>
          </div>
        </div>

        <!-- 股票行情（默认） -->
        <DashboardGrid
          v-if="currentView === 'stock'"
          :market-data="marketOverview"
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
        <!-- 基金分析 -->
        <FundDashboard v-else-if="currentView === 'fund'" />
        <!-- 期货行情 -->
        <FuturesDashboard v-else-if="currentView === 'futures'" @open-futures="openFuturesFullscreen" />
        <!-- 回测实验室 -->
        <BacktestDashboard v-else-if="currentView === 'backtest'" />
        <!-- 系统管理 -->
        <AdminDashboard v-else-if="currentView === 'admin'" />
        <!-- 宏观经济 -->
        <MacroDashboard v-else-if="currentView === 'macro'" />
        <!-- 期权分析 -->
        <OptionsAnalysis v-else-if="currentView === 'options'" />
        <!-- F9 深度资料 -->
        <StockDetail v-else-if="currentView === 'f9'" :symbol="f9Symbol" />
      </div>
    </main>

    <!-- ━━━ 快捷键帮助面板 ━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <KeyboardShortcutsHelp
      :visible="helpVisible"
      @close="helpVisible = false"
    />

    <!-- ━━━ 全局命令面板 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <CommandPalette
      :visible="commandPaletteOpen"
      @close="commandPaletteOpen = false"
      @select-stock="handlePaletteSelectStock"
      @change-view="handlePaletteChangeView"
      @open-f9="handlePaletteOpenF9"
    />

    <!-- ━━━ Copilot 抽屉 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <!-- 桌面端：右侧 sidebar | 移动端：底部抽屉 (bottom sheet) -->
    <aside
      v-show="isCopilotOpen"
      :class="isMobile 
        ? 'fixed bottom-0 left-0 right-0 z-[9998] max-h-[70vh] rounded-t-2xl border-t-2 border-theme shadow-[0_-4px_20px_rgba(0,0,0,0.3)] bg-terminal-panel pb-safe' 
        : 'flex-shrink-0 flex flex-col bg-terminal-panel border-l border-theme-secondary transition-all duration-300 ease-in-out overflow-hidden'"
      :style="isMobile ? { width: '100%', maxWidth: '100%' } : { width: '340px', maxWidth: '340px' }"
    >
      <!-- 移动端拖拽指示器 -->
      <div v-if="isMobile" class="w-full flex justify-center pt-2 pb-1 cursor-pointer" @click="toggleCopilot">
        <div class="w-12 h-1 rounded-full bg-terminal-dim/30"></div>
      </div>
      <CopilotSidebar
        :market-overview="marketOverview"
        :china-all-data="chinaAllData"
        :sectors-data="sectorsData"
        :derivatives-data="derivativesData"
        :watch-list="watchList"
        @open-chart="openFullscreenKline"
        @show-north-flow="showNorthFlow"
        @show-limit-up="showLimitUp"
        @show-limit-down="showLimitDown"
        @show-unusual="showUnusual"
        @show-watchlist="currentView = 'stock'"
      />
    </aside>

    <!-- ━━━ 移动端底部导航栏 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <MobileBottomNav
      v-if="isMobile"
      :active-id="currentView"
      @navigate="handleMobileNav"
    />

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, onErrorCaptured, watch, computed, defineAsyncComponent } from 'vue'
import { useDocumentVisibility, useIntervalFn, useBreakpoints, breakpointsTailwind } from '@vueuse/core'
import LoadingFallback from './components/LoadingFallback.vue'

// ── 始终需要的组件（同步加载）──────────────────────────────────────
import Sidebar       from './components/Sidebar.vue'
import DashboardGrid from './components/DashboardGrid.vue'
import SimpleQuotePanel from './components/SimpleQuotePanel.vue'
import KeyboardShortcutsHelp from './components/KeyboardShortcutsHelp.vue'
import CommandPalette from './components/CommandPalette.vue'
import ToastContainer from './components/ToastContainer.vue'
import MobileBottomNav from './components/MobileBottomNav.vue'

// ── 按需加载的组件（延迟加载，减小首屏包体积）────────────────────
const BondDashboard   = defineAsyncComponent(() => import('./components/BondDashboard.vue'))
const FuturesDashboard = defineAsyncComponent(() => import('./components/FuturesDashboard.vue'))
const PortfolioDashboard = defineAsyncComponent(() => import('./components/PortfolioDashboard.vue'))
const FundDashboard   = defineAsyncComponent(() => import('./components/FundDashboard.vue'))
const BacktestDashboard = defineAsyncComponent(() => import('./components/BacktestDashboard.vue'))
const FuturesPanel    = defineAsyncComponent(() => import('./components/FuturesPanel.vue'))
const CopilotSidebar  = defineAsyncComponent(() => import('./components/CopilotSidebar.vue'))
const AdminDashboard  = defineAsyncComponent(() => import('./components/AdminDashboard.vue'))
const FullscreenKline = defineAsyncComponent(() => import('./components/FullscreenKline.vue'))
const MacroDashboard  = defineAsyncComponent(() => import('./components/MacroDashboard.vue'))
const OptionsAnalysis = defineAsyncComponent(() => import('./components/OptionsAnalysis.vue'))
const StockDetail     = defineAsyncComponent(() => import('./components/StockDetail.vue'))

import { useUiStore } from './composables/useUiStore.js'
import { useMarketStore } from './stores/market.js'
import { useTheme } from './composables/useTheme.js'
import { useKeyboardShortcuts } from './composables/useKeyboardShortcuts.js'
import { useToast } from './composables/useToast.js'
import { fetchApiBatch, apiFetch, apiErrorState } from './utils/api.js'
import { logger } from './utils/logger.js'

const { ui, openKlineFullscreen } = useUiStore()
const { currentSymbol } = useMarketStore()
const { success: toastSuccess, info: toastInfo } = useToast()

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
const isSidebarOpen = ref(false)   // 侧边栏默认收起（桌面端+移动端）
const currentView   = ref('stock') // 默认视图：stock / bond / futures
const futuresFullscreen = ref(false)
const futuresFullscreenSymbol = ref('IF0')
const f9Symbol = ref('') // F9深度资料当前股票代码

function handleSidebarNavigate(viewId) {
  currentView.value = viewId
  toastInfo('视图切换', `已切换到 ${getViewName(viewId)}`)
}

function getViewName(viewId) {
  const names = {
    stock: '股票行情', bond: '债券行情', futures: '期货行情',
    fund: '基金分析', portfolio: '投资组合', macro: '宏观经济',
    backtest: '回测实验室', admin: '系统管理', f9: '深度资料'
  }
  return names[viewId] || viewId
}

function handleMobileNav(viewId) {
  if (viewId === 'copilot') {
    toggleCopilot()
  } else {
    currentView.value = viewId
    toastInfo('视图切换', `已切换到 ${getViewName(viewId)}`)
  }
}

function openFuturesFullscreen({ symbol }) {
  futuresFullscreenSymbol.value = symbol || 'IF0'
  futuresFullscreen.value = true
  ui.klineFullscreen = true
}

// 键盘快捷键系统
const { helpVisible, searchVisible } = useKeyboardShortcuts({
  onViewChange: (viewId) => { 
    currentView.value = viewId
    toastInfo('视图切换', `已切换到 ${getViewName(viewId)}`)
  },
  onSearch: () => { 
    commandPaletteOpen.value = true 
  },
  onEscape: () => {
    if (commandPaletteOpen.value) {
      commandPaletteOpen.value = false
    } else if (ui.klineFullscreen) {
      ui.klineFullscreen = false
      futuresFullscreen.value = false
    } else if (isCopilotOpen.value) {
      isCopilotOpen.value = false
    } else if (isSidebarOpen.value) {
      isSidebarOpen.value = false
    }
  },
  onFullscreen: () => {
    // F11: 切换全屏
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen()
    } else {
      document.exitFullscreen()
    }
  },
  onRefresh: () => {
    // F5: 刷新数据
    fetchHighFreq()
    fetchMedFreq()
    toastSuccess('刷新', '正在刷新市场数据...')
  },
  onWatchlist: () => {
    // F6: 自选股
    currentView.value = 'stock'
    toastInfo('自选股', '已切换到自选股视图')
  },
  onSettings: () => {
    // Ctrl+,: 系统设置
    currentView.value = 'admin'
    toastInfo('设置', '已打开系统设置')
  },
  onToggleTheme: () => {
    // Ctrl+Shift+D: 切换主题
    const newTheme = isDark.value ? 'light' : 'dark'
    localStorage.setItem('theme', newTheme)
    location.reload()
  }
})

const commandPaletteOpen = ref(false) // 全局命令面板
const isCopilotOpen = ref(false) // 默认收起 AI 助理
const copilotUnreadCount = ref(0) // Copilot 未读消息数
const isLocked = ref(true)     // 网格默认锁定
const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('md')  // < 768px is mobile

// 全屏 K 线状态（提升到 App 根级别，脱离 stacking context 约束）
function openFullscreenKline({ symbol, name }) {
  openKlineFullscreen({ symbol, name })
}

function toggleLock() {
  isLocked.value = !isLocked.value
}

function toggleCopilot() {
  isCopilotOpen.value = !isCopilotOpen.value
  if (isCopilotOpen.value) {
    copilotUnreadCount.value = 0 // 打开时清零未读
  }
}

// 命令面板事件处理
function handlePaletteSelectStock({ symbol, name }) {
  openFullscreenKline({ symbol, name })
}

function handlePaletteChangeView(viewId) {
  currentView.value = viewId
}

function handlePaletteOpenF9() {
  const sym = currentSymbol.value
  if (sym) {
    f9Symbol.value = sym
    currentView.value = 'f9'
    toastInfo('深度资料', `查看 ${sym} 的深度资料`)
  }
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

// fetchMarketData 已拆分为三个错峰梯队：fetchHighFreq(10s) / fetchMedFreq(60s) / fetchLowFreq(300s)
// ── 高频组：大盘实时行情（10秒）──────────────────────────────────────────
async function fetchHighFreq() {
  try {
    const d = await apiFetch('/api/v1/market/overview')
    marketOverview.value = d?.wind || d || null
    loadError.value = null
  } catch { /* apiErrorState 已记录 */ }
}

// ── 中频组：板块/期货/情绪（60秒）───────────────────────────────────────
async function fetchMedFreq() {
  try {
    const d = await fetchApiBatch([
      { url: '/api/v1/market/sectors', key: 'sectors', default: [] },
      { url: '/api/v1/market/china_all', key: 'china_all', default: [] },
      { url: '/api/v1/market/derivatives', key: 'derivatives', default: [] },
    ])
    sectorsData.value     = d.sectors?.sectors || d.sectors?.data?.sectors || d.sectors || []
    chinaAllData.value    = d.china_all?.china_all || d.china_all?.data?.china_all || d.china_all || []
    derivativesData.value = d.derivatives?.derivatives || d.derivatives?.data?.derivatives || d.derivatives || []
  } catch { /* apiErrorState 已记录 */ }
}

// low-freq data (macro/rates/global/news) 已下放到各组件内部自持

// ── 计数：两个梯队均完成首次加载后关闭骨架屏 ──────────────────────────
let _loadedCount = 0
let _hasAnyError = false
let _骨架屏超时 = setTimeout(() => {
  isInitialLoading.value = false
  console.warn('[App] 骨架屏超时强制关闭（3秒）')
}, 3000)

function _checkInitDone(hasError = false) {
  _loadedCount++
  _hasAnyError = _hasAnyError || hasError
  if (_loadedCount >= 2) {
    clearTimeout(_骨架屏超时)
    isInitialLoading.value = false
    _loadedCount = 0
    if (_hasAnyError) {
      loadError.value = '部分数据加载失败，请检查网络连接'
    }
  }
}

// ── 错峰轮询（useIntervalFn 自动处理组件卸载清理）───────────────────────
const { pause: pauseHigh, resume: resumeHigh } = useIntervalFn(fetchHighFreq, 10_000, { immediate: false })
const { pause: pauseMed, resume: resumeMed } = useIntervalFn(fetchMedFreq, 60_000, { immediate: false })

// ── 页面可见性控制 ─────────────────────────────────────────────────────
const visibility = useDocumentVisibility()

watch(visibility, (v) => {
  if (v === 'visible') {
    resumeHigh(); resumeMed()
    fetchHighFreq()  // 可见时立即拉一次高频
  } else {
    pauseHigh(); pauseMed()
  }
})

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)

  // 首屏：两个梯队并发启动（浏览器自动调度，无 Stalled）
  fetchHighFreq().then(_checkInitDone)
  fetchMedFreq().then(_checkInitDone)

  // 启动错峰轮询（仅在页面可见时）
  if (visibility.value === 'visible') {
    resumeHigh(); resumeMed()
  }
})

onUnmounted(() => {
  clearTimeout(_骨架屏超时)
  clearInterval(clockTimer)
  pauseHigh(); pauseMed()
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
