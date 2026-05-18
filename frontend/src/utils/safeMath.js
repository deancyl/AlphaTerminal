/**
 * Safe math utilities to prevent division by zero and invalid number operations
 */

export function safeDivide(dividend, divisor, defaultValue = 0) {
  if (divisor === 0 || divisor === null || divisor === undefined || isNaN(divisor)) {
    return defaultValue
  }
  const result = dividend / divisor
  return isNaN(result) || !isFinite(result) ? defaultValue : result
}

export function safePercent(part, total, defaultValue = 0) {
  return safeDivide(part * 100, total, defaultValue)
}

export function safeAverage(values, defaultValue = 0) {
  if (!Array.isArray(values) || values.length === 0) return defaultValue
  const validValues = values.filter(v => v != null && !isNaN(v) && isFinite(v))
  if (validValues.length === 0) return defaultValue
  return validValues.reduce((a, b) => a + b, 0) / validValues.length
}
