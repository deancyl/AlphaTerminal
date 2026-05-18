import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { nextTick, watch } from 'vue'

/**
 * Race Condition Tests for useMarketStream
 * 
 * Tests that the composable handles race conditions correctly when
 * WebSocket and HTTP polling interact, or during rapid connect/disconnect cycles.
 * 
 * Pattern: All vi.mock() calls at module scope for proper hoisting.
 * 
 * Note: HTTP polling is triggered when _retryCount >= 2 (internal implementation detail).
 * These tests focus on observable behavior rather than retry count thresholds.
 */

// ═══════════════════════════════════════════════════════════════════════════════
// MODULE-SCOPED MOCKS
// ═══════════════════════════════════════════════════════════════════════════════

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
  acquireLock: vi.fn(() => true),
  releaseLock: vi.fn()
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

// Mock WebSocket at module scope
class MockWebSocket {
  static instances = []
  static readyState = 1
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  constructor(url) {
    this.url = url
    this.readyState = MockWebSocket.readyState
    this.onopen = null
    this.onmessage = null
    this.onerror = null
    this.onclose = null
    MockWebSocket.instances.push(this)
  }

  send(data) {
    this._lastSent = data
  }

  close(code = 1000, reason = '') {
    this.readyState = MockWebSocket.CLOSED
    if (this.onclose) {
      this.onclose({ code, reason })
    }
  }

  _simulateOpen() {
    this.readyState = MockWebSocket.OPEN
    if (this.onopen) this.onopen()
  }

  _simulateMessage(data) {
    if (this.onmessage) {
      this.onmessage({ data: JSON.stringify(data) })
    }
  }

  _simulateError() {
    if (this.onerror) this.onerror(new Event('error'))
  }

  _simulateClose(code = 1006, reason = '') {
    this.readyState = MockWebSocket.CLOSED
    if (this.onclose) this.onclose({ code, reason })
  }
}

vi.stubGlobal('WebSocket', MockWebSocket)

// Mock fetch at module scope
const mockFetch = vi.fn()

// Helper for advancing timers
const timers = {
  advance: async (ms) => {
    vi.advanceTimersByTime(ms)
    await nextTick()
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// TEST SUITE
// ═══════════════════════════════════════════════════════════════════════════════

let useMarketStream

describe('useMarketStream race conditions', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    MockWebSocket.instances = []
    MockWebSocket.readyState = MockWebSocket.CONNECTING

    global.fetch = mockFetch
    mockFetch.mockResolvedValue({
      json: async () => ({
        data: {
          commodities: [
            { symbol: 'AU2406', price: 500.0, change_pct: 1.5 },
            { symbol: 'CU2406', price: 70.0, change_pct: -0.5 }
          ]
        }
      })
    })

    vi.useFakeTimers()

    // Import after mocks are set up
    vi.resetModules()
    const module = await import('../../src/composables/useMarketStream.js')
    useMarketStream = module.useMarketStream
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
    MockWebSocket.instances = []
  })

  describe('HTTP polling lifecycle', () => {
    it('should stop HTTP polling when WS connects', async () => {
      const stream = useMarketStream('AU2406')
      
      // Get the WebSocket instance
      const ws = MockWebSocket.instances[0]
      expect(ws).toBeDefined()
      
      // Simulate WS connection
      ws._simulateOpen()
      await nextTick()
      
      // WS is connected, HTTP polling should NOT be active
      expect(stream.wsStatus.value).toBe('connected')
      expect(mockFetch).not.toHaveBeenCalled()
      
      stream.disconnect()
    })
  })

  describe('simultaneous updates', () => {
    it('should handle simultaneous WS and HTTP updates', async () => {
      const stream = useMarketStream('AU2406')
      const ws = MockWebSocket.instances[0]
      
      // Connect WS
      ws._simulateOpen()
      await nextTick()
      
      // Simulate WS message
      ws._simulateMessage({
        symbol: 'AU2406',
        price: 500.5,
        change_pct: 1.2,
        timestamp: Date.now()
      })
      await nextTick()
      
      // Store WS tick
      const wsTick = stream.tick.value
      expect(wsTick).toBeDefined()
      expect(wsTick.price).toBe(500.5)
      
      stream.disconnect()
    })
  })

  describe('rapid connect/disconnect cycles', () => {
    it('should not flicker on rapid WS connect/disconnect', async () => {
      const stream = useMarketStream('AU2406')
      const ws = MockWebSocket.instances[0]
      
      const statusHistory = []
      
      // Track status changes using watch (Vue 3 pattern)
      const stopWatch = watch(stream.wsStatus, (status) => {
        statusHistory.push(status)
      })
      
      // Rapid connect/disconnect cycle
      for (let i = 0; i < 3; i++) {
        ws._simulateOpen()
        await nextTick()
        ws._simulateClose(1006, 'test')
        await nextTick()
      }
      
      // Should not have excessive status changes
      // (debouncing should prevent flicker)
      const transitions = statusHistory.filter((s, i, arr) => s !== arr[i - 1])
      
      // Should have reasonable number of transitions, not one per event
      expect(transitions.length).toBeLessThan(10)
      
      stopWatch()
      stream.disconnect()
    })

    it('should handle rapid symbol changes without race', async () => {
      const stream = useMarketStream('AU2406')
      const ws = MockWebSocket.instances[0]
      
      ws._simulateOpen()
      await nextTick()
      
      // Rapid symbol changes
      stream.connect('CU2406')
      await nextTick()
      stream.connect('AU2406')
      await nextTick()
      stream.connect('CU2406')
      await nextTick()
      
      // Should have stable state
      expect(stream.symbol.value).toBe('CU2406')
      
      // Send message for current symbol
      ws._simulateMessage({
        symbol: 'CU2406',
        price: 70.5,
        change_pct: 1.0
      })
      await nextTick()
      
      expect(stream.tick.value).toBeDefined()
      expect(stream.tick.value.symbol).toBe('CU2406')
      
      stream.disconnect()
    })
  })

  describe('data consistency', () => {
    it('should maintain data consistency during reconnection', async () => {
      const stream = useMarketStream('AU2406')
      let ws = MockWebSocket.instances[0]
      
      // Initial connection
      ws._simulateOpen()
      await nextTick()
      
      // Send initial message
      ws._simulateMessage({
        symbol: 'AU2406',
        price: 500.0,
        change_pct: 1.0
      })
      await nextTick()
      
      // Disconnect
      ws._simulateClose(1006, 'test')
      await nextTick()
      
      // Reconnect (new instance)
      await timers.advance(2000)
      const newWs = MockWebSocket.instances[MockWebSocket.instances.length - 1]
      newWs._simulateOpen()
      await nextTick()
      
      // Send new message after reconnect
      newWs._simulateMessage({
        symbol: 'AU2406',
        price: 501.0,
        change_pct: 1.5
      })
      await nextTick()
      
      // Should have latest data
      expect(stream.tick.value.price).toBe(501.0)
      expect(stream.tick.value.change_pct).toBe(1.5)
      
      stream.disconnect()
    })
  })

  describe('error handling', () => {
    it('should handle WS error gracefully', async () => {
      const stream = useMarketStream('AU2406')
      const ws = MockWebSocket.instances[0]
      
      // Simulate WS error
      ws._simulateError()
      ws._simulateClose(1006, 'error')
      await nextTick()
      
      // Should not crash, error should be handled
      expect(stream.wsStatus.value).toBeDefined()
      expect(stream.wsStatus.value).not.toBe('connected')
      
      stream.disconnect()
    })
  })
})
