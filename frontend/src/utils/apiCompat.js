/**
 * API 响应兼容提取器
 * Phase B: 后端统一使用 {code, message, data, timestamp} 包装
 * 此工具自动兼容新旧两种格式，前端无需修改。
 */

/**
 * 从 API 响应中提取 data 字段
 * 兼容：
 *   新格式 {code:0, data: {...}} → 返回 data
 *   旧格式 {...} → 直接返回（向后兼容）
 */
export function extractData(response) {
  if (response && typeof response.code === 'number' && 'data' in response) {
    if (response.code !== 0) {
      console.warn('[API] 非0响应码:', response.code, response.message)
    }
    return response.data
  }
  // 旧格式或直接返回的数据（向后兼容）
  return response
}

/**
 * 封装的 fetch，替代普通 fetch
 * 自动处理统一响应格式 {code, message, data, timestamp}
 */
export async function apiFetch(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
  
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  }
  
  const json = await res.json()
  return extractData(json)
}

/**
 * 字段标准化映射表
 * 统一不同API返回的字段差异
 */
export const FIELD_MAP = {
  // 价格相关
  price: ['price', 'trade', 'index', 'current', 'close'],
  change: ['change', 'chg', 'change_amount'],
  change_pct: ['change_pct', 'chg_pct', 'changePercent', 'changepercent', 'pct_chg'],
  // 成交量相关
  volume: ['volume', 'vol'],
  amount: ['amount', 'turnover_amount', 'money'],
  turnover: ['turnover', 'turnoverratio'],
  // 基本信息
  symbol: ['symbol', 'code', 'stock_code'],
  name: ['name', 'stock_name', 'security_name'],
  // K线数据
  open: ['open'],
  high: ['high'],
  low: ['low'],
}

/**
 * 标准化单个数据对象
 * @param {Object} raw - 原始数据
 * @returns {Object} 标准化后数据
 */
export function normalizeFields(raw) {
  if (!raw || typeof raw !== 'object') return raw || {}
  
  const result = {...raw}
  
  for (const [stdField, possibleKeys] of Object.entries(FIELD_MAP)) {
    // 如果结果中已有标准化字段，跳过
    if (stdField in result) continue
    
    // 否则尝试从可能字段中取值
    for (const key of possibleKeys) {
      if (key in raw) {
        result[stdField] = raw[key]
        break
      }
    }
  }
  
  return result
}

/**
 * 标准化数据数组
 * @param {Array} list - 原始列表
 * @returns {Array} 标准化列表
 */
export function normalizeList(list) {
  if (!Array.isArray(list)) return []
  return list.map(item => normalizeFields(item))
}
