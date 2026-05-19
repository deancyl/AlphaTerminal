<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="show"
        class="factor-param-modal__backdrop"
        @click.self="$emit('close')"
      >
        <div class="factor-param-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div class="factor-param-modal__header">
            <h3 id="modal-title" class="factor-param-modal__title">
              <span class="factor-param-modal__icon">⚙️</span>
              {{ factor?.name || '因子参数' }}
            </h3>
            <button
              class="factor-param-modal__close"
              @click="$emit('close')"
              aria-label="关闭"
            >
              ✕
            </button>
          </div>
          
          <div class="factor-param-modal__body">
            <div v-if="!paramDefs.length" class="factor-param-modal__empty">
              该因子无可配置参数
            </div>
            
            <div v-else class="factor-param-modal__fields">
              <div
                v-for="param in paramDefs"
                :key="param.key"
                class="factor-param-modal__field"
              >
                <label class="factor-param-modal__label">
                  {{ param.label }}
                  <span class="factor-param-modal__hint">默认: {{ param.default }}</span>
                </label>
                <input
                  v-model.number="localParams[param.key]"
                  type="number"
                  :min="param.min"
                  :max="param.max"
                  :step="param.step"
                  :placeholder="String(param.default)"
                  class="factor-param-modal__input"
                  @input="validateParam(param.key)"
                />
                <span v-if="errors[param.key]" class="factor-param-modal__error">
                  {{ errors[param.key] }}
                </span>
              </div>
            </div>
          </div>
          
          <div class="factor-param-modal__footer">
            <button
              class="factor-param-modal__btn factor-param-modal__btn--secondary"
              @click="resetToDefaults"
            >
              重置默认
            </button>
            <button
              class="factor-param-modal__btn factor-param-modal__btn--primary"
              :disabled="hasErrors"
              @click="applyParams"
            >
              应用
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false,
  },
  factor: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['close', 'apply'])

// Parameter definitions for each factor type
const PARAM_DEFINITIONS = {
  rsi_oversold: [
    { key: 'period', label: 'RSI周期', default: 14, min: 5, max: 50, step: 1 },
    { key: 'threshold', label: '超卖阈值', default: 30, min: 10, max: 40, step: 1 },
  ],
  breakout_ma: [
    { key: 'period', label: '均线周期', default: 20, min: 5, max: 60, step: 1 },
  ],
  volume_surge: [
    { key: 'multiplier', label: '放量倍数', default: 2.0, min: 1.5, max: 5.0, step: 0.1 },
    { key: 'period', label: '比较周期', default: 20, min: 5, max: 60, step: 1 },
  ],
  macd_golden_cross: [
    { key: 'fast', label: '快线周期', default: 12, min: 5, max: 20, step: 1 },
    { key: 'slow', label: '慢线周期', default: 26, min: 15, max: 40, step: 1 },
    { key: 'signal', label: '信号线周期', default: 9, min: 5, max: 15, step: 1 },
  ],
}

const localParams = ref({})
const errors = ref({})

const paramDefs = computed(() => {
  if (!props.factor?.id) return []
  return PARAM_DEFINITIONS[props.factor.id] || []
})

const hasErrors = computed(() => {
  return Object.values(errors.value).some(e => e !== '')
})

// Initialize local params when factor changes
watch(() => props.factor, (newFactor) => {
  if (newFactor) {
    // Start with existing params or defaults
    const defaults = {}
    for (const def of paramDefs.value) {
      defaults[def.key] = def.default
    }
    localParams.value = { ...defaults, ...newFactor.params }
    errors.value = {}
  }
}, { immediate: true })

