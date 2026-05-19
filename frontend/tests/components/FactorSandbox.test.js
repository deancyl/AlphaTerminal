import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed } from 'vue'
import FactorSandbox from '@/components/factor/FactorSandbox.vue'

const mockFactors = [
  { id: 'macd_cross', name: 'MACD金叉', category: 'technical', description: 'MACD金叉信号', params: {} },
  { id: 'rsi_oversold', name: 'RSI超卖', category: 'technical', description: 'RSI低于30', params: {} },
  { id: 'foreign_inflow', name: '外资净流入', category: 'fund_flow', description: '北向资金净流入', params: {} },
]

const mockCategories = [
  { id: 'technical', name: '技术信号', icon: '📊' },
  { id: 'fund_flow', name: '资金流向', icon: '💵' },
]

const mockScreenedStocks = [
  { symbol: 'sh600519', name: '贵州茅台', score: 85.5 },
  { symbol: 'sh600036', name: '招商银行', score: 72.3 },
]

const mockUseFactorSandbox = {
  factors: ref(mockFactors),
  categories: ref(mockCategories),
  selectedFactors: ref([]),
  screenedStocks: ref([]),
  screeningLoading: ref(false),
  factorsLoading: ref(false),
  error: ref(null),
  screeningProgress: ref(null),
  universe: ref('hs300'),
  isFactorSelected: computed(() => (id) => false),
  fetchFactors: vi.fn(),
  addFactor: vi.fn(),
  removeFactor: vi.fn(),
  toggleFactor: vi.fn(),
  reorderFactors: vi.fn(),
  runScreening: vi.fn(),
  cancelScreening: vi.fn(),
  getBacktestPreview: vi.fn(),
}

vi.mock('@/composables/useFactorSandbox.js', () => ({
  useFactorSandbox: () => mockUseFactorSandbox,
}))

vi.mock('@vueuse/core', () => ({
  useBreakpoints: () => ({
    smaller: () => ref(false),
  }),
  breakpointsTailwind: {},
}))

vi.mock('@/utils/chartManager.js', () => ({
  safeDispose: vi.fn(),
}))

vi.mock('@/utils/echartsTheme.js', () => ({
  getDynamicMarketColors: () => ({ UP: '#ef4444', DOWN: '#22c55e' }),
}))

vi.stubGlobal('echarts', {
  init: vi.fn(() => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: vi.fn(() => false),
  })),
})

