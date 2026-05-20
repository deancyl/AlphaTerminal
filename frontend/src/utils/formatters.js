// utils/formatters.js - 公共格式化函数
// 提取自各组件重复的 formatVol/formatAmount/formatPrice

import { safeNumber, safePct } from './typeCoercion.js'

/**
 * 格式化成交量
 * @param {number} v - 成交量
 * @returns {string} 格式化后的字符串
 */
export function formatVol(v) {
  if (v == null) return '--'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿股'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万股'
  return v.toFixed(0) + '股'
}

/**
 * 格式化金额
 * @param {number} v - 金额
 * @returns {string} 格式化后的字符串
 */
export function formatAmount(v) {
  if (v == null) return '--'
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + '亿元'
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + '万元'
  return (v >= 0 ? '+' : '') + v.toFixed(0) + '元'
}

/**
 * 格式化价格
 * @param {number} v - 价格
 * @param {number} digits - 小数位数，默认2
 * @returns {string} 格式化后的字符串
 */
export function formatPrice(v, digits = 2) {
  const num = safeNumber(v, NaN)
  if (Number.isNaN(num)) return '--'
  return num.toFixed(digits)
}

/**
 * 格式化涨跌幅
 * @param {number} v - 涨跌幅（百分比）
 * @returns {string} 格式化后的字符串，带正负号
 */
export function formatChangePct(v) {
  const num = safePct(v, NaN)
  if (Number.isNaN(num)) return '--'
  return (num >= 0 ? '+' : '') + num.toFixed(2) + '%'
}

/**
 * 格式化日期（YYYY-MM-DD）
 * @param {string|Date} d - 日期
 * @returns {string} 格式化后的日期
 */
export function formatDate(d) {
  if (!d) return '--'
  const date = new Date(d)
  if (Number.isNaN(date.getTime())) return '--'
  return date.toISOString().slice(0, 10)
}

/**
 * 格式化时间（HH:MM:SS）
 * @param {string|Date} d - 日期时间
 * @returns {string} 格式化后的时间
 */

/**
 * Format datetime with explicit timezone
 * @param {string|Date} d - Date/datetime string or Date object
 * @param {string} timezone - IANA timezone (default: 'Asia/Shanghai')
 * @returns {string} Formatted datetime string
 */
export function formatDateTimeTZ(d, timezone = 'Asia/Shanghai') {
  if (!d) return '--'
  const date = new Date(d)
  if (Number.isNaN(date.getTime())) return '--'
  
  try {
    const formatter = new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: timezone,
      hour12: false
    })
    return formatter.format(date)
  } catch (e) {
    // Fallback to basic format if timezone is invalid
    return date.toLocaleString('zh-CN')
  }
}

/**
 * Format date with explicit timezone
 * @param {string|Date} d - Date string or Date object
 * @param {string} timezone - IANA timezone (default: 'Asia/Shanghai')
 * @returns {string} Formatted date string (YYYY-MM-DD)
 */
export function formatDateTZ(d, timezone = 'Asia/Shanghai') {
  if (!d) return '--'
  const date = new Date(d)
  if (Number.isNaN(date.getTime())) return '--'
  
  try {
    const formatter = new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      timeZone: timezone
    })
    return formatter.format(date).replace(/\//g, '-')
  } catch (e) {
    return date.toISOString().slice(0, 10)
  }
}

export function formatTime(d) {
  if (!d) return '--'
  const date = new Date(d)
  if (Number.isNaN(date.getTime())) return '--'
  return date.toTimeString().slice(0, 8)
}

// ── 别名导出（兼容旧代码引用）────────────────────────────────────
export { formatPrice as fmtPrice }
export { formatChangePct as fmtPct }
export { formatChangePct as fmtChg }
export { formatAmount as fmtTurnover }

// ── 通用数字格式化（亿/万）────────────────────────────────────────
/**
 * 格式化数字（带亿/万单位）
 * @param {number} num - 数字
 * @returns {string} 格式化后的字符串
 */
export function formatNumber(num) {
  if (num == null) return '--'
  if (Math.abs(num) >= 1e8) return (num / 1e8).toFixed(2) + '亿'
  if (Math.abs(num) >= 1e4) return (num / 1e4).toFixed(2) + '万'
  return num.toFixed(2)
}

/**
 * 格式化金额（带万亿/亿/万单位）
 * @param {number} num - 金额
 * @returns {string} 格式化后的字符串
 */
export function formatMoney(num) {
  if (num == null) return '--'
  if (Math.abs(num) >= 1e12) return (num / 1e12).toFixed(2) + '万亿'
  if (Math.abs(num) >= 1e8) return (num / 1e8).toFixed(2) + '亿'
  if (Math.abs(num) >= 1e4) return (num / 1e4).toFixed(2) + '万'
  return num.toFixed(2)
}

/**
 * 格式化成交量（带股单位）
 * @param {number} num - 成交量（股数）
 * @returns {string} 格式化后的字符串
 */
export function formatVolume(num) {
  if (num == null) return '--'
  if (num >= 1e8) return (num / 1e8).toFixed(2) + '亿股'
  if (num >= 1e4) return (num / 1e4).toFixed(2) + '万股'
  return num.toFixed(0) + '股'
}

/**
 * 格式化股东持股数
 * @param {number|string} num - 持股数
 * @returns {string} 格式化后的字符串
 */
export function formatHolderShares(num) {
  const n = safeNumber(num, NaN)
  if (Number.isNaN(n)) return '--'
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(0)
}

/**
 * 格式化股东持股比例
 * @param {number|string} pct - 持股比例
 * @returns {string} 格式化后的字符串
 */
export function formatHolderPct(pct) {
  const n = safeNumber(pct, NaN)
  if (Number.isNaN(n)) return '--'
  return n.toFixed(2) + '%'
}
