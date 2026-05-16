<template>
  <div class="flex flex-col h-full overflow-auto gap-3 p-4" role="region" aria-label="期权分析面板">
    <!-- Header -->
    <div class="flex-shrink-0 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <span class="text-lg font-bold text-terminal-accent">📊 期权分析</span>
        <span class="text-xs text-terminal-dim hidden sm:inline">T型报价 · Greeks</span>
      </div>
      <div class="flex items-center gap-2">
        <select
          v-model="selectedSymbol"
          class="px-3 py-1.5 bg-terminal-bg border border-theme-secondary rounded-sm text-terminal-primary text-xs focus:outline-none focus:border-terminal-accent"
          @change="handleSymbolChange"
          aria-label="选择期权品种"
        >
          <option v-for="contract in contracts" :key="contract.code" :value="contract.code">
            {{ contract.name }}
          </option>
        </select>
        <button
          class="px-3 py-1.5 rounded-sm text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition disabled:opacity-50"
          @click="fetchChainData"
          :disabled="loading"
          type="button"
        >
          {{ loading ? '...' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <Transition name="fade" mode="out-in">
      <div v-if="loading && !chainData" class="flex items-center justify-center py-8">
        <div class="text-sm text-terminal-dim">加载期权链数据...</div>
      </div>

      <!-- Error State -->
      <div v-else-if="error && !chainData" class="flex-1 flex flex-col items-center justify-center py-8">
        <div class="text-3xl mb-3">⚠️</div>
        <div class="text-sm text-terminal-dim mb-3">{{ error }}</div>
        <button
          @click="fetchChainData"
          class="px-3 py-1 text-xs rounded-sm bg-terminal-accent hover:opacity-80"
          type="button"
        >
          重试
        </button>
      </div>

      <!-- Content -->
      <div v-else-if="chainData" class="flex flex-col gap-3 flex-1 min-h-0">
        <!-- Greeks Panel (shown when contract selected) -->
        <div v-if="selectedContract" class="terminal-panel border border-theme-secondary rounded-sm p-4">
          <div class="flex items-center justify-between mb-3">
            <span class="text-sm font-bold text-terminal-accent">
              {{ selectedContract.name || selectedContract.code }}
            </span>
            <button
              @click="selectedContract = null"
              class="text-xs text-terminal-dim hover:text-terminal-primary"
              type="button"
              aria-label="关闭Greeks面板"
            >
              ✕
            </button>
          </div>
          <div class="grid grid-cols-3 md:grid-cols-6 gap-2 md:gap-4">
            <div class="text-center">
              <div class="text-[10px] text-terminal-dim mb-1">Delta</div>
              <div class="text-sm font-mono" :class="(selectedContract.delta || 0) >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ formatValue(selectedContract.delta) }}
              </div>
            </div>
            <div class="text-center">
              <div class="text-[10px] text-terminal-dim mb-1">Gamma</div>
              <div class="text-sm font-mono text-terminal-primary">
                {{ formatValue(selectedContract.gamma) }}
              </div>
            </div>
            <div class="text-center">
              <div class="text-[10px] text-terminal-dim mb-1">Theta</div>
              <div class="text-sm font-mono" :class="(selectedContract.theta || 0) >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ formatValue(selectedContract.theta) }}
              </div>
            </div>
            <div class="text-center">
              <div class="text-[10px] text-terminal-dim mb-1">Vega</div>
              <div class="text-sm font-mono text-terminal-primary">
                {{ formatValue(selectedContract.vega) }}
              </div>
            </div>
            <div class="text-center">
              <div class="text-[10px] text-terminal-dim mb-1">IV</div>
              <div class="text-sm font-mono text-terminal-primary">
                {{ formatPercent(selectedContract.iv) }}
              </div>
            </div>
            <div class="text-center">
              <div class="text-[10px] text-terminal-dim mb-1">最新价</div>
              <div class="text-sm font-mono" :class="(selectedContract.change || 0) >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ formatValue(selectedContract.latest) }}
              </div>
            </div>
          </div>
          <div class="mt-3 pt-3 border-t border-theme-secondary grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
            <div>
              <span class="text-terminal-dim">行权价: </span>
              <span class="text-terminal-primary font-mono">{{ selectedContract.strike }}</span>
            </div>
            <div>
              <span class="text-terminal-dim">涨跌: </span>
              <span :class="(selectedContract.change || 0) >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ formatChange(selectedContract.change) }}
              </span>
            </div>
            <div>
              <span class="text-terminal-dim">涨跌幅: </span>
              <span :class="(selectedContract.change_pct || 0) >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ formatPercent(selectedContract.change_pct) }}
              </span>
            </div>
            <div>
              <span class="text-terminal-dim">持仓量: </span>
              <span class="text-terminal-primary font-mono">{{ formatVolume(selectedContract.open_interest) }}</span>
            </div>
          </div>
        </div>

        <!-- T型报价表 -->
        <div class="terminal-panel border border-theme-secondary rounded-sm flex-1 overflow-hidden flex flex-col">
          <div class="flex items-center justify-between px-4 py-2 border-b border-theme-secondary shrink-0">
            <span class="text-xs text-terminal-dim">{{ chainData.name }} - 期权链</span>
            <span class="text-[10px] text-terminal-dim">更新时间: {{ chainData.update_time || '--' }}</span>
          </div>

          <!-- Table Header -->
          <div class="grid grid-cols-[1fr_80px_1fr] text-[10px] text-terminal-dim border-b border-theme-secondary shrink-0">
            <div class="px-2 py-2 text-center bg-terminal-accent/5">
              <span class="text-bullish font-bold">Call 看涨</span>
            </div>
            <div class="px-2 py-2 text-center border-x border-theme-secondary bg-terminal-accent/10">
              <span class="text-terminal-accent font-bold">行权价</span>
            </div>
            <div class="px-2 py-2 text-center bg-terminal-accent/5">
              <span class="text-bearish font-bold">Put 看跌</span>
            </div>
          </div>

          <!-- Table Body - Scrollable -->
          <div class="flex-1 overflow-y-auto">
            <div
              v-for="(row, index) in tStyleData"
              :key="index"
              class="grid grid-cols-[1fr_80px_1fr] text-[11px] border-b border-theme-secondary/50 hover:bg-terminal-bg/50 cursor-pointer transition"
              :class="{
                'bg-bullish/10': selectedContract?.code === row.call?.code,
                'bg-bearish/10': selectedContract?.code === row.put?.code,
              }"
              @click="handleRowClick(row)"
            >
              <!-- Call Side -->
              <div class="px-2 py-1.5 flex flex-col justify-center">
                <div v-if="row.call" class="flex justify-between items-center">
                  <span class="font-mono text-terminal-primary">{{ formatValue(row.call.latest) }}</span>
                  <span
                    class="text-[10px] font-mono"
                    :class="(row.call.change || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
                  >
                    {{ formatChange(row.call.change) }}
                  </span>
                </div>
                <div v-else class="text-terminal-dim text-center">--</div>
              </div>

              <!-- Strike Price (Center) -->
              <div class="px-2 py-1.5 text-center border-x border-theme-secondary flex flex-col justify-center bg-terminal-bg/30">
                <span class="font-mono text-terminal-accent font-bold">{{ row.strike }}</span>
              </div>

              <!-- Put Side -->
              <div class="px-2 py-1.5 flex flex-col justify-center">
                <div v-if="row.put" class="flex justify-between items-center">
                  <span class="font-mono text-terminal-primary">{{ formatValue(row.put.latest) }}</span>
                  <span
                    class="text-[10px] font-mono"
                    :class="(row.put.change || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
                  >
                    {{ formatChange(row.put.change) }}
                  </span>
                </div>
                <div v-else class="text-terminal-dim text-center">--</div>
              </div>
            </div>
          </div>

          <!-- Greeks Header Row -->
          <div class="border-t border-theme-secondary text-[10px] text-terminal-dim grid grid-cols-[1fr_80px_1fr] shrink-0">
            <div class="px-2 py-1.5 grid grid-cols-5 gap-1">
              <span class="text-center">Delta</span>
              <span class="text-center">Gamma</span>
              <span class="text-center">Theta</span>
              <span class="text-center">Vega</span>
              <span class="text-center">IV</span>
            </div>
            <div class="px-2 py-1.5 border-x border-theme-secondary text-center">-</div>
            <div class="px-2 py-1.5 grid grid-cols-5 gap-1">
              <span class="text-center">Delta</span>
              <span class="text-center">Gamma</span>
              <span class="text-center">Theta</span>
              <span class="text-center">Vega</span>
              <span class="text-center">IV</span>
            </div>
          </div>
        </div>

        <!-- Greeks Data Rows -->
        <div class="terminal-panel border border-theme-secondary rounded-sm overflow-hidden">
          <div class="max-h-[150px] overflow-y-auto">
            <div
              v-for="(row, index) in tStyleData"
              :key="index"
              class="grid grid-cols-[1fr_80px_1fr] text-[10px] border-b border-theme-secondary/50 hover:bg-terminal-bg/50 cursor-pointer transition"
              :class="{
                'bg-bullish/10': selectedContract?.code === row.call?.code,
                'bg-bearish/10': selectedContract?.code === row.put?.code,
              }"
              @click="handleRowClick(row)"
            >
              <!-- Call Greeks -->
              <div v-if="row.call" class="px-2 py-1 grid grid-cols-5 gap-1 text-center">
                <span :class="(row.call.delta || 0) >= 0 ? 'text-bullish' : 'text-bearish'">{{ formatValue(row.call.delta) }}</span>
                <span class="text-terminal-primary">{{ formatValue(row.call.gamma) }}</span>
                <span :class="(row.call.theta || 0) >= 0 ? 'text-bullish' : 'text-bearish'">{{ formatValue(row.call.theta) }}</span>
                <span class="text-terminal-primary">{{ formatValue(row.call.vega) }}</span>
                <span class="text-terminal-primary">{{ formatPercent(row.call.iv) }}</span>
              </div>
              <div v-else class="px-2 py-1 text-center text-terminal-dim">--</div>

              <!-- Strike (empty for greeks row) -->
              <div class="px-2 py-1 border-x border-theme-secondary text-center bg-terminal-bg/30 text-terminal-dim">
                {{ row.strike }}
              </div>

              <!-- Put Greeks -->
              <div v-if="row.put" class="px-2 py-1 grid grid-cols-5 gap-1 text-center">
                <span :class="(row.put.delta || 0) >= 0 ? 'text-bullish' : 'text-bearish'">{{ formatValue(row.put.delta) }}</span>
                <span class="text-terminal-primary">{{ formatValue(row.put.gamma) }}</span>
                <span :class="(row.put.theta || 0) >= 0 ? 'text-bullish' : 'text-bearish'">{{ formatValue(row.put.theta) }}</span>
                <span class="text-terminal-primary">{{ formatValue(row.put.vega) }}</span>
                <span class="text-terminal-primary">{{ formatPercent(row.put.iv) }}</span>
              </div>
              <div v-else class="px-2 py-1 text-center text-terminal-dim">--</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="flex-1 flex flex-col items-center justify-center py-8">
        <div class="text-3xl mb-3">📊</div>
        <div class="text-sm text-terminal-dim">暂无期权数据</div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, shallowRef, computed, onMounted } from 'vue'
