/**
 * Forex Error Classification
 * 
 * Provides specific error messages for different error types
 * instead of generic "数据源异常" message.
 */

export const ForexError = {
  NETWORK: { code: 'NETWORK', message: '网络连接失败，请检查网络' },
  TIMEOUT: { code: 'TIMEOUT', message: '请求超时，请稍后重试' },
  RATE_LIMIT: { code: 'RATE_LIMIT', message: '请求过于频繁，请稍后重试' },
  DATA_SOURCE: { code: 'DATA_SOURCE', message: '数据源暂时不可用' },
  INVALID_SYMBOL: { code: 'INVALID_SYMBOL', message: '无效的交易品种' },
  UNKNOWN: { code: 'UNKNOWN', message: '数据加载失败' }
}

/**
 * Classify error into specific ForexError type
 * @param {Error} error - The error to classify
 * @returns {Object} ForexError object with code and message
 */
export function classifyForexError(error) {
  // Timeout errors (AbortError from fetch timeout)
  if (error.name === 'AbortError') return ForexError.TIMEOUT
  
  // HTTP status code based errors
  if (error.status === 429) return ForexError.RATE_LIMIT
  if (error.status === 404) return ForexError.INVALID_SYMBOL
  if (error.status === 503) return ForexError.DATA_SOURCE
  
  // Message-based classification
  const message = error.message?.toLowerCase() || ''
  if (message.includes('timeout')) return ForexError.TIMEOUT
  if (message.includes('network') || message.includes('fetch')) return ForexError.NETWORK
  if (message.includes('rate limit') || message.includes('too many')) return ForexError.RATE_LIMIT
  
  return ForexError.UNKNOWN
}
