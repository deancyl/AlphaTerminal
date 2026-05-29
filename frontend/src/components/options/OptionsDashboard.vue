<template>
  <div class="options-dashboard h-full flex flex-col bg-base overflow-hidden" role="region" aria-label="期权分析面板">
    <div class="header flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-theme-secondary">
      <div class="flex items-center gap-2">
        <span class="text-lg font-bold text-primary">📊 期权分析</span>
        <EducationalTooltip term="call" />
        <span class="text-xs text-secondary hidden sm:inline">波动率 · 市场情绪 · 风险指标</span>
      </div>
      
      <div class="flex items-center gap-2">
        <select
          v-model="localSymbol"
          @change="changeSymbol(localSymbol)"
          class="px-2 py-1 bg-surface border border-theme-secondary rounded text-primary text-xs focus:outline-none focus:border-primary"
          aria-label="选择期权品种"
        >
          <option v-for="c in contracts" :key="c.code" :value="c.code">{{ c.name }}</option>
        </select>
        
        <button
          @click="toggleAutoRefresh()"
          class="px-2 py-1 rounded text-xs transition"
          :class="autoRefreshEnabled ? 'bg-primary/20 text-primary' : 'bg-surface text-secondary'"
          :aria-pressed="autoRefreshEnabled"
          type="button"
        >
          {{ autoRefreshEnabled ? '🔄 自动' : '⏸ 手动' }}
        </button>
        
        <button
          @click="fetchChain()"
          :disabled="loading"
          class="px-3 py-1 rounded text-xs bg-primary/20 text-primary hover:bg-primary/30 disabled:opacity-50 transition"
          type="button"
        >
          {{ loading ? '...' : '刷新' }}
        </button>
      </div>
    </div>
    
    <Transition name="fade" mode="out-in">
      <div v-if="loading && !chainData" class="flex-1 flex items-center justify-center">
        <div class="text-secondary animate-pulse">加载期权链数据...</div>
      </div>
      
      <div v-else-if="error && !chainData" class="flex-1 flex flex-col items-center justify-center">
        <div class="text-3xl mb-3">⚠️</div>
        <div class="text-sm text-secondary mb-3">{{ error }}</div>
        <button @click="fetchChain()" class="px-3 py-1 text-xs rounded bg-primary hover:opacity-80" type="button">
          重试
        </button>
      </div>
      
      <div v-else-if="chainData" class="flex-1 flex flex-col min-h-0 overflow-hidden">
        <div class="charts-row flex-shrink-0 grid grid-cols-1 md:grid-cols-3 gap-3 p-4 border-b border-theme-secondary">
          <div class="chart-panel bg-surface rounded-sm p-3">
            <div class="flex items-center gap-1 text-xs text-secondary mb-2">
              <span>波动率曲线</span>
              <EducationalTooltip term="iv" />
            </div>
            <IVSmileChart :ivSmileData="ivSmileData" :atmStrike="atmStrike" />
          </div>
          
          <div class="chart-panel bg-surface rounded-sm p-3 flex items-center justify-center">
            <PCRIndicator :pcr="pcr" :sentiment="pcrSentiment" />
          </div>
          
          <div class="chart-panel bg-surface rounded-sm p-3">
            <div class="flex items-center gap-1 text-xs text-secondary mb-2">
              <span>风险指标</span>
              <EducationalTooltip term="delta" />
            </div>
            <GreeksChart :greeksData="greeksData" :atmStrike="atmStrike" />
          </div>
        </div>
        
        <div class="chain-table flex-1 overflow-hidden flex flex-col">
          <div class="table-header flex-shrink-0 grid grid-cols-[1fr_80px_1fr] text-xs border-b border-theme-secondary bg-surface">
            <div class="px-3 py-2 text-center text-bullish font-bold">Call 看涨</div>
            <div class="px-2 py-2 text-center border-x border-theme-secondary text-primary font-bold">行权价</div>
            <div class="px-3 py-2 text-center text-bearish font-bold">Put 看跌</div>
          </div>
          
          <div class="table-body flex-1 overflow-hidden">
            <VirtualizedTable
              :items="chainRows"
              :columns="tableColumns"
              :item-size="28"
              :buffer="100"
              :row-class="getRowClass"
              @row-click="handleRowClick"
            >
              <template #cell-call_latest="{ item }">
                <span :class="getPriceClass(item.call?.change)" class="font-mono tabular-nums">
                  {{ formatPrice(item.call?.latest) }}
                </span>
              </template>
              
              <template #cell-call_change="{ item }">
                <span :class="getChangeClass(item.call?.change)" class="font-mono tabular-nums">
                  {{ formatChange(item.call?.change) }}
                </span>
              </template>
              
              <template #cell-call_iv="{ item }">
                <span class="font-mono tabular-nums">
                  {{ formatPercent(item.call?.iv) }}
                </span>
              </template>
              
              <template #cell-call_delta="{ item }">
                <span class="font-mono tabular-nums">
                  {{ formatGreek(item.call?.delta) }}
                </span>
              </template>
              
              <template #cell-call_oi="{ item }">
                <div class="flex items-center justify-end gap-1">
                  <div class="oi-bar h-2 rounded" :style="{ width: getOIBarWidth(item.call?.open_interest, 'call') }"></div>
                  <span class="font-mono tabular-nums text-xs">{{ formatOI(item.call?.open_interest) }}</span>
                </div>
              </template>
              
              <template #cell-strike="{ item }">
                <div class="relative">
                  <span class="font-mono tabular-nums text-primary">{{ item.strike }}</span>
                  <span v-if="item.strike === atmStrike" class="text-warning ml-1">◀</span>
                </div>
              </template>
              
              <template #cell-put_oi="{ item }">
                <div class="flex items-center justify-end gap-1">
                  <div class="oi-bar put h-2 rounded" :style="{ width: getOIBarWidth(item.put?.open_interest, 'put') }"></div>
                  <span class="font-mono tabular-nums text-xs">{{ formatOI(item.put?.open_interest) }}</span>
                </div>
              </template>
              
              <template #cell-put_delta="{ item }">
                <span class="font-mono tabular-nums">
                  {{ formatGreek(item.put?.delta) }}
                </span>
              </template>
              
              <template #cell-put_iv="{ item }">
                <span class="font-mono tabular-nums">
                  {{ formatPercent(item.put?.iv) }}
                </span>
              </template>
              
              <template #cell-put_change="{ item }">
                <span :class="getChangeClass(item.put?.change)" class="font-mono tabular-nums">
                  {{ formatChange(item.put?.change) }}
                </span>
              </template>
              
              <template #cell-put_latest="{ item }">
                <span :class="getPriceClass(item.put?.change)" class="font-mono tabular-nums">
                  {{ formatPrice(item.put?.latest) }}
                </span>
              </template>
            </VirtualizedTable>
          </div>
        </div>
        
        <div class="footer flex-shrink-0 flex items-center justify-between px-4 py-2 border-t border-theme-secondary bg-surface text-xs text-secondary">
          <span>PCR: {{ pcrDisplay }} | ATM: {{ atmStrike || '--' }}</span>
          <span>更新时间: {{ chainData?.update_time || '--' }}</span>
        </div>
      </div>
      
      <div v-else class="flex-1 flex flex-col items-center justify-center">
        <div class="text-3xl mb-3">📊</div>
        <div class="text-sm text-secondary">暂无期权数据</div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, onDeactivated, onActivated } from 'vue'
