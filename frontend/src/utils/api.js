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
import { reactive } from 'vue'
import { broadcastDataSourceStatus } from '../composables/useDataSourceStatus.js'
import { toast } from '../composables/useToast.js'
import { isNetworkOnline } from '../composables/useNetworkStatus.js'
import { dedupedFetch, abortPendingRequest, abortAllPendingRequests } from './requestDedup.js'
import { TIMEOUTS } from './constants.js'

// ── API 基础 URL ─────────────────────────────────────────────────
// 始终使用相对路径，让前端代理（Vite proxy）转发到后端
// 这样可以确保所有环境（开发/生产）都通过前端服务器访问API
const API_BASE_URL = ''

// ── 熔断阈值（连续失败 N 次则触发降级广播）─────────────────────
// JavaScript 单线程，使用简单变量即可
let _consecutiveFailures = 0
const _DEGRADE_THRESHOLD   = 3
const _CIRCUIT_THRESHOLD   = 6

// ── 全局错误感知状态（供 UI 层消费）──────────────────────────────
export const apiErrorState = reactive({
  failedCount: 0,     // 连续失败次数
  lastError: null,    // 最近错误信息
  lastFailedAt: null, // 最近失败时间戳
  isDegraded: false, // 是否已触发降级提示
})

function _onFailure(url, status) {
  // JavaScript 单线程，直接操作即可
  _consecutiveFailures++
  const n = _consecutiveFailures
  apiErrorState.failedCount = n
  apiErrorState.lastError = `${url}: ${status ?? '网络错误'}`
  apiErrorState.lastFailedAt = Date.now()
  if (n >= _CIRCUIT_THRESHOLD) {
    apiErrorState.isDegraded = true
    broadcastDataSourceStatus('down', `API 连续${n}次失败: ${status ?? '网络错误'}`)
    toast.error('数据源异常', `API 连续${n}次失败，已触发熔断保护`)
  } else if (n >= _DEGRADE_THRESHOLD) {
    apiErrorState.isDegraded = true
    broadcastDataSourceStatus('degraded', `主数据源响应异常 (${status ?? '网络错误'})，已切换备用`)
    toast.warning('数据源降级', '主数据源响应异常，已切换备用数据源')
  }
}

