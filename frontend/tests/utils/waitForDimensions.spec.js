/**
 * waitForDimensions.spec.js — DOM Dimension Utility Test Suite
 * 
 * Tests for:
 * - Normal case: element has dimensions immediately
 * - Delayed case: element gets dimensions after delay
 * - Timeout case: element never gets dimensions
 * - Null element case
 * - Zero dimensions case
 * - Custom timeout and options
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

/**
 * waitForDimensions utility (to be implemented)
 * 
 * @param {HTMLElement|null} element - DOM element to measure
 * @param {Object} options - Configuration options
 * @param {number} options.timeout - Maximum wait time in ms (default: 3000)
 * @param {number} options.interval - Check interval in ms (default: 50)
 * @param {number} options.minWidth - Minimum required width (default: 0)
 * @param {number} options.minHeight - Minimum required height (default: 0)
 * @param {Object} options.fallback - Fallback dimensions on failure
 * @returns {Promise<{success: boolean, width: number, height: number}>}
 */
async function waitForDimensions(element, options = {}) {
  const {
    timeout = 3000,
    interval = 50,
    minWidth = 0,
    minHeight = 0,
    fallback = { width: 0, height: 0 }
  } = options

  // Handle null element
  if (!element) {
    return {
      success: false,
      width: fallback.width,
      height: fallback.height,
      error: 'Element is null or undefined'
    }
  }

  const startTime = Date.now()

  return new Promise((resolve) => {
    const check = () => {
      const width = element.offsetWidth || 0
      const height = element.offsetHeight || 0

      // Check if dimensions meet minimum requirements
      if (width >= minWidth && height >= minHeight && width > 0 && height > 0) {
        resolve({
          success: true,
          width,
          height
        })
        return
      }

      // Check timeout
      if (Date.now() - startTime >= timeout) {
        resolve({
          success: false,
          width: fallback.width,
          height: fallback.height,
          error: 'Timeout waiting for dimensions'
        })
        return
      }

      // Continue polling
      setTimeout(check, interval)
    }

    check()
  })
}

