<template>
  <div class="strategy-params-form" role="group" aria-label="策略参数配置">
    <!-- Strategy Selection -->
    <div class="param-group mb-3">
      <label class="text-[10px] text-theme-accent font-bold mb-1.5 block">策略类型</label>
      <select
        v-model="selectedStrategy"
        class="w-full min-h-[44px] bg-terminal-bg/60 border border-theme-secondary rounded-sm px-3 py-2 text-xs text-[var(--color-info)] focus:outline-none focus:border-[var(--color-info)]/60"
        @change="onStrategyChange"
        aria-label="选择策略类型"
      >
        <optgroup label="趋势跟踪">
          <option v-for="s in trendStrategies" :key="s.id" :value="s.id">{{ s.icon }} {{ s.name }}</option>
        </optgroup>
        <optgroup label="均值回归">
          <option v-for="s in meanReversionStrategies" :key="s.id" :value="s.id">{{ s.icon }} {{ s.name }}</option>
        </optgroup>
        <optgroup label="震荡指标">
          <option v-for="s in oscillatorStrategies" :key="s.id" :value="s.id">{{ s.icon }} {{ s.name }}</option>
        </optgroup>
        <optgroup label="突破策略">
          <option v-for="s in breakoutStrategies" :key="s.id" :value="s.id">{{ s.icon }} {{ s.name }}</option>
        </optgroup>
      </select>
    </div>

    <!-- Dynamic Parameters -->
    <div v-if="currentTemplate" class="params-container space-y-3">
      <div class="text-[10px] text-theme-accent font-bold mb-2">⚙️ 策略参数</div>
      
      <div
        v-for="(paramDef, paramKey) in currentTemplate.params"
        :key="paramKey"
        class="param-item"
      >
        <!-- Parameter Label -->
        <div class="flex items-center justify-between mb-1">
          <label class="text-[10px] text-theme-muted">{{ paramDef.description }}</label>
          <span class="text-[10px] font-mono text-[var(--color-info)]">
            {{ formatParamValue(localParams[paramKey], paramDef) }}
          </span>
        </div>

        <!-- Slider for numeric params -->
        <div v-if="paramDef.type === 'int' || paramDef.type === 'float'" class="param-slider">
          <input
            type="range"
            :min="paramDef.min || 0"
            :max="paramDef.max || 100"
            :step="paramDef.step || (paramDef.type === 'float' ? 0.1 : 1)"
            :value="localParams[paramKey] || paramDef.default"
            @input="onParamChange(paramKey, $event.target.value, paramDef)"
            class="w-full h-2 bg-terminal-bg rounded-sm appearance-none cursor-pointer
                   [&::-webkit-slider-thumb]:appearance-none
                   [&::-webkit-slider-thumb]:w-4
                   [&::-webkit-slider-thumb]:h-4
                   [&::-webkit-slider-thumb]:rounded-sm
                   [&::-webkit-slider-thumb]:bg-[var(--color-info)]
                   [&::-webkit-slider-thumb]:cursor-pointer
                   [&::-webkit-slider-thumb]:border-2
                   [&::-webkit-slider-thumb]:border-[var(--color-info-border)]
                   [&::-moz-range-thumb]:w-4
                   [&::-moz-range-thumb]:h-4
                   [&::-moz-range-thumb]:rounded-sm
                   [&::-moz-range-thumb]:bg-[var(--color-info)]
                   [&::-moz-range-thumb]:cursor-pointer
                   [&::-moz-range-thumb]:border-2
                   [&::-moz-range-thumb]:border-[var(--color-info-border)]"
            :aria-label="paramDef.description"
            :aria-valuemin="paramDef.min"
            :aria-valuemax="paramDef.max"
            :aria-valuenow="localParams[paramKey] || paramDef.default"
          />
          <!-- Min/Max labels -->
          <div class="flex justify-between text-[9px] text-theme-muted mt-0.5">
            <span>{{ paramDef.min || 0 }}</span>
            <span>{{ paramDef.max || 100 }}</span>
          </div>
        </div>

        <!-- Dropdown for select params -->
        <div v-else-if="paramDef.type === 'select'" class="param-select">
          <select
            :value="localParams[paramKey] || paramDef.default"
            @change="onParamChange(paramKey, $event.target.value, paramDef)"
            class="w-full min-h-[44px] bg-terminal-bg/60 border border-theme-secondary rounded-sm px-3 py-2 text-xs text-[var(--color-info)] focus:outline-none"
            :aria-label="paramDef.description"
          >
            <option v-for="opt in paramDef.options" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>

        <!-- Text input for other types -->
        <div v-else class="param-input">
          <input
            :type="paramDef.type === 'int' ? 'number' : 'text'"
            :value="localParams[paramKey] || paramDef.default"
            @input="onParamChange(paramKey, $event.target.value, paramDef)"
            class="w-full min-h-[44px] bg-terminal-bg/60 border border-theme-secondary rounded-sm px-3 py-2 text-xs text-[var(--color-info)] focus:outline-none"
            :aria-label="paramDef.description"
          />
        </div>
      </div>

      <!-- Strategy Description -->
      <div class="strategy-hint px-2 py-1.5 rounded-sm bg-[var(--color-info-bg)] border border-[var(--color-info-border)] text-[10px] leading-snug">
        💡 <span class="text-[var(--color-info-light)] font-medium">{{ currentTemplate.name }}：</span>
        <span class="text-[var(--color-info-light)]/70">{{ currentTemplate.description }}</span>
      </div>
    </div>

    <!-- Risk Settings -->
    <div v-if="currentTemplate?.riskSettings" class="risk-settings mt-3 pt-3 border-t border-theme">
      <div class="text-[10px] text-theme-accent font-bold mb-2">🛡️ 风控参数</div>
      <div class="grid grid-cols-2 gap-2">
        <div class="flex items-center justify-between">
          <span class="text-[10px] text-theme-muted">止损%</span>
          <input
            v-model.number="localRiskSettings.stopLossPct"
            type="number"
            min="0.5"
            max="10"
            step="0.5"
            class="bg-terminal-bg/60 border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[10px] text-[var(--color-danger)] w-14 text-center focus:outline-none"
            aria-label="止损百分比"
          />
        </div>
        <div class="flex items-center justify-between">
          <span class="text-[10px] text-theme-muted">止盈%</span>
          <input
            v-model.number="localRiskSettings.takeProfitPct"
            type="number"
            min="1"
            max="20"
            step="1"
            class="bg-terminal-bg/60 border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[10px] text-[var(--color-success)] w-14 text-center focus:outline-none"
            aria-label="止盈百分比"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { STRATEGY_TEMPLATES, getTemplateById, TEMPLATE_CATEGORIES } from '../../templates/strategyTemplates.js'

