/**
 * symbols.js — 前端符号规范化与映射
 * 与后端 _normalize_symbol / _SYMBOL_REGISTRY 保持一致
 */

// A股：第一位判断交易所
function _aSharePrefix(code) {
  const s = String(code).replace(/\D/g, '')
  if (s.length !== 6) return 'sz'
  if (s.startsWith('6') || s.startsWith('9')) return 'sh'
  return 'sz'
}

// 全局注册表（运行时从 /api/v1/market/symbols 填充）
let _registry = []
let _lookup = {}

export const MARKET_PREFIX = {
  AShare: ['sh', 'sz'],
  US:     ['us'],
  HK:     ['hk'],
  JP:     ['jp'],
  Macro:  [''],
}

/**
 * 规范化任意格式的 symbol 为标准带前缀格式
 * 例如: '000001' → 'sh000001', 'NDX' → 'usNDX', 'sh000001' → 'sh000001'
 */
export function normalizeSymbol(raw) {
  const s = String(raw).trim()
  const upper = s.toUpperCase()

  // 已知前缀的直接返回
  if (_lookup[s.toLowerCase()]) return s.toLowerCase()

  // 美股
  if (['NDX', 'SPX', 'DJI', 'IXIC', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META'].includes(upper)) {
    return 'us' + upper
  }

  // 港股
  if (['HSI', 'HKHSI', 'HK2000'].includes(upper)) {
    return 'hkHSI'
  }

  // 日经
  if (['N225', 'NI225', 'NIKKEI'].includes(upper)) {
    return 'jpN225'
  }

  // 宏观
  if (['GOLD', 'WTIC', 'WTI', 'VIX', 'CNHUSD', 'CNH', 'DXY'].includes(upper)) {
    return upper
  }

  // 去掉已知前缀后，纯数字 → A股
  const clean = s.replace(/^(sh|sz|us|hk|jp)/i, '')
  if (/^\d{6}$/.test(clean)) {
    return _aSharePrefix(clean) + clean
  }

  // 其他：转小写原样返回
  return s.toLowerCase()
}

/**
 * 判断是否为 A 股
 */
export function isAShare(symbol) {
  const s = normalizeSymbol(symbol)
  return s.startsWith('sh') || s.startsWith('sz')
}

/**
 * 判断是否为分钟级周期
 */
export function isIntradayPeriod(period) {
  return ['minutely', '1min', '5min', '15min', '30min', '60min'].includes(period)
}

/**
 * 提取纯数字代码（去掉 sh/sz/hk/us/jp 前缀）
 */
export function extractCode(symbol) {
  return String(symbol).replace(/^(sh|sz|us|hk|jp)/i, '').toUpperCase()
}

/**
 * 构建 ECharts 所需的时间标签
 */
export function formatDate(dateStr, period = 'daily') {
  if (!dateStr) return ''
  const s = String(dateStr)
  // 分钟/分时周期：精确到分钟
  if (period === 'minutely' || period.startsWith('min') || s.length === 19) {
    return s.slice(0, 16)  // YYYY-MM-DD HH:mm
  }
  // 日/周/月/年：精确到日期
  if (s.length >= 10) return s.slice(0, 10) // YYYY-MM-DD
  return s
}

/**
 * 从后端注册表加载搜索字典
 */
export async function loadSymbolRegistry() {
  try {
    const res = await fetch('/api/v1/market/symbols')
    if (!res.ok) return false
    const data = await res.json()
    _registry = data.symbols || []
    _lookup = {}
    for (const item of _registry) {
      _lookup[item.symbol.toLowerCase()] = item
    }
    return true
  } catch {
    return false
  }
}

/**
 * 获取注册表
 */
export function getRegistry() {
  return _registry
}

/**
 * 根据 symbol 获取元信息
 */
export function getSymbolMeta(symbol) {
  const norm = normalizeSymbol(symbol)
  return _lookup[norm.toLowerCase()] || null
}

/**
 * 生成 ECharts X轴标签（完整日期格式，周期自适应）
 * 日/周/月/年 → YYYY-MM-DD
 * 分时/分钟级 → YYYY-MM-DD HH:mm
 */
export function buildXAxisLabels(hist, period) {
  return hist.map(h => {
    const d = h.date || h.time || ''
    const isMinute = period === 'minutely' || period.startsWith('min')
    if (isMinute && d.length >= 16) return d.slice(0, 16)   // YYYY-MM-DD HH:mm
    if (d.length >= 10) return d.slice(0, 10)                  // YYYY-MM-DD
    return d
  })
}

/**
 * 导出 CSV 数据
 */
export function exportCSV(hist, indicators = {}, filename = 'kline.csv') {
  const headers = ['date', 'time', 'open', 'high', 'low', 'close', 'volume', 'change_pct', ...Object.keys(indicators)]
  const rows = hist.map((h, i) => {
    const row = [
      h.date || '', h.time || '',
      h.open ?? '', h.high ?? '', h.low ?? '', h.close ?? '',
      h.volume ?? '', h.change_pct ?? ''
    ]
    for (const key of Object.keys(indicators)) {
      row.push(indicators[key]?.[i] ?? '')
    }
    return row
  })
  const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
