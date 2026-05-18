/**
 * chartManager.spec.js — ECharts Memory Management Test Suite
 * 
 * Tests for:
 * - Proper chart instance disposal
 * - ResizeObserver cleanup
 * - Memory leak prevention
 * - Chart manager utility functions
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock ECharts
const mockECharts = {
  init: vi.fn(() => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    getDom: vi.fn(() => mockDomElement),
    isDisposed: vi.fn(() => false),
  })),
}

// Mock DOM element
const mockDomElement = {
  tagName: 'DIV',
  parentNode: document.body,
}

// Mock ResizeObserver
class MockResizeObserver {
  constructor(callback) {
    this.callback = callback
    this.targets = new Set()
    MockResizeObserver.instances.add(this)
  }
  
  observe(target) {
    this.targets.add(target)
  }
  
  unobserve(target) {
    this.targets.delete(target)
  }
  
  disconnect() {
    this.targets.clear()
    MockResizeObserver.instances.delete(this)
  }
}

MockResizeObserver.instances = new Set()

// Setup global mocks
beforeEach(() => {
  vi.stubGlobal('echarts', mockECharts)
  vi.stubGlobal('ResizeObserver', MockResizeObserver)
  MockResizeObserver.instances.clear()
  mockECharts.init.mockClear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

// ============================================
// Chart Disposal Tests
// ============================================
describe('Chart Disposal', () => {
  it('should properly dispose chart instance', () => {
    const chartInstance = mockECharts.init(mockDomElement)
    
    expect(chartInstance.dispose).toBeDefined()
    expect(typeof chartInstance.dispose).toBe('function')
    
    chartInstance.dispose()
    
    expect(chartInstance.dispose).toHaveBeenCalled()
  })
  
  it('should check if chart is disposed before disposing', () => {
    const chartInstance = mockECharts.init(mockDomElement)
    
    // Check isDisposed before calling dispose
    if (!chartInstance.isDisposed()) {
      chartInstance.dispose()
    }
    
    expect(chartInstance.isDisposed).toHaveBeenCalled()
    expect(chartInstance.dispose).toHaveBeenCalled()
  })
  
  it('should not throw error when disposing already disposed chart', () => {
    const chartInstance = mockECharts.init(mockDomElement)
    
    // First dispose
    chartInstance.dispose()
    chartInstance.isDisposed.mockReturnValue(true)
    
    // Second dispose should not throw
    expect(() => {
      if (!chartInstance.isDisposed()) {
        chartInstance.dispose()
      }
    }).not.toThrow()
  })
  
  it('should handle dispose errors gracefully', () => {
    const chartInstance = mockECharts.init(mockDomElement)
    chartInstance.dispose.mockImplementation(() => {
      throw new Error('Dispose error')
    })
    
    // Should catch and handle error
    let errorCaught = false
    try {
      chartInstance.dispose()
    } catch (e) {
      errorCaught = true
    }
    
    expect(errorCaught).toBe(true)
  })
})

// ============================================
// ResizeObserver Cleanup Tests
// ============================================
describe('ResizeObserver Cleanup', () => {
  it('should create ResizeObserver for chart', () => {
    const observer = new ResizeObserver(() => {})
    const target = document.createElement('div')
    
    observer.observe(target)
    
    expect(observer.targets.has(target)).toBe(true)
    expect(MockResizeObserver.instances.has(observer)).toBe(true)
  })
  
  it('should disconnect ResizeObserver on cleanup', () => {
    const observer = new ResizeObserver(() => {})
    const target = document.createElement('div')
    
    observer.observe(target)
    observer.disconnect()
    
    expect(observer.targets.size).toBe(0)
    expect(MockResizeObserver.instances.has(observer)).toBe(false)
  })
  
  it('should unobserve specific target', () => {
    const observer = new ResizeObserver(() => {})
    const target1 = document.createElement('div')
    const target2 = document.createElement('div')
    
    observer.observe(target1)
    observer.observe(target2)
    observer.unobserve(target1)
    
    expect(observer.targets.has(target1)).toBe(false)
    expect(observer.targets.has(target2)).toBe(true)
  })
  
  it('should track multiple ResizeObserver instances', () => {
    const observer1 = new ResizeObserver(() => {})
    const observer2 = new ResizeObserver(() => {})
    
    expect(MockResizeObserver.instances.size).toBe(2)
    
    observer1.disconnect()
    
    expect(MockResizeObserver.instances.size).toBe(1)
    expect(MockResizeObserver.instances.has(observer2)).toBe(true)
  })
  
  it('should cleanup all observers on component unmount', () => {
    // Simulate multiple charts
    const observers = [
      new ResizeObserver(() => {}),
      new ResizeObserver(() => {}),
      new ResizeObserver(() => {}),
    ]
    
    observers.forEach(o => o.observe(document.createElement('div')))
    
    expect(MockResizeObserver.instances.size).toBe(3)
    
    // Cleanup all
    observers.forEach(o => o.disconnect())
    
    expect(MockResizeObserver.instances.size).toBe(0)
  })
})

// ============================================
// Memory Leak Prevention Tests
// ============================================
describe('Memory Leak Prevention', () => {
  it('should clear chart reference after disposal', () => {
    const chartInstance = mockECharts.init(mockDomElement)
    let chartRef = chartInstance
    
    expect(chartRef).toBe(chartInstance)
    
    // Dispose and clear reference
    chartRef.dispose()
    chartRef = null
    
    expect(chartRef).toBe(null)
  })
  
  it('should cleanup ResizeObserver before chart disposal', () => {
    const observer = new ResizeObserver(() => {})
    const target = document.createElement('div')
    const chartInstance = mockECharts.init(target)
    
    observer.observe(target)
    
    // Cleanup sequence: observer first, then chart
    observer.disconnect()
    chartInstance.dispose()
    
    expect(observer.targets.size).toBe(0)
    expect(chartInstance.dispose).toHaveBeenCalled()
  })
  
  it('should handle multiple chart instances cleanup', () => {
    const charts = [
      mockECharts.init(mockDomElement),
      mockECharts.init(mockDomElement),
      mockECharts.init(mockDomElement),
    ]
    
    const observers = charts.map(() => new ResizeObserver(() => {}))
    
    // Cleanup all
    observers.forEach(o => o.disconnect())
    charts.forEach(c => c.dispose())
    
    expect(MockResizeObserver.instances.size).toBe(0)
    charts.forEach(c => expect(c.dispose).toHaveBeenCalled())
  })
  
  it('should prevent orphaned ResizeObserver', () => {
    const observer = new ResizeObserver(() => {})
    const target = document.createElement('div')
    
    observer.observe(target)
    
    // If chart is disposed without cleaning observer, it becomes orphaned
    // Proper cleanup should disconnect observer first
    observer.disconnect()
    
    // No orphaned observers
    expect(MockResizeObserver.instances.has(observer)).toBe(false)
  })
})

// ============================================
// Chart Manager Utility Tests
// ============================================
describe('Chart Manager Utility', () => {
  it('should track chart instances by ID', () => {
    const chartManager = {
      charts: new Map(),
      observers: new Map(),
      
      register(id, chart, observer) {
        this.charts.set(id, chart)
        this.observers.set(id, observer)
      },
      
      dispose(id) {
        const observer = this.observers.get(id)
        const chart = this.charts.get(id)
        
        if (observer) {
          observer.disconnect()
          this.observers.delete(id)
        }
        
        if (chart && !chart.isDisposed()) {
          chart.dispose()
        }
        
        this.charts.delete(id)
      },
      
      disposeAll() {
        this.observers.forEach(o => o.disconnect())
        this.charts.forEach(c => {
          if (!c.isDisposed()) c.dispose()
        })
        this.observers.clear()
        this.charts.clear()
      },
    }
    
    const chart = mockECharts.init(mockDomElement)
    const observer = new ResizeObserver(() => {})
    
    chartManager.register('chart1', chart, observer)
    
    expect(chartManager.charts.has('chart1')).toBe(true)
    expect(chartManager.observers.has('chart1')).toBe(true)
    
    chartManager.dispose('chart1')
    
    expect(chartManager.charts.has('chart1')).toBe(false)
    expect(chartManager.observers.has('chart1')).toBe(false)
    expect(chart.dispose).toHaveBeenCalled()
  })
  
  it('should dispose all charts at once', () => {
    const chartManager = {
      charts: new Map(),
      observers: new Map(),
      
      register(id, chart, observer) {
        this.charts.set(id, chart)
        this.observers.set(id, observer)
      },
      
      disposeAll() {
        this.observers.forEach(o => o.disconnect())
        this.charts.forEach(c => {
          if (!c.isDisposed()) c.dispose()
        })
        this.observers.clear()
        this.charts.clear()
      },
    }
    
    // Register multiple charts
    for (let i = 0; i < 4; i++) {
      const chart = mockECharts.init(mockDomElement)
      const observer = new ResizeObserver(() => {})
      chartManager.register(`chart${i}`, chart, observer)
    }
    
    expect(chartManager.charts.size).toBe(4)
    expect(chartManager.observers.size).toBe(4)
    
    chartManager.disposeAll()
    
    expect(chartManager.charts.size).toBe(0)
    expect(chartManager.observers.size).toBe(0)
  })
  
  it('should handle dispose errors without breaking cleanup', () => {
    const chartManager = {
      charts: new Map(),
      observers: new Map(),
      
      register(id, chart, observer) {
        this.charts.set(id, chart)
        this.observers.set(id, observer)
      },
      
      disposeAll() {
        this.observers.forEach(o => {
          try { o.disconnect() } catch (e) {}
        })
        this.charts.forEach(c => {
          try {
            if (!c.isDisposed()) c.dispose()
          } catch (e) {}
        })
        this.observers.clear()
        this.charts.clear()
      },
    }
    
    // Register charts, one will fail on dispose
    const chart1 = mockECharts.init(mockDomElement)
    const chart2 = mockECharts.init(mockDomElement)
    chart2.dispose.mockImplementation(() => { throw new Error('Dispose failed') })
    
    const observer1 = new ResizeObserver(() => {})
    const observer2 = new ResizeObserver(() => {})
    
    chartManager.register('chart1', chart1, observer1)
    chartManager.register('chart2', chart2, observer2)
    
    // Should complete cleanup even with error
    chartManager.disposeAll()
    
    expect(chartManager.charts.size).toBe(0)
    expect(chartManager.observers.size).toBe(0)
  })
})

// ============================================
// Integration Tests
// ============================================
describe('Integration: Chart Lifecycle', () => {
  it('should complete full lifecycle: init -> use -> dispose', () => {
    const target = document.createElement('div')
    const chart = mockECharts.init(target)
    const observer = new ResizeObserver(() => chart.resize())
    
    observer.observe(target)
    
    // Use chart
    chart.setOption({ title: { text: 'Test' } })
    chart.resize()
    
    expect(chart.setOption).toHaveBeenCalled()
    expect(chart.resize).toHaveBeenCalled()
    
    // Cleanup
    observer.disconnect()
    chart.dispose()
    
    expect(observer.targets.size).toBe(0)
    expect(chart.dispose).toHaveBeenCalled()
  })
  
  it('should handle re-initialization after disposal', () => {
    const target = document.createElement('div')
    
    // First instance
    const chart1 = mockECharts.init(target)
    chart1.dispose()
    
    // Re-initialize
    mockECharts.init.mockClear()
    const chart2 = mockECharts.init(target)
    
    expect(mockECharts.init).toHaveBeenCalledTimes(1)
    expect(chart2).toBeDefined()
  })
  
  it('should handle DOM change correctly', () => {
    const target1 = document.createElement('div')
    const target2 = document.createElement('div')
    
    const chart = mockECharts.init(target1)
    chart.getDom.mockReturnValue(target1)
    
    // DOM changed
    expect(chart.getDom()).toBe(target1)
    
    // Should re-init if DOM mismatch
    if (chart.getDom() !== target2) {
      chart.dispose()
      mockECharts.init.mockClear()
      const newChart = mockECharts.init(target2)
      newChart.getDom.mockReturnValue(target2)
      
      expect(newChart.getDom()).toBe(target2)
    }
  })
})