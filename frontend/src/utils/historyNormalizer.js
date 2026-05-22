/**
 * historyNormalizer.js
 * 
 * Normalizes history data from different API endpoints to a standard ECharts format.
 * Handles response format differences between stock/bond/futures/forex endpoints.
 * 
 * API Response Formats:
 * - Stock:  { data: { history: [{date, close, open, high, low, volume}] } }
 * - Bond:   { data: { history: [{date, yield}] } }  ← Only yield, no OHLC
 * - Futures:{ data: { history: [{date, close, open, high, low, volume, hold}] } }
 * - Forex:  { data: { data: [{date, close, open, high, low}] } }  ← Uses 'data' key!
 */

/**
 * Normalize history data from different API endpoints to ECharts format
 * 
 * @param {Object} response - API response object
 * @param {'stock'|'bond'|'futures'|'forex'|'unknown'} assetType - Asset type
 * @returns {Array<{date: string, close: number, open: number, high: number, low: number, volume: number}>}
 *   Normalized history array
 */
export function normalizeHistoryData(response, assetType) {
  let rawHistory = []
  
  switch (assetType) {
    case 'stock':
    case 'futures':
      rawHistory = response?.data?.history || response?.history || []
      break
    
    case 'bond':
      rawHistory = response?.data?.history || response?.history || []
      break
    
    case 'forex':
      rawHistory = response?.data?.data || response?.data || []
      break
    
    default:
      rawHistory = response?.data?.history || response?.data?.data || response?.history || response?.data || []
  }
  
  if (!rawHistory || !Array.isArray(rawHistory) || rawHistory.length === 0) {
    return []
  }
  
  return rawHistory.map(item => {
    if (!item) return null
    
    const date = item.date || item.time || ''
    
    if (assetType === 'bond') {
      const yieldValue = item.yield ?? item.close ?? 0
      return {
        date,
        close: yieldValue,
        open: yieldValue,
        high: yieldValue,
        low: yieldValue,
        volume: 0
      }
    }
    
    const close = item.close ?? 0
    const open = item.open ?? close
    const high = item.high ?? Math.max(open, close)
    const low = item.low ?? Math.min(open, close)
    const volume = item.volume ?? item.hold ?? 0
    
    return {
      date,
      close,
      open,
      high,
      low,
      volume
    }
  }).filter(item => item !== null)
}

/**
 * Build API endpoint URL based on symbol type
 * 
 * @param {string} symbol - Raw symbol (e.g., 'sh000001', 'bond10y', 'IF', 'USDCNY')
 * @param {'stock'|'bond'|'futures'|'forex'|'unknown'} assetType - Asset type
 * @param {Object} options - Additional options
 * @param {number} [options.limit=100] - Number of records to fetch
 * @param {string} [options.period='daily'] - Period for futures (daily/1min/5min/etc.)
 * @returns {string} API endpoint URL
 */
export function buildHistoryEndpoint(symbol, assetType, options = {}) {
  const limit = options.limit || 100
  const period = options.period || 'daily'
  
  switch (assetType) {
    case 'stock':
      return `/api/v1/market/history/${symbol}?limit=${limit}`
    
    case 'bond': {
      const tenorMatch = symbol.match(/bond(\d+)y/i)
      const tenor = tenorMatch ? `${tenorMatch[1]}年` : '10年'
      return `/api/v1/bond/history?tenor=${encodeURIComponent(tenor)}&limit=${limit}`
    }
    
    case 'futures': {
      const baseSymbol = symbol.replace(/\d+$/, '').toUpperCase()
      return `/api/v1/futures/index_history?symbol=${baseSymbol}&period=${period}&limit=${limit}`
    }
    
    case 'forex':
      return `/api/v1/forex/history/${symbol.toUpperCase()}?limit=${limit}`
    
    default:
      return `/api/v1/market/history/${symbol}?limit=${limit}`
  }
}

/**
 * Get default timeout for asset type
 * Bond and forex may need longer timeout due to external data sources
 * 
 * @param {'stock'|'bond'|'futures'|'forex'|'unknown'} assetType
 * @returns {number} Timeout in milliseconds
 */
export function getTimeoutForAssetType(assetType) {
  switch (assetType) {
    case 'bond':
      return 25000
    case 'forex':
      return 15000
    case 'futures':
      return 15000
    case 'stock':
    default:
      return 10000
  }
}