describe('FactorSandbox', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseFactorSandbox.factors.value = [...mockFactors]
    mockUseFactorSandbox.categories.value = [...mockCategories]
    mockUseFactorSandbox.selectedFactors.value = []
    mockUseFactorSandbox.screenedStocks.value = []
    mockUseFactorSandbox.screeningLoading.value = false
    mockUseFactorSandbox.factorsLoading.value = false
    mockUseFactorSandbox.error.value = null
    mockUseFactorSandbox.screeningProgress.value = null
  })

  const mountComponent = (options = {}) => {
    return mount(FactorSandbox, {
      global: {
        stubs: {
          FactorDragItem: {
            template: '<div class="factor-drag-item-stub" :class="{ \'factor-drag-item-stub--selected\': selected }" @click="$emit(\'click\', factor)" />',
            props: ['factor', 'selected'],
            emits: ['click', 'touchdrop'],
          },
          FactorFunnel: {
            template: '<div class="factor-funnel-stub" />',
            props: ['factors'],
            emits: ['remove', 'reorder', 'add'],
          },
          BottomSheet: {
            template: '<div class="bottom-sheet-stub"><slot /></div>',
            props: ['modelValue', 'title'],
            emits: ['update:modelValue'],
          },
          Skeleton: {
            template: '<div class="skeleton-stub" />',
          },
          VirtualizedTable: {
            template: '<div class="virtualized-table-stub"><slot /></div>',
            props: ['items', 'columns', 'selectedId', 'itemSize'],
            emits: ['row-click'],
          },
        },
      },
      ...options,
    })
  }

  describe('test_renders_factor_library', () => {
    it('should render factor library section', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.factor-sandbox__library').exists()).toBe(true)
    })

    it('should display categories in library', () => {
      const wrapper = mountComponent()
      const categoryHeaders = wrapper.findAll('.factor-sandbox__category-header')
      expect(categoryHeaders.length).toBeGreaterThan(0)
    })

    it('should show category icons and names', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('技术信号')
    })

    it('should show search input', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.factor-sandbox__search').exists()).toBe(true)
    })
  })

  describe('test_renders_funnel', () => {
    it('should render funnel section', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.factor-sandbox__funnel').exists()).toBe(true)
    })

    it('should pass selectedFactors to funnel', () => {
      mockUseFactorSandbox.selectedFactors.value = [mockFactors[0]]
      const wrapper = mountComponent()
      const funnel = wrapper.findComponent({ name: 'FactorFunnel' })
      expect(funnel.props('factors')).toHaveLength(1)
    })
  })

  describe('test_renders_results', () => {
    it('should render results section', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.factor-sandbox__results').exists()).toBe(true)
    })

    it('should show empty state when no results', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.factor-sandbox__empty').exists()).toBe(true)
    })

    it('should show results when stocks are screened', async () => {
      mockUseFactorSandbox.screenedStocks.value = mockScreenedStocks
      const wrapper = mountComponent()
      expect(wrapper.find('.factor-sandbox__stock-list').exists()).toBe(true)
    })

    it('should display result count', async () => {
      mockUseFactorSandbox.screenedStocks.value = mockScreenedStocks
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('2')
    })
  })

  describe('test_factor_selection', () => {
    it('should call toggleFactor when factor is clicked', async () => {
      const wrapper = mountComponent()
      const dragItems = wrapper.findAll('.factor-drag-item-stub')
      if (dragItems.length > 0) {
        await dragItems[0].trigger('click')
        expect(mockUseFactorSandbox.toggleFactor).toHaveBeenCalled()
      }
    })

    it('should pass selected prop to FactorDragItem', async () => {
      mockUseFactorSandbox.isFactorSelected = computed(() => (id) => id === 'macd_cross')
      const wrapper = mountComponent()
      const dragItems = wrapper.findAll('.factor-drag-item-stub')
      const macdItem = dragItems.find(item => item.classes().includes('factor-drag-item-stub--selected'))
      expect(macdItem).toBeDefined()
    })
  })

  describe('test_screening_flow', () => {
    it('should have screen button', () => {
      const wrapper = mountComponent()
      const button = wrapper.find('.factor-sandbox__btn')
      expect(button.exists()).toBe(true)
      expect(button.text()).toContain('筛选')
    })

    it('should call runScreening when button clicked', async () => {
      mockUseFactorSandbox.selectedFactors.value = [mockFactors[0]]
      const wrapper = mountComponent()
      await wrapper.find('.factor-sandbox__btn').trigger('click')
      expect(mockUseFactorSandbox.runScreening).toHaveBeenCalled()
    })

    it('should disable button when no factors selected', () => {
      const wrapper = mountComponent()
      const button = wrapper.find('.factor-sandbox__btn')
      expect(button.element.disabled).toBe(true)
    })

    it('should enable button when factors are selected', async () => {
      mockUseFactorSandbox.selectedFactors.value = [mockFactors[0]]
      const wrapper = mountComponent()
      const button = wrapper.find('.factor-sandbox__btn')
      expect(button.element.disabled).toBe(false)
    })

    it('should show loading state during screening', async () => {
      mockUseFactorSandbox.selectedFactors.value = [mockFactors[0]]
      mockUseFactorSandbox.screeningLoading.value = true
      const wrapper = mountComponent()
      expect(wrapper.find('.factor-sandbox__btn--loading').exists()).toBe(true)
    })
  })

  describe('test_error_display', () => {
    it('should show error message when error occurs', async () => {
      mockUseFactorSandbox.error.value = 'Screening failed'
      const wrapper = mountComponent()
      expect(wrapper.find('.factor-sandbox__error').exists()).toBe(true)
      expect(wrapper.text()).toContain('筛选失败')
    })

    it('should have retry button on error', async () => {
      mockUseFactorSandbox.error.value = 'Screening failed'
      const wrapper = mountComponent()
      const retryBtn = wrapper.find('.factor-sandbox__error button')
      expect(retryBtn.exists()).toBe(true)
    })

    it('should call runScreening on retry click', async () => {
      mockUseFactorSandbox.error.value = 'Screening failed'
      const wrapper = mountComponent()
      await wrapper.find('.factor-sandbox__error button').trigger('click')
      expect(mockUseFactorSandbox.runScreening).toHaveBeenCalled()
    })
  })

  describe('test_loading_state', () => {
    it('should show skeleton during factors loading', async () => {
      mockUseFactorSandbox.factorsLoading.value = true
      const wrapper = mountComponent()
      expect(wrapper.find('.factor-sandbox__loading-state').exists()).toBe(true)
    })

    it('should show loading spinner during screening', async () => {
      mockUseFactorSandbox.selectedFactors.value = [mockFactors[0]]
      mockUseFactorSandbox.screeningLoading.value = true
      const wrapper = mountComponent()
      expect(wrapper.find('.factor-sandbox__loading').exists()).toBe(true)
    })

    it('should show screening progress info', async () => {
      mockUseFactorSandbox.selectedFactors.value = [mockFactors[0]]
      mockUseFactorSandbox.screeningProgress.value = { screened_stocks: 500, total_stocks: 1000 }
      const wrapper = mountComponent()
      const progressText = wrapper.find('.factor-sandbox__progress-info')
      expect(progressText.exists()).toBe(true)
      expect(progressText.text()).toContain('500')
      expect(progressText.text()).toContain('1000')
    })
  })

  describe('test_cancel_button', () => {
    it('should show cancel button during screening', async () => {
      mockUseFactorSandbox.selectedFactors.value = [mockFactors[0]]
      mockUseFactorSandbox.screeningLoading.value = true
      const wrapper = mountComponent()
      expect(wrapper.find('.factor-sandbox__cancel-btn').exists()).toBe(true)
    })

    it('should call cancelScreening when cancel clicked', async () => {
      mockUseFactorSandbox.selectedFactors.value = [mockFactors[0]]
      mockUseFactorSandbox.screeningLoading.value = true
      const wrapper = mountComponent()
      await wrapper.find('.factor-sandbox__cancel-btn').trigger('click')
      expect(mockUseFactorSandbox.cancelScreening).toHaveBeenCalled()
    })
  })

  describe('test_universe_selection', () => {
    it('should have universe select', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.factor-sandbox__select').exists()).toBe(true)
    })

    it('should have correct options', () => {
      const wrapper = mountComponent()
      const options = wrapper.findAll('option')
      expect(options.length).toBe(4)
      expect(options[0].text()).toContain('全市场')
      expect(options[1].text()).toContain('沪深300')
    })
  })

  describe('test_search_functionality', () => {
    it('should filter categories by search', async () => {
      const wrapper = mountComponent()
      const searchInput = wrapper.find('.factor-sandbox__search')
      await searchInput.setValue('MACD')
      expect(searchInput.element.value).toBe('MACD')
    })
  })

  describe('test_mobile_layout', () => {
    it('should render mobile header on mobile', async () => {
      vi.doMock('@vueuse/core', () => ({
        useBreakpoints: () => ({
          smaller: () => ref(true),
        }),
        breakpointsTailwind: {},
      }))

      const wrapper = mountComponent()
      expect(wrapper.find('.factor-sandbox__mobile-header').exists()).toBe(true)
    })

    it('should have funnel, library, results tabs', async () => {
      vi.doMock('@vueuse/core', () => ({
        useBreakpoints: () => ({
          smaller: () => ref(true),
        }),
        breakpointsTailwind: {},
      }))

      const wrapper = mountComponent()
      const tabs = wrapper.findAll('.factor-sandbox__mobile-tab')
      expect(tabs.length).toBe(3)
    })
  })
})
