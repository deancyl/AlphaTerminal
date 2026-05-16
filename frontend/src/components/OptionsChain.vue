<template>
  <div class="h-full flex flex-col bg-terminal-bg overflow-hidden" role="region" aria-label="期权链分析面板">
    <div class="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-theme-secondary">
      <div class="flex items-center gap-3">
        <span class="text-lg font-bold text-terminal-accent" role="heading" aria-level="2">📊 期权链</span>
        <span class="text-xs text-terminal-dim hidden sm:inline">T型报价 · Greeks · 隐含波动率</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xs text-terminal-dim font-mono tabular-nums">{{ currentTime }}</span>
        <button 
          class="px-3 py-1.5 rounded-sm text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition disabled:opacity-50"
          @click="fetchChain"
          :disabled="loading"
          type="button"
        >
          {{ loading ? '...' : '刷新' }}
        </button>
      </div>
    </div>

    <div class="flex-shrink-0 px-4 py-3 border-b border-theme-secondary bg-surface">
      <div class="flex items-center gap-3">
        <label class="text-xs text-terminal-dim">合约:</label>
        <select 
          v-model="selectedSymbol" 
          class="px-3 py-1.5 bg-terminal-bg border border-theme-secondary rounded-sm text-terminal-primary text-sm focus:outline-none focus:border-terminal-accent"
        >
          <option v-for="c in contracts" :key="c.code" :value="c.code">{{ c.name }}</option>
        </select>
        <span v-if="chainName" class="text-xs text-terminal-dim">{{ chainName }}</span>
      </div>
    </div>

    <div class="flex-1 overflow-hidden flex flex-col">
      <div v-if="loading && !calls.length" class="flex-1 flex items-center justify-center">
        <div class="text-terminal-dim text-sm animate-pulse">加载中...</div>
      </div>

      <div v-else-if="error" class="flex-1 flex items-center justify-center">
        <div class="text-center">
          <div class="text-bearish text-sm mb-2">{{ error }}</div>
          <button 
            @click="fetchChain"
            class="px-3 py-1.5 text-xs bg-terminal-accent/20 text-terminal-accent rounded-sm hover:bg-terminal-accent/30 transition"
            type="button"
          >
            重试
          </button>
        </div>
      </div>

      <div v-else class="flex-1 overflow-auto">
        <table class="w-full text-xs border-collapse">
          <thead class="sticky top-0 bg-surface z-10">
            <tr>
              <th colspan="7" class="text-center py-2 text-bullish border-b border-theme-secondary">看涨期权 (CALL)</th>
              <th class="text-center py-2 text-terminal-accent border-b border-theme-secondary bg-terminal-accent/10">行权价</th>
              <th colspan="7" class="text-center py-2 text-bearish border-b border-theme-secondary">看跌期权 (PUT)</th>
            </tr>
            <tr class="text-terminal-dim">
              <th class="px-2 py-1.5 text-right">最新价</th>
              <th class="px-2 py-1.5 text-right">涨跌</th>
              <th class="px-2 py-1.5 text-right">成交量</th>
              <th class="px-2 py-1.5 text-right">持仓量</th>
              <th class="px-2 py-1.5 text-right">Delta</th>
              <th class="px-2 py-1.5 text-right">Gamma</th>
              <th class="px-2 py-1.5 text-right">IV</th>
              <th class="px-2 py-1.5 text-center bg-terminal-accent/10">Strike</th>
              <th class="px-2 py-1.5 text-right">IV</th>
              <th class="px-2 py-1.5 text-right">Gamma</th>
              <th class="px-2 py-1.5 text-right">Delta</th>
              <th class="px-2 py-1.5 text-right">持仓量</th>
              <th class="px-2 py-1.5 text-right">成交量</th>
              <th class="px-2 py-1.5 text-right">涨跌</th>
              <th class="px-2 py-1.5 text-right">最新价</th>
            </tr>
          </thead>
          <tbody>
            <tr 
              v-for="(row, idx) in chainRows" 
              :key="idx"
              class="hover:bg-terminal-accent/5 cursor-pointer transition"
              :class="{ 'bg-terminal-accent/10': selectedStrike === row.strike }"
              @click="selectRow(row)"
              tabindex="0"
              @keydown.enter="selectRow(row)"
            >
              <td class="px-2 py-1.5 text-right font-mono tabular-nums" :class="getPriceClass(row.call?.change)">
                {{ formatPrice(row.call?.latest) }}
              </td>
              <td class="px-2 py-1.5 text-right font-mono tabular-nums" :class="getChangeClass(row.call?.change)">
                {{ formatChange(row.call?.change, row.call?.change_pct) }}
              </td>
              <td class="px-2 py-1.5 text-right font-mono tabular-nums">{{ formatVolume(row.call?.volume) }}</td>
              <td class="px-2 py-1.5 text-right font-mono tabular-nums">{{ formatVolume(row.call?.open_interest) }}</td>
              <td class="px-2 py-1.5 text-right font-mono tabular-nums">{{ formatGreek(row.call?.delta) }}</td>
              <td class="px-2 py-1.5 text-right font-mono tabular-nums">{{ formatGreek(row.call?.gamma) }}</td>
              <td class="px-2 py-1.5 text-right font-mono tabular-nums">{{ formatPercent(row.call?.iv) }}</td>
              <td class="px-2 py-1.5 text-center font-mono tabular-nums font-bold bg-terminal-accent/10 text-terminal-accent">
                {{ formatStrike(row.strike) }}
              </td>
              <td class="px-2 py-1.5 text-right font-mono tabular-nums">{{ formatPercent(row.put?.iv) }}</td>
              <td class="px-2 py-1.5 text-right font-mono tabular-nums">{{ formatGreek(row.put?.gamma) }}</td>
              <td class="px-2 py-1.5 text-right font-mono tabular-nums">{{ formatGreek(row.put?.delta) }}</td>
              <td class="px-2 py-1.5 text-right font-mono tabular-nums">{{ formatVolume(row.put?.open_interest) }}</td>
              <td class="px-2 py-1.5 text-right font-mono tabular-nums">{{ formatVolume(row.put?.volume) }}</td>
              <td class="px-2 py-1.5 text-right font-mono tabular-nums" :class="getChangeClass(row.put?.change)">
                {{ formatChange(row.put?.change, row.put?.change_pct) }}
              </td>
              <td class="px-2 py-1.5 text-right font-mono tabular-nums" :class="getPriceClass(row.put?.change)">
                {{ formatPrice(row.put?.latest) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div 
      v-if="selectedOption" 
      class="flex-shrink-0 border-t border-theme-secondary bg-surface p-4"
      role="region"
      aria-label="Greeks详情"
    >
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-bold text-terminal-accent">
          {{ selectedOption.name || selectedOption.code }} - Greeks
        </h3>
        <span class="text-xs text-terminal-dim">{{ selectedOption.type === 'call' ? '看涨' : '看跌' }}</span>
      </div>
      <div class="grid grid-cols-5 gap-4">
        <div class="text-center">
          <div class="text-xs text-terminal-dim mb-1">Delta</div>
          <div class="text-sm font-mono tabular-nums text-terminal-primary">{{ formatGreek(selectedOption.delta) }}</div>
        </div>
        <div class="text-center">
          <div class="text-xs text-terminal-dim mb-1">Gamma</div>
          <div class="text-sm font-mono tabular-nums text-terminal-primary">{{ formatGreek(selectedOption.gamma) }}</div>
        </div>
        <div class="text-center">
          <div class="text-xs text-terminal-dim mb-1">Theta</div>
          <div class="text-sm font-mono tabular-nums text-terminal-primary">{{ formatGreek(selectedOption.theta) }}</div>
        </div>
        <div class="text-center">
          <div class="text-xs text-terminal-dim mb-1">Vega</div>
          <div class="text-sm font-mono tabular-nums text-terminal-primary">{{ formatGreek(selectedOption.vega) }}</div>
        </div>
        <div class="text-center">
          <div class="text-xs text-terminal-dim mb-1">IV</div>
          <div class="text-sm font-mono tabular-nums text-terminal-primary">{{ formatPercent(selectedOption.iv) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { apiFetch } from '../utils/api.js'

const loading = ref(false)
const error = ref(null)
const currentTime = ref('')
const selectedSymbol = ref('io2506')
const selectedStrike = ref(null)
const selectedOption = ref(null)

const contracts = ref([
  { code: 'io2506', name: '沪深300股指期权2506' },
  { code: 'io2507', name: '沪深300股指期权2507' },
  { code: 'mo2506', name: '中证1000股指期权2506' },
  { code: 'mo2507', name: '中证1000股指期权2507' },
])

const calls = ref([])
const puts = ref([])
const chainName = ref('')

const chainRows = computed(() => {
  const strikes = new Set()
  const callMap = new Map()
  const putMap = new Map()

  calls.value.forEach(c => {
    if (c.strike) {
      strikes.add(c.strike)
      callMap.set(c.strike, { ...c, type: 'call' })
    }
  })

  puts.value.forEach(p => {
    if (p.strike) {
      strikes.add(p.strike)
      putMap.set(p.strike, { ...p, type: 'put' })
    }
  })

  const sortedStrikes = Array.from(strikes).sort((a, b) => a - b)
  
  return sortedStrikes.map(strike => ({
    strike,
    call: callMap.get(strike),
    put: putMap.get(strike),
  }))
})

function formatTimeNow() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

async function fetchChain() {
  loading.value = true
  error.value = null

  try {
    const res = await apiFetch(`/api/v1/options/cffex/chain?symbol=${selectedSymbol.value}`, { timeoutMs: 30000 })
    
    if (res?.data) {
      calls.value = res.data.calls || []
      puts.value = res.data.puts || []
      chainName.value = res.data.name || ''
    }
  } catch (e) {
    error.value = e.message || '获取期权链失败'
  } finally {
    loading.value = false
  }
}

async function fetchContracts() {
  try {
    const res = await apiFetch('/api/v1/options/contracts?exchange=CFFEX', { timeoutMs: 10000 })
    if (res?.data?.contracts?.length) {
      contracts.value = res.data.contracts
    }
  } catch (e) {
    console.warn('Failed to fetch contracts:', e)
  }
}

function selectRow(row) {
  selectedStrike.value = row.strike
  selectedOption.value = row.call || row.put
}

function formatPrice(val) {
  if (val == null) return '-'
  return val.toFixed(2)
}

function formatChange(change, pct) {
  if (change == null) return '-'
  const sign = change >= 0 ? '+' : ''
  return `${sign}${change.toFixed(2)}`
}

function formatVolume(val) {
  if (val == null) return '-'
  if (val >= 10000) return `${(val / 10000).toFixed(1)}万`
  return val.toString()
}

function formatStrike(val) {
  if (val == null) return '-'
  return val.toFixed(0)
}

function formatGreek(val) {
  if (val == null) return '-'
  return val.toFixed(4)
}

function formatPercent(val) {
  if (val == null) return '-'
  return `${(val * 100).toFixed(1)}%`
}

function getPriceClass(change) {
  if (change == null) return 'text-terminal-dim'
  return change >= 0 ? 'text-bullish' : 'text-bearish'
}

function getChangeClass(change) {
  if (change == null) return 'text-terminal-dim'
  return change >= 0 ? 'text-bullish' : 'text-bearish'
}

function updateTime() {
  currentTime.value = new Date().toLocaleTimeString('zh-CN')
}

let timeInterval = null

onMounted(async () => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  
  await fetchContracts()
  await fetchChain()
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
})

watch(selectedSymbol, () => {
  selectedStrike.value = null
  selectedOption.value = null
  fetchChain()
})
</script>

<style scoped>
.bg-terminal-bg {
  background: var(--bg-base, #121212);
}

.bg-surface {
  background: var(--bg-surface, #1e1e1e);
}

.text-terminal-accent {
  color: var(--color-primary, #0F52BA);
}

.text-terminal-primary {
  color: var(--text-primary, #F0F6FC);
}

.text-terminal-dim {
  color: var(--text-secondary, #C9D1D9);
}

.text-bullish {
  color: var(--color-bull, #E63946);
}

.text-bearish {
  color: var(--color-bear, #1A936F);
}

.border-theme-secondary {
  border-color: var(--border-base, #30363D);
}

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.tabular-nums {
  font-variant-numeric: tabular-nums;
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
  border-bottom: 1px solid var(--border-base, #30363D);
}

tbody tr:hover {
  background: rgba(15, 82, 186, 0.05);
}

tbody tr:focus {
  outline: 2px solid var(--color-primary, #0F52BA);
  outline-offset: -2px;
}
</style>
