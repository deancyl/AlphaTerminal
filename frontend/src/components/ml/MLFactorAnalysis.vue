<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-theme">
      <h3 class="text-sm font-bold text-theme-primary">因子分析</h3>
    </div>

    <!-- Analysis form -->
    <div class="flex-1 overflow-y-auto p-4">
      <div class="max-w-lg mx-auto space-y-4">
        <!-- Symbol -->
        <div>
          <label class="block text-xs text-theme-muted mb-1">股票代码</label>
          <input
            v-model="form.symbol"
            type="text"
            class="w-full px-3 py-2 text-sm bg-terminal-bg border border-theme-secondary rounded focus:border-terminal-accent focus:outline-none"
            placeholder="例如: sh600519"
          />
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

        <!-- Factors selection -->
        <div>
          <label class="block text-xs text-theme-muted mb-1">分析因子</label>
          <div class="flex flex-wrap gap-2">
            <label v-for="factor in availableFactors" :key="factor" class="flex items-center gap-1 px-2 py-1 rounded border border-theme-secondary hover:bg-theme-hover cursor-pointer">
              <input type="checkbox" v-model="form.factors" :value="factor" class="w-3 h-3" />
              <span class="text-xs">{{ factorLabels[factor] || factor }}</span>
            </label>
          </div>
        </div>

        <!-- Analyze button -->
        <button
          @click="runAnalysis"
          :disabled="analyzing || !isFormValid"
          class="w-full py-2.5 text-sm font-medium rounded transition"
          :class="analyzing || !isFormValid
            ? 'bg-gray-500/20 text-gray-400 cursor-not-allowed'
            : 'bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 border border-terminal-accent/50'"
          type="button"
        >
          {{ analyzing ? '⏳ 分析中...' : '📊 开始分析' }}
        </button>
      </div>

      <!-- Results -->
      <div v-if="result" class="mt-6 max-w-lg mx-auto">
        <div class="text-sm font-bold text-theme-primary mb-3">分析结果</div>

        <!-- Exposures table -->
        <div class="mb-4">
          <div class="text-xs text-theme-muted mb-2">因子暴露</div>
          <table class="w-full text-xs">
            <thead class="border-b border-theme">
              <tr class="text-theme-muted">
                <th class="px-2 py-1 text-left">因子</th>
                <th class="px-2 py-1 text-right">Beta</th>
                <th class="px-2 py-1 text-right">t值</th>
                <th class="px-2 py-1 text-right">p值</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(data, factor) in result.exposures" :key="factor" class="border-b border-theme/30">
                <td class="px-2 py-1">{{ factorLabels[factor] || factor }}</td>
                <td class="px-2 py-1 text-right font-mono">{{ data.beta }}</td>
                <td class="px-2 py-1 text-right font-mono">{{ data.t_stat }}</td>
                <td class="px-2 py-1 text-right font-mono" :class="data.p_value < 0.05 ? 'text-green-400' : 'text-theme-muted'">
                  {{ data.p_value }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- IC values -->
        <div class="mb-4">
          <div class="text-xs text-theme-muted mb-2">信息系数 (IC)</div>
          <table class="w-full text-xs">
            <thead class="border-b border-theme">
              <tr class="text-theme-muted">
                <th class="px-2 py-1 text-left">因子</th>
                <th class="px-2 py-1 text-right">IC</th>
                <th class="px-2 py-1 text-right">Rank IC</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(data, factor) in result.ic_values" :key="factor" class="border-b border-theme/30">
                <td class="px-2 py-1">{{ factorLabels[factor] || factor }}</td>
                <td class="px-2 py-1 text-right font-mono" :class="data.ic > 0.05 ? 'text-green-400' : data.ic < -0.05 ? 'text-red-400' : 'text-theme-muted'">
                  {{ data.ic }}
                </td>
                <td class="px-2 py-1 text-right font-mono" :class="data.rank_ic > 0.05 ? 'text-green-400' : data.rank_ic < -0.05 ? 'text-red-400' : 'text-theme-muted'">
                  {{ data.rank_ic }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Summary -->
        <div class="p-3 rounded border border-theme bg-terminal-bg/50">
          <div class="text-xs text-theme-muted">数据点: {{ result.data_points }}</div>
          <div class="text-xs text-theme-muted">分析时间: {{ result.analysis_date }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiFetch } from '../../utils/api.js'

const availableFactors = ['momentum', 'value', 'quality', 'size', 'volatility']

const factorLabels = {
  momentum: '动量因子',
  value: '价值因子',
  quality: '质量因子',
  size: '规模因子',
  volatility: '波动率因子',
}

const form = ref({
  symbol: 'sh600519',
  start_date: '',
  end_date: '',
  factors: ['momentum', 'value', 'quality'],
})

const analyzing = ref(false)
const result = ref(null)

const isFormValid = computed(() => {
  return form.value.symbol && form.value.start_date && form.value.end_date && form.value.factors.length > 0
})

function setDefaultDates() {
  const end = new Date()
  const start = new Date()
  start.setFullYear(end.getFullYear() - 1)
  
  form.value.end_date = end.toISOString().slice(0, 10)
  form.value.start_date = start.toISOString().slice(0, 10)
}

async function runAnalysis() {
  if (!isFormValid.value) return
  
  analyzing.value = true
  result.value = null
  
  try {
    const res = await apiFetch('/api/v1/ml/factors', {
      method: 'POST',
      body: form.value,
    })
    
    if (res?.code === 0) {
      result.value = res.data
    } else {
      alert(res?.message || '分析失败')
    }
  } catch (e) {
    alert('分析失败: ' + e.message)
  } finally {
    analyzing.value = false
  }
}

onMounted(() => setDefaultDates())
</script>
