<template>
  <!-- ━━━ 移动端：单列垂直流式布局 (< 768px) ━━━━━━━━━━━━━━━ -->
  <div v-if="isMobile" ref="mobileContainerRef" class="flex flex-col gap-2 px-1 overflow-y-auto min-w-0" style="height: 100dvh; padding-bottom: 80px; overscroll-behavior: contain;" role="main" aria-label="市场行情仪表盘">
    
    <!-- 下拉刷新指示器 -->
    <div class="pull-refresh-indicator" :style="pullIndicatorStyle">
      <div class="flex items-center justify-center gap-2 py-2 text-terminal-accent">
        <svg v-if="isRefreshing" class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span v-if="isRefreshing" class="text-sm">刷新中...</span>
        <span v-else-if="pullDistance > 0" class="text-sm">↓ 下拉刷新</span>
      </div>
    </div>

    <!-- 快捷导航胶囊 -->
    <div class="flex gap-2 overflow-x-auto pb-1 scrollbar-hide shrink-0" role="navigation" aria-label="快捷导航">
      <button v-for="anchor in mobileAnchors" :key="anchor.id"
        :href="`#${anchor.id}`"
        class="shrink-0 px-2 py-0 rounded-full text-xs border transition-colors h-4 flex items-center"
        :class="'bg-terminal-accent/10 border-terminal-accent/30 text-terminal-accent hover:bg-terminal-accent/20'"
        @click.prevent="scrollToMobileSection(anchor.id)"
        :aria-label="`跳转到${anchor.label}区域`"
        type="button"
      >
        {{ anchor.label }}
      </button>
    </div>

    <!-- K线图：自适应高度，内部图表自适应 -->
    <div id="section-chart" class="terminal-panel p-2 rounded-lg shadow border border-theme/10 shrink-0" style="min-height: 200px;">
      <div class="flex items-center justify-between mb-2 shrink-0">
        <span class="text-terminal-accent font-bold text-sm">📈 指标图表</span>
      </div>
      <IndexLineChart :key="selectedIndex" :symbol="selectedIndex" :name="currentIndexName" :period="selectedPeriod" class="w-full" :style="{ height: '260px' }" />
    </div>

    <!-- 市场风向标：4指数 + 4宏观 -->
    <div id="section-wind" class="terminal-panel p-2 rounded-lg shadow border border-theme/10 shrink-0">
      <div class="text-terminal-accent font-bold text-sm mb-1">🌐 市场风向标</div>
      <!-- Error display with aria-live for screen readers -->
      <div v-if="macroError" 
           role="alert" 
           aria-live="polite" 
           aria-atomic="true"
           class="text-[10px] text-red-400 mb-1 px-1 py-0.5 bg-red-400/10 rounded flex items-center justify-between">
        <span>⚠️ {{ macroError }}</span>
        <button @click="retryMacroFetch" :disabled="macroLoading" class="px-1.5 py-0.5 bg-red-400/20 rounded">
          <span v-if="macroLoading" class="inline-block animate-spin">⟳</span>
          <span v-else>重试</span>
        </button>
      </div>
      <!-- Loading skeleton for wind vane (8 cards in 2 columns) -->
      <div v-if="!windItems.length && !macroError"
           role="status"
           :aria-busy="!windItems.length && !macroError"
           aria-label="正在加载市场风向标数据"
           class="grid grid-cols-2 gap-1 p-0.5">
        <!-- Visually hidden loading text for screen readers -->
        <span class="sr-only">正在加载市场风向标数据...</span>
        <div v-for="i in 8" :key="`skeleton-${i}`"
             class="bg-theme-secondary/50 rounded p-2 flex flex-col items-center justify-center animate-pulse">
          <!-- Category badge skeleton -->
          <div class="flex items-center gap-0.5 mb-0.5">
            <div class="w-4 h-3 bg-theme-tertiary/30 rounded"></div>
            <div class="w-12 h-3 bg-theme-tertiary/30 rounded"></div>
          </div>
          <!-- Price skeleton -->
          <div class="w-16 h-4 bg-theme-tertiary/30 rounded mb-0.5"></div>
          <!-- Change % skeleton -->
          <div class="w-10 h-3 bg-theme-tertiary/30 rounded"></div>
        </div>
      </div>
      <!-- 2-column grid -->
      <div v-else ref="mobileWindContainerRef" class="grid grid-cols-2 gap-1" role="grid" aria-label="市场风向标">
        <div v-for="(item, index) in windItems" :key="item.symbol"
             data-wind-card
             :tabindex="index === mobileRovingFocus.currentIndex.value ? '0' : '-1'"
             role="gridcell"
             :aria-label="item.name"
             class="bg-theme-secondary/50 rounded p-2 flex flex-col cursor-pointer hover:bg-theme-tertiary/50 transition-colors focus-visible:ring-2 focus-visible:ring-terminal-accent focus-visible:ring-offset-1 focus-visible:ring-offset-terminal-bg"
             @click="handleWindClick(item); mobileRovingFocus.handleCardClick(index)"
             @keydown.enter="handleWindClick(item)"
             @keydown.space.prevent="handleWindClick(item)">
          <!-- Category badge -->
          <div class="flex items-center gap-0.5 mb-0.5">
            <span class="text-[8px] px-1 rounded border"
                  :class="item.category === 'macro' ? 'border-yellow-500/40 text-yellow-400' : 'border-blue-500/40 text-blue-400'"
                  :title="item.category === 'macro' ? '宏观大宗商品' : '股票指数'">
              {{ item.category === 'macro' ? '宏观' : '指数' }}
            </span>
            <span class="text-[10px] text-theme-primary truncate" :title="item.name">{{ item.name }}</span>
          </div>
          <!-- Price -->
          <div class="text-[11px] font-mono text-theme-primary">
            {{ formatWindPrice(item) }}
          </div>
          <!-- Change % -->
          <div class="text-[11px] font-mono font-bold"
               :class="(item.change_pct || 0) >= 0 ? 'text-bullish' : 'text-bearish'">
            {{ formatWindChangePct(item.change_pct) }}
          </div>
        </div>
      </div>
    </div>

    <!-- A股监测：自适应高度，内部滚动 -->
    <div id="section-screener" class="terminal-panel p-2 rounded-lg shadow border border-theme/10 shrink-0" style="min-height: 280px; max-height: 50vh; overflow-y: auto;">
      <div class="text-terminal-accent font-bold text-sm mb-1 shrink-0">📊 A股监测</div>
      <div class="w-full overflow-y-auto" style="height: calc(100% - 24px);">
        <StockScreener :data="globalItems" @symbol-click="handleScreenerClick" />
      </div>
    </div>

    <!-- 市场情绪 -->
    <div id="section-sentiment" class="terminal-panel p-2 rounded-lg shadow border border-theme/10 shrink-0" style="min-height: 160px;">
      <div class="text-terminal-accent font-bold text-sm mb-1 shrink-0">🌡️ A股市场情绪</div>
      <SentimentGauge :market-data="{ indices: indices }" :macro-data="macroData" @symbol-click="handleWindClick" class="w-full" />
    </div>

    <!-- 板块热度：自适应高度，内部滚动 -->
    <div id="section-sectors" class="terminal-panel p-2 rounded-lg shadow border border-theme/10 shrink-0" style="min-height: 240px; max-height: 45vh; overflow-y: auto;">
      <HotSectors :data="sectors" class="w-full" />
    </div>

    <!-- 新闻快讯：手机版自然高度不限制，桌面版 GridStack 控制 -->
    <div id="section-news" class="terminal-panel p-2 rounded-lg shadow border border-theme/10 shrink-0">
      <NewsFeed class="w-full" />
    </div>
  </div>

  <!-- ━━━ 桌面端：GridStack 网格布局 (≥ 768px) ━━━━━━━━━━━━ -->
  <div v-else class="grid-stack" ref="gridRef" role="main" aria-label="市场行情仪表盘">

    <!-- ━━━ Widget 1：A股K线（分时/日/周/月 + MACD/BOLL预留）━━━━━━━━━━ -->
    <!-- K线主图：左侧 8列，高度6单位 -->
    <div class="grid-stack-item"
         data-widget-id="chart"
         gs-x="0" gs-y="0" gs-w="8" gs-h="6" gs-min-w="4" gs-min-h="4"
         role="region"
         aria-label="指标图表面板">
      <WidgetErrorBoundary widget-name="IndexLineChart">
        <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
          <!-- 标题行 -->
          <div class="flex items-center justify-between mb-1 shrink-0">
            <span class="text-terminal-accent font-bold text-sm">📈 指标图表</span>
            <!-- 全屏按钮：独立一行，位于右上角 -->
            <button
              class="px-1.5 py-0 text-[10px] rounded border border-theme/40 text-theme-muted hover:text-terminal-accent hover:border-terminal-accent/50 transition-colors"
              @click="handleFullscreenClick()"
              aria-label="全屏显示图表"
              type="button"
            >全屏</button>
          </div>
          <!-- 指数切换行 -->
          <div class="flex items-center gap-1 mb-1 shrink-0" role="group" aria-label="指数选择">
            <button v-for="idx in indexOptions" :key="idx.symbol"
                    class="px-2 py-0.5 text-[10px] rounded border transition"
                    :class="selectedIndex === idx.symbol
                      ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent'
                      : 'bg-terminal-bg border-theme text-theme-tertiary hover:border-gray-500'"
                    @click="switchIndex(idx)"
                    :aria-pressed="selectedIndex === idx.symbol"
                    :aria-label="`切换到${idx.name}`"
                    type="button"
            >
              {{ idx.name }}
            </button>
          </div>
          <!-- Period selector -->
          <div class="flex items-center gap-1 mb-2 shrink-0" role="group" aria-label="周期选择">
            <button v-for="p in periods" :key="p.key"
                    class="px-2 py-0.5 text-[10px] rounded border transition"
                    :class="selectedPeriod === p.key
                      ? 'bg-[var(--color-info-bg)] border-blue-500/50 text-[var(--color-info)]'
                      : 'bg-terminal-bg border-theme text-theme-tertiary hover:border-gray-500'"
                    @click="switchPeriod(p.key)"
                    :aria-pressed="selectedPeriod === p.key"
                    :aria-label="`切换到${p.label}`"
                    type="button"
            >
              {{ p.label }}
            </button>
            <!-- Indicator toggles -->
            <span class="ml-2 text-theme-tertiary text-[9px]" aria-hidden="true">指标:</span>
            <button v-for="ind in indicators" :key="ind.key"
                    class="px-1.5 py-0.5 text-[9px] rounded border transition"
                    :class="activeIndicators.includes(ind.key)
                      ? 'bg-[var(--color-primary-bg)] border-purple-500/50 text-[var(--color-primary)]'
                      : 'bg-terminal-bg border-theme text-theme-tertiary hover:border-gray-500'"
                    @click="toggleIndicator(ind.key)"
                    :aria-pressed="activeIndicators.includes(ind.key)"
                    :aria-label="`${activeIndicators.includes(ind.key) ? '隐藏' : '显示'}${ind.label}指标`"
                    type="button"
            >
              {{ ind.label }}
            </button>
          </div>
          <div class="flex-1 min-h-0">
            <!-- IndexLineChart 内部已显示名称，这里不再重复显示 -->
            <IndexLineChart
              :key="`${selectedIndex}-${selectedPeriod}`"
              :symbol="selectedIndex"
              :name="currentIndexName"
              :color="currentIndexOption.color"
              :url="`/api/v1/market/history/${selectedIndex}?period=${selectedPeriod}`"
              :indicators="activeIndicators"
            />
          </div>
        </div>
      </WidgetErrorBoundary>
    </div>

    <!-- ━━━ Widget 2：市场情绪直方图（K线正下方，左侧8列）━━━━━━━━━━━━━ -->
    <!-- 情绪面板扩展至 10 单位高度（800px），彻底消除滚动条 -->
    <div class="grid-stack-item"
         data-widget-id="sentiment"
         gs-x="0" gs-y="6" gs-w="8" gs-h="10" gs-min-w="4" gs-min-h="8"
         role="region"
         aria-label="市场情绪面板">
      <WidgetErrorBoundary widget-name="SentimentGauge">
        <div class="grid-stack-item-content terminal-panel p-3">
          <div class="flex items-center justify-between mb-2 shrink-0">
            <span class="text-terminal-accent font-bold text-sm">🌡️ A股市场情绪</span>
            <FreshnessIndicator :timestamp="timestamp" />
          </div>
          <SentimentGauge :market-data="marketData" :macro-data="macroData" @symbol-click="handleWindClick" />
        </div>
      </WidgetErrorBoundary>
    </div>

    <!-- ━━━ Widget 3：快讯新闻（情绪图下方，16起）━━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         data-widget-id="news"
         gs-x="0" gs-y="16" gs-w="8" gs-h="6" gs-min-w="4" gs-min-h="4"
         role="region"
         aria-label="新闻快讯面板">
      <WidgetErrorBoundary widget-name="NewsFeed">
        <div class="grid-stack-item-content terminal-panel p-3">
          <NewsFeed />
        </div>
      </WidgetErrorBoundary>
    </div>

    <!-- ━━━ Widget 4：风向标（右上，右侧4列）━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         data-widget-id="wind"
         gs-x="8" gs-y="0" gs-w="4" gs-h="6" gs-min-w="3" gs-min-h="3"
         role="region"
         aria-label="市场风向标面板">
      <div class="grid-stack-item-content terminal-panel p-2">
        <!-- Phase 5: 8个风向标（4指数 + 4宏观）两列卡片网格（密度升级：padding 20%） -->
        <div class="text-[10px] text-theme-tertiary mb-1 flex items-center justify-between">
          <span>🌐 市场风向标</span>
          <FreshnessIndicator :timestamp="timestamp" />
        </div>
        <!-- Error display with retry button and aria-live for screen readers -->
        <div v-if="macroError" 
             role="alert" 
             aria-live="polite" 
             aria-atomic="true"
             class="text-[10px] text-red-400 mb-1 px-1 py-0.5 bg-red-400/10 rounded flex items-center justify-between gap-2">
          <span>⚠️ {{ macroError }}</span>
          <button 
            @click="retryMacroFetch" 
            :disabled="macroLoading"
            class="px-1.5 py-0.5 bg-red-400/20 rounded hover:bg-red-400/30 transition-colors disabled:opacity-50"
            type="button"
          >
            <span v-if="macroLoading" class="inline-block animate-spin">⟳</span>
            <span v-else>重试</span>
          </button>
        </div>
        <!-- Loading skeleton for wind vane (8 cards in 2 columns) -->
        <div v-if="!windItems.length && !macroError"
             role="status"
             :aria-busy="!windItems.length && !macroError"
             aria-label="正在加载市场风向标数据"
             class="grid grid-cols-2 gap-1 p-0.5">
          <!-- Visually hidden loading text for screen readers -->
          <span class="sr-only">正在加载市场风向标数据...</span>
          <div v-for="i in 8" :key="`skeleton-${i}`"
               class="bg-theme-secondary/50 rounded p-1.5 flex flex-col items-center justify-center animate-pulse">
            <!-- Category badge skeleton -->
            <div class="flex items-center gap-0.5 mb-0.5">
              <div class="w-4 h-3 bg-theme-tertiary/30 rounded"></div>
              <div class="w-12 h-3 bg-theme-tertiary/30 rounded"></div>
            </div>
            <!-- Price skeleton -->
            <div class="w-16 h-4 bg-theme-tertiary/30 rounded mb-0.5"></div>
            <!-- Change % skeleton -->
            <div class="w-10 h-3 bg-theme-tertiary/30 rounded"></div>
          </div>
        </div>
        <!-- Actual wind vane grid -->
        <div v-else ref="desktopWindContainerRef" class="grid grid-cols-2 gap-1 p-0.5" role="grid" aria-label="市场风向标">
          <div
            v-for="(item, index) in windItems" :key="item.symbol"
            data-wind-card
            :tabindex="index === desktopRovingFocus.currentIndex.value ? '0' : '-1'"
            role="gridcell"
            :aria-label="item.name"
            class="bg-theme-secondary/50 rounded p-1.5 flex flex-col items-center justify-center cursor-pointer hover:bg-theme-tertiary/50 transition-colors min-w-0 overflow-hidden focus-visible:ring-2 focus-visible:ring-terminal-accent focus-visible:ring-offset-1 focus-visible:ring-offset-terminal-bg"
            @click="handleWindClick(item); desktopRovingFocus.handleCardClick(index)"
            @keydown.enter="handleWindClick(item)"
            @keydown.space.prevent="handleWindClick(item)"
          >
