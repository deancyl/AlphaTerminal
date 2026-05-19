/**
 * Market Radar Error Handling Utilities
 * 
 * Wave 4-30: Frontend error handling and retry mechanism
 * 
 * Provides:
 * - Error code mapping
 * - User-friendly error messages
 * - Retry with exponential backoff
 * - Error classification
 */

import { ref } from 'vue'

/**
 * Error codes matching backend MarketRadarErrorCode
 */
export const ErrorCodes = {
  SUCCESS: 'SUCCESS',
  INVALID_PARAMETER: 'INVALID_PARAMETER',
  INVALID_ANOMALY_TYPE: 'INVALID_ANOMALY_TYPE',
  RATE_LIMIT_EXCEEDED: 'RATE_LIMIT_EXCEEDED',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  TIMEOUT: 'TIMEOUT',
  DATA_SOURCE_UNAVAILABLE: 'DATA_SOURCE_UNAVAILABLE',
  NETWORK_ERROR: 'NETWORK_ERROR',
  CACHE_ERROR: 'CACHE_ERROR',
  NO_DATA: 'NO_DATA',
  INCOMPLETE_DATA: 'INCOMPLETE_DATA',
}

/**
 * User-friendly error messages in Chinese
 */
const ErrorMessages = {
  [ErrorCodes.SUCCESS]: '操作成功',
  [ErrorCodes.INVALID_PARAMETER]: '参数错误，请检查输入',
  [ErrorCodes.INVALID_ANOMALY_TYPE]: '无效的异常类型',
  [ErrorCodes.RATE_LIMIT_EXCEEDED]: '请求过于频繁，请稍后重试',
  [ErrorCodes.INTERNAL_ERROR]: '服务暂时不可用，请稍后重试',
  [ErrorCodes.TIMEOUT]: '数据加载超时，请稍后重试',
  [ErrorCodes.DATA_SOURCE_UNAVAILABLE]: '数据源暂时不可用，正在使用备用数据',
  [ErrorCodes.NETWORK_ERROR]: '网络连接异常，请检查网络设置',
  [ErrorCodes.CACHE_ERROR]: '缓存服务异常',
  [ErrorCodes.NO_DATA]: '暂无数据',
  [ErrorCodes.INCOMPLETE_DATA]: '数据不完整',
}

/**
 * Classify error from API response
 * @param {Object} response - API response
 * @returns {Object} Classified error with code, message, isRetryable
 */
export function classifyError(response) {
  // Check for error object in response
  const errorObj = response?.error || response
  
  const code = errorObj?.code || ErrorCodes.INTERNAL_ERROR
  const message = errorObj?.message || ErrorMessages[code] || '未知错误'
  const retryAfter = errorObj?.retry_after
  
  // Determine if error is retryable
  const isRetryable = [
    ErrorCodes.TIMEOUT,
    ErrorCodes.NETWORK_ERROR,
    ErrorCodes.DATA_SOURCE_UNAVAILABLE,
    ErrorCodes.RATE_LIMIT_EXCEEDED,
  ].includes(code)
  
  return {
    code,
    message,
    retryAfter,
    isRetryable,
    isRateLimited: code === ErrorCodes.RATE_LIMIT_EXCEEDED,
    isTimeout: code === ErrorCodes.TIMEOUT,
    isNetworkError: code === ErrorCodes.NETWORK_ERROR,
  }
}

/**
 * Retry options
 * @typedef {Object} RetryOptions
 * @property {number} maxRetries - Maximum number of retries (default: 3)
 * @property {number} baseDelay - Base delay in ms (default: 1000)
 * @property {number} maxDelay - Maximum delay in ms (default: 10000)
 * @property {Function} shouldRetry - Function to determine if should retry
 */

/**
 * Execute function with retry and exponential backoff
 * @param {Function} fn - Async function to execute
 * @param {RetryOptions} options - Retry options
 * @returns {Promise<any>} Result of function
 */
export async function withRetry(fn, options = {}) {
  const {
    maxRetries = 3,
    baseDelay = 1000,
    maxDelay = 10000,
    shouldRetry = (error) => error.isRetryable,
  } = options
  
  let lastError = null
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn()
    } catch (e) {
      const classified = classifyError(e.response?.data || e)
      lastError = { ...classified, originalError: e }
      
      // Check if we should retry
      if (attempt === maxRetries || !shouldRetry(classified)) {
        throw lastError
      }
      
      // Calculate delay with exponential backoff + jitter
      const delay = Math.min(
        baseDelay * Math.pow(2, attempt) + Math.random() * 1000,
        maxDelay
      )
      
      // Use retryAfter header if available (for rate limiting)
      const waitTime = classified.retryAfter ? classified.retryAfter * 1000 : delay
      
      await new Promise(resolve => setTimeout(resolve, waitTime))
    }
  }
  
  throw lastError
}

/**
 * Composable for error handling with retry
 * @returns {Object} Error handling utilities
 */
export function useMarketRadarError() {
  const lastError = ref(null)
  const isRetrying = ref(false)
  const retryCount = ref(0)
  
  /**
   * Clear error state
   */
  function clearError() {
    lastError.value = null
    retryCount.value = 0
  }
  
  /**
   * Execute function with error handling
   * @param {Function} fn - Async function to execute
   * @param {Object} options - Options
   * @returns {Promise<any>} Result
   */
  async function executeWithErrorHandling(fn, options = {}) {
    clearError()
    
    try {
      const result = await withRetry(fn, {
        ...options,
        shouldRetry: (error) => {
          retryCount.value++
          return error.isRetryable && retryCount.value <= (options.maxRetries || 3)
        },
      })
      return result
    } catch (e) {
      lastError.value = classifyError(e.response?.data || e)
      throw lastError.value
    }
  }
  
  /**
   * Retry last failed operation
   * @param {Function} fn - Function to retry
   * @returns {Promise<any>} Result
   */
  async function retryLast(fn) {
    if (!lastError.value?.isRetryable) {
      return null
    }
    
    isRetrying.value = true
    try {
      const result = await fn()
      clearError()
      return result
    } catch (e) {
      lastError.value = classifyError(e.response?.data || e)
      throw lastError.value
    } finally {
      isRetrying.value = false
    }
  }
  
  return {
    lastError,
    isRetrying,
    retryCount,
    clearError,
    executeWithErrorHandling,
    retryLast,
    classifyError,
  }
}

export default {
  ErrorCodes,
  classifyError,
  withRetry,
  useMarketRadarError,
}
