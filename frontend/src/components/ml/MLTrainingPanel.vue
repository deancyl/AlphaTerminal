<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-theme">
      <h3 class="text-sm font-bold text-theme-primary">模型训练</h3>
    </div>

    <!-- Training form -->
    <div class="flex-1 overflow-y-auto p-4">
      <div class="max-w-md mx-auto space-y-4">
        <!-- Model ID -->
        <div>
          <label class="block text-xs text-theme-muted mb-1">模型ID</label>
          <input
            v-model="form.model_id"
            type="text"
            class="w-full px-3 py-2 text-sm bg-terminal-bg border border-theme-secondary rounded focus:border-terminal-accent focus:outline-none"
            placeholder="例如: lightgbm_600519_v1"
          />
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

        <!-- Feature set -->
        <div>
          <label class="block text-xs text-theme-muted mb-1">特征集</label>
          <select
            v-model="form.feature_set"
            class="w-full px-3 py-2 text-sm bg-terminal-bg border border-theme-secondary rounded focus:border-terminal-accent focus:outline-none"
          >
            <option value="Alpha158">Alpha158 (推荐)</option>
            <option value="Alpha360">Alpha360</option>
          </select>
        </div>

        <!-- Target -->
        <div>
          <label class="block text-xs text-theme-muted mb-1">预测目标</label>
          <select
            v-model="form.target"
            class="w-full px-3 py-2 text-sm bg-terminal-bg border border-theme-secondary rounded focus:border-terminal-accent focus:outline-none"
          >
            <option value="return_1d">1日收益率</option>
            <option value="return_5d">5日收益率</option>
          </select>
        </div>

        <!-- Train button -->
        <button
          @click="trainModel"
          :disabled="training || !isFormValid"
          class="w-full py-2.5 text-sm font-medium rounded transition"
          :class="training || !isFormValid
            ? 'bg-gray-500/20 text-gray-400 cursor-not-allowed'
            : 'bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 border border-terminal-accent/50'"
          type="button"
        >
          {{ training ? '⏳ 训练中...' : '🎓 开始训练' }}
        </button>

        <!-- Status message -->
        <div v-if="statusMsg" class="text-xs text-center" :class="statusMsg.startsWith('✅') ? 'text-green-400' : 'text-red-400'">
          {{ statusMsg }}
        </div>
      </div>
    </div>

    <!-- Training result -->
    <div v-if="trainingResult" class="shrink-0 border-t border-theme bg-terminal-panel/50 p-3">
      <div class="text-sm font-bold text-terminal-accent mb-2">训练结果</div>
      <div class="grid grid-cols-2 gap-2 text-xs">
        <div>训练样本: <span class="text-theme-secondary">{{ trainingResult.train_samples }}</span></div>
        <div>测试样本: <span class="text-theme-secondary">{{ trainingResult.test_samples }}</span></div>
        <div>MSE: <span class="text-theme-secondary">{{ trainingResult.metrics?.mse?.toFixed(6) }}</span></div>
        <div>MAE: <span class="text-theme-secondary">{{ trainingResult.metrics?.mae?.toFixed(6) }}</span></div>
        <div>特征数: <span class="text-theme-secondary">{{ trainingResult.feature_count }}</span></div>
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
  feature_set: 'Alpha158',
  target: 'return_1d',
})

const training = ref(false)
const statusMsg = ref('')
const trainingResult = ref(null)

const isFormValid = computed(() => {
  return form.value.model_id && 
         form.value.symbol && 
         form.value.start_date && 
         form.value.end_date
})

function setDefaultDates() {
  const end = new Date()
  const start = new Date()
  start.setFullYear(end.getFullYear() - 1)
  
  form.value.end_date = end.toISOString().slice(0, 10)
  form.value.start_date = start.toISOString().slice(0, 10)
}

async function trainModel() {
  if (!isFormValid.value) return
  
  training.value = true
  statusMsg.value = ''
  trainingResult.value = null
  
  try {
    const res = await apiFetch('/api/v1/ml/train', {
      method: 'POST',
      body: form.value,
    })
    
    if (res?.code === 0) {
      trainingResult.value = res.data
      statusMsg.value = '✅ 训练完成'
    } else {
      statusMsg.value = '❌ ' + (res?.message || '训练失败')
    }
  } catch (e) {
    statusMsg.value = '❌ ' + e.message
  } finally {
    training.value = false
  }
}

onMounted(() => setDefaultDates())
</script>
