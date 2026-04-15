/**
 * API 请求工具 - 统一处理响应格式
 * 
 * 功能:
 * - 超时控制 + 自动重试
 * - 标准 API 格式解包 (兼容新旧格式)
 * - 字段标准化映射
 */

/**
 * 从 API 响应中提取 data 字段
 * 兼容：新格式 {code:0, data: {...}} → 返回 data
 *       旧格式 {...} → 直接返回（向后兼容）
 */
export function extractData(response) {
  if (response && typeof response.code === 'number' && 'data' in response) {
    if (response.code !== 0) {
      console.warn('[API] 非0响应码:', response.code, response.message)
    }
    return response.data
  }
  return response
}

/**
 * 字段标准化映射表
 */
export const FIELD_MAP = {
  price: ['price', 'trade', 'index', 'current', 'close'],
  chg: ['change', 'chg', 'change_amount'],
  chg_pct: ['change_pct', 'chg_pct', 'changePercent', 'changepercent', 'pct_chg'],
  volume: ['volume', 'vol'],
  amount: ['amount', 'turnover_amount', 'money'],
  turnover: ['turnover', 'turnoverratio'],
  symbol: ['symbol', 'code', 'stock_code'],
  name: ['name', 'stock_name', 'security_name'],
}

/**
 * 标准化单个数据对象
 */
export function normalizeFields(raw) {
  if (!raw || typeof raw !== 'object') return raw || {}
  const result = {...raw}
  for (const [stdField, possibleKeys] of Object.entries(FIELD_MAP)) {
    if (stdField in result) continue
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
 */
export function normalizeList(list) {
  if (!Array.isArray(list)) return []
  return list.map(item => normalizeFields(item))
}

// 睡眠函数
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * @param {string} url - 请求 URL
 * @param {Object} options - 选项
 * @param {number} options.timeoutMs - 超时时间 (默认 8000ms)
 * @param {number} options.retries - 重试次数 (默认 0)
 * @param {string} options.method - HTTP方法 (默认 GET)
 * @param {Object} options.headers - 请求头
 * @param {any} options.body - 请求体
 * @returns {Promise<any>}
 */
export async function apiFetch(url, options = {}) {
  const { timeoutMs = 8000, retries = 0, method = 'GET', headers = {}, body } = options
  let lastError = null

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    
    try {
      const fetchOptions = { 
        signal: controller.signal,
        method,
        headers: {
          ...headers,
        },
      }
      if (body && ['POST', 'PUT', 'PATCH'].includes(method)) {
        fetchOptions.body = typeof body === 'string' ? body : JSON.stringify(body)
        // 自动设置 Content-Type 为 application/json
        if (!fetchOptions.headers['Content-Type'] && !fetchOptions.headers['content-type']) {
          fetchOptions.headers['Content-Type'] = 'application/json'
        }
      }
      const res = await fetch(url, fetchOptions)
      clearTimeout(timer)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      
      const d = await res.json()
      return extractData(d)
      
    } catch (e) {
      clearTimeout(timer)
      lastError = e
      if (attempt < retries) {
        console.warn(`[apiFetch] ${url} failed (attempt ${attempt + 1}), retrying...`)
        await sleep(500 * (attempt + 1))
        continue
      }
    } finally {
      clearTimeout(timer)
    }
  }
  
  if (lastError) {
    if (lastError.name === 'AbortError') {
      throw new Error(`请求超时（${timeoutMs / 1000}s）`)
    }
    throw lastError
  }
  throw new Error('请求失败')
}

/**
 * 批量获取 API 数据
 * @param {Array<{url: string, key: string, default?: any}>} requests 
 * @returns {Promise<Object>}
 */
export async function fetchApiBatch(requests) {
  const results = await Promise.all(
    requests.map(async ({ url, key, default: defaultValue = null }) => {
      try {
        const data = await apiFetch(url)
        return { key, data: data ?? defaultValue }
      } catch (e) {
        console.warn(`[fetchApiBatch] ${url} failed:`, e.message)
        return { key, data: defaultValue }
      }
    })
  )
  return results.reduce((acc, { key, data }) => {
    acc[key] = data
    return acc
  }, {})
}