import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import QuotePanel from '../QuotePanel.vue'

// Mock useMarketStream composable
vi.mock('../composables/useMarketStream.js', () => ({
  useMarketStream: () => ({
    tick: ref(null),
    subscribe: vi.fn(),
    unsubscribe: vi.fn()
  })
}))

// Mock useTheme composable
vi.mock('../composables/useTheme.js', () => ({
  useTheme: () => ({
    getChartColors: () => ({
      bullish: '#ef4444',
      bearish: '#22c55e',
      tooltipBg: '#1f2937',
      tooltipBorder: '#374151',
      tooltipText: '#f3f4f6'
    }),
    onThemeChange: vi.fn()
  })
}))

// Mock ECharts
vi.stubGlobal('echarts', {
  init: vi.fn(() => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: vi.fn(() => false)
  }))
})

describe('QuotePanel', () => {
  // ═══ P0-2: Empty object validation ═════════════════════════════════════
  
  it('shows loading when realtimeData is empty object', () => {
    const wrapper = mount(QuotePanel, {
      props: { symbol: 'sh000001', realtimeData: {} },
      global: {
        stubs: {
          LoadingSpinner: true,
          FreshnessIndicator: true
        }
      }
    })
    expect(wrapper.findComponent({ name: 'LoadingSpinner' }).exists()).toBe(true)
  })
  
  it('shows loading when price is null', () => {
    const wrapper = mount(QuotePanel, {
      props: { symbol: 'sh000001', realtimeData: { price: null } },
      global: {
        stubs: {
          LoadingSpinner: true,
          FreshnessIndicator: true
        }
      }
    })
    expect(wrapper.findComponent({ name: 'LoadingSpinner' }).exists()).toBe(true)
  })
  
  it('shows loading when price is 0', () => {
    const wrapper = mount(QuotePanel, {
      props: { symbol: 'sh000001', realtimeData: { price: 0 } },
      global: {
        stubs: {
          LoadingSpinner: true,
          FreshnessIndicator: true
        }
      }
    })
    expect(wrapper.findComponent({ name: 'LoadingSpinner' }).exists()).toBe(true)
  })
  
  it('displays data when realtimeData is valid', () => {
    const wrapper = mount(QuotePanel, {
      props: { 
        symbol: 'sh000001', 
        realtimeData: { price: 3100.50, change_pct: 1.5 } 
      },
      global: {
        stubs: {
          LoadingSpinner: true,
          FreshnessIndicator: true
        }
      }
    })
    expect(wrapper.text()).toContain('3100.50')
  })
  
  // ═══ P1-6: WebSocket tick connection ═══════════════════════════════════
  
  it('accepts wsTick prop for real-time updates', async () => {
    const wrapper = mount(QuotePanel, {
      props: { 
        symbol: 'sh000001',
        realtimeData: { price: 3100 },
        wsTick: { price: 3105, change_pct: 0.5 }
      },
      global: {
        stubs: {
          LoadingSpinner: true,
          FreshnessIndicator: true
        }
      }
    })
    // Should prefer wsTick over realtimeData
    expect(wrapper.text()).toContain('3105')
  })
  
  // ═══ Data validation tests ═════════════════════════════════════════════
  
  it('handles negative change_pct correctly', () => {
    const wrapper = mount(QuotePanel, {
      props: { 
        symbol: 'sh000001', 
        realtimeData: { price: 3000, change_pct: -2.5 } 
      },
      global: {
        stubs: {
          LoadingSpinner: true,
          FreshnessIndicator: true
        }
      }
    })
    expect(wrapper.text()).toContain('-2.50')
  })
  
  it('displays symbol in header', () => {
    const wrapper = mount(QuotePanel, {
      props: { 
        symbol: 'sh600519', 
        realtimeData: { price: 1800 } 
      },
      global: {
        stubs: {
          LoadingSpinner: true,
          FreshnessIndicator: true
        }
      }
    })
    expect(wrapper.text()).toContain('sh600519')
  })
  
  it('handles loading prop correctly', () => {
    const wrapper = mount(QuotePanel, {
      props: { 
        symbol: 'sh000001', 
        realtimeData: { price: 3100 },
        loading: true 
      },
      global: {
        stubs: {
          LoadingSpinner: true,
          FreshnessIndicator: true
        }
      }
    })
    expect(wrapper.findComponent({ name: 'LoadingSpinner' }).exists()).toBe(true)
  })
  
  // ═══ Snapshot data priority ════════════════════════════════════════════
  
  it('prefers snapshotData over realtimeData', () => {
    const wrapper = mount(QuotePanel, {
      props: { 
        symbol: 'sh000001',
        realtimeData: { price: 3100 },
        snapshotData: { price: 3150, change_pct: 1.0 }
      },
      global: {
        stubs: {
          LoadingSpinner: true,
          FreshnessIndicator: true
        }
      }
    })
    expect(wrapper.text()).toContain('3150')
  })
  
  // ═══ Edge cases ═══════════════════════════════════════════════════════
  
  it('handles missing optional fields gracefully', () => {
    const wrapper = mount(QuotePanel, {
      props: { 
        symbol: 'sh000001', 
        realtimeData: { 
          price: 3100,
          // Missing: change, change_pct, volume, amount
        } 
      },
      global: {
        stubs: {
          LoadingSpinner: true,
          FreshnessIndicator: true
        }
      }
    })
    // Should render without crashing
    expect(wrapper.exists()).toBe(true)
  })
  
  it('handles very large price values', () => {
    const wrapper = mount(QuotePanel, {
      props: { 
        symbol: 'usNDX', 
        realtimeData: { price: 15000.123 } 
      },
      global: {
        stubs: {
          LoadingSpinner: true,
          FreshnessIndicator: true
        }
      }
    })
    expect(wrapper.text()).toContain('15000.123')
  })
  
  it('handles very small price values', () => {
    const wrapper = mount(QuotePanel, {
      props: { 
        symbol: 'sz399006', 
        realtimeData: { price: 0.123 } 
      },
      global: {
        stubs: {
          LoadingSpinner: true,
          FreshnessIndicator: true
        }
      }
    })
    expect(wrapper.text()).toContain('0.123')
  })
})
