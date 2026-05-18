<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-bold text-theme-primary">🤖 多模型配置矩阵</h2>
        <p class="text-xs text-theme-muted mt-1">管理多个 LLM Provider 和模型，支持并发控制和成本监控</p>
      </div>
      <div class="flex gap-2">
        <button
          class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm hover:bg-terminal-accent/25 transition-colors"
          @click="$emit('refresh')"
        >
          🔄 刷新
        </button>
        <button
          class="px-4 py-2 bg-[var(--color-primary)] text-theme-inverse rounded-sm text-sm hover:bg-[var(--color-primary-hover)] transition-colors"
          @click="showAddModelModal = true"
        >
          ➕ 添加模型
        </button>
      </div>
    </div>

    <!-- Provider Tabs -->
    <div class="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
      <button
        v-for="provider in providerList"
        :key="provider.id"
        class="px-4 py-2 rounded-sm text-sm whitespace-nowrap transition-all"
        :class="activeProvider === provider.id
          ? 'bg-terminal-accent/20 text-terminal-accent border border-terminal-accent/40'
          : 'bg-theme-surface text-theme-secondary border border-theme hover:bg-theme-hover hover:text-theme-primary'"
        @click="activeProvider = provider.id"
      >
        {{ provider.icon }} {{ provider.label }}
        <span
          v-if="provider.modelCount > 0"
          class="ml-1.5 px-1.5 py-0.5 rounded-sm text-[10px] bg-terminal-accent/30"
        >
          {{ provider.modelCount }}
        </span>
      </button>
    </div>

    <!-- Loading State -->
    <LoadingSpinner v-if="loading" text="加载模型配置..." />

    <!-- Error State -->
    <ErrorDisplay v-else-if="error" :error="error" :retry="loadModels" />

    <!-- Model Cards -->
    <div v-else class="space-y-4">
      <template v-if="currentModels.length > 0">
        <div
          v-for="model in currentModels"
          :key="model.model_id"
          class="bg-theme-surface border border-theme rounded-sm overflow-hidden"
        >
          <!-- Model Header -->
          <div
            class="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-theme-hover transition-colors"
            @click="toggleModelExpand(model.model_id)"
          >
            <div class="flex items-center gap-3">
              <div class="flex items-center gap-2">
                <span class="text-sm font-medium text-theme-primary">{{ model.model_id }}</span>
                <span
                  v-if="model.is_default"
                  class="px-2 py-0.5 rounded-sm text-[10px] bg-[var(--color-primary-bg)] text-[var(--color-primary)] border border-[var(--color-primary-border)]"
                >
                  默认
                </span>
                <span
                  v-if="!model.enabled"
                  class="px-2 py-0.5 rounded-sm text-[10px] bg-[var(--color-warning-bg)] text-[var(--color-warning)] border border-[var(--color-warning-border)]"
                >
                  已禁用
                </span>
              </div>
            </div>
            <div class="flex items-center gap-4">
              <div class="text-xs text-theme-muted hidden sm:flex items-center gap-4">
                <span>上下文: {{ formatContext(model.context_length) }}</span>
                <span>并发: {{ model.concurrency_limit || 10 }}</span>
                <span v-if="model.pricing_input">输入: {{ model.pricing_input }}</span>
                <span v-if="model.pricing_output">输出: {{ model.pricing_output }}</span>
              </div>
              <button
                class="text-xs text-theme-muted hover:text-theme-primary transition-colors"
                @click.stop="toggleModelExpand(model.model_id)"
              >
                {{ expandedModels.has(model.model_id) ? '🔼 收起' : '🔽 展开' }}
              </button>
            </div>
          </div>

          <!-- Expanded Config -->
          <div
            v-if="expandedModels.has(model.model_id)"
            class="px-4 py-4 border-t border-theme bg-theme-hover/30"
          >
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <!-- API Key -->
              <div>
                <label class="text-[11px] text-theme-muted mb-1.5 block">API Key</label>
                <div class="relative">
                  <input
                    v-model="modelConfigs[model.model_id].api_key"
                    :type="modelConfigs[model.model_id].show_key ? 'text' : 'password'"
                    class="w-full bg-theme-surface border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary
                           focus:outline-none focus:border-terminal-accent/60 pr-10"
                    placeholder="sk-..."
                  >
                  <button
                    class="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-theme-muted hover:text-terminal-accent"
                    @click="modelConfigs[model.model_id].show_key = !modelConfigs[model.model_id].show_key"
                  >
                    {{ modelConfigs[model.model_id].show_key ? '🙈' : '👁' }}
                  </button>
                </div>
              </div>

              <!-- Base URL -->
              <div>
                <label class="text-[11px] text-theme-muted mb-1.5 block">Base URL</label>
                <input
                  v-model="modelConfigs[model.model_id].base_url"
                  class="w-full bg-theme-surface border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary
                         focus:outline-none focus:border-terminal-accent/60"
                  :placeholder="model.default_base_url || 'https://api.example.com/v1'"
                >
              </div>

              <!-- Concurrency Limit -->
              <div>
                <label class="text-[11px] text-theme-muted mb-1.5 block">并发限制</label>
                <input
                  v-model.number="modelConfigs[model.model_id].concurrency_limit"
                  type="number"
                  min="1"
                  max="100"
                  class="w-full bg-theme-surface border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary
                         focus:outline-none focus:border-terminal-accent/60"
                  placeholder="10"
                >
              </div>

              <!-- Context Length -->
              <div>
                <label class="text-[11px] text-theme-muted mb-1.5 block">上下文长度 (tokens)</label>
                <input
                  v-model.number="modelConfigs[model.model_id].context_length"
                  type="number"
                  min="1024"
                  max="1000000"
                  class="w-full bg-theme-surface border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary
                         focus:outline-none focus:border-terminal-accent/60"
                  placeholder="128000"
                >
              </div>
            </div>

            <!-- Actions -->
            <div class="flex flex-wrap gap-3 mt-4">
              <button
                class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm hover:bg-terminal-accent/25 transition-colors"
                :disabled="modelConfigs[model.model_id].testing"
                @click="testModelConnection(model.model_id)"
              >
                {{ modelConfigs[model.model_id].testing ? '⏳ 测试中...' : '🔗 测试连接' }}
              </button>
              <button
                class="px-4 py-2 bg-terminal-accent rounded-sm text-sm text-theme-inverse hover:bg-terminal-accent/80 transition-colors"
                :disabled="modelConfigs[model.model_id].saving"
                @click="saveModelConfig(model.model_id)"
              >
                {{ modelConfigs[model.model_id].saving ? '💾 保存中...' : '💾 保存配置' }}
              </button>
              <button
                v-if="!model.is_default"
                class="px-4 py-2 bg-[var(--color-primary-bg)] text-[var(--color-primary)] rounded-sm text-sm hover:bg-[var(--color-primary-bg)]/80 transition-colors border border-[var(--color-primary-border)]"
                @click="setAsDefault(model.model_id)"
              >
                ⭐ 设为默认
              </button>
              <button
                class="px-4 py-2 rounded-sm text-sm transition-colors"
                :class="model.enabled
                  ? 'bg-[var(--color-warning-bg)] text-[var(--color-warning)] border border-[var(--color-warning-border)] hover:bg-[var(--color-warning-bg)]/80'
                  : 'bg-[var(--color-success-bg)] text-[var(--color-success)] border border-[var(--color-success-border)] hover:bg-[var(--color-success-bg)]/80'"
                @click="toggleModelEnabled(model.model_id)"
              >
                {{ model.enabled ? '🚫 禁用模型' : '✅ 启用模型' }}
              </button>
              <span
                v-if="modelConfigs[model.model_id].message"
                class="flex items-center text-[11px]"
                :class="modelConfigs[model.model_id].message_ok ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'"
              >
                {{ modelConfigs[model.model_id].message }}
              </span>
            </div>
          </div>
        </div>
      </template>

      <!-- Empty State -->
      <div
        v-else
        class="p-8 text-center bg-theme-surface border border-theme rounded-sm"
      >
        <div class="text-4xl mb-3">📭</div>
        <div class="text-sm text-theme-secondary">该 Provider 下暂无配置的模型</div>
        <button
          class="mt-4 px-4 py-2 bg-terminal-accent text-theme-inverse rounded-sm text-sm hover:bg-terminal-accent/80 transition-colors"
          @click="showAddModelModal = true"
        >
          ➕ 添加第一个模型
        </button>
      </div>
    </div>

    <!-- Add Model Modal -->
    <div
      v-if="showAddModelModal"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="showAddModelModal = false"
    >
      <div class="bg-theme-surface border border-theme rounded-sm p-6 max-w-lg w-full mx-4">
        <h3 class="text-lg font-bold text-theme-primary mb-4">➕ 添加新模型</h3>

        <div class="space-y-4">
          <div>
            <label class="text-[11px] text-theme-muted mb-1.5 block">Provider</label>
            <select
              v-model="newModel.provider"
              class="w-full bg-theme-surface border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary
                     focus:outline-none focus:border-terminal-accent/60 cursor-pointer"
            >
              <option v-for="p in providerList" :key="p.id" :value="p.id">{{ p.icon }} {{ p.label }}</option>
            </select>
          </div>

          <div>
            <label class="text-[11px] text-theme-muted mb-1.5 block">模型 ID</label>
            <input
              v-model="newModel.model_id"
              class="w-full bg-theme-surface border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary
                     focus:outline-none focus:border-terminal-accent/60"
              placeholder="gpt-4o, deepseek-chat, qwen-plus..."
            >
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="text-[11px] text-theme-muted mb-1.5 block">API Key</label>
              <input
                v-model="newModel.api_key"
                type="password"
                class="w-full bg-theme-surface border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary
                       focus:outline-none focus:border-terminal-accent/60"
                placeholder="sk-..."
              >
            </div>
            <div>
              <label class="text-[11px] text-theme-muted mb-1.5 block">Base URL</label>
              <input
                v-model="newModel.base_url"
                class="w-full bg-theme-surface border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary
                       focus:outline-none focus:border-terminal-accent/60"
                placeholder="https://api.example.com/v1"
              >
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="text-[11px] text-theme-muted mb-1.5 block">并发限制</label>
              <input
                v-model.number="newModel.concurrency_limit"
                type="number"
                min="1"
                max="100"
                class="w-full bg-theme-surface border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary
                       focus:outline-none focus:border-terminal-accent/60"
                placeholder="10"
              >
            </div>
            <div>
              <label class="text-[11px] text-theme-muted mb-1.5 block">上下文长度</label>
              <input
                v-model.number="newModel.context_length"
                type="number"
                min="1024"
                class="w-full bg-theme-surface border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary
                       focus:outline-none focus:border-terminal-accent/60"
                placeholder="128000"
              >
            </div>
          </div>
        </div>

        <div class="flex gap-3 justify-end mt-6">
          <button
            class="px-4 py-2 bg-theme-hover text-theme-secondary rounded-sm text-sm hover:bg-theme-hover/80 transition-colors"
            @click="showAddModelModal = false"
          >
            取消
          </button>
          <button
            class="px-4 py-2 bg-terminal-accent text-theme-inverse rounded-sm text-sm hover:bg-terminal-accent/80 transition-colors"
            :disabled="!newModel.model_id || addingModel"
            @click="addNewModel"
          >
            {{ addingModel ? '添加中...' : '添加模型' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { apiFetch } from '../../utils/api.js'
import { toast } from '../../composables/useToast.js'
import LoadingSpinner from '../f9/LoadingSpinner.vue'
import ErrorDisplay from '../f9/ErrorDisplay.vue'

const emit = defineEmits(['refresh'])

// State
const loading = ref(true)
const error = ref(null)
const activeProvider = ref('deepseek')
const expandedModels = ref(new Set())
const showAddModelModal = ref(false)
const addingModel = ref(false)

// Provider list with icons
const providerList = ref([
  { id: 'deepseek', label: 'DeepSeek', icon: '🧠', modelCount: 0 },
  { id: 'qianwen', label: '通义千问', icon: '🌐', modelCount: 0 },
  { id: 'openai', label: 'OpenAI', icon: '🤖', modelCount: 0 },
  { id: 'anthropic', label: 'Anthropic', icon: '🎭', modelCount: 0 },
  { id: 'siliconflow', label: '硅基流动', icon: '💎', modelCount: 0 },
  { id: 'opencode', label: 'OpenCode', icon: '🚀', modelCount: 0 },
])

// Models data from API
const modelsData = ref({})

// Model configs for editing
const modelConfigs = reactive({})

// New model form
const newModel = reactive({
  provider: 'deepseek',
  model_id: '',
  api_key: '',
  base_url: '',
  concurrency_limit: 10,
  context_length: 128000,
})

// Computed
const currentModels = computed(() => {
  return modelsData.value[activeProvider.value] || []
})

// Methods
function formatContext(tokens) {
  if (!tokens) return '未知'
  if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(1)}M`
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(0)}K`
  return tokens.toString()
}

function toggleModelExpand(modelId) {
  if (expandedModels.value.has(modelId)) {
    expandedModels.value.delete(modelId)
  } else {
    expandedModels.value.add(modelId)
  }
}

async function loadModels() {
  loading.value = true
  error.value = null
  try {
    const data = await apiFetch('/api/v1/admin/models/')
    modelsData.value = data.models || {}

    // Update provider counts
    for (const provider of providerList.value) {
      provider.modelCount = (modelsData.value[provider.id] || []).length
    }

    // Initialize model configs
    for (const [provider, models] of Object.entries(modelsData.value)) {
      for (const model of models) {
        if (!modelConfigs[model.model_id]) {
          modelConfigs[model.model_id] = {
            api_key: model.api_key || '',
            base_url: model.base_url || '',
            concurrency_limit: model.concurrency_limit || 10,
            context_length: model.context_length || 128000,
            show_key: false,
            saving: false,
            testing: false,
            message: '',
            message_ok: false,
          }
        }
      }
    }
  } catch (e) {
    error.value = e.message || '加载模型配置失败'
  } finally {
    loading.value = false
  }
}

async function testModelConnection(modelId) {
  const config = modelConfigs[modelId]
  if (!config.api_key) {
    config.message = '⚠️ 请先输入 API Key'
    config.message_ok = false
    return
  }

  config.testing = true
  config.message = ''
  try {
    const result = await apiFetch('/api/v1/admin/models/test', {
      method: 'POST',
      body: JSON.stringify({
        provider: activeProvider.value,
        model_id: modelId,
        api_key: config.api_key,
        base_url: config.base_url,
      }),
    })
    config.message = '✅ 连接成功'
    config.message_ok = true
  } catch (e) {
    config.message = '❌ ' + (e.message || '连接失败')
    config.message_ok = false
  } finally {
    config.testing = false
  }
  setTimeout(() => { config.message = '' }, 6000)
}

async function saveModelConfig(modelId) {
  const config = modelConfigs[modelId]
  config.saving = true
  config.message = ''
  try {
    await apiFetch('/api/v1/admin/models/update', {
      method: 'POST',
      body: JSON.stringify({
        provider: activeProvider.value,
        model_id: modelId,
        api_key: config.api_key,
        base_url: config.base_url,
        concurrency_limit: config.concurrency_limit,
        context_length: config.context_length,
      }),
    })
    config.message = '✅ 已保存'
    config.message_ok = true
    toast.success('配置已保存', `模型 ${modelId} 配置已更新`)
  } catch (e) {
    config.message = '❌ ' + (e.message || '保存失败')
    config.message_ok = false
  } finally {
    config.saving = false
  }
  setTimeout(() => { config.message = '' }, 4000)
}

async function setAsDefault(modelId) {
  try {
    await apiFetch('/api/v1/admin/models/default', {
      method: 'POST',
      body: JSON.stringify({
        provider: activeProvider.value,
        model_id: modelId,
      }),
    })
    toast.success('默认模型已设置', `${modelId} 已设为默认模型`)
    await loadModels()
  } catch (e) {
    toast.error('设置失败', e.message || '无法设置默认模型')
  }
}

async function toggleModelEnabled(modelId) {
  const model = currentModels.value.find(m => m.model_id === modelId)
  if (!model) return

  try {
    await apiFetch('/api/v1/admin/models/toggle', {
      method: 'POST',
      body: JSON.stringify({
        provider: activeProvider.value,
        model_id: modelId,
        enabled: !model.enabled,
      }),
    })
    toast.success(model.enabled ? '模型已禁用' : '模型已启用', `${modelId} 状态已更新`)
    await loadModels()
  } catch (e) {
    toast.error('操作失败', e.message || '无法切换模型状态')
  }
}

async function addNewModel() {
  if (!newModel.model_id) return

  addingModel.value = true
  try {
    await apiFetch('/api/v1/admin/models/add', {
      method: 'POST',
      body: JSON.stringify({
        provider: newModel.provider,
        model_id: newModel.model_id,
        api_key: newModel.api_key,
        base_url: newModel.base_url,
        concurrency_limit: newModel.concurrency_limit,
        context_length: newModel.context_length,
      }),
    })
    toast.success('模型已添加', `${newModel.model_id} 已添加到 ${newModel.provider}`)
    showAddModelModal.value = false
    activeProvider.value = newModel.provider
    // Reset form
    newModel.model_id = ''
    newModel.api_key = ''
    newModel.base_url = ''
    newModel.concurrency_limit = 10
    newModel.context_length = 128000
    await loadModels()
  } catch (e) {
    toast.error('添加失败', e.message || '无法添加模型')
  } finally {
    addingModel.value = false
  }
}

// Lifecycle
onMounted(() => {
  loadModels()
})

// Watch for refresh events
watch(() => emit, () => {
  loadModels()
})
</script>
