/**
 * 统一错误处理工具
 * 
 * 功能:
 * - 错误分类和标准化
 * - 用户友好的错误消息
 * - 错误上报
 * - 重试机制
 */

import { logger } from './logger.js'

/**
 * 错误类型枚举
 */
export const ErrorType = {
  NETWORK: 'network',           // 网络错误
  TIMEOUT: 'timeout',           // 超时错误
  SERVER: 'server',             // 服务器错误 (5xx)
  CLIENT: 'client',             // 客户端错误 (4xx)
  VALIDATION: 'validation',     // 验证错误
  BUSINESS: 'business',         // 业务逻辑错误
  UNKNOWN: 'unknown',           // 未知错误
}

/**
 * 错误码映射
 */
export const ErrorCode = {
  // 成功
  SUCCESS: 0,
  
  // 客户端错误 (1xx)
  BAD_REQUEST: 100,
  UNAUTHORIZED: 101,
  FORBIDDEN: 102,
  NOT_FOUND: 104,
  VALIDATION_ERROR: 110,
  RATE_LIMITED: 120,
  
  // 服务器错误 (2xx)
  INTERNAL_ERROR: 200,
  DATABASE_ERROR: 210,
  
  // 第三方错误 (3xx)
  THIRD_PARTY_ERROR: 302,
  TIMEOUT_ERROR: 310,
}

/**
 * 用户友好的错误消息
 */
const USER_MESSAGES = {
  [ErrorType.NETWORK]: '网络连接失败，请检查网络设置',
  [ErrorType.TIMEOUT]: '请求超时，请稍后重试',
  [ErrorType.SERVER]: '服务器繁忙，请稍后重试',
  [ErrorType.CLIENT]: '请求参数错误',
  [ErrorType.VALIDATION]: '输入数据验证失败',
  [ErrorType.BUSINESS]: '操作失败，请重试',
  [ErrorType.UNKNOWN]: '发生未知错误，请联系管理员',
}

/**
 * 分类错误
 * @param {Error} error 
 * @returns {string} 错误类型
 */
export function classifyError(error) {
  if (!error) return ErrorType.UNKNOWN
  
  const message = error.message || ''
  const name = error.name || ''
  
  // 网络错误
  if (
    name === 'TypeError' ||
    message.includes('fetch') ||
    message.includes('network') ||
    message.includes('Failed to fetch') ||
    message.includes('NetworkError')
  ) {
    return ErrorType.NETWORK
  }
  
  // 超时错误
  if (
    name === 'AbortError' ||
    message.includes('timeout') ||
    message.includes('超时')
  ) {
    return ErrorType.TIMEOUT
  }
  
  // HTTP 状态码判断
  if (message.includes('HTTP 5')) {
    return ErrorType.SERVER
  }
  
  if (message.includes('HTTP 4')) {
    if (message.includes('422') || message.includes('validation')) {
      return ErrorType.VALIDATION
    }
    return ErrorType.CLIENT
  }
  
  // 业务错误
  if (message.includes('业务') || message.includes('business')) {
    return ErrorType.BUSINESS
  }
  
  return ErrorType.UNKNOWN
}

/**
 * 获取用户友好的错误消息
 * @param {Error} error 
 * @returns {string}
 */
export function getUserMessage(error) {
  const type = classifyError(error)
  return USER_MESSAGES[type] || error.message || '发生错误'
}

/**
 * 创建错误对象
 * @param {string} type - 错误类型
 * @param {string} message - 错误消息
 * @param {Object} data - 附加数据
 * @returns {Error}
 */
export function createError(type, message, data = {}) {
  const error = new Error(message)
  error.type = type
  error.data = data
  error.timestamp = Date.now()
  return error
}

/**
 * 错误上报
 * @param {Error} error 
 * @param {Object} context 
 */
export function reportError(error, context = {}) {
  const errorInfo = {
    type: error.type || classifyError(error),
    message: error.message,
    stack: error.stack,
    timestamp: new Date().toISOString(),
    url: window.location.href,
    userAgent: navigator.userAgent,
    ...context,
  }
  
  // 控制台输出
  logger.error('[Error Report]', errorInfo)
  
  // TODO: 发送到错误监控服务
  // 例如: Sentry, LogRocket, 或自建服务
  if (window.reportError) {
    window.reportError(errorInfo)
  }
}

/**
 * 带重试的请求
 * @param {Function} fn - 要执行的函数
 * @param {Object} options 
 * @param {number} options.retries - 重试次数 (默认 3)
 * @param {number} options.delay - 延迟基数 (默认 1000ms)
 * @param {Function} options.onRetry - 重试回调
 * @returns {Promise}
 */
