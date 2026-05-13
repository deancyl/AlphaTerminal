/**
 * Type-safe number parsing utilities
 */

export function safeNumber(value, fallback = 0) {
  if (value === null || value === undefined) {
    return fallback
  }
  const num = Number(value)
  return Number.isNaN(num) ? fallback : num
}

export function safeInt(value, fallback = 0) {
  const num = safeNumber(value, fallback)
  return Math.round(num)
}

export function safePct(value, fallback = 0) {
  const num = safeNumber(value, fallback)
  return Math.max(-100, Math.min(100, num))
}

export function safePrice(value, fallback = 0) {
  const num = safeNumber(value, fallback)
  return Math.max(0, num)
}
