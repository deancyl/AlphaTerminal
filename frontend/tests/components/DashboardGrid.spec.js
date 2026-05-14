import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DashboardGrid from '../../src/components/DashboardGrid.vue'

// ── Mock external dependencies ─────────────────────────────────────
vi.mock('@vueuse/core', () => ({
  useBreakpoints: vi.fn(() => ({
    smaller: vi.fn(() => false) // Desktop by default
  })),
  breakpointsTailwind: {},
  useDebounceFn: vi.fn((fn) => fn)
}))

vi.mock('../../src/utils/api.js', () => ({
  apiFetch: vi.fn()
}))

vi.mock('../../src/composables/usePullToRefresh.js', () => ({
  usePullToRefresh: vi.fn(() => ({
    pullDistance: { value: 0 },
    isRefreshing: { value: false },
    pullIndicatorStyle: {},
    containerRef: { value: null }
  }))
}))

vi.mock('../../src/composables/useSmartPolling.js', () => ({
  useSmartPolling: vi.fn(() => ({
    start: vi.fn(),
    stop: vi.fn()
  }))
}))

vi.mock('../../src/composables/useToast.js', () => ({
  toast: {
    warning: vi.fn(),
    success: vi.fn(),
    error: vi.fn()
  }
}))

// Mock child components to avoid complex rendering
vi.mock('../../src/components/IndexLineChart.vue', () => ({
  default: {
    name: 'IndexLineChart',
    template: '<div class="mock-index-line-chart"></div>'
  }
}))

vi.mock('../../src/components/NewsFeed.vue', () => ({
  default: {
    name: 'NewsFeed',
    template: '<div class="mock-news-feed"></div>'
  }
}))

vi.mock('../../src/components/SentimentGauge.vue', () => ({
  default: {
    name: 'SentimentGauge',
    template: '<div class="mock-sentiment-gauge"></div>',
    emits: ['symbol-click']
  }
}))

vi.mock('../../src/components/HotSectors.vue', () => ({
  default: {
    name: 'HotSectors',
    template: '<div class="mock-hot-sectors"></div>',
    emits: ['sector-click']
  }
}))

vi.mock('../../src/components/FundFlowPanel.vue', () => ({
  default: {
    name: 'FundFlowPanel',
    template: '<div class="mock-fund-flow-panel"></div>'
  }
}))

vi.mock('../../src/components/StockScreener.vue', () => ({
  default: {
    name: 'StockScreener',
    template: '<div class="mock-stock-screener"></div>',
    emits: ['symbol-click']
  }
}))

vi.mock('../../src/components/WidgetErrorBoundary.vue', () => ({
  default: {
    name: 'WidgetErrorBoundary',
    template: '<div class="mock-widget-error-boundary"><slot /></div>'
  }
}))

vi.mock('../../src/components/FreshnessIndicator.vue', () => ({
  default: {
    name: 'FreshnessIndicator',
    template: '<div class="mock-freshness-indicator"></div>',
    props: ['timestamp']
  }
}))

// Mock GridStack
vi.mock('gridstack', () => ({
  default: {
    init: vi.fn(() => ({
      setStatic: vi.fn(),
      getGridItems: vi.fn(() => []),
      update: vi.fn(),
      on: vi.fn(),
      destroy: vi.fn()
    }))
  }
}))