<!-- 标的名称（分类标签） -->
            <div class="flex items-center gap-0.5 mb-0.5">
              <span
                class="text-[7px] px-1 rounded border cursor-help"
                :class="item.category === 'macro' ? 'border-yellow-500/40 text-yellow-400' : 'border-agent-blue/40 text-agent-blue'"
                :title="item.category === 'macro' ? '宏观大宗商品' : '股票指数'"
              >{{ item.category === 'macro' ? '宏观' : '指数' }}</span>
              <span class="text-[9px] text-gray-300 truncate max-w-[60px]" :title="item.name">{{ item.name }}</span>
            </div>
            <!-- 最新价（右对齐） -->
            <div class="text-[10px] font-mono text-gray-300 text-right w-full tabular-nums">
              {{ formatWindPrice(item) }}
            </div>
            <!-- 涨跌幅（右对齐） -->
            <div
              class="text-[10px] font-mono font-bold text-right w-full tabular-nums"
              :class="(item.change_pct || 0) >= 0 ? 'text-market-up' : 'text-market-down'"
            >
              {{ formatWindChangePct(item.change_pct) }}
            </div>
            <!-- Timestamp for macro items -->
            <div v-if="item.category === 'macro' && item.status"
                 class="text-[8px] text-theme-tertiary text-right w-full mt-0.5"
                 :title="`数据时间: ${item.status}`">
              {{ item.status }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ━━━ Widget 5：资金流向（独立，右侧4列，6起）━━━━━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         data-widget-id="fundflow"
         gs-x="8" gs-y="6" gs-w="4" gs-h="5" gs-min-w="3" gs-min-h="4"
         role="region"
         aria-label="资金流向面板">
      <WidgetErrorBoundary widget-name="FundFlowPanel">
        <div class="grid-stack-item-content terminal-panel p-2">
          <FundFlowPanel />
        </div>
      </WidgetErrorBoundary>
    </div>

    <!-- ━━━ Widget 5.1：行业风口（独立，右侧4列，11起）━━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         data-widget-id="sectors"
         gs-x="8" gs-y="11" gs-w="4" gs-h="5" gs-min-w="3" gs-min-h="4"
         role="region"
         aria-label="行业板块面板">
      <WidgetErrorBoundary widget-name="HotSectors">
        <div class="grid-stack-item-content terminal-panel p-2">
          <HotSectors @sector-click="handleSectorClick" />
        </div>
      </WidgetErrorBoundary>
    </div>

    <!-- ━━━ Widget 6：国内市场指数（右侧4列，16起，填补Y=16空挡）━━━━━━━━ -->
    <div class="grid-stack-item"
         data-widget-id="china"
         gs-x="8" gs-y="16" gs-w="4" gs-h="5" gs-min-w="3" gs-min-h="3"
         role="region"
         aria-label="国内指数面板">
      <div class="grid-stack-item-content terminal-panel p-4 flex flex-col">
        <div class="flex items-center justify-between mb-2 shrink-0">
          <span class="text-terminal-accent font-bold text-sm">🇨🇳 国内指数</span>
          <div class="flex items-center gap-2">
            <FreshnessIndicator :timestamp="timestamp" />
            <span class="text-theme-tertiary text-[10px]">{{ tsDisplay }}</span>
          </div>
        </div>
        <div class="flex-1 overflow-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="text-theme-tertiary border-b border-theme">
                <th class="text-left py-1">指数</th>
                <th class="text-right py-1">最新价</th>
                <th class="text-right py-1">涨跌幅</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in chinaAllItems" :key="item.symbol"
                  class="border-b border-theme-secondary hover:bg-white/5 cursor-pointer transition-colors"
                  @click="handleChinaClick(item)">
                <td class="py-1 text-theme-primary text-[11px]">{{ item.name }}</td>
                <td class="py-1 text-right font-mono text-[11px]">{{ formatPrice(item.price) }}</td>
                <td class="py-1 text-right font-mono text-[11px]"
                    :class="(item.change_pct || 0) >= 0 ? 'text-bullish' : 'text-bearish'">
                  {{ formatChangePct(item.change_pct) }}
                </td>
              </tr>
              <tr v-if="!chinaAllItems.length">
                <td colspan="3" class="py-4 text-center text-theme-tertiary text-xs">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ━━━ Widget 7：全市场个股透视看板（底部全宽12列，21起）━━━━━━━━━━━ -->
    <div class="grid-stack-item"
         data-widget-id="screener"
         gs-x="0" gs-y="21" gs-w="12" gs-h="8" gs-min-w="6" gs-min-h="5"
         role="region"
         aria-label="个股监测面板">
      <WidgetErrorBoundary widget-name="StockScreener">
        <div class="grid-stack-item-content terminal-panel p-3">
          <StockScreener @symbol-click="handleScreenerClick" />
        </div>
      </WidgetErrorBoundary>
    </div>

    </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch, onErrorCaptured } from 'vue'
