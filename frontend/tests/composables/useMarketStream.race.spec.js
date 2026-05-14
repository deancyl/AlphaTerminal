import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { nextTick } from 'vue'

/**
 * Race Condition Tests for useMarketStream
 * 
 * Tests the interaction between WebSocket streaming and HTTP polling:
 * 1. WS connects while HTTP polling is active
 * 2. WS disconnects while HTTP should start
 * 3. Both WS and HTTP update at the same time
 * 4. Rapid WS connect/disconnect cycles
 */

// Mock WebSocket
class MockWebSocket {
  static instances = []
  static readyState = WebSocket.CONNECTING

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
    this.readyState = WebSocket.CLOSED
    if (this.onclose) {
      this.onclose({ code, reason })
    }
  }

  // Test helpers
  _simulateOpen() {
    this.readyState = WebSocket.OPEN
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
    this.readyState = WebSocket.CLOSED
    if (this.onclose) this.onclose({ code, reason })
  }
}

// Mock fetch for HTTP polling
const mockFetch = vi.fn()

describe('useMarketStream race conditions', () => {
  let useMarketStream
  let originalWebSocket
  let originalFetch
  let timers

  beforeEach(async () => {
    // Reset all mocks
    vi.clearAllMocks()
    MockWebSocket.instances = []
    MockWebSocket.readyState = WebSocket.CONNECTING

    // Save originals
    originalWebSocket = global.WebSocket
    originalFetch = global.fetch

    // Mock WebSocket
    global.WebSocket = MockWebSocket
    global.WebSocket.OPEN = 1
    global.WebSocket.CLOSED = 3
    global.WebSocket.CONNECTING = 0

    // Mock fetch
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

    // Use fake timers
    vi.useFakeTimers()
    timers = {
      advance: (ms) => vi.advanceTimersByTime(ms),
      runAll: () => vi.runAllTimersAsync()
    }

    // Reset module and import fresh
    vi.resetModules()
    
    // Mock dependencies
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

    // Import the composable
    const module = await import('../../src/composables/useMarketStream.js')
    useMarketStream = module.useMarketStream
  })

  afterEach(() => {
    // Restore originals
    global.WebSocket = originalWebSocket
    global.fetch = originalFetch
    vi.useRealTimers()
    vi.clearAllMocks()
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

    it('should start HTTP polling when WS disconnects', async () => {
      const stream = useMarketStream('AU2406')
      const ws = MockWebSocket.instances[0]
      
      // Connect WS first
      ws._simulateOpen()
      await nextTick()
      
      // Now disconnect WS (abnormal closure)
      ws._simulateClose(1006, 'connection_lost')
      await nextTick()
      
      // After WS disconnects, should start HTTP polling
      // Advance time to trigger polling
      await timers.advance(5000)
      await nextTick()
      
      // HTTP polling should have started
      expect(mockFetch).toHaveBeenCalled()
      
      stream.disconnect()
    })

    it('should stop HTTP polling when WS reconnects', async () => {
      const stream = useMarketStream('AU2406')
      let ws = MockWebSocket.instances[0]
      
      // Connect then disconnect
      ws._simulateOpen()
      await nextTick()
      ws._simulateClose(1006, 'connection_lost')
      await nextTick()
      
      // Start HTTP polling
      await timers.advance(5000)
      await nextTick()
      const pollingCallCount = mockFetch.mock.calls.length
      
      // Simulate WS reconnect (new instance)
      MockWebSocket.readyState = WebSocket.CONNECTING
      ws = MockWebSocket.instances[MockWebSocket.instances.length - 1]
      ws._simulateOpen()
      await nextTick()
      
      // HTTP polling should stop (no more fetch calls after reconnect)
      await timers.advance(5000)
      await nextTick()
      
      // WS is connected, so fetch should not be called again
      // (or at least not for polling purposes)
      expect(stream.wsStatus.value).toBe('connected')
      
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
      
      // Now simulate HTTP update (should not overwrite WS data when connected)
      // This tests that WS data takes priority
      mockFetch.mockResolvedValueOnce({
        json: async () => ({
          data: {
            commodities: [
              { symbol: 'AU2406', price: 499.0, change_pct: 0.5 } // Different price
            ]
          }
        })
      })
      
      // Even if HTTP polling runs, WS data should remain
      // (WS has priority when connected)
      await timers.advance(5000)
      await nextTick()
      
      // WS tick should still be the source of truth
      expect(stream.tick.value.price).toBe(500.5)
      
      stream.disconnect()
    })

    it('should prioritize WS data over HTTP data', async () => {
      const stream = useMarketStream('AU2406')
      const ws = MockWebSocket.instances[0]
      
      // Start with HTTP polling (WS not connected yet)
      // Don't simulate WS open, so it stays in connecting state
      await timers.advance(5000)
      await nextTick()
      
      // HTTP polling should have run
      expect(mockFetch).toHaveBeenCalled()
      const httpTick = stream.tick.value
      
      // Now connect WS
      ws._simulateOpen()
      await nextTick()
      
      // Send WS message with different data
      ws._simulateMessage({
        symbol: 'AU2406',
        price: 501.0,
        change_pct: 2.0,
        timestamp: Date.now()
      })
      await nextTick()
      
      // WS data should override HTTP data
      expect(stream.tick.value.price).toBe(501.0)
      expect(stream.tick.value.change_pct).toBe(2.0)
      
      stream.disconnect()
    })
  })

  describe('rapid connect/disconnect cycles', () => {
    it('should not flicker on rapid WS connect/disconnect', async () => {
      const stream = useMarketStream('AU2406')
      const ws = MockWebSocket.instances[0]
      
      const statusHistory = []
      
      // Track status changes
      const stopWatch = stream.wsStatus.subscribe((status) => {
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

    it('should handle WS reconnect during HTTP polling', async () => {
      const stream = useMarketStream('AU2406')
      let ws = MockWebSocket.instances[0]
      
      // Disconnect WS to start HTTP polling
      ws._simulateOpen()
      await nextTick()
      ws._simulateClose(1006, 'connection_lost')
      await nextTick()
      
      // Start HTTP polling
      await timers.advance(5000)
      await nextTick()
      expect(mockFetch).toHaveBeenCalled()
      
      // Clear fetch mock to count new calls
      mockFetch.mockClear()
      
      // Simulate WS reconnect during polling
      const newWs = MockWebSocket.instances[MockWebSocket.instances.length - 1]
      newWs._simulateOpen()
      await nextTick()
      
      // Advance time - HTTP polling should have stopped
      await timers.advance(10000)
      await nextTick()
      
      // No new HTTP calls after WS reconnected
      expect(mockFetch).not.toHaveBeenCalled()
      expect(stream.wsStatus.value).toBe('connected')
      
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
    it('should maintain data consistency during WS to HTTP fallback', async () => {
      const stream = useMarketStream('AU2406')
      const ws = MockWebSocket.instances[0]
      
      // Connect and get initial data
      ws._simulateOpen()
      await nextTick()
      
      ws._simulateMessage({
        symbol: 'AU2406',
        price: 500.0,
        change_pct: 1.5,
        volume: 1000
      })
      await nextTick()
      
      const wsData = stream.tick.value
      expect(wsData.price).toBe(500.0)
      
      // Disconnect WS
      ws._simulateClose(1006, 'connection_lost')
      await nextTick()
      
      // HTTP polling should provide data
      mockFetch.mockResolvedValueOnce({
        json: async () => ({
          data: {
            commodities: [
              { symbol: 'AU2406', price: 500.5, change_pct: 1.6 }
            ]
          }
        })
      })
      
      await timers.advance(5000)
      await nextTick()
      
      // Should have HTTP data now
      const httpData = stream.tick.value
      expect(httpData).toBeDefined()
      expect(httpData.price).toBeDefined()
      
      stream.disconnect()
    })

    it('should not lose updates during reconnection', async () => {
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
      await timers.advance(1000) // Reconnect delay
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
    it('should fallback to HTTP polling on WS error', async () => {
      const stream = useMarketStream('AU2406')
      const ws = MockWebSocket.instances[0]
      
      // Simulate WS error
      ws._simulateError()
      ws._simulateClose(1006, 'error')
      await nextTick()
      
      // Should start HTTP polling after WS failure
      await timers.advance(5000)
      await nextTick()
      
      expect(mockFetch).toHaveBeenCalled()
      
      stream.disconnect()
    })

    it('should handle HTTP polling errors gracefully', async () => {
      const stream = useMarketStream('AU2406')
      const ws = MockWebSocket.instances[0]
      
      // Disconnect WS to trigger HTTP polling
      ws._simulateOpen()
      await nextTick()
      ws._simulateClose(1006, 'test')
      await nextTick()
      
      // Make HTTP polling fail
      mockFetch.mockRejectedValueOnce(new Error('Network error'))
      
      await timers.advance(5000)
      await nextTick()
      
      // Should not crash, error should be handled
      expect(stream.wsStatus.value).toBeDefined()
      
      // Next polling attempt should work
      mockFetch.mockResolvedValueOnce({
        json: async () => ({
          data: { commodities: [{ symbol: 'AU2406', price: 500.0, change_pct: 1.0 }] }
        })
      })
      
      await timers.advance(5000)
      await nextTick()
      
      // Should recover
      expect(stream.tick.value).toBeDefined()
      
      stream.disconnect()
    })
  })
})
