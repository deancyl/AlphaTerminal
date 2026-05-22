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
          
          <div class="table-body flex-1 overflow-x-auto overflow-y-auto">
            <table class="w-full text-xs border-collapse">
               <thead class="sticky top-0 bg-surface z-10">
                 <tr class="text-secondary">
                   <th class="px-2 py-1.5 text-right">最新价</th>
                   <th class="px-2 py-1.5 text-right">涨跌</th>
                   <th class="px-2 py-1.5 text-right">IV</th>
                   <th class="px-2 py-1.5 text-right">Delta</th>
                   <th class="px-2 py-1.5 text-right">持仓量</th>
                   <th class="px-2 py-1.5 text-center bg-primary/10 sticky left-0 z-20">Strike</th>
                   <th class="px-2 py-1.5 text-right">持仓量</th>
                   <th class="px-2 py-1.5 text-right">Delta</th>
                   <th class="px-2 py-1.5 text-right">IV</th>
                   <th class="px-2 py-1.5 text-right">涨跌</th>
                   <th class="px-2 py-1.5 text-right">最新价</th>
                 </tr>
               </thead>
               <tbody>
                 <tr
                   v-for="row in chainRows"
                   :key="row.strike"
                   class="hover:bg-primary/5 transition"
                   :class="{ 'bg-primary/10 font-bold': row.strike === atmStrike }"
                   tabindex="0"
                 >
                   <td class="px-2 py-1.5 text-right font-mono tabular-nums" :class="getPriceClass(row.call?.change)">
                     {{ formatPrice(row.call?.latest) }}
                   </td>
                   <td class="px-2 py-1.5 text-right font-mono tabular-nums" :class="getChangeClass(row.call?.change)">
                     {{ formatChange(row.call?.change) }}
                   </td>
                   <td class="px-2 py-1.5 text-right font-mono tabular-nums">
                     {{ formatPercent(row.call?.iv) }}
                   </td>
                   <td class="px-2 py-1.5 text-right font-mono tabular-nums">
                     {{ formatGreek(row.call?.delta) }}
                   </td>
                   <td class="px-2 py-1.5 text-right">
                     <div class="flex items-center justify-end gap-1">
                       <div class="oi-bar h-2 rounded" :style="{ width: getOIBarWidth(row.call?.open_interest, 'call') }"></div>
                       <span class="font-mono tabular-nums text-xs">{{ formatOI(row.call?.open_interest) }}</span>
                     </div>
                   </td>
                   
                   <td class="px-2 py-1.5 text-center font-mono tabular-nums bg-primary/10 sticky left-0 z-10 text-primary">
                     {{ row.strike }}
                     <span v-if="row.strike === atmStrike" class="text-warning ml-1">◀</span>
                   </td>
                   
                   <td class="px-2 py-1.5 text-right">
                     <div class="flex items-center justify-end gap-1">
                       <div class="oi-bar put h-2 rounded" :style="{ width: getOIBarWidth(row.put?.open_interest, 'put') }"></div>
                       <span class="font-mono tabular-nums text-xs">{{ formatOI(row.put?.open_interest) }}</span>
                     </div>
                   </td>
                   <td class="px-2 py-1.5 text-right font-mono tabular-nums">
                     {{ formatGreek(row.put?.delta) }}
                   </td>
                   <td class="px-2 py-1.5 text-right font-mono tabular-nums">
                     {{ formatPercent(row.put?.iv) }}
                   </td>
                   <td class="px-2 py-1.5 text-right font-mono tabular-nums" :class="getChangeClass(row.put?.change)">
                     {{ formatChange(row.put?.change) }}
                   </td>
                   <td class="px-2 py-1.5 text-right font-mono tabular-nums" :class="getPriceClass(row.put?.change)">
                     {{ formatPrice(row.put?.latest) }}
                   </td>
                 </tr>
               </tbody>
            </table>
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
import { ref, computed, onMounted } from 'vue'
import { useOptions } from '../../composables/useOptions.js'
import EducationalTooltip from './EducationalTooltip.vue'
import IVSmileChart from './IVSmileChart.vue'
import PCRIndicator from './PCRIndicator.vue'
import GreeksChart from './GreeksChart.vue'

const {
  symbol, chainData, loading, error, autoRefreshEnabled,
  atmStrike, pcr, pcrSentiment, ivSmileData, greeksData, chainRows,
  fetchChain, toggleAutoRefresh, changeSymbol, contracts
} = useOptions('io2506', 60000)

const localSymbol = ref(symbol.value)

const pcrDisplay = computed(() => pcr.value === null ? '--' : pcr.value.toFixed(2))

/**
 * Maximum OI across all visible rows for bar scaling
 */
const maxOI = computed(() => {
  const allOI = chainRows.value.flatMap(r => [
    r.call?.open_interest || 0,
    r.put?.open_interest || 0
  ])
  return Math.max(...allOI, 1)
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