import { useBreakpoints, breakpointsTailwind, useDebounceFn } from '@vueuse/core'
import { apiFetch } from '../utils/api.js'
import { useMarketStore } from '../stores/market.js'
import { formatPrice, formatChangePct } from '../utils/formatters.js'
import { usePullToRefresh } from '../composables/usePullToRefresh.js'
import { useSmartPolling } from '../composables/useSmartPolling.js'
import { toast } from '../composables/useToast.js'
import { useRovingFocus } from '../composables/useRovingFocus.js'
import IndexLineChart    from './IndexLineChart.vue'
import NewsFeed          from './NewsFeed.vue'
import SentimentGauge    from './SentimentGauge.vue'
import HotSectors        from './HotSectors.vue'
import FundFlowPanel     from './FundFlowPanel.vue'
import StockScreener     from './StockScreener.vue'
import WidgetErrorBoundary from './WidgetErrorBoundary.vue'
import FreshnessIndicator from './FreshnessIndicator.vue'

// ── Layout Persistence Constants ─────────────────────────────────────
const LAYOUT_STORAGE_KEY = 'alphaterminal_grid_layout'
const LAYOUT_VERSION = 1  // Increment when default layout changes

// Default widget positions (must match template gs-* attributes)
const DEFAULT_LAYOUT = [
  { id: 'chart',      x: 0,  y: 0,  w: 8,  h: 6,  minW: 4, minH: 4 },
  { id: 'sentiment',  x: 0,  y: 6,  w: 8,  h: 10, minW: 4, minH: 8 },
  { id: 'news',       x: 0,  y: 16, w: 8,  h: 6,  minW: 4, minH: 4 },
  { id: 'wind',       x: 8,  y: 0,  w: 4,  h: 6,  minW: 3, minH: 3 },
  { id: 'fundflow',   x: 8,  y: 6,  w: 4,  h: 5,  minW: 3, minH: 4 },
  { id: 'sectors',    x: 8,  y: 11, w: 4,  h: 5,  minW: 3, minH: 4 },
  { id: 'china',      x: 8,  y: 16, w: 4,  h: 5,  minW: 3, minH: 3 },
  { id: 'screener',   x: 0,  y: 21, w: 12, h: 8,  minW: 6, minH: 5 },
]

