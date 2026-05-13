/**
 * indicators.worker.js — Web Worker for technical indicator calculations
 * Offloads heavy computations from main thread to prevent UI lag
 * Supports Transferable objects for efficient data transfer
 */

// Import indicator calculation functions
import {
  calcMA,
  calcEMA,
  calcMACD,
  calcKDJ,
  calcRSI,
  calcBOLL,
  calcDMI,
  calcOBV,
  calcCCI,
  calcWR,
  calcBIAS,
  calcVWAP,
  calcSAR
} from '../utils/indicators.js'

/**
 * Message handler for indicator calculation requests
 * @param {MessageEvent} e - Worker message event
 */
self.onmessage = (e) => {
  const { type, data, params = {}, requestId } = e.data
  
  try {
    let result
    const startTime = performance.now()
    
    switch (type) {
      // Single indicator calculations
      case 'MA':
        result = calcMA(data.closes, params.period)
        break
        
      case 'EMA':
        result = calcEMA(data.closes, params.period)
        break
        
      case 'MACD':
        result = calcMACD(data.closes, params.fast, params.slow, params.signal)
        break
        
      case 'KDJ':
        result = calcKDJ(data.closes, data.highs, data.lows, params.n)
        break
        
      case 'RSI':
        result = calcRSI(data.closes, params.period)
        break
        
      case 'BOLL':
        result = calcBOLL(data.closes, params.period, params.stdDev)
        break
        
      case 'DMI':
        result = calcDMI(data.highs, data.lows, data.closes, params.period)
        break
        
      case 'OBV':
        result = calcOBV(data.closes, data.volumes)
        break
        
      case 'CCI':
        result = calcCCI(data.closes, data.highs, data.lows, params.period)
        break
        
      case 'WR':
        result = calcWR(data.closes, data.highs, data.lows, params.n)
        break
        
      case 'BIAS':
        result = calcBIAS(data.closes, params.period)
        break
        
      case 'VWAP':
        result = calcVWAP(data.closes, data.volumes)
        break
        
      case 'SAR':
        result = calcSAR(data.highs, data.lows, params.afStep, params.afMax)
        break
        
      // Calculate all common indicators at once (optimized for K-line charts)
      case 'ALL':
        result = calculateAllIndicators(data, params)
        break
        
      // Calculate only main chart indicators (MA, BOLL)
      case 'MAIN':
        result = {
          ma5: calcMA(data.closes, 5),
          ma10: calcMA(data.closes, 10),
          ma20: calcMA(data.closes, 20),
          ma60: params.ma60 ? calcMA(data.closes, 60) : null,
          boll: calcBOLL(data.closes, params.bollPeriod || 20, params.bollStdDev || 2),
        }
        break
        
      // Calculate only sub chart indicators (MACD, KDJ, RSI, etc.)
      case 'SUB':
        result = {
          macd: calcMACD(data.closes, params.macdFast || 12, params.macdSlow || 26, params.macdSignal || 9),
          kdj: calcKDJ(data.closes, data.highs, data.lows, params.kdjN || 9),
          rsi: calcRSI(data.closes, params.rsiPeriod || 14),
          obv: calcOBV(data.closes, data.volumes),
          dmi: calcDMI(data.highs, data.lows, data.closes, params.dmiPeriod || 14),
          cci: calcCCI(data.closes, data.highs, data.lows, params.cciPeriod || 14),
        }
        break
        
      default:
        throw new Error(`Unknown indicator type: ${type}`)
    }
    
    const calcTime = performance.now() - startTime
    
    // Collect Transferable objects (ArrayBuffer from typed arrays)
    const transferables = collectTransferables(result)
    
    // Post result back to main thread
    self.postMessage(
      {
        type,
        requestId,
        result,
        success: true,
        calcTime,
      },
      transferables
    )
  } catch (error) {
    self.postMessage({
      type,
      requestId,
      error: error.message,
      success: false,
    })
  }
}

/**
 * Calculate all common indicators for K-line chart
 * @param {Object} data - { closes, highs, lows, volumes }
 * @param {Object} params - Indicator parameters
 * @returns {Object} All indicator results
 */
function calculateAllIndicators(data, params = {}) {
  const { closes, highs, lows, volumes } = data
  
  return {
    // Main chart indicators
    ma5: calcMA(closes, 5),
    ma10: calcMA(closes, 10),
    ma20: calcMA(closes, 20),
    ma60: params.ma60 ? calcMA(closes, 60) : null,
    boll: calcBOLL(closes, params.bollPeriod || 20, params.bollStdDev || 2),
    
    // Sub chart indicators
    macd: calcMACD(closes, params.macdFast || 12, params.macdSlow || 26, params.macdSignal || 9),
    kdj: calcKDJ(closes, highs, lows, params.kdjN || 9),
    rsi: calcRSI(closes, params.rsiPeriod || 14),
    obv: calcOBV(closes, volumes),
    dmi: calcDMI(highs, lows, closes, params.dmiPeriod || 14),
    cci: calcCCI(closes, highs, lows, params.cciPeriod || 14),
  }
}

/**
 * Collect Transferable objects from result for efficient transfer
 * @param {*} result - Calculation result
 * @returns {Array} Array of Transferable objects
 */
function collectTransferables(result) {
  const transferables = []
  
  if (result == null) return transferables
  
  // Handle array results
  if (Array.isArray(result)) {
    // Check if it's a typed array with buffer
    if (result.buffer && result.buffer instanceof ArrayBuffer) {
      transferables.push(result.buffer)
    }
    return transferables
  }
  
  // Handle object results (multiple indicators)
  if (typeof result === 'object') {
    Object.values(result).forEach(value => {
      if (value == null) return
      
      if (Array.isArray(value)) {
        if (value.buffer && value.buffer instanceof ArrayBuffer) {
          transferables.push(value.buffer)
        }
      } else if (typeof value === 'object') {
        // Nested objects (e.g., { dif, dea, macd })
        Object.values(value).forEach(nestedValue => {
          if (Array.isArray(nestedValue) && nestedValue.buffer && nestedValue.buffer instanceof ArrayBuffer) {
            transferables.push(nestedValue.buffer)
          }
        })
      }
    })
  }
  
  return transferables
}

// Log worker initialization
console.log('[IndicatorWorker] Initialized and ready')