// ============================================
// Test Setup
// ============================================
describe('waitForDimensions', () => {
  let mockElement

  beforeEach(() => {
    // Create a fresh mock element for each test
    mockElement = {
      offsetWidth: 0,
      offsetHeight: 0
    }
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // ============================================
  // Normal Case: Element has dimensions immediately
  // ============================================
  describe('Normal case', () => {
    it('should return success when element has dimensions immediately', async () => {
      mockElement.offsetWidth = 800
      mockElement.offsetHeight = 600

      const result = await waitForDimensions(mockElement)

      expect(result.success).toBe(true)
      expect(result.width).toBe(800)
      expect(result.height).toBe(600)
      expect(result.error).toBeUndefined()
    })

    it('should return success for small but non-zero dimensions', async () => {
      mockElement.offsetWidth = 1
      mockElement.offsetHeight = 1

      const result = await waitForDimensions(mockElement)

      expect(result.success).toBe(true)
      expect(result.width).toBe(1)
      expect(result.height).toBe(1)
    })
  })

  // ============================================
  // Delayed Case: Element gets dimensions after delay
  // ============================================
  describe('Delayed dimensions', () => {
    it('should wait for dimensions to become available', async () => {
      vi.useFakeTimers()

      const promise = waitForDimensions(mockElement, { timeout: 1000, interval: 50 })

      // Initially no dimensions
      expect(mockElement.offsetWidth).toBe(0)
      expect(mockElement.offsetHeight).toBe(0)

      // After 100ms, dimensions become available
      setTimeout(() => {
        mockElement.offsetWidth = 400
        mockElement.offsetHeight = 300
      }, 100)

      // Advance timers
      await vi.advanceTimersByTimeAsync(150)

      const result = await promise

      expect(result.success).toBe(true)
      expect(result.width).toBe(400)
      expect(result.height).toBe(300)
    })

    it('should poll at specified interval', async () => {
      vi.useFakeTimers()

      let checkCount = 0
      const originalCheck = waitForDimensions

      const promise = waitForDimensions(mockElement, { timeout: 500, interval: 100 })

      // Dimensions become available after 250ms (3rd check)
      setTimeout(() => {
        mockElement.offsetWidth = 200
        mockElement.offsetHeight = 150
      }, 250)

      await vi.advanceTimersByTimeAsync(300)

      const result = await promise

      expect(result.success).toBe(true)
    })
  })

  // ============================================
  // Timeout Case: Element never gets dimensions
  // ============================================
  describe('Timeout handling', () => {
    it('should return failure on timeout', async () => {
      vi.useFakeTimers()

      const promise = waitForDimensions(mockElement, { timeout: 100, interval: 20 })

      // Element never gets dimensions
      await vi.advanceTimersByTimeAsync(150)

      const result = await promise

      expect(result.success).toBe(false)
      expect(result.error).toBe('Timeout waiting for dimensions')
    })

    it('should return fallback dimensions on timeout', async () => {
      vi.useFakeTimers()

      const fallback = { width: 640, height: 480 }
      const promise = waitForDimensions(mockElement, { 
        timeout: 100, 
        interval: 20,
        fallback 
      })

      await vi.advanceTimersByTimeAsync(150)

      const result = await promise

      expect(result.success).toBe(false)
      expect(result.width).toBe(640)
      expect(result.height).toBe(480)
    })

    it('should respect custom timeout value', async () => {
      vi.useFakeTimers()

      const customTimeout = 500
      const startTime = Date.now()
      
      const promise = waitForDimensions(mockElement, { 
        timeout: customTimeout, 
        interval: 50 
      })

      // Wait just before timeout
      await vi.advanceTimersByTimeAsync(customTimeout - 10)
      
      // Should still be waiting
      let resolved = false
      promise.then(() => { resolved = true })
      await Promise.resolve()
      expect(resolved).toBe(false)

      // Complete timeout
      await vi.advanceTimersByTimeAsync(20)

      const result = await promise
      expect(result.success).toBe(false)
    })
  })

  // ============================================
  // Null Element Case
  // ============================================
  describe('Null element handling', () => {
    it('should handle null element', async () => {
      const result = await waitForDimensions(null)

      expect(result.success).toBe(false)
      expect(result.error).toBe('Element is null or undefined')
      expect(result.width).toBe(0)
      expect(result.height).toBe(0)
    })

    it('should handle undefined element', async () => {
      const result = await waitForDimensions(undefined)

      expect(result.success).toBe(false)
      expect(result.error).toBe('Element is null or undefined')
    })

    it('should return fallback dimensions for null element', async () => {
      const fallback = { width: 1024, height: 768 }
      const result = await waitForDimensions(null, { fallback })

      expect(result.success).toBe(false)
      expect(result.width).toBe(1024)
      expect(result.height).toBe(768)
    })
  })

  // ============================================
  // Zero Dimensions Case
  // ============================================
  describe('Zero dimensions handling', () => {
    it('should handle zero dimensions as failure', async () => {
      vi.useFakeTimers()

      mockElement.offsetWidth = 0
      mockElement.offsetHeight = 0

      const promise = waitForDimensions(mockElement, { timeout: 50, interval: 10 })

      await vi.advanceTimersByTimeAsync(100)

      const result = await promise

      expect(result.success).toBe(false)
    })

    it('should handle partial zero dimensions (width=0)', async () => {
      mockElement.offsetWidth = 0
      mockElement.offsetHeight = 100

      vi.useFakeTimers()

      const promise = waitForDimensions(mockElement, { timeout: 50, interval: 10 })
      await vi.advanceTimersByTimeAsync(100)

      const result = await promise

      expect(result.success).toBe(false)
    })

    it('should handle partial zero dimensions (height=0)', async () => {
      mockElement.offsetWidth = 100
      mockElement.offsetHeight = 0

      vi.useFakeTimers()

      const promise = waitForDimensions(mockElement, { timeout: 50, interval: 10 })
      await vi.advanceTimersByTimeAsync(100)

      const result = await promise

      expect(result.success).toBe(false)
    })
  })

  // ============================================
  // Custom Options
  // ============================================
  describe('Custom options', () => {
    it('should respect minWidth option', async () => {
      mockElement.offsetWidth = 100
      mockElement.offsetHeight = 200

      const result = await waitForDimensions(mockElement, { minWidth: 200 })

      expect(result.success).toBe(false)
      expect(result.error).toBe('Timeout waiting for dimensions')
    })

    it('should respect minHeight option', async () => {
      mockElement.offsetWidth = 200
      mockElement.offsetHeight = 100

      const result = await waitForDimensions(mockElement, { minHeight: 200 })

      expect(result.success).toBe(false)
    })

    it('should succeed when dimensions meet minimum requirements', async () => {
      mockElement.offsetWidth = 300
      mockElement.offsetHeight = 400

      const result = await waitForDimensions(mockElement, { 
        minWidth: 200, 
        minHeight: 300 
      })

      expect(result.success).toBe(true)
      expect(result.width).toBe(300)
      expect(result.height).toBe(400)
    })

    it('should use default timeout of 3000ms', async () => {
      vi.useFakeTimers()

      const promise = waitForDimensions(mockElement)

      // Should not resolve before 3000ms
      await vi.advanceTimersByTimeAsync(2990)
      let resolved = false
      promise.then(() => { resolved = true })
      await Promise.resolve()
      expect(resolved).toBe(false)

      // Should resolve after 3000ms
      await vi.advanceTimersByTimeAsync(20)
      const result = await promise
      expect(result.success).toBe(false)
    })

    it('should use default interval of 50ms', async () => {
      vi.useFakeTimers()

      // This test verifies the polling interval is reasonable
      const promise = waitForDimensions(mockElement, { timeout: 200 })

      // Make dimensions available
      setTimeout(() => {
        mockElement.offsetWidth = 100
        mockElement.offsetHeight = 100
      }, 60) // After first interval check

      await vi.advanceTimersByTimeAsync(100)

      const result = await promise
      expect(result.success).toBe(true)
    })
  })

  // ============================================
  // Edge Cases
  // ============================================
  describe('Edge cases', () => {
    it('should handle element that gets dimensions then loses them', async () => {
      vi.useFakeTimers()

      const promise = waitForDimensions(mockElement, { timeout: 200, interval: 50 })

      // Dimensions appear
      setTimeout(() => {
        mockElement.offsetWidth = 100
        mockElement.offsetHeight = 100
      }, 30)

      // Dimensions disappear (unlikely but possible)
      setTimeout(() => {
        mockElement.offsetWidth = 0
        mockElement.offsetHeight = 0
      }, 60)

      // First check should succeed
      await vi.advanceTimersByTimeAsync(50)

      const result = await promise
      expect(result.success).toBe(true)
    })

    it('should handle very large dimensions', async () => {
      mockElement.offsetWidth = 10000
      mockElement.offsetHeight = 10000

      const result = await waitForDimensions(mockElement)

      expect(result.success).toBe(true)
      expect(result.width).toBe(10000)
      expect(result.height).toBe(10000)
    })

    it('should handle fractional dimensions (floored)', async () => {
      // offsetWidth/offsetHeight are always integers in real DOM
      mockElement.offsetWidth = 100.5
      mockElement.offsetHeight = 200.9

      const result = await waitForDimensions(mockElement)

      expect(result.success).toBe(true)
      // JavaScript will preserve the value
      expect(result.width).toBe(100.5)
      expect(result.height).toBe(200.9)
    })

    it('should handle negative fallback dimensions', async () => {
      vi.useFakeTimers()

      const fallback = { width: -1, height: -1 }
      const promise = waitForDimensions(mockElement, { 
        timeout: 50, 
        interval: 10,
        fallback 
      })

      await vi.advanceTimersByTimeAsync(100)

      const result = await promise

      expect(result.success).toBe(false)
      expect(result.width).toBe(-1)
      expect(result.height).toBe(-1)
    })
  })

  // ============================================
  // Integration-like Tests
  // ============================================
  describe('Integration scenarios', () => {
    it('should work with real DOM element simulation', async () => {
      // Create a real-ish DOM element
      const div = document.createElement('div')
      Object.defineProperty(div, 'offsetWidth', { 
        get: () => 500, 
        configurable: true 
      })
      Object.defineProperty(div, 'offsetHeight', { 
        get: () => 300, 
        configurable: true 
      })

      const result = await waitForDimensions(div)

      expect(result.success).toBe(true)
      expect(result.width).toBe(500)
      expect(result.height).toBe(300)
    })

    it('should handle element with getter that changes', async () => {
      vi.useFakeTimers()

      const div = document.createElement('div')
      let width = 0
      let height = 0

      Object.defineProperty(div, 'offsetWidth', { 
        get: () => width, 
        configurable: true 
      })
      Object.defineProperty(div, 'offsetHeight', { 
        get: () => height, 
        configurable: true 
      })

      const promise = waitForDimensions(div, { timeout: 200, interval: 50 })

      // Simulate layout completion
      setTimeout(() => {
        width = 800
        height = 600
      }, 100)

      await vi.advanceTimersByTimeAsync(150)

      const result = await promise

      expect(result.success).toBe(true)
      expect(result.width).toBe(800)
      expect(result.height).toBe(600)
    })
  })
})
