/**
 * API 请求工具 - 统一处理响应格式
 *
 * 功能:
 * - 超时控制 + 自动重试
 * - 标准 API 格式解包 (兼容新旧格式)
 * - 字段标准化映射
 * - 数据源熔断广播（通过 useDataSourceStatus）
 */

import { logger } from './logger.js'
import { broadcastDataSourceStatus } from '../composables/useDataSourceStatus.js'

// ── 熔断阈值（连续失败 N 次则触发降级广播）─────────────────────
const _consecutiveFailures = { count: 0 }
const _DEGRADE_THRESHOLD   = 3
const _CIRCUIT_THRESHOLD   = 6

function _onFailure(url, status) {
  _consecutiveFailures.count++
  const n = _consecutiveFailures.count
  if (n >= _CIRCUIT_THRESHOLD) {
    broadcastDataSourceStatus('down', `API 连续${n}次失败: ${status ?? '网络错误'}`)
  } else if (n >= _DEGRADE_THRESHOLD) {
    broadcastDataSourceStatus('degraded', `主数据源响应异常 (${status ?? '网络错误'})，已切换备用`)
  }
}

function _onSuccess() {
  if (_consecutiveFailures.count > 0) {
    _consecutiveFailures.count = 0
    broadcastDataSourceStatus('ok', '数据源已恢复正常')
  }
}

/**
 * 从 API 响应中提取 data 字段
 * 兼容：新格式 {code:0, data: {...}} → 返回 data
 *       旧格式 {...} → 直接返回（向后兼容）
 */
export function extractData(response) {
  if (response && typeof response.code === 'number' && 'data' in response) {
    if (response.code !== 0) {
      logger.warn('[API] 非0响应码:', response.code, response.message)
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
      
      // 仅对5xx服务器错误和超时应试重试，4xx客户端错误立即失败
      if (!res.ok) {
        if (res.status >= 500 || res.status === 429) {
          // 服务器错误，可以重试
          if (attempt < retries) {
            logger.warn(`[apiFetch] ${url} returned ${res.status}, retrying (${attempt + 1}/${retries})...`)
            await sleep(500 * (attempt + 1))
            continue
          }
        }
        // 4xx错误或已达到重试上限，抛出异常
        throw new Error(`HTTP ${res.status}`)
      }

      _onSuccess()
      const d = await res.json()
      return extractData(d)
      
    } catch (e) {
      clearTimeout(timer)
      lastError = e
      // 修复: 增加网络错误 (TypeError) 和 Fetch 失败的重试
      const isNetworkError = e.name === 'TypeError' || e.message?.includes('fetch') || e.message?.includes('Failed to fetch')
      if (attempt < retries && (e.name === 'AbortError' || e.message?.startsWith('HTTP 5') || isNetworkError)) {
        logger.warn(`[apiFetch] ${url} failed (attempt ${attempt + 1}): ${e.message}, retrying...`)
        await sleep(500 * (attempt + 1))
        continue
      }
      // 记录失败（用于熔断计数）
      _onFailure(url, e.message)
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

export { broadcastDataSourceStatus }

/**
 * 批量获取 API 数据
 * @param {Array<{url: string, key: string, default?: any, required?: boolean}>} requests 
 * @param {boolean} silent - 如果为true，则返回defaultValue而非抛出（不推荐）
 * @returns {Promise<Object>}
 * @throws {Error} 当required=true的请求失败时抛出
 */
export async function fetchApiBatch(requests, silent = false) {
  const results = await Promise.all(
    requests.map(async ({ url, key, default: defaultValue = null, required = true }) => {
      try {
        const data = await apiFetch(url)
        return { key, data, error: null }
      } catch (e) {
        logger.error(`[fetchApiBatch] ${url} failed:`, e.message)
        if (!silent && required) {
          throw new Error(`API请求失败 [${key}]: ${e.message}`)
        }
        return { key, data: defaultValue, error: e.message }
      }
    })
  )
  
  // 构建结果对象，收集错误信息
  const errors = results.filter(r => r.error).map(r => ({ key: r.key, error: r.error }))
  const data = results.reduce((acc, { key, data }) => {
    acc[key] = data
    return acc
  }, {})
  
  // 如果有错误且不是silent模式，在结果中标记
  if (errors.length > 0) {
    data._errors = errors
    data._stale = true  // 标记数据可能过期
  }
  return data
}