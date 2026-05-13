import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiFetch, extractData } from '../utils/api.js'
import { logger } from '../utils/logger.js'

export const FUND_QUICK_LIST = {
  etf: [
    { code: '510300', name: '沪深 300ETF' },
    { code: '510500', name: '中证 500ETF' },
    { code: '159915', name: '创业板 ETF' },
    { code: '518880', name: '黄金 ETF' },
    { code: '513050', name: '中概互联 ETF' },
  ],
  open: [
    { code: '005827', name: '易方达蓝筹' },
    { code: '000311', name: '景顺长城沪深 300' },
    { code: '110011', name: '易方达中小盘' },
    { code: '007119', name: '睿远成长价值' },
  ],
}

export const useFundStore = defineStore('fund', () => {
  const selectedFundCode = ref('')
  const fundInfo = ref(null)
  const navHistory = ref([])
  const topHoldings = ref([])
  const assetAllocation = ref([])
  const trailingReturns = ref({
    fund: {},
    category: {},
    benchmark: {},
  })
  const riskMetrics = ref({
    sharpe: null,
    max_drawdown: null,
    alpha: null,
    beta: null,
  })
  const compareFunds = ref([])
  const loading = ref(false)
  const error = ref(null)
  const dataSource = ref('')
  const lastUpdateTime = ref('')

  const hasFundInfo = computed(() => fundInfo.value !== null)
  const isLoading = computed(() => loading.value)
  const hasError = computed(() => error.value !== null)

  async function fetchFundInfo(code) {
    loading.value = true
    error.value = null
    selectedFundCode.value = code

    try {
      const [infoRes, returnsRes, riskRes] = await Promise.all([
        apiFetch(`/api/v1/fund/open/info?code=${code}`),
        apiFetch(`/api/v1/fund/open/returns/${code}`),
        apiFetch(`/api/v1/fund/open/risk/${code}`),
      ])

      const infoData = extractData(infoRes)
      const returnsData = extractData(returnsRes)
      const riskData = extractData(riskRes)

      if (infoData) {
        fundInfo.value = {
          code: infoData.code || code,
          name: infoData.name || '-',
          type: infoData.type || '-',
          nav: infoData.nav || '-',
          accumulated_nav: infoData.accumulated_nav || '-',
          nav_change_pct: infoData.nav_change_pct ? parseFloat(infoData.nav_change_pct).toFixed(2) : '-',
          nav_date: infoData.nav_date || '-',
          scale: infoData.scale || '-',
          found_date: infoData.found_date || '-',
          manager: infoData.manager || '-',
          company: infoData.company || '-',
          quarter: infoData.quarter || '-',
          rating: infoData.rating || 'N/A',
          purchase_fee: infoData.purchase_fee || 'N/A',
          redemption_fee: infoData.redemption_fee || 'N/A',
          dividend_freq: infoData.dividend_freq || 'N/A',
        }
        dataSource.value = infoData.source || 'unknown'
      }

      if (returnsData && returnsData.returns) {
        trailingReturns.value = {
          fund: {
            '1w': returnsData.returns['1w'] ?? null,
            '1m': returnsData.returns['1m'] ?? null,
            '3m': returnsData.returns['3m'] ?? null,
            '6m': returnsData.returns['6m'] ?? null,
            'ytd': returnsData.returns['ytd'] ?? null,
            '1y': returnsData.returns['1y'] ?? null,
            '3y': returnsData.returns['3y'] ?? null,
            '5y': returnsData.returns['since_inception'] ?? null,
          },
          category: { '1w': null, '1m': null, '3m': null, '6m': null, 'ytd': null, '1y': null, '3y': null, '5y': null },
          benchmark: { '1w': null, '1m': null, '3m': null, '6m': null, 'ytd': null, '1y': null, '3y': null, '5y': null },
        }
      }

      if (riskData) {
        riskMetrics.value = {
          sharpe: riskData.sharpe ?? null,
          max_drawdown: riskData.max_drawdown ?? null,
          alpha: riskData.alpha ?? null,
          beta: riskData.beta ?? null,
        }
      }

      lastUpdateTime.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    } catch (e) {
      logger.error('[FundStore] 加载失败:', e)
      error.value = e.message || '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchNavHistory(code, period = '6m') {
    try {
      const res = await apiFetch(`/api/v1/fund/open/nav/${code}?period=${period}`)
      const data = extractData(res)
      navHistory.value = Array.isArray(data) ? data : []
    } catch (e) {
      logger.warn('[FundStore] 净值历史加载失败:', e)
      navHistory.value = []
    }
  }

  async function fetchPortfolio(code) {
    try {
      const res = await apiFetch(`/api/v1/fund/portfolio/${code}`)
      const data = extractData(res)
      if (data) {
        topHoldings.value = (data.stocks || []).slice(0, 10)
        assetAllocation.value = (data.assets || []).map((a, i) => ({
          name: a.name,
          value: a.ratio,
          color: ['#60a5fa', '#34d399', '#fbbf24', '#f87171', '#a78bfa'][i % 5],
        }))
      }
    } catch (e) {
      logger.warn('[FundStore] 持仓数据加载失败:', e)
    }
  }

  async function fetchCompareFundReturns(code) {
    try {
      const res = await apiFetch(`/api/v1/fund/open/returns/${code}`)
      return extractData(res)
    } catch (e) {
      logger.warn(`[FundStore] 对比基金 ${code} 收益加载失败:`, e)
      return null
    }
  }

  function addCompareFund(fund) {
    if (compareFunds.value.length >= 3) {
      return { success: false, message: '最多只能对比 3 只基金' }
    }
    if (compareFunds.value.some(f => f.code === fund.code)) {
      return { success: false, message: '该基金已在对比列表中' }
    }
    compareFunds.value.push(fund)
    return { success: true }
  }

  function removeCompareFund(index) {
    compareFunds.value.splice(index, 1)
  }

  function clearCompareFunds() {
    compareFunds.value = []
  }

  function clearFundInfo() {
    fundInfo.value = null
    navHistory.value = []
    topHoldings.value = []
    assetAllocation.value = []
    trailingReturns.value = { fund: {}, category: {}, benchmark: {} }
    riskMetrics.value = { sharpe: null, max_drawdown: null, alpha: null, beta: null }
    selectedFundCode.value = ''
    error.value = null
  }

  return {
    selectedFundCode,
    fundInfo,
    navHistory,
    topHoldings,
    assetAllocation,
    trailingReturns,
    riskMetrics,
    compareFunds,
    loading,
    error,
    dataSource,
    lastUpdateTime,
    hasFundInfo,
    isLoading,
    hasError,
    fetchFundInfo,
    fetchNavHistory,
    fetchPortfolio,
    fetchCompareFundReturns,
    addCompareFund,
    removeCompareFund,
    clearCompareFunds,
    clearFundInfo,
  }
})