import { apiFetch } from '../utils/api.js'

const loading = ref(false)
const error = ref(null)
const chainData = ref(null)
const contracts = ref([])
const selectedSymbol = ref('io2506')
const selectedContract = ref(null)

const tStyleData = computed(() => {
  if (!chainData.value) return []

  const calls = chainData.value.calls || []
  const puts = chainData.value.puts || []

  // Create a map of strike prices to options
  const strikeMap = new Map()

  calls.forEach(call => {
    const strike = call.strike
    if (strike !== null && strike !== undefined) {
      if (!strikeMap.has(strike)) {
        strikeMap.set(strike, { strike, call: null, put: null })
      }
      strikeMap.get(strike).call = call
    }
  })

  puts.forEach(put => {
    const strike = put.strike
    if (strike !== null && strike !== undefined) {
      if (!strikeMap.has(strike)) {
        strikeMap.set(strike, { strike, call: null, put: null })
      }
      strikeMap.get(strike).put = put
    }
  })

  // Sort by strike price
  return Array.from(strikeMap.values()).sort((a, b) => a.strike - b.strike)
})

async function fetchContracts() {
  try {
    const res = await apiFetch('/api/v1/options/contracts?exchange=CFFEX', { timeoutMs: 15000 })
    if (res?.data?.contracts) {
      contracts.value = res.data.contracts
      if (contracts.value.length > 0 && !contracts.value.find(c => c.code === selectedSymbol.value)) {
        selectedSymbol.value = contracts.value[0].code
      }
    }
  } catch (e) {
    console.error('[Options] Failed to fetch contracts:', e)
  }
}

