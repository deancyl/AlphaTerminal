/**
 * Price Source Tracker - Unified price data source with priority chain
 * 
 * Priority: WS tick > latestCandle > realtimeData > snapshotData
 * 
 * This utility ensures consistent price display and helps users understand
 * which data source is currently active.
 */

/**
 * Get unified price from multiple sources with priority chain
 * @param {Object} sources - Available price sources
 * @param {Object} sources.wsTick - WebSocket tick data { price, timestamp }
 * @param {Object} sources.latestCandle - Latest K-line candle { close, change_pct, ... }
 * @param {Object} sources.realtimeData - API quote data { price, change_pct, ... }
 * @param {Object} sources.snapshotData - Crosshair historical snapshot { price, ... }
 * @returns {{ price: number|null, source: string|null, sourceKey: string|null }}
 */
export function getUnifiedPrice(sources) {
  const { wsTick, latestCandle, realtimeData, snapshotData } = sources
  
  // Priority 1: WebSocket tick (most real-time)
  if (wsTick?.price != null && wsTick.price > 0) {
    return { 
      price: wsTick.price, 
      source: '实时', 
      sourceKey: 'ws',
      change: wsTick.change ?? null,
      changePct: wsTick.change_pct ?? null
    }
  }
  
  // Priority 2: Latest K-line candle (from chart, very reliable)
  if (latestCandle?.close != null && latestCandle.close > 0) {
    return { 
      price: latestCandle.close, 
      source: 'K线', 
      sourceKey: 'candle',
      change: latestCandle.change ?? null,
      changePct: latestCandle.change_pct ?? null
    }
  }
  
  // Priority 3: Realtime API data
  if (realtimeData?.price != null && realtimeData.price > 0) {
    return { 
      price: realtimeData.price, 
      source: 'API', 
      sourceKey: 'api',
      change: realtimeData.change ?? null,
      changePct: realtimeData.change_pct ?? null
    }
  }
  
  // Priority 4: Crosshair snapshot (historical)
  if (snapshotData?.price != null && snapshotData.price > 0) {
    return { 
      price: snapshotData.price, 
      source: '快照', 
      sourceKey: 'snapshot',
      change: snapshotData.change ?? null,
      changePct: snapshotData.change_pct ?? null
    }
  }
  
  // No valid price source
  return { 
    price: null, 
    source: null, 
    sourceKey: null,
    change: null,
    changePct: null
  }
}

/**
 * Check price consistency across multiple sources
 * @param {Object} sources - Available price sources
 * @returns {{ consistent: boolean, maxDiff: number, pctDiff: number, sources: Array }}
 */
export function getPriceConsistency(sources) {
  const { wsTick, latestCandle, realtimeData } = sources
  
  const prices = []
  
  if (wsTick?.price != null && wsTick.price > 0) {
    prices.push({ val: wsTick.price, src: 'ws', label: '实时' })
  }
  if (latestCandle?.close != null && latestCandle.close > 0) {
    prices.push({ val: latestCandle.close, src: 'candle', label: 'K线' })
  }
  if (realtimeData?.price != null && realtimeData.price > 0) {
    prices.push({ val: realtimeData.price, src: 'api', label: 'API' })
  }
  
  // Need at least 2 sources to compare
  if (prices.length < 2) {
    return { 
      consistent: true, 
      maxDiff: 0, 
      pctDiff: 0, 
      sources: prices,
      message: '数据源单一'
    }
  }
  
  const maxPrice = Math.max(...prices.map(p => p.val))
  const minPrice = Math.min(...prices.map(p => p.val))
  const avgPrice = prices.reduce((s, p) => s + p.val, 0) / prices.length
  
  const maxDiff = maxPrice - minPrice
  const pctDiff = avgPrice > 0 ? (maxDiff / avgPrice) * 100 : 0
  
  // Consider consistent if difference < 0.1%
  const consistent = pctDiff < 0.1
  
  return {
    consistent,
    maxDiff,
    pctDiff,
    sources: prices,
    message: consistent 
      ? '数据一致' 
      : `数据差异 ${pctDiff.toFixed(2)}%`
  }
}

/**
 * Get source indicator style based on source key
 * @param {string} sourceKey - Source key ('ws', 'candle', 'api', 'snapshot')
 * @returns {{ color: string, bgColor: string, icon: string }}
 */
export function getSourceStyle(sourceKey) {
  const styles = {
    ws: { 
      color: 'text-green-400', 
      bgColor: 'bg-green-400/10', 
      icon: '●',
      pulse: true
    },
    candle: { 
      color: 'text-blue-400', 
      bgColor: 'bg-blue-400/10', 
      icon: '▲',
      pulse: false
    },
    api: { 
      color: 'text-yellow-400', 
      bgColor: 'bg-yellow-400/10', 
      icon: '◆',
      pulse: false
    },
    snapshot: { 
      color: 'text-purple-400', 
      bgColor: 'bg-purple-400/10', 
      icon: '📌',
      pulse: false
    }
  }
  
  return styles[sourceKey] || { 
    color: 'text-gray-400', 
    bgColor: 'bg-gray-400/10', 
    icon: '?',
    pulse: false
  }
}

/**
 * Format price with source indicator
 * @param {number} price - Price value
 * @param {string} source - Source label
 * @param {number} decimals - Decimal places (default 3)
 * @returns {string}
 */
export function formatPriceWithSource(price, source, decimals = 3) {
  if (price == null || price <= 0) return '--'
  const formatted = price.toFixed(decimals)
  return source ? `${formatted} (${source})` : formatted
}
