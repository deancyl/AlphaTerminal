/**
 * Tests for WebSocket status transitions in useMarketStream
 * Verifies that status is never incorrectly set to 'connected' on error
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

class MockWebSocket {
  static instances = []
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3
  
  constructor(url) {
    this.url = url
    this.readyState = MockWebSocket.CONNECTING
    this.onopen = null
    this.onmessage = null
    this.onerror = null
    this.onclose = null
    MockWebSocket.instances.push(this)
  }
  
  send(data) {}
  close(code, reason) {
    this.readyState = MockWebSocket.CLOSED
    if (this.onclose) this.onclose({ code: code || 1000, reason: reason || '' })
  }
  
  simulateOpen() {
    this.readyState = MockWebSocket.OPEN
    if (this.onopen) this.onopen({ type: 'open' })
  }
  
  simulateError() {
    if (this.onerror) this.onerror({ type: 'error' })
  }
  
  simulateClose(code = 1006, reason = '') {
    this.readyState = MockWebSocket.CLOSED
    if (this.onclose) this.onclose({ code, reason })
  }
}

vi.stubGlobal('WebSocket', MockWebSocket)

describe('useMarketStream - WebSocket Status', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    vi.resetModules()
  })
  
  afterEach(() => {
    vi.clearAllMocks()
    MockWebSocket.instances = []
  })

  it('should NOT set status to "connected" on WebSocket error', async () => {
    const { useMarketStream } = await import('@/composables/useMarketStream.js')
    const { wsStatus, connect } = useMarketStream()
    
    connect('600519')
    
    const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1]
    expect(ws).toBeDefined()
    
    ws.simulateError()
    
    expect(wsStatus.value).not.toBe('connected')
  })

  it('should set status to "disconnected" after error+close sequence', async () => {
    const { useMarketStream } = await import('@/composables/useMarketStream.js')
    const { wsStatus, connect } = useMarketStream()
    
    connect('600519')
    
    const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1]
    expect(ws).toBeDefined()
    
    ws.simulateError()
    ws.simulateClose(1006, 'connection_failed')
    
    expect(wsStatus.value).not.toBe('connected')
    expect(['disconnected', 'connecting']).toContain(wsStatus.value)
  })

  it('should correctly set status to "connected" only on successful open', async () => {
    const { useMarketStream } = await import('@/composables/useMarketStream.js')
    const { wsStatus, connect } = useMarketStream()
    
    connect('600519')
    
    const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1]
    expect(ws).toBeDefined()
    
    ws.simulateOpen()
    
    expect(wsStatus.value).toBe('connected')
  })

  it('should never have "connected" status when error occurs during connection', async () => {
    const { useMarketStream } = await import('@/composables/useMarketStream.js')
    const { wsStatus, connect } = useMarketStream()
    
    connect('600519')
    
    const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1]
    expect(ws).toBeDefined()
    
    ws.readyState = MockWebSocket.CONNECTING
    ws.simulateError()
    ws.simulateClose(1006)
    
    expect(wsStatus.value).not.toBe('connected')
  })
})
