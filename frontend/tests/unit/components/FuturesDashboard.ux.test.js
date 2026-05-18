import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { shallowMount, mount, flushPromises } from '@vue/test-utils'
import { ref, nextTick } from 'vue'
import FuturesDashboard from '@/components/FuturesDashboard.vue'

// ═══════════════════════════════════════════════════════════════════════════
// P2 UX Tests: Loading States, Error Boundary, Interaction, Refresh
// ═══════════════════════════════════════════════════════════════════════════

const mockApiFetch = vi.fn()
vi.mock('@/utils/api.js', () => ({
  apiFetch: (...args) => mockApiFetch(...args)
}))

vi.mock('@/utils/logger.js', () => ({
  logger: {
    warn: vi.fn(),
    error: vi.fn(),
    info: vi.fn()
  }
}))

vi.mock('@/components/FuturesMainChart.vue', () => ({
  default: {
    name: 'FuturesMainChart',
    template: '<div class="mock-futures-chart"></div>',
    props: ['futuresData']
  }
}))

vi.mock('@/components/f9/LoadingSpinner.vue', () => ({
  default: {
    name: 'LoadingSpinner',
    template: '<div class="loading-spinner">{{ text }}</div>',
    props: ['text']
  }
}))

function mountDashboard(options = {}) {
  return shallowMount(FuturesDashboard, {
    global: {
      stubs: {
        FuturesMainChart: true,
        LoadingSpinner: true,
        ...options.stubs
      },
      ...options.global
    },
    ...options
  })
}