const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('md')  // < 768px is mobile

const { currentSymbol, currentSymbolName, currentColor, setSymbol, normalizeSymbol, indices } = useMarketStore()
const currentIndexName = ref('上证指数')

async function handlePullRefresh() {
  await fetchLowFreq()
}

const {
  pullDistance,
  isRefreshing,
  pullIndicatorStyle,
  containerRef: mobileContainerRef,
} = usePullToRefresh(handlePullRefresh)

const props = defineProps({
  marketData:     { type: Object, default: null },
  chinaAllData:   { type: Array,  default: () => [] },
  sectorsData:    { type: Array,  default: () => [] },
  derivativesData:{ type: Array,  default: () => [] },
  isLocked:       { type: Boolean, default: true },
})

const emit = defineEmits(['toggle-lock', 'open-fullscreen', 'reset-layout'])

const gridRef          = ref(null)
const selectedIndex    = ref(currentSymbol.value)
const selectedPeriod   = ref('daily')
const activeIndicators = ref([])
const dashboardError   = ref(null)

const mobileWindContainerRef = ref(null)
const desktopWindContainerRef = ref(null)

// ── Error Capture Safety Net ─────────────────────────────────────
onErrorCaptured((err, instance, info) => {
  console.error('[DashboardGrid] Uncaught error:', err)
  console.error('[DashboardGrid] Component:', instance?.$options?.name || 'unknown')
  console.error('[DashboardGrid] Info:', info)
  
  dashboardError.value = {
    message: err.message || String(err),
    component: instance?.$options?.name || 'unknown',
    info,
    timestamp: Date.now(),
  }
  
  // Report to monitoring if available
  if (typeof window !== 'undefined' && typeof window.reportError === 'function') {
    try {
      window.reportError(err)
    } catch (e) {
      console.error('[DashboardGrid] Failed to report error:', e)
    }
  }
  
  // Prevent propagation to App.vue
  return false
})