import { useOptions } from '../../composables/useOptions.js'
import EducationalTooltip from './EducationalTooltip.vue'
import IVSmileChart from './IVSmileChart.vue'
import PCRIndicator from './PCRIndicator.vue'
import GreeksChart from './GreeksChart.vue'
import VirtualizedTable from '../VirtualizedTable.vue'

const {
  symbol, chainData, loading, error, autoRefreshEnabled,
  atmStrike, pcr, pcrSentiment, ivSmileData, greeksData, chainRows,
  fetchChain, toggleAutoRefresh, changeSymbol, contracts
} = useOptions('io2506', 60000)

const localSymbol = ref(symbol.value)

const pcrDisplay = computed(() => pcr.value === null ? '--' : pcr.value.toFixed(2))

/**
 * Table columns for virtualized options chain
 */
const tableColumns = computed(() => [
  { key: 'call_latest', label: '最新价', width: '60px', align: 'right', sortable: false },
  { key: 'call_change', label: '涨跌', width: '60px', align: 'right', sortable: false },
  { key: 'call_iv', label: 'IV', width: '50px', align: 'right', sortable: false },
  { key: 'call_delta', label: 'Delta', width: '60px', align: 'right', sortable: false },
  { key: 'call_oi', label: '持仓量', width: '70px', align: 'right', sortable: false },
  { key: 'strike', label: 'Strike', width: '60px', align: 'center', sortable: false },
  { key: 'put_oi', label: '持仓量', width: '70px', align: 'right', sortable: false },
  { key: 'put_delta', label: 'Delta', width: '60px', align: 'right', sortable: false },
  { key: 'put_iv', label: 'IV', width: '50px', align: 'right', sortable: false },
  { key: 'put_change', label: '涨跌', width: '60px', align: 'right', sortable: false },
  { key: 'put_latest', label: '最新价', width: '60px', align: 'right', sortable: false },
])

