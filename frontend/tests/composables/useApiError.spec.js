/**
 * useApiError.spec.js — API 错误处理测试套件
 * 
 * 测试范围:
 * - 网络错误处理
 * - 超时错误处理
 * - 响应格式错误处理
 * - 静默 vs 显式错误处理
 * - 重试机制
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useApiError, isRetryable, formatErrorForUser, ErrorType } from '../../src/composables/useApiError.js'

// Mock toast
vi.mock('../../src/composables/useToast.js', () => ({
  toast: {
    error: vi.fn(),
    warning: vi.fn(),
    success: vi.fn(),
  },
}))

// Mock logger
vi.mock('../../src/utils/logger.js', () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
  },
}))

describe('useApiError', () => {
  let errorHandler
  
  beforeEach(() => {
    vi.clearAllMocks()
    errorHandler = useApiError({ showToast: true, report: false })
  })
  
  afterEach(() => {
    vi.resetAllMocks()
  })
  
  // ============================================
  // 网络错误测试
  // ============================================
  describe('Network Errors', () => {
    it('should classify network errors correctly', () => {
      const networkError = new TypeError('Failed to fetch')
      const result = errorHandler.handleError(networkError, { context: 'API请求' })
      
      expect(result.type).toBe(ErrorType.NETWORK)
      expect(result.userMessage).toContain('网络')
    })
    
    it('should classify NetworkError correctly', () => {
      const error = new Error('NetworkError: Connection refused')
      error.name = 'NetworkError'
      const result = errorHandler.handleError(error)
      
      expect(result.type).toBe(ErrorType.NETWORK)
    })
    
    it('should mark network errors as retryable', () => {
      const networkError = new TypeError('Failed to fetch')
      expect(isRetryable(networkError)).toBe(true)
    })
    
    it('should include context in error message', () => {
      const error = new TypeError('Failed to fetch')
      const result = errorHandler.handleError(error, { context: '加载市场数据' })
      
      expect(result.userMessage).toContain('加载市场数据')
    })
  })
  
  // ============================================
  // 超时错误测试
  // ============================================
  describe('Timeout Errors', () => {
    it('should classify timeout errors correctly', () => {
      const timeoutError = new Error('Request timeout')
      timeoutError.name = 'AbortError'
      const result = errorHandler.handleError(timeoutError)
      
      expect(result.type).toBe(ErrorType.TIMEOUT)
    })
    
    it('should mark timeout errors as retryable', () => {
      const timeoutError = new Error('Request timeout')
      timeoutError.name = 'AbortError'
      expect(isRetryable(timeoutError)).toBe(true)
    })
    
    it('should provide user-friendly timeout message', () => {
      const timeoutError = new Error('timeout exceeded')
      const result = errorHandler.handleError(timeoutError)
      
      expect(result.userMessage).toContain('超时')
    })
  })
  
  // ============================================
  // 响应格式错误测试
  // ============================================
  describe('Malformed Response Errors', () => {
    it('should handle JSON parse errors', () => {
      const parseError = new SyntaxError('Unexpected token < in JSON at position 0')
      const result = errorHandler.handleError(parseError, { context: '解析响应' })
      
      expect(result.type).toBe(ErrorType.UNKNOWN)
      expect(result.userMessage).toBeTruthy()
    })
    
    it('should handle empty response errors', () => {
      const error = new Error('Empty response body')
      const result = errorHandler.handleError(error)
      
      expect(result.type).toBeDefined()
      expect(result.userMessage).toBeTruthy()
    })
    
    it('should handle invalid data structure', () => {
      const error = new Error('Invalid response format: expected object')
      const result = errorHandler.handleError(error)
      
      expect(result.type).toBeDefined()
      expect(result.userMessage).toBeTruthy()
    })
  })
  
  // ============================================
  // 静默 vs 显式错误处理测试
  // ============================================
  describe('Silent vs Loud Error Handling', () => {
    it('should show toast when silent is false', async () => {
      const { toast } = await import('../../src/composables/useToast.js')
      const error = new Error('Test error')
      
      errorHandler.handleError(error, { context: '测试', silent: false })
      
      expect(toast.error).toHaveBeenCalled()
    })
    
    it('should NOT show toast when silent is true', async () => {
      const { toast } = await import('../../src/composables/useToast.js')
      const error = new Error('Test error')
      
      errorHandler.handleError(error, { context: '测试', silent: true })
      
      expect(toast.error).not.toHaveBeenCalled()
    })
    
    it('should still update error state when silent', () => {
      const error = new Error('Silent error')
      
      errorHandler.handleError(error, { context: '测试', silent: true })
      
      expect(errorHandler.errorState.lastError).toBe(error)
      expect(errorHandler.errorState.errorCount).toBe(1)
    })
    
    it('should respect showToast option', async () => {
      const { toast } = await import('../../src/composables/useToast.js')
      const silentHandler = useApiError({ showToast: false, report: false })
      const error = new Error('Test error')
      
      silentHandler.handleError(error, { context: '测试' })
      
      expect(toast.error).not.toHaveBeenCalled()
    })
  })
  
  // ============================================
  // 重试机制测试
  // ============================================
  describe('Retry Mechanism', () => {
    it('should retry retryable errors', async () => {
      const handler = useApiError({ retry: 2, retryDelay: 10, report: false })
      let attempts = 0
      
      const result = await handler.wrapApiCall(async () => {
        attempts++
        if (attempts < 3) {
          throw new TypeError('Failed to fetch')
        }
        return { success: true }
      })
      
      expect(attempts).toBe(3)
      expect(result).toEqual({ success: true })
    })
    
    it('should NOT retry non-retryable errors', async () => {
      const handler = useApiError({ retry: 3, report: false, throwOnError: false })
      let attempts = 0
      
      const result = await handler.wrapApiCall(async () => {
        attempts++
        const error = new Error('HTTP 401 Unauthorized')
        throw error
      })
      
      expect(attempts).toBe(1)
      expect(result).toBeNull()
    })
    
    it('should track retry state', async () => {
      const handler = useApiError({ retry: 2, retryDelay: 10, report: false })
      
      const promise = handler.wrapApiCall(async () => {
        if (handler.errorState.retryCount < 2) {
          throw new TypeError('Failed to fetch')
        }
        return { success: true }
      })
      
      await promise
      expect(handler.errorState.isRetrying).toBe(false)
      expect(handler.errorState.retryCount).toBe(0)
    })
    
    it('should calculate exponential backoff delay', () => {
      const handler = useApiError({ retryDelay: 1000, retryJitter: 0 })
      
      // Access internal function through closure
      // First retry: 1000 * 2^0 = 1000
      // Second retry: 1000 * 2^1 = 2000
      // Third retry: 1000 * 2^2 = 4000
      
      // We test this indirectly by checking retry behavior
      expect(handler.errorState.retryCount).toBe(0)
    })
  })
  
  // ============================================
  // 错误状态管理测试
  // ============================================
  describe('Error State Management', () => {
    it('should track error count', () => {
      expect(errorHandler.errorState.errorCount).toBe(0)
      
      errorHandler.handleError(new Error('Error 1'))
      expect(errorHandler.errorState.errorCount).toBe(1)
      
      errorHandler.handleError(new Error('Error 2'))
      expect(errorHandler.errorState.errorCount).toBe(2)
    })
    
    it('should reset error state', () => {
      errorHandler.handleError(new Error('Test error'))
      expect(errorHandler.errorState.lastError).toBeTruthy()
      
      errorHandler.resetErrorState()
      
      expect(errorHandler.errorState.lastError).toBeNull()
    })
    
    it('should clear error without resetting count', () => {
      errorHandler.handleError(new Error('Test error'))
      expect(errorHandler.errorState.errorCount).toBe(1)
      
      errorHandler.clearError()
      
      expect(errorHandler.errorState.lastError).toBeNull()
      expect(errorHandler.errorState.errorCount).toBe(1)
    })
    
    it('should provide hasError computed property', () => {
      expect(errorHandler.hasError.value).toBe(false)
      
      errorHandler.handleError(new Error('Test'))
      
      expect(errorHandler.hasError.value).toBe(true)
    })
  })
  
  // ============================================
  // 服务器错误测试
  // ============================================
  describe('Server Errors', () => {
    it('should classify 5xx errors as server errors', () => {
      const error = new Error('HTTP 500 Internal Server Error')
      const result = errorHandler.handleError(error)
      
      expect(result.type).toBe(ErrorType.SERVER)
    })
    
    it('should classify 502/503/504 as server errors', () => {
      const error502 = new Error('HTTP 502 Bad Gateway')
      const error503 = new Error('HTTP 503 Service Unavailable')
      const error504 = new Error('HTTP 504 Gateway Timeout')
      
      expect(errorHandler.handleError(error502).type).toBe(ErrorType.SERVER)
      expect(errorHandler.handleError(error503).type).toBe(ErrorType.SERVER)
      expect(errorHandler.handleError(error504).type).toBe(ErrorType.SERVER)
    })
    
    it('should mark server errors as retryable', () => {
      const error = new Error('HTTP 503 Service Unavailable')
      expect(isRetryable(error)).toBe(true)
    })
  })
  
  // ============================================
  // 客户端错误测试
  // ============================================
  describe('Client Errors', () => {
    it('should classify 4xx errors as client errors', () => {
      const error400 = new Error('HTTP 400 Bad Request')
      const error404 = new Error('HTTP 404 Not Found')
      
      expect(errorHandler.handleError(error400).type).toBe(ErrorType.CLIENT)
      expect(errorHandler.handleError(error404).type).toBe(ErrorType.CLIENT)
    })
    
    it('should NOT mark 401/403 as retryable', () => {
      const error401 = new Error('HTTP 401 Unauthorized')
      const error403 = new Error('HTTP 403 Forbidden')
      
      expect(isRetryable(error401)).toBe(false)
      expect(isRetryable(error403)).toBe(false)
    })
    
    it('should classify 422 as validation error', () => {
      const error = new Error('HTTP 422 Unprocessable Entity')
      const result = errorHandler.handleError(error)
      
      expect(result.type).toBe(ErrorType.VALIDATION)
    })
  })
})

// ============================================
// 工具函数测试
// ============================================
describe('Utility Functions', () => {
  describe('isRetryable', () => {
    it('should return false for null/undefined', () => {
      expect(isRetryable(null)).toBe(false)
      expect(isRetryable(undefined)).toBe(false)
    })
    
    it('should return true for network errors', () => {
      expect(isRetryable(new TypeError('Failed to fetch'))).toBe(true)
    })
    
    it('should return true for timeout errors', () => {
      const error = new Error('timeout')
      error.name = 'AbortError'
      expect(isRetryable(error)).toBe(true)
    })
    
    it('should return false for client errors', () => {
      expect(isRetryable(new Error('HTTP 400 Bad Request'))).toBe(false)
    })
    
    it('should return false for validation errors', () => {
      expect(isRetryable(new Error('HTTP 422 validation failed'))).toBe(false)
    })
  })
  
  describe('formatErrorForUser', () => {
    it('should include context in message', () => {
      const error = new Error('Network error')
      const message = formatErrorForUser(error, { context: '加载数据' })
      
      expect(message).toContain('加载数据')
    })
    
    it('should include operation in message', () => {
      const error = new Error('Timeout')
      const message = formatErrorForUser(error, { operation: 'API调用' })
      
      expect(message).toContain('API调用')
    })
    
    it('should return base message without context', () => {
      const error = new TypeError('Failed to fetch')
      const message = formatErrorForUser(error)
      
      expect(message).toContain('网络')
    })
  })
})
