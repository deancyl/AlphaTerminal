import { reactive, computed, ref, watch } from 'vue'

const DEFAULT_MESSAGES = {
  required: '此字段为必填项',
  email: '请输入有效的邮箱地址',
  min: '最小值为 {min}',
  max: '最大值为 {max}',
  range: '值应在 {min} 到 {max} 之间',
  pattern: '格式不正确',
  length: '长度应在 {min} 到 {max} 之间',
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function formatMessage(template, params) {
  if (typeof template !== 'string') return template
  return template.replace(/\{(\w+)\}/g, (_, key) => params[key] ?? '')
}

export function createValidators() {
  return {
    required: (value, options = {}) => {
      const { message = DEFAULT_MESSAGES.required, strict = false } = options
      const isEmpty = value === null || value === undefined || value === ''
      const isWhitespace = typeof value === 'string' && value.trim() === ''
      const isStrictEmpty = strict && (Array.isArray(value) && value.length === 0)
      const valid = !isEmpty && !isWhitespace && !isStrictEmpty
      return { valid, message: valid ? '' : message }
    },

    pattern: (value, pattern, options = {}) => {
      const { message = DEFAULT_MESSAGES.pattern } = options
      if (!value) return { valid: true, message: '' }
      const valid = pattern.test(value)
      return { valid, message: valid ? '' : message }
    },

    min: (value, minValue, options = {}) => {
      const { message = DEFAULT_MESSAGES.min } = options
      if (!value && value !== 0) return { valid: true, message: '' }
      const numValue = typeof value === 'number' ? value : 
                        (typeof value === 'string' && !isNaN(Number(value)) ? Number(value) : value.length)
      const valid = numValue >= minValue
      return { valid, message: valid ? '' : formatMessage(message, { min: minValue }) }
    },

    max: (value, maxValue, options = {}) => {
      const { message = DEFAULT_MESSAGES.max } = options
      if (!value && value !== 0) return { valid: true, message: '' }
      const numValue = typeof value === 'number' ? value : 
                        (typeof value === 'string' && !isNaN(Number(value)) ? Number(value) : value.length)
      const valid = numValue <= maxValue
      return { valid, message: valid ? '' : formatMessage(message, { max: maxValue }) }
    },

    range: (value, [minVal, maxVal], options = {}) => {
      const { message = DEFAULT_MESSAGES.range } = options
      if (!value && value !== 0) return { valid: true, message: '' }
      const numValue = Number(value)
      const valid = numValue >= minVal && numValue <= maxVal
      return { valid, message: valid ? '' : formatMessage(message, { min: minVal, max: maxVal }) }
    },

    email: (value, options = {}) => {
      const { message = DEFAULT_MESSAGES.email } = options
      if (!value) return { valid: true, message: '' }
      const valid = EMAIL_PATTERN.test(value)
      return { valid, message: valid ? '' : message }
    },

    length: (value, [minLen, maxLen], options = {}) => {
      const { message = DEFAULT_MESSAGES.length } = options
      if (!value) return { valid: true, message: '' }
      const len = String(value).length
      const valid = len >= minLen && len <= maxLen
      return { valid, message: valid ? '' : formatMessage(message, { min: minLen, max: maxLen }) }
    },

    custom: (value, validatorFn, options = {}) => {
      const result = validatorFn(value)
      if (typeof result === 'boolean') {
        return { valid: result, message: result ? '' : (options.message || '验证失败') }
      }
      return result
    },
  }
}

const validators = createValidators()

function resolveRule(rule) {
  if (typeof rule === 'string') {
    return { name: rule, params: undefined, options: {} }
  }
  if (typeof rule === 'object') {
    const hasCustomValidate = rule.validate !== undefined
    return {
      name: hasCustomValidate ? 'custom' : rule.name,
      params: rule.params,
      options: { message: rule.message, ...rule.options },
      validate: rule.validate,
    }
  }
  return { name: 'custom', params: rule, options: {} }
}

async function runValidation(value, rule) {
  const resolved = resolveRule(rule)
  
  if (resolved.validate) {
    return validators.custom(value, resolved.validate, resolved.options)
  }
  
  const validatorFn = validators[resolved.name]
  if (!validatorFn) {
    console.warn(`[useValidation] Unknown validator: ${resolved.name}`)
    return { valid: true, message: '' }
  }
  
  const params = resolved.params !== undefined ? resolved.params : resolved.options
  return validatorFn(value, params, resolved.options)
}

export function useValidation(fieldConfig) {
  const fields = reactive({})
  const debounceTimers = {}
  
  for (const [name, config] of Object.entries(fieldConfig)) {
    fields[name] = reactive({
      value: config.value ?? '',
      error: '',
      touched: false,
      dirty: false,
      rules: config.rules || [],
      validateOnInput: config.validateOnInput ?? false,
      validateOnBlur: config.validateOnBlur ?? true,
      debounce: config.debounce ?? 0,
    })
  }

  function field(name) {
    const f = fields[name]
    if (!f) return null
    return {
      get value() { return f.value },
      set value(v) { f.value = v },
      get error() { return f.error },
      get touched() { return f.touched },
      get dirty() { return f.dirty },
      get showError() { return Boolean(f.touched && f.error) },
    }
  }

  async function validateField(name) {
    const f = fields[name]
    if (!f) return true
    
    f.touched = true
    
    for (const rule of f.rules) {
      const result = await runValidation(f.value, rule)
      if (!result.valid) {
        f.error = result.message
        return false
      }
    }
    
    f.error = ''
    return true
  }

  function handleInput(name, value) {
    const f = fields[name]
    if (!f) return
    
    const oldValue = f.value
    f.value = value
    f.dirty = oldValue !== value
    
    if (f.validateOnInput) {
      if (f.debounce > 0) {
        if (debounceTimers[name]) {
          clearTimeout(debounceTimers[name])
        }
        debounceTimers[name] = setTimeout(() => {
          validateField(name)
          delete debounceTimers[name]
        }, f.debounce)
      } else {
        return validateField(name)
      }
    } else if (f.touched && f.error) {
      return validateField(name)
    }
  }

  function handleBlur(name) {
    const f = fields[name]
    if (!f) return
    
    if (f.validateOnBlur) {
      return validateField(name)
    }
  }

  async function validateAll() {
    let allValid = true
    for (const name of Object.keys(fields)) {
      const valid = await validateField(name)
      if (!valid) allValid = false
    }
    return allValid
  }

  const isValid = computed(() => {
    return Object.values(fields).every(f => !f.error || !f.touched)
  })

  const isDirty = computed(() => {
    return Object.values(fields).some(f => f.dirty)
  })

  function resetField(name) {
    const f = fields[name]
    if (!f) return
    
    f.value = ''
    f.error = ''
    f.touched = false
    f.dirty = false
  }

  function resetAll() {
    for (const name of Object.keys(fields)) {
      resetField(name)
    }
  }

  function getAriaAttributes(name) {
    const f = fields[name]
    if (!f) return {}
    
    const errorId = `error-${name}`
    const hasError = f.touched && f.error
    
    return {
      'aria-invalid': hasError ? 'true' : 'false',
      'aria-describedby': hasError ? errorId : undefined,
      'aria-errormessage': hasError ? errorId : undefined,
    }
  }

  function showError(name) {
    const f = fields[name]
    return f?.touched && f?.error
  }

  function setFieldValue(name, value) {
    const f = fields[name]
    if (f) f.value = value
  }

  function setFieldError(name, error) {
    const f = fields[name]
    if (f) {
      f.error = error
      f.touched = true
    }
  }

  return {
    fields,
    field,
    validateField,
    validateAll,
    handleInput,
    handleBlur,
    resetField,
    resetAll,
    isValid,
    isDirty,
    getAriaAttributes,
    showError,
    setFieldValue,
    setFieldError,
    validators,
  }
}

export async function validateForm(data, schema) {
  const errors = {}
  let valid = true
  
  for (const [name, rules] of Object.entries(schema)) {
    const value = data[name]
    
    for (const rule of rules) {
      const result = await runValidation(value, rule)
      if (!result.valid) {
        errors[name] = result.message
        valid = false
        break
      }
    }
  }
  
  return { valid, errors }
}

export { validators, DEFAULT_MESSAGES }