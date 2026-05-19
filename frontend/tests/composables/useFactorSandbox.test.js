import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { nextTick } from 'vue'

vi.mock('@/utils/api.js', () => ({
  apiFetch: vi.fn(),
  apiFetchDeduped: vi.fn(),
}))

vi.mock('@/utils/logger.js', () => ({
  logger: {
    error: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('@/utils/constants.js', () => ({
  TIMEOUTS: {
    API_DEFAULT: 15000,
  },
}))

import { useFactorSandbox } from '@/composables/useFactorSandbox.js'
import * as apiModule from '@/utils/api.js'

const mockFactors = [
  { id: 'macd_cross', name: 'MACD金叉', category: 'technical', description: 'MACD金叉信号', params: { fast: 12, slow: 26, signal: 9 } },
  { id: 'rsi_oversold', name: 'RSI超卖', category: 'technical', description: 'RSI低于30', params: { period: 14, threshold: 30 } },
  { id: 'ma_breakout', name: '突破均线', category: 'technical', description: '突破20日均线', params: { period: 20 } },
  { id: 'foreign_inflow', name: '外资净流入', category: 'fund_flow', description: '北向资金净流入', params: {} },
  { id: 'llm_sentiment', name: 'LLM情绪得分', category: 'sentiment', description: 'AI情绪分析', params: {} },
  { id: 'volume_breakout', name: '放量突破', category: 'technical', description: '成交量放大突破', params: { volume_ratio: 2 } },
  { id: 'institution_research', name: '机构调研', category: 'fund_flow', description: '近期机构调研', params: { days: 30 } },
  { id: 'new_high', name: '创新高', category: 'momentum', description: '创60日新高', params: { period: 60 } },
]

const mockScreenedStocks = [
  { symbol: 'sh600519', name: '贵州茅台', score: 85.5, factor_values: { macd_cross: true, rsi_oversold: false } },
  { symbol: 'sh600036', name: '招商银行', score: 72.3, factor_values: { macd_cross: true, rsi_oversold: true } },
  { symbol: 'sh601318', name: '中国平安', score: 68.1, factor_values: { macd_cross: false, rsi_oversold: true } },
]

describe('useFactorSandbox', () => {
  let sandbox

  beforeEach(() => {
    vi.clearAllMocks()
    sandbox = useFactorSandbox()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('fetchFactors', () => {
    it('should fetch factors successfully', async () => {
      apiModule.apiFetchDeduped.mockResolvedValueOnce({ factors: mockFactors })

      const result = await sandbox.fetchFactors()

      expect(apiModule.apiFetchDeduped).toHaveBeenCalledWith(
        'factor_sandbox:factors',
        '/api/v1/factor_sandbox/factors',
        { timeoutMs: 15000 }
      )
      expect(result).toHaveLength(8)
      expect(sandbox.factors.value).toHaveLength(8)
    })

    it('should extract categories from factors', async () => {
      apiModule.apiFetchDeduped.mockResolvedValueOnce({ factors: mockFactors })

      await sandbox.fetchFactors()

      expect(sandbox.categories.value.length).toBeGreaterThan(0)
      expect(sandbox.categories.value.find(c => c.id === 'technical')).toBeDefined()
      expect(sandbox.categories.value.find(c => c.id === 'fund_flow')).toBeDefined()
    })

    it('should handle fetch error', async () => {
      apiModule.apiFetchDeduped.mockRejectedValueOnce(new Error('Network error'))

      const result = await sandbox.fetchFactors()

      expect(result).toEqual([])
      expect(sandbox.error.value).toBe('Network error')
    })

    it('should set factorsLoading state correctly', async () => {
      let resolvePromise
      apiModule.apiFetchDeduped.mockImplementationOnce(() => new Promise(resolve => {
        resolvePromise = resolve
      }))

      const promise = sandbox.fetchFactors()
      
      expect(sandbox.factorsLoading.value).toBe(true)
      
      resolvePromise({ factors: mockFactors })
      await promise
      
      expect(sandbox.factorsLoading.value).toBe(false)
    })

    it('should handle empty response', async () => {
      apiModule.apiFetchDeduped.mockResolvedValueOnce({})

      const result = await sandbox.fetchFactors()

      expect(result).toEqual([])
      expect(sandbox.factors.value).toEqual([])
    })
  })

  describe('addFactor', () => {
    it('should add factor to selection', () => {
      const factor = mockFactors[0]
      sandbox.addFactor(factor)

      expect(sandbox.selectedFactors.value).toHaveLength(1)
      expect(sandbox.selectedFactors.value[0].id).toBe('macd_cross')
    })

    it('should not add duplicate factor', () => {
      const factor = mockFactors[0]
      sandbox.addFactor(factor)
      sandbox.addFactor(factor)

      expect(sandbox.selectedFactors.value).toHaveLength(1)
    })

    it('should copy factor params', () => {
      const factor = mockFactors[0]
      sandbox.addFactor(factor)

      expect(sandbox.selectedFactors.value[0].params).toEqual({ fast: 12, slow: 26, signal: 9 })
    })

    it('should add multiple different factors', () => {
      sandbox.addFactor(mockFactors[0])
      sandbox.addFactor(mockFactors[1])
      sandbox.addFactor(mockFactors[3])

      expect(sandbox.selectedFactors.value).toHaveLength(3)
    })
  })

  describe('removeFactor', () => {
    it('should remove factor from selection', () => {
      sandbox.addFactor(mockFactors[0])
      sandbox.addFactor(mockFactors[1])

      sandbox.removeFactor('macd_cross')

      expect(sandbox.selectedFactors.value).toHaveLength(1)
      expect(sandbox.selectedFactors.value[0].id).toBe('rsi_oversold')
    })

    it('should handle removing non-existent factor', () => {
      sandbox.addFactor(mockFactors[0])

      sandbox.removeFactor('non_existent')

      expect(sandbox.selectedFactors.value).toHaveLength(1)
    })

    it('should handle removing from empty selection', () => {
      sandbox.removeFactor('macd_cross')

      expect(sandbox.selectedFactors.value).toHaveLength(0)
    })
  })

  describe('toggleFactor', () => {
    it('should add factor when not selected', () => {
      sandbox.toggleFactor(mockFactors[0])

      expect(sandbox.selectedFactors.value).toHaveLength(1)
      expect(sandbox.selectedFactors.value[0].id).toBe('macd_cross')
    })

    it('should remove factor when already selected', () => {
      sandbox.addFactor(mockFactors[0])
      sandbox.toggleFactor(mockFactors[0])

      expect(sandbox.selectedFactors.value).toHaveLength(0)
    })

    it('should toggle multiple times correctly', () => {
      sandbox.toggleFactor(mockFactors[0])
      expect(sandbox.selectedFactors.value).toHaveLength(1)

      sandbox.toggleFactor(mockFactors[0])
      expect(sandbox.selectedFactors.value).toHaveLength(0)

      sandbox.toggleFactor(mockFactors[0])
      expect(sandbox.selectedFactors.value).toHaveLength(1)
    })
  })

  describe('reorderFactors', () => {
    it('should reorder factors correctly', () => {
      sandbox.addFactor(mockFactors[0])
      sandbox.addFactor(mockFactors[1])
      sandbox.addFactor(mockFactors[2])

      sandbox.reorderFactors(0, 2)

      expect(sandbox.selectedFactors.value[0].id).toBe('rsi_oversold')
      expect(sandbox.selectedFactors.value[1].id).toBe('ma_breakout')
      expect(sandbox.selectedFactors.value[2].id).toBe('macd_cross')
    })

    it('should handle reorder to same position', () => {
      sandbox.addFactor(mockFactors[0])
      sandbox.addFactor(mockFactors[1])

      sandbox.reorderFactors(0, 0)

      expect(sandbox.selectedFactors.value[0].id).toBe('macd_cross')
    })

    it('should handle reorder from end to start', () => {
      sandbox.addFactor(mockFactors[0])
      sandbox.addFactor(mockFactors[1])
      sandbox.addFactor(mockFactors[2])

      sandbox.reorderFactors(2, 0)

      expect(sandbox.selectedFactors.value[0].id).toBe('ma_breakout')
      expect(sandbox.selectedFactors.value[1].id).toBe('macd_cross')
      expect(sandbox.selectedFactors.value[2].id).toBe('rsi_oversold')
    })
  })

  describe('runScreening', () => {
    it('should run screening successfully', async () => {
      sandbox.addFactor(mockFactors[0])
      sandbox.addFactor(mockFactors[1])

      apiModule.apiFetch.mockResolvedValueOnce({ stocks: mockScreenedStocks })

      const result = await sandbox.runScreening()

      expect(apiModule.apiFetch).toHaveBeenCalledWith(
        '/api/v1/factor_sandbox/screen',
        expect.objectContaining({
          method: 'POST',
          timeoutMs: 35000,
        })
      )
      expect(result).toHaveLength(3)
      expect(sandbox.screenedStocks.value).toHaveLength(3)
    })

    it('should not run screening with no factors selected', async () => {
      await sandbox.runScreening()

      expect(apiModule.apiFetch).not.toHaveBeenCalled()
    })

    it('should not run screening when already loading', async () => {
      sandbox.addFactor(mockFactors[0])
      
      let resolvePromise
      apiModule.apiFetch.mockImplementationOnce(() => new Promise(resolve => {
        resolvePromise = resolve
      }))

      const promise1 = sandbox.runScreening()
      const promise2 = sandbox.runScreening()

      resolvePromise({ stocks: mockScreenedStocks })
      await promise1

      expect(apiModule.apiFetch).toHaveBeenCalledTimes(1)
    })

    it('should send correct request body', async () => {
      sandbox.addFactor(mockFactors[0])
      sandbox.universe.value = 'hs300'
      sandbox.limit.value = 100

      apiModule.apiFetch.mockResolvedValueOnce({ stocks: [] })

      await sandbox.runScreening()

      const callArgs = apiModule.apiFetch.mock.calls[0]
      const body = JSON.parse(callArgs[1].body)

      expect(body.factors).toHaveLength(1)
      expect(body.factors[0].id).toBe('macd_cross')
      expect(body.universe).toBe('hs300')
      expect(body.limit).toBe(100)
    })

    it('should handle screening error', async () => {
      sandbox.addFactor(mockFactors[0])

      apiModule.apiFetch.mockRejectedValueOnce(new Error('Screening failed'))

      const result = await sandbox.runScreening()

      expect(result).toEqual([])
      expect(sandbox.error.value).toBe('Screening failed')
    })

    it('should set screeningLoading state correctly', async () => {
      sandbox.addFactor(mockFactors[0])

      let resolvePromise
      apiModule.apiFetch.mockImplementationOnce(() => new Promise(resolve => {
        resolvePromise = resolve
      }))

      const promise = sandbox.runScreening()

      expect(sandbox.screeningLoading.value).toBe(true)

      resolvePromise({ stocks: mockScreenedStocks })
      await promise

      expect(sandbox.screeningLoading.value).toBe(false)
    })
  })

  describe('cancelScreening', () => {
    it('should cancel ongoing screening', async () => {
      sandbox.addFactor(mockFactors[0])

      let resolvePromise
      apiModule.apiFetch.mockImplementationOnce(() => new Promise(resolve => {
        resolvePromise = resolve
      }))

      const promise = sandbox.runScreening()
      
      expect(sandbox.screeningLoading.value).toBe(true)
      
      sandbox.cancelScreening()
      
      expect(sandbox.screeningLoading.value).toBe(false)

      resolvePromise({ stocks: mockScreenedStocks })
      await promise
    })

    it('should handle cancel when no screening is running', () => {
      sandbox.cancelScreening()
      expect(sandbox.screeningLoading.value).toBe(false)
    })
  })

  describe('screeningProgress', () => {
    it('should update progress from response', async () => {
      sandbox.addFactor(mockFactors[0])

      const progressData = { screened_stocks: 500, total_stocks: 1000 }
      apiModule.apiFetch.mockResolvedValueOnce({ 
        stocks: mockScreenedStocks, 
        progress: progressData 
      })

      await sandbox.runScreening()

      expect(sandbox.screeningProgress.value).toEqual(progressData)
    })

    it('should reset progress before new screening', async () => {
      sandbox.addFactor(mockFactors[0])
      sandbox.screeningProgress.value = { screened_stocks: 500, total_stocks: 1000 }

      apiModule.apiFetch.mockResolvedValueOnce({ stocks: mockScreenedStocks })

      await sandbox.runScreening()

      expect(sandbox.screeningProgress.value).toEqual(null)
    })
  })

  describe('isFactorSelected', () => {
    it('should return true for selected factor', () => {
      sandbox.addFactor(mockFactors[0])

      expect(sandbox.isFactorSelected.value('macd_cross')).toBe(true)
    })

    it('should return false for non-selected factor', () => {
      sandbox.addFactor(mockFactors[0])

      expect(sandbox.isFactorSelected.value('rsi_oversold')).toBe(false)
    })

    it('should return false when no factors selected', () => {
      expect(sandbox.isFactorSelected.value('macd_cross')).toBe(false)
    })
  })

  describe('factorsByCategory', () => {
    it('should group factors by category', async () => {
      apiModule.apiFetchDeduped.mockResolvedValueOnce({ factors: mockFactors })

      await sandbox.fetchFactors()

      const grouped = sandbox.factorsByCategory.value
      expect(grouped['technical']).toBeDefined()
      expect(grouped['technical']).toHaveLength(4)
      expect(grouped['fund_flow']).toBeDefined()
      expect(grouped['fund_flow']).toHaveLength(2)
    })

    it('should handle factors without category', async () => {
      const factorsWithUncategorized = [
        ...mockFactors,
        { id: 'uncategorized', name: 'Uncategorized', params: {} }
      ]
      apiModule.apiFetchDeduped.mockResolvedValueOnce({ factors: factorsWithUncategorized })

      await sandbox.fetchFactors()

      const grouped = sandbox.factorsByCategory.value
      expect(grouped['other']).toBeDefined()
      expect(grouped['other']).toHaveLength(1)
    })
  })

  describe('clearSelectedFactors', () => {
    it('should clear all selected factors', () => {
      sandbox.addFactor(mockFactors[0])
      sandbox.addFactor(mockFactors[1])
      sandbox.addFactor(mockFactors[2])

      sandbox.clearSelectedFactors()

      expect(sandbox.selectedFactors.value).toHaveLength(0)
    })
  })

  describe('clearResults', () => {
    it('should clear screening results', () => {
      sandbox.screenedStocks.value = mockScreenedStocks
      sandbox.backtestPreviews.value = [{ symbol: 'sh600519' }]

      sandbox.clearResults()

      expect(sandbox.screenedStocks.value).toHaveLength(0)
      expect(sandbox.backtestPreviews.value).toHaveLength(0)
    })
  })

  describe('getBacktestPreview', () => {
    it('should fetch backtest preview successfully', async () => {
      const mockPreview = [
        { symbol: 'sh600519', total_return_pct: 25.5, max_drawdown_pct: 10.2 }
      ]
      apiModule.apiFetch.mockResolvedValueOnce({ results: mockPreview })

      const result = await sandbox.getBacktestPreview(['sh600519'], '2024-01-01', '2024-12-31')

      expect(apiModule.apiFetch).toHaveBeenCalledWith(
        '/api/v1/factor_sandbox/backtest_preview',
        expect.objectContaining({
          method: 'POST',
          timeoutMs: 35000,
        })
      )
      expect(result).toHaveLength(1)
    })

    it('should not fetch with empty symbols', async () => {
      const result = await sandbox.getBacktestPreview([], '2024-01-01', '2024-12-31')

      expect(apiModule.apiFetch).not.toHaveBeenCalled()
      expect(result).toBeUndefined()
    })

    it('should handle backtest error', async () => {
      apiModule.apiFetch.mockRejectedValueOnce(new Error('Backtest failed'))

      const result = await sandbox.getBacktestPreview(['sh600519'], '2024-01-01', '2024-12-31')

      expect(result).toEqual([])
    })
  })
})