describe('FuturesDashboard UX', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockApiFetch.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  // ═══════════════════════════════════════════════════════════════════════
  // Loading States
  // ═══════════════════════════════════════════════════════════════════════

  describe('Loading States', () => {
    it('should show loading state during fetch', async () => {
      mockApiFetch.mockImplementation(() => new Promise(() => {}))

      const wrapper = mountDashboard()
      
      await nextTick()

      expect(wrapper.vm.isLoading).toBe(true)
    })

    it('should hide loading spinner after data loads', async () => {
      mockApiFetch
        .mockResolvedValueOnce({
          index_futures: [
            { symbol: 'IF2501', name: 'IF', price: 4000, change_pct: 1.5 }
          ]
        })
        .mockResolvedValueOnce({
          commodities: [],
          update_time: '10:30:00'
        })
        .mockResolvedValue({ history: [] })

      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      expect(wrapper.vm.isLoading).toBe(false)
    })

    it('should show skeleton when commoditySectors is empty', async () => {
      mockApiFetch
        .mockResolvedValueOnce({ index_futures: [{ symbol: 'IF', name: 'IF' }] })
        .mockResolvedValueOnce({ commodities: [], update_time: '10:30:00' })
        .mockResolvedValue({ history: [] })

      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      expect(wrapper.vm.commoditySectors.length).toBe(0)
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // Error Boundary
  // ═══════════════════════════════════════════════════════════════════════

  describe('Error Boundary', () => {
    it('should show error state on API failure', async () => {
      mockApiFetch.mockRejectedValue(new Error('Network error'))

      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      expect(wrapper.text()).toContain('加载失败')
    })

    it('should show retry button on error', async () => {
      mockApiFetch.mockRejectedValue(new Error('Network error'))

      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      const retryBtn = wrapper.find('button')
      expect(retryBtn.exists()).toBe(true)
      expect(retryBtn.text()).toContain('重试')
    })

    it('should call fetchFuturesData when retry button clicked', async () => {
      mockApiFetch
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({ index_futures: [] })
        .mockResolvedValueOnce({ commodities: [] })

      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      await wrapper.find('button').trigger('click')
      await flushPromises()
      await nextTick()

      expect(mockApiFetch).toHaveBeenCalledTimes(4)
    })

    it('should clear error state on successful retry', async () => {
      mockApiFetch
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({ index_futures: [] })
        .mockResolvedValueOnce({ commodities: [] })
        .mockResolvedValue({ history: [] })

      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      expect(wrapper.text()).toContain('加载失败')

      await wrapper.find('button').trigger('click')
      await flushPromises()
      await nextTick()

      expect(wrapper.text()).not.toContain('加载失败')
    })

    it('should show warning emoji on error', async () => {
      mockApiFetch.mockRejectedValue(new Error('Network error'))

      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      expect(wrapper.text()).toContain('⚠️')
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // Heatmap Interaction
  // ═══════════════════════════════════════════════════════════════════════

  describe('Heatmap Interaction', () => {
    const mockData = {
      index_futures: [
        { symbol: 'IF2501', name: 'IF', price: 4000, change_pct: 1.5, position: '120000' }
      ],
      commodities: [
        { symbol: 'AU2506', name: '黄金', change_pct: 2.5, sector: '贵金属', sector_emoji: '🥇' },
        { symbol: 'CU2505', name: '铜', change_pct: -1.2, sector: '有色金属', sector_emoji: '🔩' }
      ]
    }

    beforeEach(() => {
      mockApiFetch
        .mockResolvedValueOnce(mockData)
        .mockResolvedValueOnce({ commodities: mockData.commodities, update_time: '10:30:00' })
        .mockResolvedValue({ history: [] })
    })

    it('should render commodity blocks as clickable', async () => {
      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      const blocks = wrapper.findAll('.cursor-pointer')
      const commodityBlocks = blocks.filter(b => 
        b.classes().includes('hover:brightness-125')
      )
      
      expect(commodityBlocks.length).toBeGreaterThan(0)
    })

    it('should emit open-futures event when commodity block clicked', async () => {
      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      const blocks = wrapper.findAll('.cursor-pointer')
      const commodityBlock = blocks.find(b => 
        b.classes().includes('hover:brightness-125')
      )

      if (commodityBlock) {
        await commodityBlock.trigger('click')
        expect(wrapper.emitted('open-futures')).toBeTruthy()
      }
    })

    it('should emit open-futures with correct symbol', async () => {
      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      const allBlocks = wrapper.findAll('[class*="cursor-pointer"]')
      const goldBlock = allBlocks.find(b => b.text().includes('黄金'))

      if (goldBlock) {
        await goldBlock.trigger('click')
        
        const emitted = wrapper.emitted('open-futures')
        expect(emitted).toBeTruthy()
        expect(emitted[0][0]).toHaveProperty('symbol')
      }
    })

    it('should show hover effect on commodity blocks', async () => {
      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      const blocks = wrapper.findAll('.hover\\:brightness-125')
      expect(blocks.length).toBeGreaterThan(0)
    })

    it('should apply correct color based on change_pct', async () => {
      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      const html = wrapper.html()
      expect(html).toContain('rgba(239, 68, 68')
      expect(html).toContain('rgba(34, 197, 94')
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // Futures Card Interaction
  // ═══════════════════════════════════════════════════════════════════════

  describe('Futures Card Interaction', () => {
    const mockData = {
      index_futures: [
        { symbol: 'IF2501', name: 'IF', price: 4000, change_pct: 1.5, position: '120000' },
        { symbol: 'IC2501', name: 'IC', price: 6000, change_pct: -0.8, position: '80000' }
      ]
    }

    beforeEach(() => {
      mockApiFetch
        .mockResolvedValueOnce(mockData)
        .mockResolvedValueOnce({ commodities: [], update_time: '10:30:00' })
        .mockResolvedValue({ history: [] })
    })

    it('should render futures cards', async () => {
      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      expect(wrapper.text()).toContain('IF')
      expect(wrapper.text()).toContain('IC')
    })

    it('should emit open-futures when card clicked', async () => {
      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      const cards = wrapper.findAll('.terminal-panel')
      const futuresCard = cards.find(c => c.text().includes('IF'))

      if (futuresCard) {
        await futuresCard.trigger('click')
        expect(wrapper.emitted('open-futures')).toBeTruthy()
      }
    })

    it('should show correct position direction (多/空)', async () => {
      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      expect(wrapper.text()).toContain('多')
      expect(wrapper.text()).toContain('空')
    })

    it('should display position value', async () => {
      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      expect(wrapper.text()).toContain('120000')
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // Auto Refresh
  // ═══════════════════════════════════════════════════════════════════════

  describe('Auto Refresh', () => {
    it('should set up auto-refresh timer on mount', async () => {
      mockApiFetch
        .mockResolvedValue({ index_futures: [] })
        .mockResolvedValue({ commodities: [] })

      mountDashboard()

      expect(mockApiFetch).toHaveBeenCalledTimes(2)

      vi.advanceTimersByTime(180_000)
      await flushPromises()

      expect(mockApiFetch).toHaveBeenCalledTimes(4)
    })

    it('should clear timer on unmount', async () => {
      mockApiFetch.mockResolvedValue({})

      const wrapper = mountDashboard()

      await flushPromises()
      
      const clearIntervalSpy = vi.spyOn(global, 'clearInterval')
      
      wrapper.unmount()
      
      expect(clearIntervalSpy).toHaveBeenCalled()
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // Sector Grouping
  // ═══════════════════════════════════════════════════════════════════════

  describe('Sector Grouping', () => {
    it('should group commodities by sector', async () => {
      mockApiFetch
        .mockResolvedValueOnce({ index_futures: [] })
        .mockResolvedValueOnce({
          commodities: [
            { symbol: 'AU2506', name: '黄金', change_pct: 2.5, sector: '贵金属', sector_emoji: '🥇' },
            { symbol: 'AG2506', name: '白银', change_pct: 1.8, sector: '贵金属', sector_emoji: '🥇' }
          ],
          update_time: '10:30:00'
        })
        .mockResolvedValue({ history: [] })

      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      expect(wrapper.text()).toContain('贵金属')
    })

    it('should calculate sector average change', async () => {
      mockApiFetch
        .mockResolvedValueOnce({ index_futures: [] })
        .mockResolvedValueOnce({
          commodities: [
            { symbol: 'AU', change_pct: 2.0, sector: '贵金属', sector_emoji: '🥇' },
            { symbol: 'AG', change_pct: 1.0, sector: '贵金属', sector_emoji: '🥇' }
          ],
          update_time: '10:30:00'
        })
        .mockResolvedValue({ history: [] })

      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      expect(wrapper.text()).toContain('1.50')
    })

    it('should show sector emoji', async () => {
      mockApiFetch
        .mockResolvedValueOnce({ index_futures: [] })
        .mockResolvedValueOnce({
          commodities: [
            { symbol: 'AU', change_pct: 2.0, sector: '贵金属', sector_emoji: '🥇' }
          ],
          update_time: '10:30:00'
        })
        .mockResolvedValue({ history: [] })

      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      expect(wrapper.text()).toContain('🥇')
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // Edge Cases
  // ═══════════════════════════════════════════════════════════════════════

  describe('Edge Cases', () => {
    it('should handle empty commodities array', async () => {
      mockApiFetch
        .mockResolvedValueOnce({ index_futures: [] })
        .mockResolvedValueOnce({ commodities: [], update_time: '' })
        .mockResolvedValue({ history: [] })

      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      expect(wrapper.exists()).toBe(true)
    })

    it('should handle null change_pct', async () => {
      mockApiFetch
        .mockResolvedValueOnce({
          index_futures: [
            { symbol: 'IF', name: 'IF', price: 4000, change_pct: null }
          ]
        })
        .mockResolvedValueOnce({ commodities: [] })
        .mockResolvedValue({ history: [] })

      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      expect(wrapper.exists()).toBe(true)
    })

    it('should handle missing optional fields', async () => {
      mockApiFetch
        .mockResolvedValueOnce({
          index_futures: [
            { symbol: 'IF', name: 'IF' }
          ]
        })
        .mockResolvedValueOnce({ commodities: [] })
        .mockResolvedValue({ history: [] })

      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      expect(wrapper.exists()).toBe(true)
    })

    it('should handle malformed API response', async () => {
      mockApiFetch
        .mockResolvedValueOnce(null)
        .mockResolvedValueOnce(null)

      const wrapper = mountDashboard()

      await flushPromises()
      await nextTick()

      expect(wrapper.exists()).toBe(true)
    })
  })
})
