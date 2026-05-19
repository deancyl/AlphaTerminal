<template>
  <div class="condition-builder">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-semibold text-theme-primary flex items-center gap-2">
        <span>🎨</span> 可视化策略构建器
      </h3>
      <div class="flex items-center gap-2">
        <button
          @click="switchToCodeMode"
          class="px-3 py-1.5 text-xs rounded-lg border border-theme-secondary text-theme-secondary hover:border-blue-500/50 hover:text-blue-400 transition"
        >
          切换到代码模式
        </button>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div class="lg:col-span-1 space-y-3">
        <div class="text-xs text-theme-muted mb-2">选择策略类型</div>
        <div class="space-y-2">
          <div
            v-for="template in availableTemplates"
            :key="template.id"
            @click="selectTemplate(template.id)"
            class="p-3 rounded-lg border cursor-pointer transition-all"
            :class="selectedTemplateId === template.id
              ? 'bg-blue-500/20 border-blue-500/50 text-blue-400'
              : 'bg-terminal-bg border-theme-secondary hover:border-blue-500/30 text-theme-secondary'"
          >
            <div class="flex items-center gap-2">
              <span class="text-lg">{{ template.icon }}</span>
              <div>
                <div class="text-sm font-medium">{{ template.name }}</div>
                <div class="text-[10px] text-theme-muted">{{ template.description }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="lg:col-span-2 space-y-4">
        <div v-if="!selectedTemplateId" class="flex items-center justify-center h-64 text-theme-muted text-sm">
          请先选择左侧的策略类型
        </div>

        <template v-else>
          <div class="bg-terminal-bg border border-theme rounded-lg p-4">
            <div class="flex items-center justify-between mb-3">
              <div class="text-sm font-medium text-theme-primary">
                {{ currentTemplate?.name }}
              </div>
              <span class="px-2 py-0.5 text-xs rounded bg-purple-500/20 text-purple-400 border border-purple-500/30">
                {{ getCategoryLabel(currentTemplate?.category) }}
              </span>
            </div>

            <div class="space-y-4">
              <div class="text-xs text-theme-muted mb-2">策略参数</div>
              <div class="grid grid-cols-2 gap-3">
                <div v-for="(paramConfig, paramKey) in currentTemplate?.defaultParams" :key="paramKey">
                  <label class="text-xs text-theme-muted block mb-1.5">{{ paramConfig.label }}</label>
                  <input
                    v-model.number="localParams[paramKey]"
                    type="number"
                    :min="paramConfig.min"
                    :max="paramConfig.max"
                    :step="paramConfig.step || 1"
                    class="w-full bg-terminal-panel border border-theme rounded-lg px-3 py-2 text-sm text-theme-primary focus:outline-none focus:border-blue-500/50"
                  />
                </div>
              </div>
            </div>
          </div>

          <div class="bg-terminal-bg border border-theme rounded-lg p-4">
            <div class="text-xs text-theme-muted mb-3">条件预览</div>
            <div class="space-y-2">
              <div
                v-for="(condition, idx) in currentAST?.conditions"
                :key="idx"
                class="flex items-center gap-2 p-2 rounded bg-terminal-panel/50"
              >
                <span class="text-lg">{{ getIndicatorIcon(condition.indicator) }}</span>
                <span class="text-sm text-theme-primary">
                  {{ getConditionDescription(condition) }}
                </span>
              </div>
            </div>
          </div>

          <div class="bg-terminal-bg border border-theme rounded-lg p-4">
            <div class="text-xs text-theme-muted mb-3">交易动作</div>
            <div class="flex flex-wrap gap-2">
              <div
                v-for="(action, idx) in currentAST?.actions"
                :key="idx"
                class="px-3 py-1.5 rounded-lg text-xs font-medium"
                :class="action.type === 'buy'
                  ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                  : 'bg-red-500/20 text-red-400 border border-red-500/30'"
              >
                {{ action.type === 'buy' ? '📈 买入' : '📉 卖出' }}
                <span v-if="action.quantity" class="ml-1 opacity-70">×{{ action.quantity }}股</span>
              </div>
            </div>
          </div>

          <!-- Validation Errors Display -->
          <div 
            v-if="validationErrors.length > 0" 
            class="validation-errors p-3 bg-bear/10 border border-bear/30 rounded-lg"
            role="alert"
            aria-live="polite"
          >
            <div class="flex items-start gap-2">
              <span class="text-bear text-sm">⚠️</span>
              <div class="flex-1">
                <div class="text-xs text-bear font-medium mb-1">条件冲突</div>
                <div 
                  v-for="error in validationErrors" 
                  :key="error" 
                  class="text-bear text-sm"
                >
                  {{ error }}
                </div>
              </div>
            </div>
          </div>

          <div class="flex items-center gap-3">
            <button
              @click="generateCode"
              :disabled="isGenerating || validationErrors.length > 0"
              class="flex-1 px-4 py-2.5 text-sm rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium transition flex items-center justify-center gap-2"
            >
              <span v-if="isGenerating" class="animate-spin">⏳</span>
              <span v-else>⚙️</span>
              {{ isGenerating ? '生成中...' : '生成策略代码' }}
            </button>
            <button
              @click="resetBuilder"
              class="px-4 py-2.5 text-sm rounded-lg border border-theme-secondary text-theme-secondary hover:border-red-500/50 hover:text-red-400 transition"
            >
              重置
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import {
  STRATEGY_TEMPLATES,
  createStrategyFromTemplate,
  getAvailableTemplates,
  INDICATOR_TYPES,
  DIRECTION_TYPES,
} from '@/schemas/strategy-ast.js'
import { apiFetch } from '@/utils/api.js'
import { useToast } from '@/composables/useToast.js'
import { logger } from '@/utils/logger.js'

// ── Mutually Exclusive Condition Pairs ───────────────────────────────────────
/**
 * Pairs of condition types that cannot be enabled simultaneously.
 * These represent logically contradictory conditions that would result in no matches.
 */
const MUTUALLY_EXCLUSIVE = [
  ['MA_cross_up', 'MA_cross_down'],
  ['RSI_overbought', 'RSI_oversold'],
  ['MACD_golden_cross', 'MACD_death_cross'],
  ['price_above_MA', 'price_below_MA'],
  ['volume_surge', 'volume_decline'],
]

/**
 * Validate conditions for mutually exclusive pairs
 * @param {Array} conditions - Array of condition objects with { type, enabled }
 * @returns {string[]} Array of error messages
 */
function validateConditions(conditions) {
  const errors = []
  const activeTypes = conditions.filter(c => c.enabled).map(c => c.type)
  
  for (const [type1, type2] of MUTUALLY_EXCLUSIVE) {
    if (activeTypes.includes(type1) && activeTypes.includes(type2)) {
      errors.push(`条件冲突: "${type1}" 和 "${type2}" 不能同时启用`)
    }
  }
  
  return errors
}

const emit = defineEmits(['code-generated', 'switch-to-code'])

const { success: toastSuccess, error: toastError } = useToast()

const availableTemplates = getAvailableTemplates()
const selectedTemplateId = ref(null)
const localParams = ref({})
const isGenerating = ref(false)

const currentTemplate = computed(() => {
  return selectedTemplateId.value ? STRATEGY_TEMPLATES[selectedTemplateId.value] : null
})

const currentAST = computed(() => {
  if (!selectedTemplateId.value) return null
  try {
    return createStrategyFromTemplate(selectedTemplateId.value, localParams.value)
  } catch (e) {
    logger.error('[ConditionBuilder] Failed to create AST:', e)
    return null
  }
})

/**
 * Computed validation errors for mutually exclusive conditions.
 * Returns an array of error messages when conflicting conditions are enabled.
 */
const validationErrors = computed(() => {
  // For future multi-condition support, validate against enabled conditions
  // Currently, templates define single conditions, but this prepares for expansion
  if (!currentAST.value?.conditions) return []
  
  // Map AST conditions to validation format
  const conditionsForValidation = currentAST.value.conditions.map(cond => ({
    type: getConditionTypeKey(cond),
    enabled: true, // All template conditions are enabled by default
  }))
  
  return validateConditions(conditionsForValidation)
})

/**
 * Convert AST condition to validation type key.
 * Maps indicator + direction to the validation type used in MUTUALLY_EXCLUSIVE.
 */
function getConditionTypeKey(condition) {
  const { indicator, direction, threshold, band } = condition
  
  // MA conditions
  if (indicator === INDICATOR_TYPES.MA) {
    if (direction === DIRECTION_TYPES.CROSS_ABOVE) return 'MA_cross_up'
    if (direction === DIRECTION_TYPES.CROSS_BELOW) return 'MA_cross_down'
    if (direction === DIRECTION_TYPES.ABOVE) return 'price_above_MA'
    if (direction === DIRECTION_TYPES.BELOW) return 'price_below_MA'
  }
  
  // RSI conditions
  if (indicator === INDICATOR_TYPES.RSI) {
    if (direction === DIRECTION_TYPES.ABOVE && threshold >= 70) return 'RSI_overbought'
    if (direction === DIRECTION_TYPES.BELOW && threshold <= 30) return 'RSI_oversold'
  }
  
  // MACD conditions
  if (indicator === INDICATOR_TYPES.MACD) {
    if (direction === DIRECTION_TYPES.CROSS_ABOVE) return 'MACD_golden_cross'
    if (direction === DIRECTION_TYPES.CROSS_BELOW) return 'MACD_death_cross'
  }
  
  // Volume conditions
  if (indicator === INDICATOR_TYPES.VOLUME) {
    if (direction === DIRECTION_TYPES.ABOVE) return 'volume_surge'
    if (direction === DIRECTION_TYPES.BELOW) return 'volume_decline'
  }
  
  // Return a unique key for non-conflicting conditions
  return `${indicator}_${direction}`
}

watch(selectedTemplateId, (newId) => {
  if (newId && STRATEGY_TEMPLATES[newId]?.defaultParams) {
    const defaults = {}
    Object.entries(STRATEGY_TEMPLATES[newId].defaultParams).forEach(([key, config]) => {
      defaults[key] = config.default
    })
    localParams.value = defaults
  }
})

function selectTemplate(templateId) {
  selectedTemplateId.value = templateId
}

function getIndicatorIcon(indicator) {
  const icons = {
    [INDICATOR_TYPES.MA]: '📈',
    [INDICATOR_TYPES.MACD]: '📊',
    [INDICATOR_TYPES.RSI]: '📉',
    [INDICATOR_TYPES.BOLL]: '📏',
    [INDICATOR_TYPES.VOLUME]: '📦',
  }
  return icons[indicator] || '❓'
}

function getCategoryLabel(category) {
  const labels = {
    trend: '趋势策略',
    oscillator: '震荡指标',
    volatility: '波动率策略',
    volume: '成交量策略',
  }
  return labels[category] || category
}

function getConditionDescription(condition) {
  const indicatorNames = {
    [INDICATOR_TYPES.MA]: '均线',
    [INDICATOR_TYPES.MACD]: 'MACD',
    [INDICATOR_TYPES.RSI]: 'RSI',
    [INDICATOR_TYPES.BOLL]: '布林带',
    [INDICATOR_TYPES.VOLUME]: '成交量',
  }

  const directionNames = {
    [DIRECTION_TYPES.CROSS_ABOVE]: '上穿',
    [DIRECTION_TYPES.CROSS_BELOW]: '下穿',
    [DIRECTION_TYPES.ABOVE]: '高于',
    [DIRECTION_TYPES.BELOW]: '低于',
  }

  const name = indicatorNames[condition.indicator] || condition.indicator
  const dir = directionNames[condition.direction] || condition.direction

  if (condition.indicator === INDICATOR_TYPES.MA) {
    return `MA${condition.params?.fast_period} ${dir} MA${condition.params?.slow_period}`
  }
  if (condition.indicator === INDICATOR_TYPES.MACD) {
    return `DIF ${dir} DEA`
  }
  if (condition.indicator === INDICATOR_TYPES.RSI) {
    return `RSI(${condition.params?.period}) ${dir} ${condition.threshold}`
  }
  if (condition.indicator === INDICATOR_TYPES.BOLL) {
    const band = condition.band === 'upper' ? '上轨' : condition.band === 'lower' ? '下轨' : '中轨'
    return `价格 ${dir} 布林${band}`
  }
  if (condition.indicator === INDICATOR_TYPES.VOLUME) {
    return `成交量 ${dir} ${condition.multiplier}倍均量`
  }

  return `${name} ${dir}`
}

async function generateCode() {
  if (!currentAST.value) {
    toastError('生成失败', '请先选择策略类型')
    return
  }

  isGenerating.value = true

  try {
    const response = await apiFetch('/api/v1/strategy/compile', {
      method: 'POST',
      body: currentAST.value,
    })

    if (response?.code) {
      emit('code-generated', response.code)
      toastSuccess('生成成功', '策略代码已生成')
    } else {
      throw new Error('Invalid response from server')
    }
  } catch (err) {
    logger.error('[ConditionBuilder] Generate code failed:', err)
    toastError('生成失败', err.message || '无法生成策略代码')
  } finally {
    isGenerating.value = false
  }
}

function resetBuilder() {
  selectedTemplateId.value = null
  localParams.value = {}
}

function switchToCodeMode() {
  emit('switch-to-code')
}

defineExpose({
  generateCode,
  resetBuilder,
  currentAST,
})
</script>

<style scoped>
.condition-builder {
  min-height: 400px;
}
</style>