const props = defineProps({
  strategyId: {
    type: String,
    default: 'ma_cross'
  },
  params: {
    type: Object,
    default: () => ({})
  },
  riskSettings: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:strategyId', 'update:params', 'update:riskSettings', 'strategy-change'])

// Local state
const selectedStrategy = ref(props.strategyId)
const localParams = ref({})
const localRiskSettings = ref({
  stopLossPct: 2.0,
  takeProfitPct: 6.0
})

// Computed: current template
const currentTemplate = computed(() => getTemplateById(selectedStrategy.value))

// Computed: grouped strategies
const trendStrategies = computed(() => 
  Object.values(STRATEGY_TEMPLATES).filter(s => s.category === 'trend')
)
const meanReversionStrategies = computed(() => 
  Object.values(STRATEGY_TEMPLATES).filter(s => s.category === 'mean_reversion')
)
const oscillatorStrategies = computed(() => 
  Object.values(STRATEGY_TEMPLATES).filter(s => s.category === 'oscillator')
)
const breakoutStrategies = computed(() => 
  Object.values(STRATEGY_TEMPLATES).filter(s => s.category === 'breakout')
)

// Initialize params from template defaults
function initParamsFromTemplate(template) {
  if (!template?.params) return
  const defaults = {}
  for (const [key, def] of Object.entries(template.params)) {
    defaults[key] = def.default
  }
  localParams.value = { ...defaults, ...props.params }
}

// Initialize on mount
onMounted(() => {
  initParamsFromTemplate(currentTemplate.value)
  if (props.riskSettings) {
    localRiskSettings.value = { ...localRiskSettings.value, ...props.riskSettings }
  }
})

// Watch for strategy changes
watch(selectedStrategy, (newId) => {
  const template = getTemplateById(newId)
  initParamsFromTemplate(template)
  if (template?.riskSettings) {
    localRiskSettings.value = { ...localRiskSettings.value, ...template.riskSettings }
  }
  emit('update:strategyId', newId)
  emit('strategy-change', { id: newId, template, params: localParams.value })
})

// Watch for external params changes
watch(() => props.params, (newParams) => {
  if (newParams && Object.keys(newParams).length > 0) {
    localParams.value = { ...localParams.value, ...newParams }
  }
}, { deep: true })

// Handle param change
function onParamChange(key, value, def) {
  let parsedValue = value
  if (def.type === 'int') {
    parsedValue = parseInt(value, 10)
    // Clamp to min/max
    if (def.min !== undefined) parsedValue = Math.max(def.min, parsedValue)
    if (def.max !== undefined) parsedValue = Math.min(def.max, parsedValue)
  } else if (def.type === 'float') {
    parsedValue = parseFloat(value)
    if (def.min !== undefined) parsedValue = Math.max(def.min, parsedValue)
    if (def.max !== undefined) parsedValue = Math.min(def.max, parsedValue)
  }
  localParams.value[key] = parsedValue
  emit('update:params', { ...localParams.value })
}

// Handle strategy change from dropdown
function onStrategyChange() {
  // Already handled by watch(selectedStrategy)
}

// Format param value for display
function formatParamValue(value, def) {
  if (def.type === 'float') {
    return value.toFixed(def.step ? 1 : 2)
  }
  return value
}

// Expose for parent component
defineExpose({
  getParams: () => ({ ...localParams.value }),
  getRiskSettings: () => ({ ...localRiskSettings.value }),
  getStrategyId: () => selectedStrategy.value,
  getTemplate: () => currentTemplate.value
})
</script>

<style scoped>
.strategy-params-form {
  padding: var(--space-sm);
}

.param-slider input[type="range"] {
  background: linear-gradient(to right, var(--color-info-bg) 0%, var(--color-info-bg) 100%);
  border-radius: var(--radius-sm);
}

.param-slider input[type="range"]::-webkit-slider-runnable-track {
  height: 4px;
  background: var(--bg-surface-hover);
  border-radius: var(--radius-sm);
}
</style>