// ── Layout Persistence Functions ─────────────────────────────────────
function saveLayout() {
  if (!grid || typeof window === 'undefined') return
  
  const nodes = grid.getGridItems().map(el => {
    const node = el.gridstackNode
    return {
      id: el.dataset.widgetId || node.id,
      x: node.x,
      y: node.y,
      w: node.w,
      h: node.h,
    }
  })
  
  const layoutData = {
    version: LAYOUT_VERSION,
    timestamp: Date.now(),
    nodes,
  }
  
  try {
    localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(layoutData))
  } catch (e) {
    console.warn('[DashboardGrid] Failed to save layout:', e)
  }
}

// Debounced save to avoid excessive writes during drag
const debouncedSaveLayout = useDebounceFn(saveLayout, 500)

function loadLayout() {
  if (typeof window === 'undefined') return null
  
  try {
    const stored = localStorage.getItem(LAYOUT_STORAGE_KEY)
    if (!stored) return null
    
    const data = JSON.parse(stored)
    
    // Version check - reset if incompatible
    if (data.version !== LAYOUT_VERSION) {
      console.log('[DashboardGrid] Layout version mismatch, resetting to default')
      clearLayout()
      return null
    }
    
    return data.nodes
  } catch (e) {
    console.warn('[DashboardGrid] Failed to load layout:', e)
    return null
  }
}

function clearLayout() {
  if (typeof window === 'undefined') return
  try {
    localStorage.removeItem(LAYOUT_STORAGE_KEY)
  } catch (e) {
    console.warn('[DashboardGrid] Failed to clear layout:', e)
  }
}

function applyLayout(nodes) {
  if (!grid || !nodes || !nodes.length) return false
  
  let applied = false
  nodes.forEach(node => {
    const el = gridRef.value?.querySelector(`[data-widget-id="${node.id}"]`)
    if (el && el.gridstackNode) {
      grid.update(el, {
        x: node.x,
        y: node.y,
        w: node.w,
        h: node.h,
      })
      applied = true
    }
  })
  
  return applied
}

// Expose reset function for parent component
defineExpose({
  resetLayout: () => {
    clearLayout()
    if (grid) {
      // Re-apply default positions from template
      grid.getGridItems().forEach(el => {
        const widgetId = el.dataset.widgetId
        const defaultPos = DEFAULT_LAYOUT.find(d => d.id === widgetId)
        if (defaultPos) {
          grid.update(el, {
            x: defaultPos.x,
            y: defaultPos.y,
            w: defaultPos.w,
            h: defaultPos.h,
          })
        }
      })
    }
  }
})

// ── 列表点击联动 ─────────────────────────────────────────────────
// Comprehensive macro symbol mapping (Chinese/English variants → standard symbol)
const MACRO_SYMBOL_MAP = {
  // Gold variants
  '黄金': 'GOLD', '黄金(美元)': 'GOLD', '黄金(人民币)': 'GOLD',
  'XAU': 'GOLD', 'GLD': 'GOLD', 'GOLD': 'GOLD',
  'SGE黄金': 'GOLD', 'SGE黄金(人民币)': 'GOLD',
  'gold': 'GOLD', 'xau': 'GOLD', 'gld': 'GOLD',
  
  // WTI/Crude Oil variants
  'WTI原油': 'WTI', 'WTI': 'WTI', '原油': 'WTI',
  'NYMEX_WTI': 'WTI', 'CL': 'WTI', 'WTI原油(美元)': 'WTI',
  'wti': 'WTI', 'wtic': 'WTI',
  
  // VIX variants
  'VIX': 'VIX', '恐慌指数': 'VIX', '波动率指数': 'VIX',
  'vix': 'VIX',
  
  // USD/CNH variants
  'USD/CNH': 'CNHUSD', 'CNHUSD': 'CNHUSD', '离岸人民币': 'CNHUSD',
  '人民币': 'CNHUSD', 'usd/cnh': 'CNHUSD', 'cnhusd': 'CNHUSD',
  
  // DXY variants
  'DXY': 'DXY', '美元指数': 'DXY', 'dxy': 'DXY',
  
  // VHSI (Hang Seng Volatility) variants
  '恒指波幅': 'VHSI', 'VHSI': 'VHSI', 'VHKS': 'VHSI',
  'vhsi': 'VHSI',
  
  // Nikkei variants
  '日经225': 'N225', '日经': 'N225', 'N225': 'N225',
  
  // DJI/SPX/NDX
  'DJI': 'DJI', '道琼斯': 'DJI',
  'SPX': 'SPX', '标普500': 'SPX',
  'NDX': 'NDX', '纳斯达克100': 'NDX',
}

function normalizeMacroSymbol(name) {
  if (!name) return null
  
  // Direct match
  if (MACRO_SYMBOL_MAP[name]) return MACRO_SYMBOL_MAP[name]
  
  // Remove parentheses content and try again
  const cleaned = name.replace(/\([^)]*\)/g, '').trim()
  if (MACRO_SYMBOL_MAP[cleaned]) return MACRO_SYMBOL_MAP[cleaned]
  
  // Try lowercase
  const lower = cleaned.toLowerCase()
  if (MACRO_SYMBOL_MAP[lower]) return MACRO_SYMBOL_MAP[lower]
  
  // Log unmapped symbols for future updates
  console.warn(`[WindVane] Unmapped macro symbol: "${name}"`)
  return null
}

