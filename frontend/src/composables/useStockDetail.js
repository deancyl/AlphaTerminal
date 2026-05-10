import { ref, computed } from 'vue'
import { apiFetch } from '../utils/api.js'
import { formatNumber, formatMoney, formatVolume, formatHolderShares, formatHolderPct } from '../utils/formatters.js'

/**
 * Composable for shared stock detail logic
 * Provides data fetching, formatting utilities, and state management
 */
export function useStockDetail() {
  // Helper: strip sh/sz prefix for F9 API calls
  function getBareSymbol(symbol) {
    if (!symbol) return ''
    return symbol.replace(/^(sh|sz)/i, '')
  }

  // Get change class (bullish/bearish)
  function getChangeClass(change) {
    if (!change) return 'text-terminal-dim'
    const str = String(change)
    if (str.includes('新进') || str.includes('增')) return 'text-bullish'
    if (str.includes('减') || str.includes('不变')) return 'text-bearish'
    return 'text-terminal-dim'
  }

  // Get announcement type class
  function getAnnouncementTypeClass(type) {
    if (!type) return 'bg-gray-500/20 text-gray-400'
    const t = type.toLowerCase()
    if (t.includes('业绩') || t.includes('财报')) {
      return 'bg-blue-500/20 text-blue-400'
    }
    if (t.includes('重大') || t.includes('重要')) {
      return 'bg-red-500/20 text-red-400'
    }
    if (t.includes('分红') || t.includes('派息')) {
      return 'bg-green-500/20 text-green-400'
    }
    if (t.includes('增发') || t.includes('配股')) {
      return 'bg-yellow-500/20 text-yellow-400'
    }
    if (t.includes('减持') || t.includes('增持')) {
      return 'bg-purple-500/20 text-purple-400'
    }
    return 'bg-gray-500/20 text-gray-400'
  }

  // Format metric for peer comparison
  function formatMetric(value) {
    if (value === null || value === undefined) return '--'
    return value.toFixed(2)
  }

  // Get metric class for peer comparison
  function getMetricClass(value, type) {
    if (value === null || value === undefined) return 'text-terminal-dim'
    
    if (type === 'growth') {
      return value >= 0 ? 'text-bullish' : 'text-bearish'
    }
    
    if (type === 'pe') {
      if (value > 0 && value < 20) return 'text-bullish'
      if (value >= 20 && value < 40) return 'text-yellow-400'
      return 'text-bearish'
    }
    
    if (type === 'roe') {
      if (value >= 15) return 'text-bullish'
      if (value >= 8) return 'text-yellow-400'
      return 'text-bearish'
    }
    
    return 'text-terminal-secondary'
  }

  // Get rating class
  function getRatingClass(rating) {
    if (!rating) return 'text-terminal-dim'
    const r = rating.toLowerCase()
    if (r.includes('买入') || r.includes('增持') || r.includes('推荐')) {
      return 'bg-green-500/20 text-green-400'
    }
    if (r.includes('卖出') || r.includes('减持')) {
      return 'bg-red-500/20 text-red-400'
    }
    if (r.includes('中性') || r.includes('持有')) {
      return 'bg-yellow-500/20 text-yellow-400'
    }
    return 'text-terminal-dim'
  }

  return {
    getBareSymbol,
    formatNumber,
    formatMoney,
    formatVolume,
    formatHolderShares,
    formatHolderPct,
    getChangeClass,
    getAnnouncementTypeClass,
    formatMetric,
    getMetricClass,
    getRatingClass
  }
}

/**
 * Composable for fetching stock quote data
 */
export function useStockQuote() {
  const stockInfo = ref(null)
  const loading = ref(false)

  async function fetchQuote(symbol) {
    if (!symbol) return null
    
    loading.value = true
    
    // Ensure symbol format (add sh/sz prefix)
    let symbolToQuery = symbol
    if (!symbolToQuery.startsWith('sh') && !symbolToQuery.startsWith('sz')) {
      const firstChar = symbolToQuery.charAt(0)
      if (firstChar === '6') {
        symbolToQuery = 'sh' + symbolToQuery
      } else if (firstChar === '0' || firstChar === '3') {
        symbolToQuery = 'sz' + symbolToQuery
      }
    }
    
    try {
      const data = await apiFetch(`/api/v1/stocks/quote?symbol=${symbolToQuery}`, { timeoutMs: 10000 })
      if (data && data.name) {
        stockInfo.value = {
          symbol: symbol,
          name: data.name || symbol,
          price: data.price || 0,
          change: data.change_pct || 0,
          industry: data.industry || '--',
          totalShares: data.totalShares,
          floatShares: data.floatShares,
          totalMarketCap: data.totalMarketCap,
          floatMarketCap: data.floatMarketCap,
          listDate: data.listDate,
          business: data.business || '暂无主营业务数据',
        }
      } else {
        // Demo data fallback
        stockInfo.value = {
          symbol: symbol,
          name: '演示股票',
          price: 10.50,
          change: 2.35,
          industry: '计算机软件',
          totalShares: 1000000000,
          floatShares: 800000000,
          totalMarketCap: 10500000000,
          floatMarketCap: 8400000000,
          listDate: '2020-01-01',
          business: '公司主要从事人工智能、大数据、云计算等前沿技术的研发与应用，为客户提供智能化的解决方案。',
        }
      }
      return stockInfo.value
    } catch (e) {
      console.error('[useStockQuote] Fetch error:', e)
      // Demo data fallback
      stockInfo.value = {
        symbol: symbol,
        name: '演示股票',
        price: 10.50,
        change: 2.35,
        industry: '计算机软件',
        totalShares: 1000000000,
        floatShares: 800000000,
        totalMarketCap: 10500000000,
        floatMarketCap: 8400000000,
        listDate: '2020-01-01',
        business: '公司主要从事人工智能、大数据、云计算等前沿技术的研发与应用，为客户提供智能化的解决方案。',
      }
      return stockInfo.value
    } finally {
      loading.value = false
    }
  }

  const priceClass = computed(() => {
    if (!stockInfo.value) return ''
    return stockInfo.value.change >= 0 ? 'text-bullish' : 'text-bearish'
  })

  const changeClass = computed(() => {
    if (!stockInfo.value) return ''
    return stockInfo.value.change >= 0 ? 'text-bullish' : 'text-bearish'
  })

  return {
    stockInfo,
    loading,
    fetchQuote,
    priceClass,
    changeClass
  }
}
