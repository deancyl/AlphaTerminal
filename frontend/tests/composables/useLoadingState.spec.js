/**
 * useLoadingState.spec.js — Tri-state loading pattern tests
 * 
 * Test coverage:
 * - Tri-state transitions: idle → loading → success → error
 * - showSkeleton delay (300ms default)
 * - timeout functionality (30s default)
 * - Timer cleanup on unmount
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useLoadingState } from '../../src/composables/useLoadingState.js'

describe('useLoadingState', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  // ============================================
  // Initial State Tests
  // ============================================
  describe('Initial State', () => {
    it('should start with idle state', () => {
      const { state, isLoading, isSuccess, isError, isIdle, showSkeleton, error } = useLoadingState()

      expect(state.value).toBe('idle')
      expect(isIdle.value).toBe(true)
      expect(isLoading.value).toBe(false)
      expect(isSuccess.value).toBe(false)
      expect(isError.value).toBe(false)
      expect(showSkeleton.value).toBe(false)
      expect(error.value).toBeNull()
    })
  })

  // ============================================
  // Tri-state Transition Tests
  // ============================================
  describe('Tri-state Transitions', () => {
    it('should transition from idle to loading when startLoading() is called', () => {
      const { state, isLoading, isIdle, showSkeleton, startLoading } = useLoadingState()

      startLoading()

      expect(state.value).toBe('loading')
      expect(isLoading.value).toBe(true)
      expect(isIdle.value).toBe(false)
      // showSkeleton should be false immediately (300ms delay)
      expect(showSkeleton.value).toBe(false)
    })

    it('should show skeleton after 300ms delay', () => {
      const { showSkeleton, startLoading } = useLoadingState()

      startLoading()
      expect(showSkeleton.value).toBe(false)

      vi.advanceTimersByTime(299)
      expect(showSkeleton.value).toBe(false)

      vi.advanceTimersByTime(1)
      expect(showSkeleton.value).toBe(true)
    })

    it('should transition from loading to success when stopLoading() is called', () => {
      const { state, isSuccess, isLoading, showSkeleton, error, startLoading, stopLoading } = useLoadingState()

      startLoading()
      stopLoading()

      expect(state.value).toBe('success')
      expect(isSuccess.value).toBe(true)
      expect(isLoading.value).toBe(false)
      expect(showSkeleton.value).toBe(false)
      expect(error.value).toBeNull()
    })

    it('should transition from loading to error when stopLoading(error) is called', () => {
      const { state, isError, isLoading, showSkeleton, error, startLoading, stopLoading } = useLoadingState()
      const testError = new Error('Test error')

      startLoading()
      stopLoading(testError)

      expect(state.value).toBe('error')
      expect(isError.value).toBe(true)
      expect(isLoading.value).toBe(false)
      expect(showSkeleton.value).toBe(false)
      expect(error.value).toBe(testError)
    })

    it('should clear error when starting new load', () => {
      const { state, error, startLoading, stopLoading } = useLoadingState()
      const testError = new Error('Previous error')

      startLoading()
      stopLoading(testError)
      expect(error.value).toBe(testError)

      startLoading()
      expect(error.value).toBeNull()
      expect(state.value).toBe('loading')
    })
  })

  // ============================================
  // showSkeleton Delay Tests
  // ============================================
  describe('showSkeleton Delay (300ms)', () => {
    it('should not show skeleton immediately on fast loads', () => {
      const { showSkeleton, state, startLoading, stopLoading } = useLoadingState()

      startLoading()
      // Fast load completes before 300ms
      vi.advanceTimersByTime(100)
      stopLoading()

      expect(showSkeleton.value).toBe(false)
      expect(state.value).toBe('success')
    })

    it('should show skeleton after 300ms for slow loads', () => {
      const { showSkeleton, state, startLoading } = useLoadingState()

      startLoading()
      vi.advanceTimersByTime(300)

      expect(showSkeleton.value).toBe(true)
      expect(state.value).toBe('loading')
    })

    it('should hide skeleton when loading succeeds (respecting minDisplayTime)', () => {
      const { showSkeleton, state, startLoading, stopLoading } = useLoadingState()

      startLoading()
      vi.advanceTimersByTime(300)
      expect(showSkeleton.value).toBe(true)

      stopLoading()
      // minDisplayTime default is 400ms, we're at 300ms, need to wait 100ms more
      vi.advanceTimersByTime(100)
      expect(showSkeleton.value).toBe(false)
      expect(state.value).toBe('success')
    })

    it('should hide skeleton when loading errors', () => {
      const { showSkeleton, state, startLoading, stopLoading } = useLoadingState()

      startLoading()
      vi.advanceTimersByTime(300)
      expect(showSkeleton.value).toBe(true)

      stopLoading(new Error('Failed'))
      expect(showSkeleton.value).toBe(false)
      expect(state.value).toBe('error')
    })

    it('should support custom skeletonDelay', () => {
      const { showSkeleton, startLoading } = useLoadingState({ skeletonDelay: 500 })

      startLoading()
      vi.advanceTimersByTime(300)
      expect(showSkeleton.value).toBe(false)

      vi.advanceTimersByTime(200)
      expect(showSkeleton.value).toBe(true)
    })

    it('should show skeleton immediately when skeletonDelay is 0', () => {
      const { showSkeleton, startLoading } = useLoadingState({ skeletonDelay: 0 })

      startLoading()
      expect(showSkeleton.value).toBe(true)
    })
  })

  // ============================================
  // Timeout Tests
  // ============================================
  describe('Timeout Functionality (30s default)', () => {
    it('should transition to error after timeout', () => {
      const { state, isError, error, showSkeleton, startLoading } = useLoadingState({ timeoutMs: 30000 })

      startLoading()
      expect(state.value).toBe('loading')

      vi.advanceTimersByTime(29999)
      expect(state.value).toBe('loading')

      vi.advanceTimersByTime(1)
      expect(state.value).toBe('error')
      expect(isError.value).toBe(true)
      expect(error.value).toBeInstanceOf(Error)
      expect(error.value.message).toBe('请求超时')
      expect(showSkeleton.value).toBe(false)
    })

    it('should support custom timeout', () => {
      const { state, isError, startLoading } = useLoadingState({ timeoutMs: 5000 })

      startLoading()
      vi.advanceTimersByTime(5000)

      expect(state.value).toBe('error')
      expect(isError.value).toBe(true)
    })

    it('should clear timeout when loading succeeds', () => {
      const { state, isError, startLoading, stopLoading } = useLoadingState({ timeoutMs: 5000 })

      startLoading()
      vi.advanceTimersByTime(2000)
      stopLoading()

      // Advance past timeout - should not error
      vi.advanceTimersByTime(5000)
      expect(state.value).toBe('success')
      expect(isError.value).toBe(false)
    })

    it('should clear timeout when loading errors', () => {
      const { state, startLoading, stopLoading } = useLoadingState({ timeoutMs: 5000 })

      startLoading()
      vi.advanceTimersByTime(1000)
      stopLoading(new Error('Custom error'))

      vi.advanceTimersByTime(5000)
      expect(state.value).toBe('error')
      // Should keep custom error, not timeout error
    })
  })

  // ============================================
  // onTimeout Callback Tests
  // ============================================
  describe('onTimeout Callback', () => {
    it('should call onTimeout when timeout occurs', () => {
      const onTimeout = vi.fn()
      const { state, startLoading } = useLoadingState({ timeoutMs: 5000, onTimeout })

      startLoading()
      vi.advanceTimersByTime(5000)

      expect(onTimeout).toHaveBeenCalledTimes(1)
      expect(state.value).toBe('error')
    })

    it('should NOT call onTimeout if loading succeeds before timeout', () => {
      const onTimeout = vi.fn()
      const { state, startLoading, stopLoading } = useLoadingState({ timeoutMs: 5000, onTimeout })

      startLoading()
      vi.advanceTimersByTime(2000)
      stopLoading()
      vi.advanceTimersByTime(3000)

      expect(onTimeout).not.toHaveBeenCalled()
      expect(state.value).toBe('success')
    })
  })

  // ============================================
  // onError Callback Tests
  // ============================================
  describe('onError Callback', () => {
    it('should call onError when stopLoading(error) is called', () => {
      const onError = vi.fn()
      const testError = new Error('Test error')
      const { state, startLoading, stopLoading } = useLoadingState({ onError })

      startLoading()
      stopLoading(testError)

      expect(onError).toHaveBeenCalledWith(testError)
      expect(state.value).toBe('error')
    })

    it('should NOT call onError on success', () => {
      const onError = vi.fn()
      const { state, startLoading, stopLoading } = useLoadingState({ onError })

      startLoading()
      stopLoading()

      expect(onError).not.toHaveBeenCalled()
      expect(state.value).toBe('success')
    })
  })

  // ============================================
  // minDisplayTime Tests
  // ============================================
  describe('minDisplayTime', () => {
    it('should keep skeleton visible for minimum display time', () => {
      const { showSkeleton, state, startLoading, stopLoading } = useLoadingState({ minDisplayTime: 500, skeletonDelay: 0 })

      startLoading()
      expect(showSkeleton.value).toBe(true)

      // Load completes in 100ms (faster than minDisplayTime)
      vi.advanceTimersByTime(100)
      stopLoading()

      // Should still show skeleton until minDisplayTime elapsed
      expect(showSkeleton.value).toBe(true)
      expect(state.value).toBe('loading')

      vi.advanceTimersByTime(400)
      expect(showSkeleton.value).toBe(false)
      expect(state.value).toBe('success')
    })

    it('should transition immediately if load took longer than minDisplayTime', () => {
      const { showSkeleton, state, startLoading, stopLoading } = useLoadingState({ minDisplayTime: 300, skeletonDelay: 0 })

      startLoading()
      vi.advanceTimersByTime(500) // Already past minDisplayTime
      stopLoading()

      expect(showSkeleton.value).toBe(false)
      expect(state.value).toBe('success')
    })

    it('should NOT apply minDisplayTime if skeleton was not shown', () => {
      const { showSkeleton, state, startLoading, stopLoading } = useLoadingState({ minDisplayTime: 500, skeletonDelay: 300 })

      startLoading()
      vi.advanceTimersByTime(100) // Skeleton not shown yet
      stopLoading()

      // Should transition immediately since skeleton was never shown
      expect(showSkeleton.value).toBe(false)
      expect(state.value).toBe('success')
    })
  })

  // ============================================
  // reset() Tests
  // ============================================
  describe('reset()', () => {
    it('should reset all state to idle', () => {
      const { state, error, showSkeleton, isIdle, startLoading, stopLoading, reset } = useLoadingState()

      startLoading()
      vi.advanceTimersByTime(300)
      stopLoading(new Error('Test'))

      reset()

      expect(state.value).toBe('idle')
      expect(error.value).toBeNull()
      expect(showSkeleton.value).toBe(false)
      expect(isIdle.value).toBe(true)
    })

    it('should clear all timers', () => {
      const onTimeout = vi.fn()
      const { state, startLoading, reset } = useLoadingState({ timeoutMs: 5000, onTimeout })

      startLoading()
      vi.advanceTimersByTime(2000)
      reset()
      vi.advanceTimersByTime(5000) // Past original timeout

      expect(onTimeout).not.toHaveBeenCalled()
      expect(state.value).toBe('idle')
    })
  })

  // ============================================
  // Timer Cleanup Tests
  // ============================================
  describe('Timer Cleanup', () => {
    it('should clear skeleton delay timer on stopLoading', () => {
      const { showSkeleton, state, startLoading, stopLoading } = useLoadingState({ skeletonDelay: 300 })

      startLoading()
      vi.advanceTimersByTime(100)
      stopLoading()

      // Advance past 300ms - skeleton should never show
      vi.advanceTimersByTime(500)
      expect(showSkeleton.value).toBe(false)
      expect(state.value).toBe('success')
    })

    it('should clear timeout timer on stopLoading', () => {
      const onTimeout = vi.fn()
      const { state, startLoading, stopLoading } = useLoadingState({ timeoutMs: 5000, onTimeout })

      startLoading()
      vi.advanceTimersByTime(2000)
      stopLoading()
      vi.advanceTimersByTime(5000)

      expect(onTimeout).not.toHaveBeenCalled()
    })

    it('should clear all timers on reset', () => {
      const onTimeout = vi.fn()
      const { state, startLoading, reset } = useLoadingState({ timeoutMs: 5000, onTimeout })

      startLoading()
      reset()
      vi.advanceTimersByTime(10000)

      expect(onTimeout).not.toHaveBeenCalled()
      expect(state.value).toBe('idle')
    })

    it('should handle multiple startLoading calls', () => {
      const onTimeout = vi.fn()
      const { state, showSkeleton, startLoading } = useLoadingState({ timeoutMs: 5000, onTimeout })

      startLoading()
      vi.advanceTimersByTime(1000)

      startLoading() // Restart - should clear previous timers
      vi.advanceTimersByTime(4000)
      expect(state.value).toBe('loading')

      vi.advanceTimersByTime(1000)
      expect(state.value).toBe('error')
      expect(onTimeout).toHaveBeenCalledTimes(1)
    })
  })

  // ============================================
  // Edge Cases
  // ============================================
  describe('Edge Cases', () => {
    it('should handle stopLoading without startLoading', () => {
      const { state, isSuccess, stopLoading } = useLoadingState()

      stopLoading()

      expect(state.value).toBe('success')
      expect(isSuccess.value).toBe(true)
    })

    it('should handle reset without startLoading', () => {
      const { state, isIdle, reset } = useLoadingState()

      reset()

      expect(state.value).toBe('idle')
      expect(isIdle.value).toBe(true)
    })

    it('should handle multiple stopLoading calls', () => {
      const { state, error, startLoading, stopLoading } = useLoadingState()
      const error1 = new Error('Error 1')
      const error2 = new Error('Error 2')

      startLoading()
      stopLoading(error1)
      expect(error.value).toBe(error1)

      stopLoading(error2)
      expect(error.value).toBe(error2)
      expect(state.value).toBe('error')
    })

    it('should handle multiple reset calls', () => {
      const { state, isIdle, reset } = useLoadingState()

      reset()
      reset()
      reset()

      expect(state.value).toBe('idle')
      expect(isIdle.value).toBe(true)
    })
  })

  // ============================================
  // Integration Tests
  // ============================================
  describe('Integration', () => {
    it('should handle complete loading lifecycle', () => {
      const { state, isLoading, isSuccess, showSkeleton, error, isIdle, startLoading, stopLoading } = useLoadingState()

      // Initial state
      expect(state.value).toBe('idle')
      expect(isIdle.value).toBe(true)

      // Start loading
      startLoading()
      expect(state.value).toBe('loading')
      expect(isLoading.value).toBe(true)
      expect(showSkeleton.value).toBe(false)

      // After 300ms
      vi.advanceTimersByTime(300)
      expect(showSkeleton.value).toBe(true)

      // Complete successfully (need extra 100ms for minDisplayTime)
      stopLoading()
      vi.advanceTimersByTime(100)
      expect(state.value).toBe('success')
      expect(isSuccess.value).toBe(true)
      expect(showSkeleton.value).toBe(false)
      expect(error.value).toBeNull()
    })

    it('should handle error lifecycle', () => {
      const { state, isError, showSkeleton, error, startLoading, stopLoading } = useLoadingState()
      const testError = new Error('Network failed')

      startLoading()
      vi.advanceTimersByTime(300)
      expect(showSkeleton.value).toBe(true)

      stopLoading(testError)
      expect(state.value).toBe('error')
      expect(isError.value).toBe(true)
      expect(showSkeleton.value).toBe(false)
      expect(error.value).toBe(testError)
    })

    it('should handle timeout lifecycle', () => {
      const { state, isError, showSkeleton, error, startLoading } = useLoadingState({ timeoutMs: 10000 })

      startLoading()
      vi.advanceTimersByTime(300)
      expect(showSkeleton.value).toBe(true)

      vi.advanceTimersByTime(9700) // Total 10000ms
      expect(state.value).toBe('error')
      expect(isError.value).toBe(true)
      expect(showSkeleton.value).toBe(false)
      expect(error.value.message).toBe('请求超时')
    })

    it('should handle retry scenario (error → startLoading → success)', () => {
      const { state, isError, isSuccess, error, startLoading, stopLoading } = useLoadingState()

      // First attempt fails
      startLoading()
      stopLoading(new Error('Failed'))

      expect(state.value).toBe('error')
      expect(error.value.message).toBe('Failed')

      // Retry
      startLoading()
      expect(state.value).toBe('loading')
      expect(error.value).toBeNull()

      stopLoading()
      expect(state.value).toBe('success')
      expect(isSuccess.value).toBe(true)
    })
  })
})
