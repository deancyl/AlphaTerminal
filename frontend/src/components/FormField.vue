<template>
  <div class="form-field">
    <label
      v-if="label"
      :for="inputId"
      class="block text-[var(--text-secondary)] text-xs mb-1"
    >
      {{ label }}
      <span v-if="required" class="text-[var(--color-danger)]">*</span>
    </label>

    <div class="relative">
      <input
        v-if="type !== 'select' && type !== 'textarea'"
        :id="inputId"
        v-bind="$attrs"
        :value="modelValue"
        :type="type"
        :placeholder="placeholder"
        :disabled="disabled"
        :readonly="readonly"
        :maxlength="maxlength"
        :min="min"
        :max="max"
        :step="step"
        :class="inputClasses"
        :aria-invalid="error ? 'true' : 'false'"
        :aria-describedby="error ? `${inputId}-error` : undefined"
        :aria-required="required ? 'true' : undefined"
        @input="handleInput"
        @blur="$emit('blur', $event)"
        @focus="$emit('focus', $event)"
      />

      <textarea
        v-else-if="type === 'textarea'"
        :id="inputId"
        v-bind="$attrs"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :readonly="readonly"
        :maxlength="maxlength"
        :rows="rows"
        :class="inputClasses"
        :aria-invalid="error ? 'true' : 'false'"
        :aria-describedby="error ? `${inputId}-error` : undefined"
        :aria-required="required ? 'true' : undefined"
        @input="handleInput"
        @blur="$emit('blur', $event)"
        @focus="$emit('focus', $event)"
      />

      <select
        v-else
        :id="inputId"
        v-bind="$attrs"
        :value="modelValue"
        :disabled="disabled"
        :class="inputClasses"
        :aria-invalid="error ? 'true' : 'false'"
        :aria-describedby="error ? `${inputId}-error` : undefined"
        :aria-required="required ? 'true' : undefined"
        @change="handleChange"
        @blur="$emit('blur', $event)"
        @focus="$emit('focus', $event)"
      >
        <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
        <option v-for="opt in options" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </option>
        <slot />
      </select>

      <div v-if="showSuccess && !error" class="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none">
        <span class="text-[var(--color-success)] text-sm">✓</span>
      </div>
    </div>

    <div v-if="hint && !error" class="text-[var(--text-muted)] text-xs mt-1">
      {{ hint }}
    </div>

    <div
      v-if="error"
      :id="`${inputId}-error`"
      class="text-[var(--color-danger)] text-xs mt-1 flex items-center gap-1"
      role="alert"
      aria-live="polite"
    >
      <span aria-hidden="true">⚠️</span>
      <span>{{ error }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  modelValue: {
    type: [String, Number],
    default: ''
  },
  label: {
    type: String,
    default: ''
  },
  type: {
    type: String,
    default: 'text'
  },
  placeholder: {
    type: String,
    default: ''
  },
  disabled: {
    type: Boolean,
    default: false
  },
  readonly: {
    type: Boolean,
    default: false
  },
  required: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  },
  hint: {
    type: String,
    default: ''
  },
  id: {
    type: String,
    default: ''
  },
  maxlength: {
    type: Number,
    default: undefined
  },
  min: {
    type: Number,
    default: undefined
  },
  max: {
    type: Number,
    default: undefined
  },
  step: {
    type: Number,
    default: undefined
  },
  rows: {
    type: Number,
    default: 3
  },
  options: {
    type: Array,
    default: () => []
  },
  showSuccess: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'blur', 'focus', 'validate'])

const defaultId = ref(`field-${Math.random().toString(36).slice(2, 9)}`)
const inputId = computed(() => props.id || defaultId.value)

const inputClasses = computed(() => {
  return [
    'w-full bg-[var(--bg-secondary)] rounded-sm px-3 py-2 text-theme-primary mt-1',
    'border transition-colors focus:outline-none',
    props.error
      ? 'border-[var(--color-danger)] focus:border-[var(--color-danger)]'
      : 'border-[var(--border-primary)] focus:border-terminal-accent/60',
    props.disabled ? 'opacity-50 cursor-not-allowed' : '',
    props.type === 'textarea' ? 'resize-none' : ''
  ]
})

function handleInput(event) {
  const value = props.type === 'number' ? Number(event.target.value) : event.target.value
  emit('update:modelValue', value)
}

function handleChange(event) {
  emit('update:modelValue', event.target.value)
}
</script>

<style scoped>
.form-field {
  @apply block;
}
</style>
