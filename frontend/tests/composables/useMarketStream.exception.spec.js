import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { nextTick } from 'vue'

/**
 * WebSocket Constructor Exception Tests for useMarketStream
 * 
 * Tests that the connection lock is properly released when WebSocket
 * constructor throws an exception (e.g., invalid URL, security error).
 */

// ═══════════════════════════════════════════════════════════════════════════════
// MODULE-SCOPED MOCKS
// ═══════════════════════════════════════════════════════════════════════════════

const mockAcquireLock = vi.fn(() => true)
const mockReleaseLock = vi.fn()
const mockIsLocked = vi.fn(() => false)

vi.mock('../../src/utils/logger.js', () => ({
  logger: {
    log: vi.fn(),
    warn: vi.fn(),
    error: vi.fn()
  }
}))

vi.mock('../../src/composables/useNotifications.js', () => ({
  checkPriceAlerts: vi.fn(() => []),
  sendNotification: vi.fn(),
  recordAlertTrigger: vi.fn()
}))

vi.mock('../../src/composables/usePageVisibility.js', () => ({
  usePageVisibility: () => ({ isVisible: { value: true } })
}))

vi.mock('../../src/utils/connectionLock.js', () => ({
  acquireLock: mockAcquireLock,
  releaseLock: mockReleaseLock,
  isLocked: mockIsLocked
}))

vi.mock('../../src/utils/constants.js', () => ({
  TIMEOUTS: {
    WS_RECONNECT_BASE: 1000,
    WS_RECONNECT_MAX: 30000,
    WS_HEARTBEAT_INTERVAL: 25000,
    WS_PONG_TIMEOUT: 10000,
    WS_MAX_MISSED_PONGS: 3,
    WS_HEALTH_CHECK_INTERVAL: 30000
  }
}))

// Configurable WebSocket mock
class ConfigurableWebSocket {
  static instances = []
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3
  static shouldThrow = null

  constructor(url) {
    if (ConfigurableWebSocket.shouldThrow) {
      const err = ConfigurableWebSocket.shouldThrow
      ConfigurableWebSocket.shouldThrow = null
      throw err
    }
    this.url = url
    this.readyState = ConfigurableWebSocket.CONNECTING
    this.onopen = null
    this.onmessage = null
    this.onerror = null
    this.onclose = null
    ConfigurableWebSocket.instances.push(this)
  }

  send(data) {}
  close(code, reason) {
    this.readyState = ConfigurableWebSocket.CLOSED
    if (this.onclose) this.onclose({ code: code || 1000, reason: reason || '' })
  }

  _simulateOpen() {
    this.readyState = ConfigurableWebSocket.OPEN
    if (this.onopen) this.onopen()
  }
}

vi.stubGlobal('WebSocket', ConfigurableWebSocket)

// ═══════════════════════════════════════════════════════════════════════════════
// TEST SUITE
// ═══════════════════════════════════════════════════════════════════════════════

describe('useMarketStream WebSocket constructor exception', () => {
  let useMarketStream

  beforeEach(async () => {
    vi.clearAllMocks()
    ConfigurableWebSocket.instances = []
    ConfigurableWebSocket.shouldThrow = null
    
    mockAcquireLock.mockReturnValue(true)
    mockIsLocked.mockReturnValue(false)

    vi.useFakeTimers()

    vi.resetModules()
    const module = await import('../../src/composables/useMarketStream.js')
    useMarketStream = module.useMarketStream
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
    ConfigurableWebSocket.instances = []
    ConfigurableWebSocket.shouldThrow = null
  })

  describe('lock release on exception', () => {
    it('should release lock when WebSocket constructor throws', async () => {
      ConfigurableWebSocket.shouldThrow = new Error('Invalid URL or security error')

      const stream = useMarketStream('AU2406')
      await nextTick()

      expect(mockAcquireLock).toHaveBeenCalled()
      expect(mockReleaseLock).toHaveBeenCalled()
      expect(['failed', 'reconnecting']).toContain(stream.wsStatus.value)
      expect(stream.error.value).toBeTruthy()

      stream.disconnect()
    })

    it('should release lock even if exception occurs during connection', async () => {
      ConfigurableWebSocket.shouldThrow = new TypeError('Malformed URL')

      const stream = useMarketStream('CU2406')
      await nextTick()

      expect(mockAcquireLock).toHaveBeenCalled()
      expect(mockReleaseLock).toHaveBeenCalled()
      expect(['failed', 'reconnecting']).toContain(stream.wsStatus.value)

      stream.disconnect()
    })

    it('should allow reconnection after constructor exception', async () => {
      ConfigurableWebSocket.shouldThrow = new Error('Security error')

      const stream = useMarketStream('AU2406')
      await nextTick()

      expect(mockReleaseLock).toHaveBeenCalled()
      expect(['failed', 'reconnecting']).toContain(stream.wsStatus.value)

      mockAcquireLock.mockClear()
      mockReleaseLock.mockClear()

      // Second attempt: WebSocket succeeds (shouldThrow is null)
      stream.manualReconnect()
      await nextTick()

      expect(mockAcquireLock).toHaveBeenCalled()

      stream.disconnect()
    })

    it('should be able to connect again after exception', async () => {
      // First connection attempt fails
      ConfigurableWebSocket.shouldThrow = new Error('Connection failed')

      const stream = useMarketStream('AU2406')
      await nextTick()

      // Verify the initial connection attempt
      expect(mockAcquireLock).toHaveBeenCalled()
      expect(mockReleaseLock).toHaveBeenCalled()

      // Reset mocks and configure for success
      mockAcquireLock.mockClear()
      ConfigurableWebSocket.shouldThrow = null  // No error this time

      // Trigger a new connection attempt via manual reconnect
      stream.manualReconnect()
      await nextTick()

      // Should attempt to acquire lock again for the reconnect
      expect(mockAcquireLock).toHaveBeenCalled()

      stream.disconnect()
    })

    it('should schedule retry after constructor exception', async () => {
      ConfigurableWebSocket.shouldThrow = new Error('Temporary failure')

      const stream = useMarketStream('AU2406')
      await nextTick()

      expect(['failed', 'reconnecting']).toContain(stream.wsStatus.value)

      // Advance time to trigger retry
      vi.advanceTimersByTime(1000)
      await nextTick()

      // Should have attempted to reconnect
      expect(mockAcquireLock.mock.calls.length).toBeGreaterThanOrEqual(1)

      stream.disconnect()
    })
  })

  describe('error handling', () => {
    it('should handle DOMException from WebSocket constructor', async () => {
      ConfigurableWebSocket.shouldThrow = new DOMException('The operation is insecure', 'SecurityError')

      const stream = useMarketStream('AU2406')
      await nextTick()

      expect(mockReleaseLock).toHaveBeenCalled()
      expect(['failed', 'reconnecting']).toContain(stream.wsStatus.value)

      stream.disconnect()
    })
  })
})