async function fetchChainData() {
  loading.value = true
  error.value = null

  try {
    const res = await apiFetch(`/api/v1/options/cffex/chain?symbol=${selectedSymbol.value}`, { timeoutMs: 30000 })
    if (res?.data) {
      chainData.value = res.data
    } else {
      error.value = '数据格式错误'
    }
  } catch (e) {
    error.value = e.message || '获取期权链失败'
    chainData.value = null
  } finally {
    loading.value = false
  }
}

function handleSymbolChange() {
  selectedContract.value = null
  fetchChainData()
}

function handleRowClick(row) {
  // Prefer selecting the side that was clicked, or the call side if both exist
  const contract = row.call || row.put
  if (contract) {
    selectedContract.value = selectedContract.value?.code === contract.code ? null : contract
  }
}

function formatValue(val) {
  if (val === null || val === undefined) return '--'
  if (typeof val !== 'number') return val
  return val.toFixed(4)
}

function formatPercent(val) {
  if (val === null || val === undefined) return '--'
  if (typeof val !== 'number') return val
  return (val * 100).toFixed(2) + '%'
}

function formatChange(val) {
  if (val === null || val === undefined) return '--'
  if (typeof val !== 'number') return val
  return (val >= 0 ? '+' : '') + val.toFixed(4)
}

function formatVolume(val) {
  if (val === null || val === undefined) return '--'
  if (typeof val !== 'number') return val
  return val.toLocaleString()
}

onMounted(async () => {
  await fetchContracts()
  await fetchChainData()
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

.bg-terminal-accent\/5 {
  background: rgba(15, 82, 186, 0.05);
}

.bg-terminal-accent\/10 {
  background: rgba(15, 82, 186, 0.1);
}

.bg-bullish\/10 {
  background: rgba(230, 57, 70, 0.1);
}

.bg-bearish\/10 {
  background: rgba(26, 147, 111, 0.1);
}

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.terminal-panel {
  background: var(--bg-surface, #1e1e1e);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