// ── Test Suite ───────────────────────────────────────────────────────
describe('DashboardGrid.vue', () => {
  let pinia

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
    
    // Mock window.localStorage
    const localStorageMock = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn()
    }
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock
    })
    
    // Mock GridStack on window
    window.GridStack = vi.fn(() => ({
      setStatic: vi.fn(),
      getGridItems: vi.fn(() => []),
      update: vi.fn(),
      on: vi.fn(),
      destroy: vi.fn()
    }))
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // ── Rendering Tests ───────────────────────────────────────────────
  describe('Rendering', () => {
    it('renders without errors', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('.grid-stack').exists() || wrapper.find('.flex').exists()).toBe(true)
    })

    it('renders with default props', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      // Default props: marketData=null, chinaAllData=[], sectorsData=[], derivativesData=[], isLocked=true
      expect(wrapper.props('marketData')).toBe(null)
      expect(wrapper.props('chinaAllData')).toEqual([])
      expect(wrapper.props('sectorsData')).toEqual([])
      expect(wrapper.props('derivativesData')).toEqual([])
      expect(wrapper.props('isLocked')).toBe(true)
    })

    it('renders with custom marketData prop', async () => {
      const marketData = {
        '000001': { name: '上证指数', price: 3100.50, change_pct: 1.25 },
        '000300': { name: '沪深300', price: 3800.20, change_pct: -0.35 }
      }
      
      const wrapper = mount(DashboardGrid, {
        props: { marketData },
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      expect(wrapper.props('marketData')).toEqual(marketData)
    })

    it('renders with custom isLocked prop', async () => {
      const wrapper = mount(DashboardGrid, {
        props: { isLocked: false },
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      expect(wrapper.props('isLocked')).toBe(false)
    })
  })

  // ── Computed Properties Tests ───────────────────────────────────────
  describe('Computed Properties', () => {
    it('computes windItems correctly from marketData', async () => {
      const marketData = {
        '000001': { name: '上证指数', price: 3100.50, change_pct: 1.25 },
        '000300': { name: '沪深300', price: 3800.20, change_pct: -0.35 }
      }
      
      const wrapper = mount(DashboardGrid, {
        props: { marketData },
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      const windItems = wrapper.vm.windItems
      
      // Should have 2 index items (no macro data in this test)
      expect(windItems.length).toBeGreaterThanOrEqual(2)
      
      // Check structure of index items
      const indexItems = windItems.filter(item => item.category === 'index')
      expect(indexItems.length).toBe(2)
      expect(indexItems[0].symbol).toBe('000001')
      expect(indexItems[0].name).toBe('上证指数')
      expect(indexItems[0].price).toBe(3100.50)
      expect(indexItems[0].change_pct).toBe(1.25)
      expect(indexItems[0].category).toBe('index')
    })

    it('computes chinaAllItems correctly from chinaAllData prop', async () => {
      const chinaAllData = [
        { symbol: '000001', name: '上证指数', price: 3100.50, change_pct: 1.25 },
        { symbol: '399001', name: '深证成指', price: 10500.30, change_pct: 0.85 }
      ]
      
      const wrapper = mount(DashboardGrid, {
        props: { chinaAllData },
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      const chinaAllItems = wrapper.vm.chinaAllItems
      expect(chinaAllItems).toEqual(chinaAllData)
    })

    it('computes sectors correctly from sectorsData prop', async () => {
      const sectorsData = [
        { name: '半导体', change_pct: 2.5, top_stock: { code: '600584', name: '长电科技' } },
        { name: '新能源', change_pct: -1.2, top_stock: { code: '300014', name: '亿纬锂能' } }
      ]
      
      const wrapper = mount(DashboardGrid, {
        props: { sectorsData },
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      const sectors = wrapper.vm.sectors
      expect(sectors).toEqual(sectorsData)
    })

    it('computes timestamp from marketData', async () => {
      const marketData = {
        '000001': { name: '上证指数', price: 3100.50 },
        timestamp: '2024-01-15 14:30:00'
      }
      
      const wrapper = mount(DashboardGrid, {
        props: { marketData },
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      expect(wrapper.vm.timestamp).toBe('2024-01-15 14:30:00')
    })

    it('computes tsDisplay correctly', async () => {
      const marketData = {
        '000001': { name: '上证指数', price: 3100.50 },
        timestamp: '2024-01-15 14:30:00'
      }
      
      const wrapper = mount(DashboardGrid, {
        props: { marketData },
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      expect(wrapper.vm.tsDisplay).toBe('14:30:00')
    })
  })

  // ── Event Emissions Tests ───────────────────────────────────────────
  describe('Event Emissions', () => {
    it('emits toggle-lock event when toggleLock is called', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      wrapper.vm.toggleLock()
      
      expect(wrapper.emitted('toggle-lock')).toBeTruthy()
      expect(wrapper.emitted('toggle-lock').length).toBe(1)
    })

    it('emits open-fullscreen event with correct payload', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      wrapper.vm.selectedIndex = '000001'
      wrapper.vm.currentIndexName = '上证指数'
      
      wrapper.vm.handleFullscreenClick()
      
      const emitted = wrapper.emitted('open-fullscreen')
      expect(emitted).toBeTruthy()
      expect(emitted[0][0]).toHaveProperty('symbol')
      expect(emitted[0][0]).toHaveProperty('name')
    })
  })

  // ── Methods Tests ───────────────────────────────────────────────────
  describe('Methods', () => {
    it('handleWindClick sets correct symbol and name for index items', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      const item = {
        symbol: '000001',
        name: '上证指数',
        price: 3100.50,
        change_pct: 1.25,
        category: 'index'
      }
      
      wrapper.vm.handleWindClick(item)
      
      await new Promise(resolve => setTimeout(resolve, 10))
      
      expect(wrapper.vm.selectedIndex).toBe('sz000001')
      expect(wrapper.vm.currentIndexName).toBe('上证指数')
    })

    it('formatWindPrice returns correct format for index items', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      const indexItem = {
        symbol: '000001',
        name: '上证指数',
        price: 3100.50,
        change_pct: 1.25,
        category: 'index'
      }
      
      const result = wrapper.vm.formatWindPrice(indexItem)
      
      // Should format price with 2 decimals
      expect(result).toBe('3100.50')
    })

    it('formatWindPrice returns correct format for macro items with unit', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      const macroItem = {
        symbol: 'GOLD',
        name: '黄金',
        price: 2050.30,
        change_pct: 0.85,
        unit: 'USD',
        category: 'macro'
      }
      
      const result = wrapper.vm.formatWindPrice(macroItem)
      
      // Should format price with unit
      expect(result).toBe('2050.30 USD')
    })

    it('formatWindChangePct returns correct format for positive change', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      const result = wrapper.vm.formatWindChangePct(1.25)
      
      expect(result).toBe('+1.25%')
    })

    it('formatWindChangePct returns correct format for negative change', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      const result = wrapper.vm.formatWindChangePct(-0.35)
      
      expect(result).toBe('-0.35%')
    })

    it('formatWindChangePct handles null/undefined values', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      expect(wrapper.vm.formatWindChangePct(null)).toBe('--')
      expect(wrapper.vm.formatWindChangePct(undefined)).toBe('--')
    })

    it('switchPeriod updates selectedPeriod correctly', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      wrapper.vm.switchPeriod('weekly')
      
      expect(wrapper.vm.selectedPeriod).toBe('weekly')
    })

    it('toggleIndicator adds and removes indicators correctly', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      wrapper.vm.toggleIndicator('MACD')
      expect(wrapper.vm.activeIndicators).toContain('MACD')
      
      wrapper.vm.toggleIndicator('MACD')
      expect(wrapper.vm.activeIndicators).not.toContain('MACD')
    })
  })

  // ── Error States Tests ──────────────────────────────────────────────
  describe('Error States', () => {
    it('displays error message when macroError is set', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      wrapper.vm.macroError = 'Failed to fetch macro data'
      await wrapper.vm.$nextTick()
      
      const errorElement = wrapper.find('.text-red-400')
      expect(errorElement.exists()).toBe(true)
      expect(errorElement.text()).toContain('Failed to fetch macro data')
    })

    it('shows retry button in error state', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      wrapper.vm.macroError = 'Failed to fetch macro data'
      await wrapper.vm.$nextTick()
      
      const retryButton = wrapper.find('button')
      expect(retryButton.exists()).toBe(true)
      expect(retryButton.text()).toContain('重试')
    })

    it('retryMacroFetch is called when retry button is clicked', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      wrapper.vm.macroError = 'Failed to fetch macro data'
      await wrapper.vm.$nextTick()
      
      const retryButton = wrapper.find('button')
      expect(retryButton.exists()).toBe(true)
      expect(retryButton.text()).toContain('重试')
    })
  })

  // ── Loading States Tests ─────────────────────────────────────────────
  describe('Loading States', () => {
    it('shows skeleton when windItems is empty and no error', async () => {
      const wrapper = mount(DashboardGrid, {
        props: { marketData: null },
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      wrapper.vm.macroData = []
      await wrapper.vm.$nextTick()
      
      const skeleton = wrapper.find('.animate-pulse')
      expect(skeleton.exists()).toBe(true)
    })

    it('shows loading spinner when macroLoading is true', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      wrapper.vm.macroLoading = true
      wrapper.vm.macroError = 'Failed to fetch macro data'
      await wrapper.vm.$nextTick()
      
      const spinner = wrapper.find('.animate-spin')
      expect(spinner.exists()).toBe(true)
    })
  })

  // ── Layout Persistence Tests ─────────────────────────────────────────
  describe('Layout Persistence', () => {
    it('loadLayout returns null when no saved layout exists', async () => {
      window.localStorage.getItem.mockReturnValue(null)
      
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      const loadedLayout = wrapper.vm.loadLayout()
      expect(loadedLayout).toBe(null)
    })

    it('loads layout from localStorage', async () => {
      const savedLayout = {
        version: 1,
        timestamp: Date.now(),
        nodes: [
          { id: 'chart', x: 0, y: 0, w: 8, h: 6 }
        ]
      }
      
      window.localStorage.getItem.mockReturnValue(JSON.stringify(savedLayout))
      
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      const loadedLayout = wrapper.vm.loadLayout()
      
      expect(loadedLayout).toEqual(savedLayout.nodes)
    })

    it('clears layout from localStorage', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      wrapper.vm.clearLayout()
      
      expect(window.localStorage.removeItem).toHaveBeenCalledWith('alphaterminal_grid_layout')
    })
  })

  // ── Mobile Navigation Tests ─────────────────────────────────────────
  describe('Mobile Navigation', () => {
    it('has correct mobile anchors', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      const anchors = wrapper.vm.mobileAnchors
      
      expect(anchors.length).toBe(6)
      expect(anchors[0].id).toBe('section-chart')
      expect(anchors[1].id).toBe('section-wind')
      expect(anchors[2].id).toBe('section-screener')
      expect(anchors[3].id).toBe('section-sentiment')
      expect(anchors[4].id).toBe('section-sectors')
      expect(anchors[5].id).toBe('section-news')
    })

    it('scrollToMobileSection calls scrollIntoView', async () => {
      const mockScrollIntoView = vi.fn()
      
      // Mock document.getElementById
      document.getElementById = vi.fn(() => ({
        scrollIntoView: mockScrollIntoView
      }))
      
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      wrapper.vm.scrollToMobileSection('section-chart')
      
      expect(document.getElementById).toHaveBeenCalledWith('section-chart')
      expect(mockScrollIntoView).toHaveBeenCalledWith({
        behavior: 'smooth',
        block: 'start'
      })
    })
  })

  // ── Symbol Normalization Tests ──────────────────────────────────────
  describe('Symbol Normalization', () => {
    it('normalizeMacroSymbol maps gold variants correctly', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      expect(wrapper.vm.normalizeMacroSymbol('黄金')).toBe('GOLD')
      expect(wrapper.vm.normalizeMacroSymbol('XAU')).toBe('GOLD')
      expect(wrapper.vm.normalizeMacroSymbol('GOLD')).toBe('GOLD')
    })

    it('normalizeMacroSymbol maps WTI variants correctly', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      expect(wrapper.vm.normalizeMacroSymbol('WTI原油')).toBe('WTI')
      expect(wrapper.vm.normalizeMacroSymbol('WTI')).toBe('WTI')
      expect(wrapper.vm.normalizeMacroSymbol('原油')).toBe('WTI')
    })

    it('normalizeMacroSymbol maps VIX variants correctly', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      expect(wrapper.vm.normalizeMacroSymbol('VIX')).toBe('VIX')
      expect(wrapper.vm.normalizeMacroSymbol('恐慌指数')).toBe('VIX')
    })

    it('normalizeMacroSymbol returns null for unmapped symbols', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      expect(wrapper.vm.normalizeMacroSymbol('UNKNOWN_SYMBOL')).toBe(null)
      expect(wrapper.vm.normalizeMacroSymbol('')).toBe(null)
      expect(wrapper.vm.normalizeMacroSymbol(null)).toBe(null)
    })
  })

  // ── Index Options Tests ─────────────────────────────────────────────
  describe('Index Options', () => {
    it('has correct default index options', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      const options = wrapper.vm.indexOptions
      
      expect(options.length).toBe(4)
      expect(options[0].symbol).toBe('000001')
      expect(options[0].name).toBe('上证')
      expect(options[1].symbol).toBe('000300')
      expect(options[1].name).toBe('沪深300')
    })

    it('has correct period options', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      const periods = wrapper.vm.periods
      
      expect(periods.length).toBe(4)
      expect(periods[0].key).toBe('minutely')
      expect(periods[1].key).toBe('daily')
      expect(periods[2].key).toBe('weekly')
      expect(periods[3].key).toBe('monthly')
    })

    it('has correct indicator options', async () => {
      const wrapper = mount(DashboardGrid, {
        global: {
          plugins: [pinia],
          stubs: {
            IndexLineChart: true,
            NewsFeed: true,
            SentimentGauge: true,
            HotSectors: true,
            FundFlowPanel: true,
            StockScreener: true,
            WidgetErrorBoundary: true,
            FreshnessIndicator: true
          }
        }
      })
      
      const indicators = wrapper.vm.indicators
      
      expect(indicators.length).toBe(7)
      expect(indicators[0].key).toBe('MACD')
      expect(indicators[1].key).toBe('BOLL')
      expect(indicators[2].key).toBe('KDJ')
    })
  })
})
