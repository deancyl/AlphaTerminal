<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-theme">
      <h3 class="text-sm font-bold text-theme-primary">预测分析</h3>
    </div>

    <!-- Prediction form -->
    <div class="flex-1 overflow-y-auto p-4">
      <div class="max-w-md mx-auto space-y-4">
        <!-- Model selection -->
        <div>
          <label class="block text-xs text-theme-muted mb-1">选择模型</label>
          <select
            v-model="form.model_id"
            class="w-full px-3 py-2 text-sm bg-terminal-bg border border-theme-secondary rounded focus:border-terminal-accent focus:outline-none"
          >
            <option value="">-- 选择模型 --</option>
            <option v-for="m in models" :key="m.model_id" :value="m.model_id">
              {{ m.model_id }} ({{ m.model_type }})
            </option>
          </select>
        </div>

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

        <!-- Predict button -->
        <button
          @click="runPrediction"
          :disabled="predicting || !isFormValid"
          class="w-full py-2.5 text-sm font-medium rounded transition"
          :class="predicting || !isFormValid
            ? 'bg-gray-500/20 text-gray-400 cursor-not-allowed'
            : 'bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 border border-terminal-accent/50'"
          type="button"
        >
          {{ predicting ? '⏳ 预测中...' : '🔮 生成预测' }}
        </button>
      </div>

      <!-- Predictions table -->
      <div v-if="predictions.length > 0" class="mt-6">
        <div class="text-sm font-bold text-theme-primary mb-2">预测结果 (最近20条)</div>
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead class="border-b border-theme">
              <tr class="text-theme-muted">
                <th class="px-2 py-1 text-left">日期</th>
                <th class="px-2 py-1 text-right">收盘价</th>
                <th class="px-2 py-1 text-right">预测值</th>
                <th class="px-2 py-1 text-center">信号</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(p, i) in recentPredictions" :key="i" class="border-b border-theme/30 hover:bg-theme-hover">
                <td class="px-2 py-1 font-mono">{{ p.date }}</td>
                <td class="px-2 py-1 text-right font-mono">{{ p.close?.toFixed(2) }}</td>
                <td class="px-2 py-1 text-right font-mono">{{ p.prediction?.toFixed(4) }}</td>
                <td class="px-2 py-1 text-center">
                  <span
                    class="px-1.5 py-0.5 rounded text-[10px]"
                    :class="{
                      'bg-green-500/20 text-green-400': p.signal === 1,
                      'bg-red-500/20 text-red-400': p.signal === -1,
                      'bg-gray-500/20 text-gray-400': p.signal === 0,
                    }"
                  >
                    {{ p.signal === 1 ? '买入' : p.signal === -1 ? '卖出' : '持有' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiFetch } from '../../utils/api.js'

const form = ref({
  model_id: '',
  symbol: 'sh600519',
  start_date: '',
  end_date: '',
})

const models = ref([])
const predicting = ref(false)
const predictions = ref([])

const isFormValid = computed(() => {
  return form.value.model_id && form.value.symbol && form.value.start_date && form.value.end_date
})

const recentPredictions = computed(() => predictions.value.slice(-20).reverse())

function setDefaultDates() {
  const end = new Date()
  const start = new Date()
  start.setMonth(end.getMonth() - 3)
  
  form.value.end_date = end.toISOString().slice(0, 10)
  form.value.start_date = start.toISOString().slice(0, 10)
}

async function loadModels() {
  try {
    const res = await apiFetch('/api/v1/ml/models')
    models.value = res?.data?.models || []
  } catch (e) {
    console.error('[MLPredictionPanel] Failed to load models:', e)
  }
}

async function runPrediction() {
  if (!isFormValid.value) return
  
  predicting.value = true
  predictions.value = []
  
  try {
    const res = await apiFetch('/api/v1/ml/predict', {
      method: 'POST',
      body: form.value,
    })
    
    if (res?.code === 0) {
      predictions.value = res.data?.predictions || []
    } else {
      alert(res?.message || '预测失败')
    }
  } catch (e) {
    alert('预测失败: ' + e.message)
  } finally {
    predicting.value = false
  }
}

onMounted(() => {
  loadModels()
  setDefaultDates()
})
</script>
