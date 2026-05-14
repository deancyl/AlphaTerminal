import { computed } from 'vue'
import { safeDivide, safePercent, safeAverage } from '../utils/safeMath.js'

export function useSafeNumber(valueRef, defaultValue = 0) {
  const safeValue = computed(() => {
    const v = valueRef.value
    if (v == null || isNaN(v) || !isFinite(v)) return defaultValue
    return v
  })

  const isValid = computed(() => {
    const v = valueRef.value
    return v != null && !isNaN(v) && isFinite(v)
  })

  return {
    safeValue,
    isValid,
    safeDivide: (divisor, defaultVal = 0) => safeDivide(safeValue.value, divisor, defaultVal),
    safePercentFn: (total, defaultVal = 0) => safePercent(safeValue.value, total, defaultVal),
  }
}

export function formatSafeNumber(value, decimals = 2, defaultStr = '--') {
  if (value == null || isNaN(value) || !isFinite(value)) return defaultStr
  return value.toFixed(decimals)
}

export function formatSafePercent(value, decimals = 2, defaultStr = '--') {
  if (value == null || isNaN(value) || !isFinite(value)) return defaultStr
  return value.toFixed(decimals) + '%'
}