function _onSuccess() {
  if (_consecutiveFailures > 0) {
    _consecutiveFailures = 0
    apiErrorState.failedCount = 0
    apiErrorState.lastError = null
    if (apiErrorState.isDegraded) {
      apiErrorState.isDegraded = false
      broadcastDataSourceStatus('ok', '数据源已恢复正常')
      toast.success('数据源恢复', '主数据源已恢复正常')
    }
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
const RETRY_JITTER = 0.25
const RETRY_BASE_DELAY = 500
const RETRY_MAX_DELAY = 8000

function calculateRetryDelay(attempt) {
  const baseDelay = RETRY_BASE_DELAY * Math.pow(2, attempt)
  const cappedDelay = Math.min(baseDelay, RETRY_MAX_DELAY)
  const jitter = 1 - RETRY_JITTER + Math.random() * RETRY_JITTER * 2
  return Math.floor(cappedDelay * jitter)
}

export async function apiFetch(url, options = {}) {
  const { timeoutMs = 8000, retries = 0, method = 'GET', headers = {}, body, signal: externalSignal } = options
  let lastError = null

  if (!isNetworkOnline()) {
    throw new Error('网络已断开，请检查连接')
  }

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    // 优先使用外部 signal（组件卸载时由外部中止），否则用本地 controller.signal
    const activeSignal = (externalSignal && !externalSignal.aborted) ? externalSignal : controller.signal
    
    try {
      const fetchOptions = { 
        signal: activeSignal,
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
      // 构建完整 URL（生产环境添加基础 URL）
      const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`
      const res = await fetch(fullUrl, fetchOptions)
      clearTimeout(timer)
      
      // 仅对5xx服务器错误和超时应试重试，4xx客户端错误立即失败
      if (!res.ok) {
        if (res.status >= 500 || res.status === 429) {
          if (attempt < retries) {
            const backoffMs = calculateRetryDelay(attempt)
            logger.warn(`[apiFetch] ${url} returned ${res.status}, retrying (${attempt + 1}/${retries}) in ${backoffMs}ms...`)
            await sleep(backoffMs)
            continue
          }
        }
        // 422 校验错误：解析后端返回的详细错误信息
        if (res.status === 422) {
          try {
            const data = await res.json()
            const detail = data?.detail?.[0]?.msg || data?.message || JSON.stringify(data)
            throw new Error(`参数校验失败: ${detail}`)
          } catch (parseErr) {
            if (parseErr.message.startsWith('参数校验失败')) throw parseErr
            throw new Error(`参数校验失败 (HTTP ${res.status})`)
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
        const backoffMs = calculateRetryDelay(attempt)
        logger.warn(`[apiFetch] ${url} failed (attempt ${attempt + 1}): ${e.message}, retrying in ${backoffMs}ms...`)
        await sleep(backoffMs)
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
 * @param {boolean} silent - 如果为true，则即使required=true也不抛出错误，而是返回defaultValue
 * @returns {Promise<Object>}
 * @throws {Error} 当required=true且silent=false的请求失败时抛出
 */
export async function fetchApiBatch(requests, silent = false) {
  const settled = await Promise.all(
    requests.map(async ({ url, key, default: defaultValue = null, required = true }) => {
      try {
        const data = await apiFetch(url)
        return { key, data, error: null, required }
      } catch (e) {
        logger.warn(`[fetchApiBatch] ${url} failed (key=${key}): ${e.message}`)
        return { key, data: defaultValue, error: e.message, required }
      }
    })
  )

  const errors = settled.filter(r => r.error).map(r => ({ key: r.key, error: r.error }))
  const data = settled.reduce((acc, { key, data }) => {
    acc[key] = data
    return acc
  }, {})

  if (errors.length > 0) {
    data._errors = errors
    data._stale = true
    const requiredErrors = errors.filter(e => settled.find(s => s.key === e.key)?.required)
    if (requiredErrors.length > 0 && !silent) {
      throw new Error(`必需接口失败: ${requiredErrors.map(e => `[${e.key}] ${e.error}`).join(', ')}`)
    }
  }
  return data
}

export async function apiFetchValidated(url, schema, options = {}) {
  const data = await apiFetch(url, options)
  const result = schema.safeParse(data)
  
  if (!result.success) {
    const errorMessages = result.error.errors
      .map(e => `${e.path.join('.')}: ${e.message}`)
      .join(', ')
    throw new Error(`数据验证失败: ${errorMessages}`)
  }
  
  return result.data
}

export async function apiFetchDeduped(key, url, options = {}) {
  const { debounce = 100, ...fetchOptions } = options
  return dedupedFetch(key, async (signal) => {
    return apiFetch(url, { ...fetchOptions, signal })
  }, { debounce })
}

export { 
  dedupedFetch,
  abortPendingRequest,
  abortAllPendingRequests
}

/**
 * Fetch quote with automatic deduplication.
 */
export async function fetchQuote(symbol, options = {}) {
  const { timeoutMs = TIMEOUTS.API_QUOTE } = options
  const cacheKey = `quote:${symbol}`
  
  return apiFetchDeduped(
    cacheKey,
    `/api/v1/market/quote/${symbol}`,
    { timeoutMs, debounce: 100 }
  )
}

/**
 * Fetch quote detail with automatic deduplication.
 */
export async function fetchQuoteDetail(symbol, options = {}) {
  const { timeoutMs = TIMEOUTS.API_QUOTE_DETAIL } = options
  const cacheKey = `quote_detail:${symbol}`
  
  return apiFetchDeduped(
    cacheKey,
    `/api/v1/market/quote_detail/${symbol}`,
    { timeoutMs, debounce: 100 }
  )
}

/**
 * Fetch order book with automatic deduplication.
 */
export async function fetchOrderBook(symbol, options = {}) {
  const { timeoutMs = TIMEOUTS.API_QUOTE } = options
  const cacheKey = `order_book:${symbol}`
  
  return apiFetchDeduped(
    cacheKey,
    `/api/v1/market/order_book/${symbol}`,
    { timeoutMs, debounce: 50 }
  )
}