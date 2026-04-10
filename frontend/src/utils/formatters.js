/**
 * 数值格式化工具 - 统一小数位数显示
 */

/**
 * 统一保留两位小数
 * @param {number|string} v 
 * @returns {string}
 */
export function fmt2(v) {
  if (v === null || v === undefined || v === '' || v === '-') return '--'
  const n = parseFloat(v)
  if (Number.isNaN(n)) return '--'
  return n.toFixed(2)
}

/**
 * 价格（保留两位小数）
 */
export function fmtPrice(v) {
  return fmt2(v)
}

/**
 * 涨跌幅（保留两位小数 + %）
 */
export function fmtPct(v) {
  if (v === null || v === undefined || v === '') return '--'
  const n = parseFloat(v)
  if (Number.isNaN(n)) return '--'
  const sign = n >= 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}%`
}

/**
 * 涨跌额（保留两位小数）
 */
export function fmtChg(v) {
  if (v === null || v === undefined || v === '') return '--'
  const n = parseFloat(v)
  if (Number.isNaN(n)) return '--'
  const sign = n >= 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}`
}

/**
 * 换手率（保留两位小数 + %）
 */
export function fmtTurnover(v) {
  return fmt2(v) + '%'
}

/**
 * 成交量/成交额（大数字简化）
 */
export function fmtVolume(v) {
  if (!v) return '--'
  const n = parseFloat(v)
  if (Number.isNaN(n)) return '--'
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(2)
}
