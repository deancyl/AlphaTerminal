import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { acquireLock, releaseLock, isLocked } from '../../src/utils/connectionLock.js'

describe('connectionLock', () => {
  beforeEach(() => {
    // Reset lock state before each test
    releaseLock()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('acquireLock', () => {
    it('acquires lock successfully when unlocked', () => {
      expect(isLocked()).toBe(false)
      const result = acquireLock()
      expect(result).toBe(true)
      expect(isLocked()).toBe(true)
    })

    it('fails to acquire lock when already locked', () => {
      acquireLock()
      const result = acquireLock()
      expect(result).toBe(false)
      expect(isLocked()).toBe(true)
    })

    it('auto-releases lock after 5 seconds', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      
      acquireLock()
      expect(isLocked()).toBe(true)
      
      // Advance time by 5 seconds
      vi.advanceTimersByTime(5000)
      
      expect(isLocked()).toBe(false)
      expect(warnSpy).toHaveBeenCalledWith('[connectionLock] Auto-releasing lock after 5s')
      
      warnSpy.mockRestore()
    })

    it('does not auto-release before 5 seconds', () => {
      acquireLock()
      
      // Advance time by 4.9 seconds
      vi.advanceTimersByTime(4900)
      
      expect(isLocked()).toBe(true)
    })
  })

  describe('releaseLock', () => {
    it('releases lock successfully', () => {
      acquireLock()
      expect(isLocked()).toBe(true)
      
      releaseLock()
      
      expect(isLocked()).toBe(false)
    })

    it('clears auto-release timeout when called manually', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      
      acquireLock()
      releaseLock()
      
      // Advance time past auto-release threshold
      vi.advanceTimersByTime(6000)
      
      // Should not warn because timeout was cleared
      expect(warnSpy).not.toHaveBeenCalled()
      
      warnSpy.mockRestore()
    })

    it('is safe to call when already unlocked', () => {
      expect(() => releaseLock()).not.toThrow()
      expect(isLocked()).toBe(false)
    })
  })

  describe('isLocked', () => {
    it('returns false initially', () => {
      expect(isLocked()).toBe(false)
    })

    it('returns true after acquireLock', () => {
      acquireLock()
      expect(isLocked()).toBe(true)
    })

    it('returns false after releaseLock', () => {
      acquireLock()
      releaseLock()
      expect(isLocked()).toBe(false)
    })
  })

  describe('lock lifecycle', () => {
    it('allows re-acquiring lock after release', () => {
      acquireLock()
      releaseLock()
      
      const result = acquireLock()
      expect(result).toBe(true)
      expect(isLocked()).toBe(true)
    })

    it('allows re-acquiring lock after auto-release', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      
      acquireLock()
      vi.advanceTimersByTime(5000)
      
      const result = acquireLock()
      expect(result).toBe(true)
      expect(isLocked()).toBe(true)
      
      warnSpy.mockRestore()
    })
  })
})