/**
 * Maximum OI across all visible rows for bar scaling
 */
const maxOI = computed(() => {
  const allOI = chainRows.value.flatMap(r => [
    r.call?.open_interest || 0,
    r.put?.open_interest || 0
  ]).filter(oi => oi > 0)  // FILTER: Remove zeros

  // LENGTH CHECK: Handle empty array
  if (allOI.length === 0) return 1

  return Math.max(...allOI)
})

/**
 * Calculate OI bar width percentage
 * @param {number} oi - Open interest value
 * @param {string} type - 'call' or 'put'
 * @returns {string} CSS width percentage (max 50%)
 */
function getOIBarWidth(oi, type) {
  if (!oi || oi <= 0) return '0%'
  const percentage = (oi / maxOI.value) * 50
  return `${Math.min(percentage, 50)}%`
}

/**
 * Format OI number for display
 * @param {number} oi - Open interest value
 * @returns {string} Formatted number or dash
 */
function formatOI(oi) {
  if (oi == null) return '-'
  if (oi >= 10000) return `${(oi / 1000).toFixed(1)}K`
  return oi.toString()
}

function formatPrice(val) {
  if (val == null) return '-'
  return val.toFixed(2)
}

function formatChange(val) {
  if (val == null) return '-'
  const sign = val >= 0 ? '+' : ''
  return `${sign}${val.toFixed(2)}`
}

function formatPercent(val) {
  if (val == null) return '-'
  return `${(val * 100).toFixed(1)}%`
}

function formatGreek(val) {
  if (val == null) return '-'
  return val.toFixed(4)
}

function getPriceClass(change) {
  if (change == null) return 'text-secondary'
  return change >= 0 ? 'text-bullish' : 'text-bearish'
}

function getChangeClass(change) {
  if (change == null) return 'text-secondary'
  return change >= 0 ? 'text-bullish' : 'text-bearish'
}

/**
 * Handle row click in virtualized table
 * @param {Object} payload - { item, index }
 */
function handleRowClick({ item, index }) {
  // Row click handler for future use (e.g., show detailed info)
  console.log('Row clicked:', item.strike)
}

/**
 * Get row class for virtualized table (highlight ATM strike)
 * @param {Object} item - Row item
 * @returns {string} CSS class
 */
function getRowClass(item) {
  return item.strike === atmStrike.value ? 'bg-primary/10 font-bold' : ''
}

// P0: KeepAlive cleanup
onDeactivated(() => {
  // Stop auto-refresh timer
  if (autoRefreshEnabled.value) {
    toggleAutoRefresh()
  }
})

onActivated(() => {
  // Resume auto-refresh if was enabled
  if (!autoRefreshEnabled.value) {
    toggleAutoRefresh()
  }
})
</script>

<style scoped>
.bg-base { background: var(--bg-base, #121212); }
.bg-surface { background: var(--bg-surface, #1e1e1e); }
.text-primary { color: var(--text-primary, #f0f6fc); }
.text-secondary { color: var(--text-secondary, #9ca3af); }
.text-bullish { color: var(--color-bull, #ef4444); }
.text-bearish { color: var(--color-bear, #22c55e); }
.text-warning { color: #fbbf24; }
.border-theme-secondary { border-color: var(--border-base, #30363d); }
.bg-primary\/10 { background: rgba(15, 82, 186, 0.1); }
.bg-primary\/20 { background: rgba(15, 82, 186, 0.2); }
.bg-primary\/5 { background: rgba(15, 82, 186, 0.05); }

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.tabular-nums {
  font-variant-numeric: tabular-nums;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

table {
  border-spacing: 0;
}

th, td {
  border-bottom: 1px solid var(--border-base, #30363d);
}

/* OI Bar Visualization */
.oi-bar {
  background: var(--color-bull, #22c55e);
  transition: width var(--duration-normal, 250ms) var(--easing-default, cubic-bezier(0.2, 0, 0, 1));
  min-width: 2px;
}

.oi-bar.put {
  background: var(--color-bear, #ef4444);
}

.oi-bar:hover {
  opacity: 0.8;
}
</style>