function handleWindClick(item) {
  let sym = item.symbol || item.key || ''
  
  // For macro items, use comprehensive mapping
  if (item.category === 'macro') {
    const mapped = normalizeMacroSymbol(item.name)
    if (mapped) {
      sym = mapped
    } else {
      // Fallback: show toast and return
      toast.warning('无法识别', `暂不支持 ${item.name} 的K线图`)
      return
    }
  } else {
    // For indices, use existing normalization
    if (!/^[A-Za-z]{2,6}$/.test(sym)) {
      const cleaned = sym.replace(/\([^)]*\)/g, '').trim()
      const lower = cleaned.toLowerCase()
      if (MACRO_SYMBOL_MAP[lower] || MACRO_SYMBOL_MAP[cleaned]) {
        sym = MACRO_SYMBOL_MAP[cleaned] || MACRO_SYMBOL_MAP[lower]
      } else {
        // Fallback: strip non-alphanumeric and normalize
        const stripped = cleaned.replace(/[^a-zA-Z0-9]/g, '').slice(0, 6)
        sym = MACRO_SYMBOL_MAP[stripped] || normalizeSymbol(stripped)
      }
    }
  }
  
  const norm = normalizeSymbol(sym)
  setSymbol(norm, item.name || sym, '#f87171')
  queueMicrotask(() => {
    selectedIndex.value = norm
    currentIndexName.value = item.name || norm
  })
}

function handleGlobalClick(item) {
  // globalItems 可能有 usIXIC / usNDX / hkHSI 等前缀
  const norm = normalizeSymbol(item.symbol || item.name || item.key || '')
  setSymbol(norm, item.name || norm, '#60a5fa')
  // 同步更新本地 selectedIndex
  queueMicrotask(() => {
    selectedIndex.value = norm
    currentIndexName.value = item.name || norm
  })
}

function handleChinaClick(item) {
  const norm = normalizeSymbol(item.symbol)
  setSymbol(norm, item.name, '#f87171')
  // 同步更新本地 selectedIndex
  queueMicrotask(() => {
    selectedIndex.value = norm
    currentIndexName.value = item.name || item.symbol
  })
}

function handleSectorClick(sec) {
  // 板块无独立K线，使用板块的领涨股代码替代
  const rawCode = sec.top_stock?.code || ''
  const topName = sec.top_stock?.name || ''

  // 统一用 normalizeSymbol 处理：自动添加 sh/sz 前缀（兼容纯数字码）
  // normalizeSymbol 规则：6/9/000开头→sh；其余(0/2/3)→sz
  const code = rawCode ? normalizeSymbol(rawCode) : 'sh000001'
  const displayName = topName ? `${sec.name}-${topName}` : sec.name
  setSymbol(code, displayName, '#fbbf24')
  queueMicrotask(() => {
    selectedIndex.value = code
    currentIndexName.value = displayName
  })
}

function handleScreenerClick({ symbol, name }) {
  const norm = normalizeSymbol(symbol)
  setSymbol(norm, name || symbol, '#00ff88')
  queueMicrotask(() => {
    selectedIndex.value = norm
    currentIndexName.value = name || symbol
  })
}

let grid = null
let _fetchController = null  // AbortController：组件卸载时取消 pending 请求

// ── 指数选项（K线切换）──────────────────────────────────────────
const indexOptions = [
  { symbol: '000001', name: '上证',   color: '#f87171' },
  { symbol: '000300', name: '沪深300', color: '#60a5fa' },
  { symbol: '399001', name: '深证',   color: '#fbbf24' },
  { symbol: '399006', name: '创业板',  color: '#a78bfa' },
]
// 注意：必须从本地 selectedIndex 查找，不能用 currentSymbol（全局面经 store）
// 否则切换 K 线组件指数时 name 不跟随 selectedIndex 更新
const currentIndexOption = computed(() => {
  const opt = indexOptions.find(o => o.symbol === selectedIndex.value) || indexOptions[0]
  return opt
})

const periods = [
  { key: 'minutely', label: '分时' },
  { key: 'daily',    label: '日K' },
  { key: 'weekly',   label: '周K' },
  { key: 'monthly',  label: '月K' },
]

const indicators = [
  { key: 'MACD',  label: 'MACD' },
  { key: 'BOLL',  label: 'BOLL' },
  { key: 'KDJ',  label: 'KDJ' },
  { key: 'RSI',  label: 'RSI' },
  { key: 'WR',   label: 'WR' },
  { key: 'OBV',  label: 'OBV' },
  { key: 'DMI',  label: 'DMI' },
]

function switchIndex(idx) {
  setSymbol(idx.symbol, idx.name, idx.color)
  queueMicrotask(() => {
    selectedIndex.value = idx.symbol
    currentIndexName.value = idx.name || idx.symbol
  })
}
function onFullscreenSymbolChange({ symbol, name }) {
  switchIndex({ symbol, name })
}

function handleFullscreenClick() {
  // selectedIndex 是 Vue ref，模板中需加 .value 才能取到字符串值；
  // 使用 indexOptions[0].symbol 作为兜底，确保永远有有效 symbol
  let raw = selectedIndex.value || indexOptions[0]?.symbol || 'sh000001'
  let finalSymbol = String(raw)

  // ── 硬编码前缀修复（v0.5.106）：后端 WS 要求带 sh/sz 前缀，纯数字码直接硬塞 ──
  if (/^\d{6}$/.test(finalSymbol)) {
    if (finalSymbol.startsWith('6') || finalSymbol.startsWith('0000')) {
      finalSymbol = 'sh' + finalSymbol
    } else {
      finalSymbol = 'sz' + finalSymbol
    }
  }

  const name = currentIndexName.value || indexOptions[0]?.name || '上证指数'
  emit('open-fullscreen', { symbol: finalSymbol, name })
}
function switchPeriod(p)   { selectedPeriod.value = p }
function toggleIndicator(k) {
  const idx = activeIndicators.value.indexOf(k)
  if (idx >= 0) activeIndicators.value.splice(idx, 1)
  else activeIndicators.value.push(k)
}