function validateParam(key) {
  const def = paramDefs.value.find(d => d.key === key)
  if (!def) return
  
  const value = localParams.value[key]
  
  if (value === '' || value === null || value === undefined) {
    errors.value[key] = ''
    return
  }
  
  if (typeof value !== 'number' || isNaN(value)) {
    errors.value[key] = '请输入有效数字'
    return
  }
  
  if (value < def.min) {
    errors.value[key] = `最小值: ${def.min}`
    return
  }
  
  if (value > def.max) {
    errors.value[key] = `最大值: ${def.max}`
    return
  }
  
  // Special validation for MACD
  if (props.factor?.id === 'macd_golden_cross') {
    const fast = localParams.value.fast
    const slow = localParams.value.slow
    if (key === 'fast' && fast >= slow) {
      errors.value[key] = '快线必须小于慢线'
      return
    }
    if (key === 'slow' && slow <= fast) {
      errors.value[key] = '慢线必须大于快线'
      return
    }
  }
  
  errors.value[key] = ''
}

function resetToDefaults() {
  for (const def of paramDefs.value) {
    localParams.value[def.key] = def.default
  }
  errors.value = {}
}

function applyParams() {
  // Validate all params first
  for (const def of paramDefs.value) {
    validateParam(def.key)
  }
  
  if (hasErrors.value) return
  
  // Clean params - only include defined values
  const cleanParams = {}
  for (const def of paramDefs.value) {
    const value = localParams.value[def.key]
    if (value !== '' && value !== null && value !== undefined) {
      cleanParams[def.key] = value
    }
  }
  
  emit('apply', {
    factorId: props.factor.id,
    params: cleanParams,
  })
}
</script>

<style scoped>
.factor-param-modal__backdrop {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal-backdrop);
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--bg-overlay);
  backdrop-filter: blur(4px);
}

.factor-param-modal {
  width: 90%;
  max-width: 360px;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  animation: modalSlideIn 0.2s ease-out;
}

@keyframes modalSlideIn {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.factor-param-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-md);
  border-bottom: 1px solid var(--border-base);
}

.factor-param-modal__title {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.factor-param-modal__icon {
  font-size: 16px;
}

.factor-param-modal__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  font-size: 12px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--easing-default);
}

.factor-param-modal__close:hover {
  color: var(--text-primary);
  background-color: var(--bg-surface-hover);
}

.factor-param-modal__body {
  padding: var(--space-md);
}

.factor-param-modal__empty {
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  padding: var(--space-lg);
}

.factor-param-modal__fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.factor-param-modal__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.factor-param-modal__label {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.factor-param-modal__hint {
  font-size: 10px;
  font-weight: 400;
  color: var(--text-muted);
}

.factor-param-modal__input {
  width: 100%;
  height: var(--input-height);
  padding: 0 var(--space-sm);
  font-size: 13px;
  font-family: var(--font-mono);
  color: var(--text-primary);
  background-color: var(--bg-base);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  transition: border-color var(--duration-fast) var(--easing-default);
}

.factor-param-modal__input:hover {
  border-color: var(--border-hover);
}

.factor-param-modal__input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-bg);
}

.factor-param-modal__input::placeholder {
  color: var(--text-placeholder);
  font-family: var(--font-sans);
}

.factor-param-modal__error {
  font-size: 10px;
  color: var(--color-danger);
}

.factor-param-modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
  padding: var(--space-md);
  border-top: 1px solid var(--border-base);
}

.factor-param-modal__btn {
  padding: var(--space-xs) var(--space-md);
  font-size: 12px;
  font-weight: 500;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--easing-default);
}

.factor-param-modal__btn--secondary {
  color: var(--text-secondary);
  background-color: var(--bg-surface-hover);
  border: 1px solid var(--border-base);
}

.factor-param-modal__btn--secondary:hover {
  color: var(--text-primary);
  border-color: var(--border-hover);
}

.factor-param-modal__btn--primary {
  color: var(--text-inverse);
  background-color: var(--color-primary);
  border: 1px solid var(--color-primary);
}

.factor-param-modal__btn--primary:hover:not(:disabled) {
  background-color: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}

.factor-param-modal__btn--primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Transition */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .factor-param-modal,
.modal-leave-active .factor-param-modal {
  transition: transform 0.2s ease;
}

.modal-enter-from .factor-param-modal,
.modal-leave-to .factor-param-modal {
  transform: translateY(-20px);
}
</style>