export async function withRetry(fn, options = {}) {
  const { retries = 3, delay = 1000, onRetry } = options
  
  let lastError = null
  
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error
      
      // 如果是最后一次尝试，抛出错误
      if (attempt === retries) {
        break
      }
      
      // 某些错误不需要重试
      const errorType = classifyError(error)
      if (errorType === ErrorType.CLIENT || errorType === ErrorType.VALIDATION) {
        throw error
      }
      
      // 计算退避时间 (指数退避)
      const backoffDelay = Math.min(delay * Math.pow(2, attempt), 10000)
      
      logger.warn(`[Retry] Attempt ${attempt + 1}/${retries + 1} failed, retrying in ${backoffDelay}ms...`)
      
      if (onRetry) {
        onRetry(error, attempt + 1, retries + 1)
      }
      
      await sleep(backoffDelay)
    }
  }
  
  throw lastError
}

/**
 * 睡眠函数
 * @param {number} ms 
 * @returns {Promise}
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * 全局错误处理器
 */
export class ErrorHandler {
  constructor(options = {}) {
    this.onError = options.onError || (() => {})
    this.onReport = options.onReport || reportError
    this.retryOptions = options.retryOptions || { retries: 3, delay: 1000 }
  }
  
  /**
   * 处理错误
   * @param {Error} error 
   * @param {Object} context 
   */
  handle(error, context = {}) {
    const type = classifyError(error)
    const userMessage = getUserMessage(error)
    
    // 上报错误
    this.onReport(error, context)
    
    // 调用错误回调
    this.onError({
      error,
      type,
      userMessage,
      context,
    })
    
    return {
      type,
      userMessage,
      originalError: error,
    }
  }
  
  /**
   * 包装异步函数
   * @param {Function} fn 
   * @returns {Function}
   */
  wrap(fn) {
    return async (...args) => {
      try {
        return await fn(...args)
      } catch (error) {
        this.handle(error, { args })
        throw error
      }
    }
  }
  
  /**
   * 包装带重试的异步函数
   * @param {Function} fn 
   * @returns {Function}
   */
  wrapWithRetry(fn) {
    return async (...args) => {
      return withRetry(
        () => fn(...args),
        {
          ...this.retryOptions,
          onRetry: (error, attempt, total) => {
            logger.warn(`[Retry] ${fn.name || 'anonymous'} attempt ${attempt}/${total} failed: ${error.message}`)
          },
        }
      )
    }
  }
}

// 默认错误处理器实例
export const defaultErrorHandler = new ErrorHandler()

/**
 * 便捷方法：处理 API 错误
 * @param {Error} error 
 * @returns {Object}
 */
export function handleApiError(error) {
  const type = classifyError(error)
  const userMessage = getUserMessage(error)
  
  // 上报错误
  reportError(error, { source: 'api' })
  
  return {
    type,
    userMessage,
    code: error.code || ErrorCode.INTERNAL_ERROR,
    traceId: error.traceId || generateTraceId(),
  }
}

/**
 * 生成追踪 ID
 * @returns {string}
 */
function generateTraceId() {
  return Math.random().toString(36).substring(2, 10).toUpperCase()
}

/**
 * 显示错误提示 (用于 UI)
 * @param {Error} error 
 * @param {Object} options 
 */
export function showErrorNotification(error, options = {}) {
  const { showDetails = false, duration = 5000 } = options
  const userMessage = getUserMessage(error)
  
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification('错误', {
      body: userMessage,
      icon: '/favicon.ico',
    })
  }
  
  if (window.showToast) {
    window.showToast({
      type: 'error',
      message: userMessage,
      duration,
    })
  }
  
  logger.error('[Error Notification]', error)
}

export function isRetryable(error) {
  if (!error) return false
  
  const type = classifyError(error)
  
  if (type === ErrorType.CLIENT || type === ErrorType.VALIDATION) {
    return false
  }
  
  const message = error.message || ''
  if (message.includes('HTTP 401') || message.includes('HTTP 403')) {
    return false
  }
  
  return type === ErrorType.NETWORK || 
         type === ErrorType.TIMEOUT || 
         type === ErrorType.SERVER
}

export function formatErrorForUser(error, context = {}) {
  const baseMessage = getUserMessage(error)
  const { context: contextName, operation } = context
  
  if (contextName || operation) {
    return `${contextName || operation}失败: ${baseMessage}`
  }
  
  return baseMessage
}
