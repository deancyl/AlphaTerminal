/**
 * useApiError.js — 统一 API 错误处理组合式函数
 * 
 * 功能:
 * - 统一错误分类和处理
 * - 自动显示 Toast 通知
 * - 可选重试机制
 * - 错误上报
 * 
 * 使用方式:
 *   import { useApiError } from './composables/useApiError.js'
 *   
 *   // 基础用法
 *   const { handleError, wrapApiCall } = useApiError()
 *   
 *   // 包装 API 调用
 *   const data = await wrapApiCall(() => apiFetch('/api/v1/market/overview'))
 *   
 *   // 手动处理错误
 *   try {
 *     const data = await apiFetch('/api/v1/market/overview')
 *   } catch (error) {
 *     handleError(error, { context: '加载市场数据' })
 *   }
 */

import { ref, reactive, computed } from 'vue'
import { 
  ErrorType, 
  classifyError, 
  getUserMessage, 
  createError,
  reportError as reportErrorBase,
  ErrorCode,
} from '../utils/errorHandler.js'
import { toast } from './useToast.js'
import { logger } from '../utils/logger.js'

/**
 * 判断错误是否可重试
 * @param {Error} error 
 * @returns {boolean}
 */
export function isRetryable(error) {
  if (!error) return false
  
  const type = classifyError(error)
  
  // 客户端错误和验证错误不应重试
  if (type === ErrorType.CLIENT || type === ErrorType.VALIDATION) {
    return false
  }
  
  // 特定 HTTP 状态码不应重试
  const message = error.message || ''
  if (message.includes('HTTP 401') || message.includes('HTTP 403')) {
    return false
  }
  
  // 网络错误、超时、服务器错误可以重试
  return type === ErrorType.NETWORK || 
         type === ErrorType.TIMEOUT || 
         type === ErrorType.SERVER
}

/**
 * 格式化错误为用户友好的消息
 * @param {Error} error 
 * @param {Object} context - 上下文信息
 * @returns {string}
 */
export function formatErrorForUser(error, context = {}) {
  const baseMessage = getUserMessage(error)
  const { context: contextName, operation } = context
  
  if (contextName || operation) {
    return `${contextName || operation}失败: ${baseMessage}`
  }
  
  return baseMessage
}

/**
 * 默认配置
 */
const DEFAULT_OPTIONS = {
  showToast: true,           // 是否显示 Toast
  retry: 0,                  // 重试次数
  retryDelay: 1000,          // 重试延迟基数 (ms)
  retryJitter: 0.25,         // 抖动因子 (±25%)
  maxRetryDelay: 10000,      // 最大重试延迟 (ms)
  report: true,              // 是否上报错误
  throwOnError: true,        // 是否抛出错误
}

/**
 * useApiError 组合式函数
 * @param {Object} options - 配置选项
 * @returns {Object}
 */
export function useApiError(options = {}) {
  const config = { ...DEFAULT_OPTIONS, ...options }
  
  // 错误状态
  const errorState = reactive({
    lastError: null,
    errorType: null,
    errorMessage: null,
    errorCount: 0,
    retryCount: 0,
    isRetrying: false,
  })
  
  /**
   * 计算重试延迟（带抖动）
   * @param {number} attempt - 当前尝试次数
   * @returns {number}
   */
  function calculateRetryDelay(attempt) {
    const baseDelay = config.retryDelay * Math.pow(2, attempt)
    const cappedDelay = Math.min(baseDelay, config.maxRetryDelay)
    const jitter = 1 - config.retryJitter + Math.random() * config.retryJitter * 2
    return Math.floor(cappedDelay * jitter)
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
   * 处理错误
   * @param {Error} error - 错误对象
   * @param {Object} context - 上下文信息
   */
  function handleError(error, context = {}) {
    const type = classifyError(error)
    const userMessage = formatErrorForUser(error, context)
    
    // 更新状态
    errorState.lastError = error
    errorState.errorType = type
    errorState.errorMessage = userMessage
    errorState.errorCount++
    
    // 显示 Toast
    if (config.showToast) {
      const { silent = false } = context
      if (!silent) {
        toast.error('操作失败', userMessage)
      }
    }
    
    // 上报错误
    if (config.report) {
      reportErrorBase(error, {
        source: 'api',
        ...context,
        errorType: type,
      })
    }
    
    // 记录日志
    logger.error(`[useApiError] ${type}: ${error.message}`, { error, context })
    
    return {
      type,
      userMessage,
      originalError: error,
    }
  }
  
  /**
   * 包装 API 调用（带重试）
   * @param {Function} fn - 返回 Promise 的函数
   * @param {Object} callOptions - 调用选项
   * @returns {Promise}
   */
  async function wrapApiCall(fn, callOptions = {}) {
    const callConfig = { ...config, ...callOptions }
    const { retry = callConfig.retry } = callOptions
    
    let lastError = null
    
    for (let attempt = 0; attempt <= retry; attempt++) {
      try {
        errorState.isRetrying = attempt > 0
        errorState.retryCount = attempt
        
        const result = await fn()
        
        // 成功后重置状态
        if (attempt > 0) {
          toast.success('重试成功', '数据加载成功')
        }
        
        errorState.isRetrying = false
        errorState.retryCount = 0
        
        return result
        
      } catch (error) {
        lastError = error
        
        // 检查是否可重试
        if (attempt < retry && isRetryable(error)) {
          const delay = calculateRetryDelay(attempt)
          logger.warn(`[useApiError] 重试 ${attempt + 1}/${retry + 1} 在 ${delay}ms 后...`)
          
          if (callConfig.showToast) {
            toast.warning('请求失败', `正在重试 (${attempt + 1}/${retry})...`)
          }
          
          await sleep(delay)
          continue
        }
        
        // 不可重试或已达到最大重试次数
        handleError(error, callOptions)
        
        if (callConfig.throwOnError) {
          throw error
        }
        
        return null
      }
    }
    
    // 所有重试都失败
    if (lastError) {
      handleError(lastError, callOptions)
      
      if (callConfig.throwOnError) {
        throw lastError
      }
    }
    
    return null
  }
  
  /**
   * 重置错误状态
   */
  function resetErrorState() {
    errorState.lastError = null
    errorState.errorType = null
    errorState.errorMessage = null
    errorState.retryCount = 0
    errorState.isRetrying = false
  }
  
  /**
   * 清除错误
   */
  function clearError() {
    errorState.lastError = null
    errorState.errorType = null
    errorState.errorMessage = null
  }
  
  return {
    // 状态
    errorState,
    hasError: computed(() => errorState.lastError !== null),
    isRetrying: computed(() => errorState.isRetrying),
    
    // 方法
    handleError,
    wrapApiCall,
    resetErrorState,
    clearError,
    
    // 工具函数
    isRetryable,
    formatErrorForUser,
    classifyError,
    
    // 常量
    ErrorType,
    ErrorCode,
  }
}

// 导出工具函数和常量
export { ErrorType, ErrorCode, classifyError, getUserMessage, createError }
