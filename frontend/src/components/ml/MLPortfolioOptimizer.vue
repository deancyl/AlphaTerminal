<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-theme">
      <h3 class="text-sm font-bold text-theme-primary">组合优化</h3>
    </div>

    <!-- Optimization form -->
    <div class="flex-1 overflow-y-auto p-4">
      <div class="max-w-lg mx-auto space-y-4">
        <!-- Symbols -->
        <div>
          <label class="block text-xs text-theme-muted mb-1">股票列表 (逗号分隔)</label>
          <textarea
            v-model="symbolsText"
            rows="2"
            class="w-full px-3 py-2 text-sm bg-terminal-bg border border-theme-secondary rounded focus:border-terminal-accent focus:outline-none"
            placeholder="sh600519, sh600036, sh601318"
          ></textarea>
        </div>

        <!-- Date range -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs text-theme-muted mb-1">开始日期</label>
            <input
              v-model="form.start_date"
              type="date"
              class="w-full px-3 py-2 text-sm bg-terminal-bg border border-theme-secondary rounded focus:border-terminal-accent focus:outline-none"
            />
          </div>
          <div>
            <label class="block text-xs text-theme-muted mb-1">结束日期</label>
            <input
              v-model="form.end_date"
              type="date"
              class="w-full px-3 py-2 text-sm bg-terminal-bg border border-theme-secondary rounded focus:border-terminal-accent focus:outline-none"
            />
          </div>
        </div>

        <!-- Method -->
        <div>
          <label class="block text-xs text-theme-muted mb-1">优化方法</label>
          <select
            v-model="form.method"
            class="w-full px-3 py-2 text-sm bg-terminal-bg border border-theme-secondary rounded focus:border-terminal-accent focus:outline-none"
          >
            <option value="mvo">均值-方差优化 (MVO)</option>
            <option value="gmv">全局最小方差 (GMV)</option>
            <option value="rp">风险平价 (RP)</option>
            <option value="inv">逆波动率 (INV)</option>
          </select>
        </div>

        <!-- Risk aversion -->
        <div v-if="form.method === 'mvo'">
          <label class="block text-xs text-theme-muted mb-1">风险厌恶系数 (0-10)</label>
          <input
            v-model.number="form.risk_aversion"
            type="range"
            min="0"
            max="10"
            step="0.5"
            class="w-full"
          />
          <div class="text-xs text-theme-tertiary text-center">{{ form.risk_aversion }}</div>
        </div>

        <!-- Max weight -->
        <div>
          <label class="block text-xs text-theme-muted mb-1">最大权重限制</label>
          <input
            v-model.number="form.max_weight"
            type="number"
            min="0.1"
            max="1"
            step="0.1"
            class="w-full px-3 py-2 text-sm bg-terminal-bg border border-theme-secondary rounded focus:border-terminal-accent focus:outline-none"
          />
        </div>

        <!-- Optimize button -->
        <button
          @click="runOptimization"
          :disabled="optimizing || !isFormValid"
          class="w-full py-2.5 text-sm font-medium rounded transition"
          :class="optimizing || !isFormValid
            ? 'bg-gray-500/20 text-gray-400 cursor-not-allowed'
            : 'bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 border border-terminal-accent/50'"
          type="button"
        >
          {{ optimizing ? '⏳ 优化中...' : '⚖️ 开始优化' }}
        </button>
      </div>

      <!-- Results -->
      <div v-if="result" class="mt-6 max-w-lg mx-auto">
        <div class="text-sm font-bold text-theme-primary mb-3">优化结果</div>
        
        <!-- Metrics -->
        <div class="grid grid-cols-3 gap-2 mb-4">
          <div class="p-2 rounded border border-theme bg-terminal-bg/50 text-center">
            <div class="text-[10px] text-theme-muted">预期收益</div>
            <div class="text-sm font-mono text-green-400">{{ result.expected_return }}%</div>
          </div>
          <div class="p-2 rounded border border-theme bg-terminal-bg/50 text-center">
            <div class="text-[10px] text-theme-muted">预期波动</div>
            <div class="text-sm font-mono text-yellow-400">{{ result.expected_volatility }}%</div>
          </div>
          <div class="p-2 rounded border border-theme bg-terminal-bg/50 text-center">
            <div class="text-[10px] text-theme-muted">夏普比率</div>
            <div class="text-sm font-mono text-terminal-accent">{{ result.sharpe_ratio }}</div>
          </div>
        </div>

        <!-- Weights -->
        <div class="text-xs text-theme-muted mb-2">权重分配</div>
        <div class="space-y-1">
          <div v-for="(weight, symbol) in result.weights" :key="symbol" class="flex items-center gap-2">
            <span class="w-24 font-mono text-theme-secondary">{{ symbol }}</span>
            <div class="flex-1 h-2 bg-gray-700 rounded overflow-hidden">
              <div class="h-full bg-terminal-accent" :style="{ width: (weight * 100) + '%' }"></div>
            </div>
            <span class="w-16 text-right font-mono">{{ (weight * 100).toFixed(1) }}%</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiFetch } from '../../utils/api.js'

const symbolsText = ref('sh600519, sh600036, sh601318')

const form = ref({
  start_date: '',
  end_date: '',
  method: 'mvo',
  risk_aversion: 1.0,
  max_weight: 0.3,
})

const optimizing = ref(false)
const result = ref(null)

const isFormValid = computed(() => {
  return symbolsText.value.trim() && form.value.start_date && form.value.end_date
})

function setDefaultDates() {
  const end = new Date()
  const start = new Date()
  start.setFullYear(end.getFullYear() - 1)
  
  form.value.end_date = end.toISOString().slice(0, 10)
  form.value.start_date = start.toISOString().slice(0, 10)
}

async function runOptimization() {
  if (!isFormValid.value) return
  
  const symbols = symbolsText.value.split(',').map(s => s.trim()).filter(s => s)
  if (symbols.length < 2) {
    alert('请输入至少2个股票代码')
    return
  }
  
  optimizing.value = true
  result.value = null
  
  try {
    const res = await apiFetch('/api/v1/ml/optimize', {
      method: 'POST',
      body: {
        symbols,
        ...form.value,
      },
    })
    
    if (res?.code === 0) {
      result.value = res.data
    } else {
      alert(res?.message || '优化失败')
    }
  } catch (e) {
    alert('优化失败: ' + e.message)
  } finally {
    optimizing.value = false
  }
}

onMounted(() => setDefaultDates())
</script>
