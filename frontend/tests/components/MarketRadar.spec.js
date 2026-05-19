/**
 * Market Radar Component Tests
 * 
 * Wave 4-31: Frontend component tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, nextTick } from 'vue'
import MarketRadar from '@/components/MarketRadar.vue'

// Mock composables
vi.mock('@/composables/useECharts.js', () => ({
  useECharts: () => ({
    initChart: vi.fn().mockResolvedValue({
      on: vi.fn(),
      off: vi.fn(),
      setOption: vi.fn(),
    }),
    setOption: vi.fn(),
    dispose: vi.fn(),
    isReady: ref(true),
  }),
}))

vi.mock('@/composables/useMarketRadar.js', () => ({
  useMarketRadar: () => ({
    treemapData: ref([
      { name: '白酒', value: 100, change_pct: 2.5, children: [] },
    ]),
    anomalies: ref([
      { type: 'volatility', title: '振幅最大', stocks: [] },
    ]),
    loading: ref(false),
    error: ref(null),
    lastUpdate: ref('2024-01-01T00:00:00'),
    dataSource: ref({ name: '东方财富', type: '实时' }),
    refreshInterval: ref(60000),
    refresh: vi.fn(),
    formatTime: (t) => t ? '00:00:00' : '--',
    setRefreshInterval: vi.fn(),
    startAutoRefresh: vi.fn(),
    stopAutoRefresh: vi.fn(),
  }),
  REFRESH_INTERVAL_OPTIONS: [
    { label: '30秒', value: 30000 },
    { label: '60秒', value: 60000 },
    { label: '关闭', value: 0 },
  ],
}))

vi.mock('@vueuse/core', () => ({
  useBreakpoints: () => ({
    smaller: () => ref(false), // Desktop by default
  }),
}))

describe('MarketRadar.vue', () => {
  let wrapper
  
  beforeEach(() => {
    wrapper = mount(MarketRadar, {
      global: {
        stubs: {
          AnomalyCard: true,
          Skeleton: true,
          Teleport: true,
        },
      },
    })
  })
  
  afterEach(() => {
    wrapper?.unmount()
  })
  
  describe('Rendering', () => {
    it('should render title and description', () => {
      expect(wrapper.find('h2').text()).toBe('市场温度计')
      expect(wrapper.find('p').text()).toContain('市场温度图')
    })
    
    it('should render refresh button', () => {
      const button = wrapper.find('button.theme-btn')
      expect(button.exists()).toBe(true)
      expect(button.text()).toBe('刷新')
    })
    
    it('should render data source indicator', () => {
      const dataSource = wrapper.find('.text-xs.text-secondary')
      expect(dataSource.exists()).toBe(true)
    })
    
    it('should render refresh interval selector', () => {
      const select = wrapper.find('select')
      expect(select.exists()).toBe(true)
    })
  })
  
  describe('ARIA Accessibility', () => {
    it('should have aria-label on treemap container', () => {
      const treemapContainer = wrapper.find('[role="img"]')
      expect(treemapContainer.exists()).toBe(true)
      expect(treemapContainer.attributes('aria-label')).toContain('市场温度图')
    })
    
    it('should have tabindex on treemap container', () => {
      const treemapContainer = wrapper.find('[role="img"]')
      expect(treemapContainer.attributes('tabindex')).toBe('0')
    })
  })
  
  describe('Mobile Layout', () => {
    it('should show mobile layout on small screens', async () => {
      // Re-mount with mobile mock
      vi.mocked(await import('@vueuse/core')).useBreakpoints = () => ({
        smaller: () => ref(true), // Mobile
      })
      
      const mobileWrapper = mount(MarketRadar, {
        global: {
          stubs: {
            AnomalyCard: true,
            Skeleton: true,
            Teleport: true,
          },
        },
      })
      
      // Check for mobile-specific elements
      const mobileTreemap = mobileWrapper.find('[style*="min-height: 350px"]')
      expect(mobileTreemap.exists()).toBe(true)
      
      mobileWrapper.unmount()
    })
  })
  
  describe('Error Handling', () => {
    it('should display error message when error occurs', async () => {
      // Re-mount with error
      vi.mocked(await import('@/composables/useMarketRadar.js')).useMarketRadar = () => ({
        treemapData: ref([]),
        anomalies: ref([]),
        loading: ref(false),
        error: ref('数据加载失败'),
        lastUpdate: ref(null),
        dataSource: ref(null),
        refreshInterval: ref(60000),
        refresh: vi.fn(),
        formatTime: () => '--',
        setRefreshInterval: vi.fn(),
        startAutoRefresh: vi.fn(),
        stopAutoRefresh: vi.fn(),
      })
      
      const errorWrapper = mount(MarketRadar, {
        global: {
          stubs: {
            AnomalyCard: true,
            Skeleton: true,
            Teleport: true,
          },
        },
      })
      
      const errorDiv = errorWrapper.find('.bg-danger-bg')
      expect(errorDiv.exists()).toBe(true)
      expect(errorDiv.text()).toContain('数据加载失败')
      
      errorWrapper.unmount()
    })
  })
  
  describe('Drill-Down Modal', () => {
    it('should have drill-down modal structure', () => {
      // Modal is rendered via Teleport, check for the structure
      expect(wrapper.html()).toContain('showDrillDown')
    })
  })
})
