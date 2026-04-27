/**
 * symbols.js — 前端符号规范化与映射
 * 与后端 _normalize_symbol / _SYMBOL_REGISTRY 保持一致
 */

// A股：第一位判断交易所
// 规则：6xx/9xx → sh；0xx/1xx/2xx/3xx → sz
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
const US_SYMBOLS = ['NDX', 'SPX', 'DJI', 'IXIC', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META']
const HK_SYMBOLS = ['HSI', 'HKHSI', 'HK2000']
const JP_SYMBOLS = ['N225', 'NI225', 'NIKKEI']
const MACRO_SYMBOLS = ['GOLD', 'GLD', 'XAU', 'GC', 'WTIC', 'WTI', 'CL', 'VIX', 'CNHUSD', 'CNH', 'DXY', 'USDX']

// 前缀映射，与后端 _normalize_symbol 保持一致
const US_PREFIX_MAP = {}
for (const s of US_SYMBOLS) US_PREFIX_MAP[s] = 'us' + s

export function normalizeSymbol(raw) {
  const s = String(raw).trim()
  const upper = s.toUpperCase()

  if (_lookup[s.toLowerCase()]) return s.toLowerCase()

  // 已带前缀的完整symbol直接返回小写
  if (/^(sh|sz|us|hk|jp)/i.test(s)) return s.toLowerCase()

  if (US_SYMBOLS.includes(upper)) {
    return 'us' + upper
  }

  if (HK_SYMBOLS.includes(upper)) {
    return 'hkHSI'
  }

  if (JP_SYMBOLS.includes(upper)) {
    return 'jpN225'
  }

  if (MACRO_SYMBOLS.includes(upper)) {
    return upper
  }

  // CNHUSD 特殊处理
  if (upper === 'CNHUSD') return 'CNHUSD'
  if (upper.startsWith('CNH')) return 'CNHUSD'

  const clean = s.replace(/^(sh|sz|us|hk|jp)/i, '')

  if (/^\d{6}$/.test(clean)) {
    return _aSharePrefix(clean) + clean
  }

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
