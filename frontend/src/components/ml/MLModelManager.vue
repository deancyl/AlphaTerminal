<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-theme">
      <h3 class="text-sm font-bold text-theme-primary">ML模型列表</h3>
      <div class="flex gap-2">
        <button
          @click="refreshModels"
          :disabled="loading"
          class="px-3 py-1.5 text-xs rounded border border-theme-secondary hover:bg-theme-hover transition"
          type="button"
        >
          {{ loading ? '加载中...' : '🔄 刷新' }}
        </button>
      </div>
    </div>

    <!-- Model list -->
    <div class="flex-1 overflow-y-auto p-4">
      <div v-if="loading" class="flex items-center justify-center h-32">
        <div class="text-theme-muted text-sm">加载模型中...</div>
      </div>
      
      <div v-else-if="models.length === 0" class="flex flex-col items-center justify-center h-32 text-theme-muted">
        <div class="text-2xl mb-2">📭</div>
        <div class="text-sm">暂无模型，请先训练模型</div>
      </div>
      
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        <div
          v-for="model in models"
          :key="model.model_id"
          class="p-3 rounded border border-theme bg-terminal-bg/50 hover:border-terminal-accent/50 transition cursor-pointer"
          @click="selectModel(model)"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="font-mono text-sm text-terminal-accent">{{ model.model_id }}</span>
            <span
              class="px-1.5 py-0.5 text-[10px] rounded"
              :class="model.is_loaded ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'"
            >
              {{ model.is_loaded ? '已加载' : '未加载' }}
            </span>
          </div>
          <div class="text-xs text-theme-muted space-y-1">
            <div>类型: <span class="text-theme-secondary">{{ model.model_type }}</span></div>
            <div>特征: <span class="text-theme-secondary">{{ model.feature_set }}</span></div>
            <div v-if="model.metrics && Object.keys(model.metrics).length > 0" class="text-[10px] text-theme-tertiary">
              MSE: {{ model.metrics.mse?.toFixed(4) || '-' }} | MAE: {{ model.metrics.mae?.toFixed(4) || '-' }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Selected model details -->
    <div v-if="selectedModel" class="shrink-0 border-t border-theme bg-terminal-panel/50 p-3">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-bold text-terminal-accent">{{ selectedModel.model_id }}</span>
        <button
          @click="deleteModel(selectedModel.model_id)"
          class="px-2 py-1 text-xs text-red-400 hover:bg-red-500/20 rounded transition"
          type="button"
        >
          🗑️ 删除
        </button>
      </div>
      <div class="text-xs text-theme-muted grid grid-cols-2 gap-2">
        <div>创建时间: {{ formatDate(selectedModel.created_at) }}</div>
        <div>更新时间: {{ formatDate(selectedModel.updated_at) }}</div>
        <div>提供商: {{ selectedModel.provider }}</div>
        <div>特征集: {{ selectedModel.feature_set }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiFetch } from '../../utils/api.js'

const models = ref([])
const loading = ref(false)
const selectedModel = ref(null)

async function refreshModels() {
  loading.value = true
  try {
    const res = await apiFetch('/api/v1/ml/models')
    models.value = res?.data?.models || []
  } catch (e) {
    console.error('[MLModelManager] Failed to fetch models:', e)
  } finally {
    loading.value = false
  }
}

function selectModel(model) {
  selectedModel.value = model
}

async function deleteModel(modelId) {
  if (!confirm(`确定删除模型 ${modelId}?`)) return
  
  try {
    await apiFetch(`/api/v1/ml/models/${modelId}`, { method: 'DELETE' })
    models.value = models.value.filter(m => m.model_id !== modelId)
    if (selectedModel.value?.model_id === modelId) {
      selectedModel.value = null
    }
  } catch (e) {
    console.error('[MLModelManager] Failed to delete model:', e)
    alert('删除失败: ' + e.message)
  }
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN', { 
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}

onMounted(() => refreshModels())
</script>