// ── 数据计算属性 ────────────────────────────────────────────────
const timestamp = computed(() => props.marketData?.timestamp || '')
const tsDisplay  = computed(() => timestamp.value.slice(11, 19) || '')

// Phase 5: 合并4大指数 + 4大宏观 = 8个风向标
const windItems = computed(() => {
  // 修复: marketData 从 App.vue 传来时已经是 wind 对象本身（不是 {wind: {...}}）
  const indices = props.marketData || {}
  const macros  = macroData.value || []

  // 指数行（实时 Sina 数据：item.price 是当前价）
  const indexRows = Object.entries(indices).map(([sym, item]) => ({
    symbol:     sym,
    name:       item.name,
    price:      item.price ?? item.index ?? 0,  // 兼容新旧格式
    change_pct: item.change_pct ?? 0,
    status:     item.status,
    category:   'index',   // 指数
  }))

  // 宏观行（USD/CNH · 黄金 · WTI · VIX）
  const macroRows = macros.map(m => ({
    symbol:     m.name,      // 展示用名称作 key
    name:       m.name,
    price:      m.price,
    change_pct: m.change_pct,
    unit:       m.unit || '',
    status:     m.timestamp || '',
    category:   'macro',    // 宏观大宗
  }))

return [...indexRows, ...macroRows]
 })
const globalItems = computed(() => globalData.value || [])
const chinaAllItems = computed(() => props.chinaAllData || [])
const sectors = computed(() => props.sectorsData || [])

const mobileRovingFocus = useRovingFocus({
  containerRef: mobileWindContainerRef,
  items: windItems,
  columns: 2,
  onSelect: handleWindClick
})

const desktopRovingFocus = useRovingFocus({
  containerRef: desktopWindContainerRef,
  items: windItems,
  columns: 2,
  onSelect: handleWindClick
})

const mobileAnchors = [
  { id: 'section-chart',     label: '📈 图表' },
  { id: 'section-wind',      label: '🌐 风向标' },
  { id: 'section-screener',  label: '📊 监测' },
  { id: 'section-sentiment', label: '🌡️ 情绪' },
  { id: 'section-sectors',   label: '🔥 板块' },
  { id: 'section-news',      label: '📰 快讯' },
]

