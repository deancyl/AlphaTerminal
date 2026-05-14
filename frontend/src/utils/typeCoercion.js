/**
 * Type-safe number parsing utilities
 */

export function safeNumber(value, fallback = 0) {
  if (value === null || value === undefined) {
    return fallback
  }
  const num = Number(value)
  // Handle NaN and Infinity
  if (Number.isNaN(num) || !Number.isFinite(num)) {
    return fallback
  }
  return num
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
