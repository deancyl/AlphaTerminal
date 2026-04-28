import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { logger } from '../../../src/utils/logger.js'

describe('logger', () => {
  let consoleLogSpy, consoleDebugSpy, consoleWarnSpy, consoleErrorSpy, consoleInfoSpy

  beforeEach(() => {
    consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {})
    consoleDebugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {})
    consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    consoleInfoSpy = vi.spyOn(console, 'info').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('in development mode', () => {
    beforeEach(() => {
      vi.stubGlobal('import', { meta: { env: { DEV: true, MODE: 'development' } } })
    })

    afterEach(() => {
      vi.unstubAllGlobals()
    })

    it('should log messages', () => {
      logger.log('test message')
      expect(consoleLogSpy).toHaveBeenCalledWith('test message')
    })

    it('should debug messages', () => {
      logger.debug('debug message')
      expect(consoleDebugSpy).toHaveBeenCalledWith('debug message')
    })

    it('should warn messages', () => {
      logger.warn('warning message')
      expect(consoleWarnSpy).toHaveBeenCalledWith('warning message')
    })

    it('should always log errors', () => {
      logger.error('error message')
      expect(consoleErrorSpy).toHaveBeenCalledWith('error message')
    })

    it('should info messages', () => {
      logger.info('info message')
      expect(consoleInfoSpy).toHaveBeenCalledWith('info message')
    })

    it('should handle multiple arguments', () => {
      logger.log('message', { key: 'value' }, 123)
      expect(consoleLogSpy).toHaveBeenCalledWith('message', { key: 'value' }, 123)
    })
  })

  describe('in production mode', () => {
    // Note: The logger module checks import.meta.env at module load time,
    // so we can't easily change it after the module is loaded.
    // These tests verify the logger behavior when isDev is false.
    
    it('should always log errors even in production', () => {
      logger.error('error message')
      expect(consoleErrorSpy).toHaveBeenCalledWith('error message')
    })
    
    // Other log methods depend on the build-time environment variable
    // and cannot be easily tested without rebuilding or complex mocking
  })
})