function scrollToMobileSection(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// ── 低频数据自持（宏观/利率/海外，5分钟轮询）────────────────────────
//
// ⚠️ Task 9 Note: Why HTTP polling instead of WebSocket for macro data?
// 
// WebSocket does NOT support macro symbols (GOLD, WTI, VIX, CNHUSD, VHSI) because:
// 
// 1. Backend Architecture:
//    - WebSocket broadcasts from `market_data_realtime` table (scheduler.py)
//    - Macro symbols are NOT stored in this table
//    - They use separate caching via `_MACRO_CACHE` in overview.py
// 
// 2. Data Source Difference:
//    - WebSocket symbols: A股指数, 全球指数, Shibor利率, 行业板块, 期货衍生品
//    - Macro symbols: CNYUSD, hf_GC (SGE黄金), hf_CL (WTI原油), hkVHSI (恒指波幅)
//    - Macro data fetched directly from Sina/Tencent APIs, not via WebSocket pipeline
// 
// 3. Update Frequency:
//    - Macro data (commodities, forex, VHSI) updates every 15-30 seconds during market hours
//    - 5-minute polling interval provides reasonable freshness
//    - Real-time updates not critical for macro indicators
// 
// 4. Implementation Note:
//    - To add WebSocket support, backend would need to:
//      a) Store macro symbols in `market_data_realtime` table
//      b) Add macro fetch to `fetch_all_and_buffer()` in data_fetcher.py
//      c) Broadcast macro ticks via `_broadcast_realtime_ticks()`
//    - Current HTTP polling approach is simpler and sufficient for macro data
//
const macroData  = ref([])
const ratesData  = ref([])
const globalData = ref([])

// Error states for each data source
const macroError  = ref(null)
const ratesError  = ref(null)
const globalError = ref(null)

// Retry state for macro data
const macroLoading = ref(false)
const macroRetryCount = ref(0)
const MAX_RETRIES = 5
const RETRY_DELAYS = [1000, 2000, 4000, 8000, 16000] // Exponential backoff

let fetchLowFreqRequestId = 0

async function fetchLowFreq() {
  // Abort any pending request before starting a new one
  _fetchController?.abort()
  _fetchController = new AbortController()
  const currentRequestId = ++fetchLowFreqRequestId

  // Fetch macro data
  try {
    const d = await apiFetch('/api/v1/market/macro', { signal: _fetchController.signal })
    // Ignore stale responses
    if (currentRequestId !== fetchLowFreqRequestId) return
    macroData.value = d?.macro || d?.data?.macro || d || []
    macroError.value = null
  } catch (e) {
    // Ignore abort errors silently
    if (e.name === 'AbortError' || e.message?.includes('aborted')) return
    if (currentRequestId !== fetchLowFreqRequestId) return
    macroError.value = e?.message || 'Failed to fetch macro data'
  }
  
  // Fetch rates data
  try {
    const d = await apiFetch('/api/v1/market/rates', { signal: _fetchController.signal })
    // Ignore stale responses
    if (currentRequestId !== fetchLowFreqRequestId) return
    ratesData.value = d?.rates || d?.data?.rates || d || []
    ratesError.value = null
  } catch (e) {
    // Ignore abort errors silently
    if (e.name === 'AbortError' || e.message?.includes('aborted')) return
    if (currentRequestId !== fetchLowFreqRequestId) return
    ratesError.value = e?.message || 'Failed to fetch rates data'
  }
  
  // Fetch global data
  try {
    const d = await apiFetch('/api/v1/market/global', { signal: _fetchController.signal })
    // Ignore stale responses
    if (currentRequestId !== fetchLowFreqRequestId) return
    globalData.value = d?.global || d?.data?.global || d || []
    globalError.value = null
  } catch (e) {
    // Ignore abort errors silently
    if (e.name === 'AbortError' || e.message?.includes('aborted')) return
    if (currentRequestId !== fetchLowFreqRequestId) return
    globalError.value = e?.message || 'Failed to fetch global data'
  } finally {
    if (currentRequestId === fetchLowFreqRequestId) {
      _fetchController = null
    }
  }
}

// Retry function for macro data with exponential backoff
async function retryMacroFetch() {
  if (macroLoading.value) return
  
  macroLoading.value = true
  try {
    await fetchLowFreq()
    macroRetryCount.value = 0 // Reset on success
  } catch (e) {
    macroRetryCount.value++
    if (macroRetryCount.value < MAX_RETRIES) {
      const delay = RETRY_DELAYS[Math.min(macroRetryCount.value - 1, RETRY_DELAYS.length - 1)]
      console.warn(`[WindVane] Retry ${macroRetryCount.value}/${MAX_RETRIES} in ${delay}ms`)
      setTimeout(retryMacroFetch, delay)
    }
  } finally {
    macroLoading.value = false
  }
}

// Use smart polling: pause when tab hidden, resume + refresh when visible
// Note: HTTP polling is the CORRECT approach for macro data (see Task 9 analysis above)
// WebSocket does not support macro symbols - they use separate Sina/Tencent APIs
const { start: startLowPolling, stop: stopLowPolling } = useSmartPolling(fetchLowFreq, {
  interval: 300_000,  // 5 minutes - appropriate for macro data freshness
  pauseWhenHidden: true,
})

onMounted(async () => {
  startLowPolling()
  await nextTick()
  if (!isMobile.value && typeof window !== 'undefined' && window.GridStack && document.querySelector('.grid-stack')) {
    grid = GridStack.init({
      column: 12,
      cellHeight: 80,
      float: true,
      margin: 8,
      disableDrag: isMobile.value,   // 手机端禁止拖拽
      disableResize: isMobile.value, // 手机端禁止缩放
    })
    grid.setStatic(props.isLocked)
    
    // ── Load saved layout from localStorage ───────────────────────────
    const savedLayout = loadLayout()
    if (savedLayout) {
      applyLayout(savedLayout)
    }
    
    // ── Setup layout change listeners for persistence ──────────────────
    grid.on('change', (event, items) => {
      debouncedSaveLayout()
    })
    grid.on('resizestop', (event, el) => {
      saveLayout()
    })
    grid.on('dragstop', (event, el) => {
      saveLayout()
    })
  }
})

onUnmounted(() => {
  // Cancel any pending fetch requests
  _fetchController?.abort()
  _fetchController = null
  grid?.destroy(false)
  stopLowPolling()
})

// Phase 5: 格式化宏观价格（带单位）
function formatMacroPrice(item) {
  const p = formatPrice(item.price)
  return item.unit ? `${p} ${item.unit}` : p
}

// 格式化风向标价格（安全处理 null/undefined/NaN/Infinity）
function formatWindPrice(item) {
  if (item.category === 'macro') {
    // Macro: show price with unit
    const price = formatPrice(item.price)
    return item.unit ? `${price} ${item.unit}` : price
  } else {
    // Index: show price with 2 decimals
    return formatPrice(item.price)
  }
}

// 格式化风向标涨跌幅（安全处理 null/undefined/NaN/Infinity）
function formatWindChangePct(value) {
  return formatChangePct(value)
}

// ── StockScreener / Copilot 等外部改变了 currentSymbol 时同步 selectedIndex ──
// 防抖版：避免 rapid setSymbol 调用导致频繁更新
let syncIndexTimer = null
watch(() => currentSymbol.value, (sym) => {
  clearTimeout(syncIndexTimer)
  syncIndexTimer = setTimeout(() => {
    if (sym && sym !== selectedIndex.value) {
      selectedIndex.value = sym
    }
    currentIndexName.value = currentSymbolName.value || currentIndexName.value
  }, 50)
})

// ── 标的切换时自动回退不支持的周期 ────────────────────────────────
watch(selectedIndex, (sym) => {
  // 分钟系（分时/1min/5min...）仅支持 _MIN_KLINE_SUPPORTED 中的5只A股指数
  const MIN_SUPPORTED = new Set(['000001', '000300', '399001', '399006', '000688'])
  const MIN_PERIODS  = new Set(['minutely', '1min', '5min', '15min', '30min', '60min'])
  if (!MIN_SUPPORTED.has(sym) && MIN_PERIODS.has(selectedPeriod.value)) {
    selectedPeriod.value = 'daily'
  }
})

// ── GridStack 锁定：响应 props.isLocked 变化 ────────────────────
function toggleLock() {
  emit('toggle-lock')
}
</script>

<style>
.grid-stack { width: 100%; height: 100%; overflow: hidden; }
.grid-stack-item { overflow: hidden; }
.grid-stack-item-content { inset: 4px; overflow: hidden; min-height: 0; border-radius: 8px; display: flex; flex-direction: column; }
.scrollbar-hide::-webkit-scrollbar { display: none; }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }

/* Screen reader only - visually hidden but accessible */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

/* ━━━ Focus Indicators for Interactive Elements ━━━━━━━━━━━━━━━━━━━━ */
/* Wind vane cards - clickable market indicator cards */
.wind-vane-card:focus-visible,
.grid-stack-item-content [class*="cursor-pointer"]:focus-visible {
  outline: 2px solid var(--accent-primary, #3b82f6);
  outline-offset: 2px;
  border-radius: 4px;
}

/* Ensure 3:1 contrast ratio for focus ring on dark backgrounds */
/* #3b82f6 on #121212 has ~4.5:1 contrast ratio (passes WCAG AA) */
.grid-stack button:focus-visible,
.terminal-panel button:focus-visible {
  outline: 2px solid var(--accent-primary, #3b82f6);
  outline-offset: 2px;
}

/* Mobile navigation buttons */
button:focus-visible {
  outline: 2px solid var(--accent-primary, #3b82f6);
  outline-offset: 2px;
}

/* Table rows with click handlers */
tr[class*="cursor-pointer"]:focus-visible {
  outline: 2px solid var(--accent-primary, #3b82f6);
  outline-offset: -2px;
}

/* Focus ring for wind vane grid items (2-column grid) */
.grid-cols-2 > div[class*="cursor-pointer"]:focus-visible {
  outline: 2px solid var(--accent-primary, #3b82f6);
  outline-offset: 2px;
}

.pull-refresh-indicator {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
  pointer-events: none;
  opacity: 0;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.animate-spin {
  animation: spin 1s linear infinite;
}
</style>
