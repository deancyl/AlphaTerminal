/**
 * useIndicatorWorker.js — Vue composable for Web Worker indicator calculations
 * Provides async interface to offload calculations to background thread
 * Falls back to main thread if Worker fails
 */
import { ref, onUnmounted } from 'vue'
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

// Shared worker instance (singleton pattern)
let worker = null
let workerError = null
const pendingRequests = new Map()
let requestIdCounter = 0

// Worker state tracking
const isWorkerReady = ref(false)
const lastCalcTime = ref(0)
const workerSupported = typeof Worker !== 'undefined'

/**
 * Initialize the Web Worker (lazy initialization)
 */
function initWorker() {
  if (worker || !workerSupported) return
  
  try {
    worker = new Worker(
      new URL('../workers/indicators.worker.js', import.meta.url),
      { type: 'module' }
    )
    
    worker.onmessage = (e) => {
      const { type, requestId, result, success, error, calcTime } = e.data
      const pending = pendingRequests.get(requestId)
      
      if (pending) {
        if (success) {
          pending.resolve(result)
          lastCalcTime.value = calcTime || 0
        } else {
          pending.reject(new Error(error || 'Worker calculation failed'))
        }
        pendingRequests.delete(requestId)
      }
    }
    
    worker.onerror = (e) => {
      console.error('[IndicatorWorker] Worker error:', e.message)
      workerError = e.message
      isWorkerReady.value = false
      
      // Reject all pending requests
      pendingRequests.forEach((pending, id) => {
        pending.reject(new Error(`Worker error: ${e.message}`))
      })
      pendingRequests.clear()
    }
    
    isWorkerReady.value = true
    console.log('[IndicatorWorker] Worker initialized successfully')
  } catch (e) {
    console.warn('[IndicatorWorker] Failed to initialize worker:', e.message)
    workerError = e.message
    isWorkerReady.value = false
  }
}

/**
 * Terminate the worker (cleanup)
 */
function terminateWorker() {
  if (worker) {
    worker.terminate()
    worker = null
    isWorkerReady.value = false
    pendingRequests.clear()
  }
}

/**
 * Send calculation request to worker
 * @param {string} type - Indicator type (MA, MACD, KDJ, etc.)
 * @param {Object} data - Input data { closes, highs, lows, volumes }
 * @param {Object} params - Indicator parameters
 * @param {number} timeout - Request timeout in ms (default: 10000)
 * @returns {Promise} Calculation result
 */
function calculateInWorker(type, data, params = {}, timeout = 10000) {
  return new Promise((resolve, reject) => {
    if (!workerSupported || !isWorkerReady.value) {
      reject(new Error('Worker not available'))
      return
    }
    
    const requestId = ++requestIdCounter
    
    // Set up timeout
    const timeoutId = setTimeout(() => {
      pendingRequests.delete(requestId)
      reject(new Error(`Worker timeout after ${timeout}ms`))
    }, timeout)
    
    pendingRequests.set(requestId, {
      resolve: (result) => {
        clearTimeout(timeoutId)
        resolve(result)
      },
      reject: (error) => {
        clearTimeout(timeoutId)
        reject(error)
      }
    })
    
    worker.postMessage({ type, data, params, requestId })
  })
}

/**
 * Fallback calculation on main thread
 * Used when Worker is unavailable or fails
 */
const fallbackCalculators = {
  MA: (data, params) => calcMA(data.closes, params.period),
  EMA: (data, params) => calcEMA(data.closes, params.period),
  MACD: (data, params) => calcMACD(data.closes, params.fast, params.slow, params.signal),
  KDJ: (data, params) => calcKDJ(data.closes, data.highs, data.lows, params.n),
  RSI: (data, params) => calcRSI(data.closes, params.period),
  BOLL: (data, params) => calcBOLL(data.closes, params.period, params.stdDev),
  DMI: (data, params) => calcDMI(data.highs, data.lows, data.closes, params.period),
  OBV: (data, params) => calcOBV(data.closes, data.volumes),
  CCI: (data, params) => calcCCI(data.closes, data.highs, data.lows, params.period),
  WR: (data, params) => calcWR(data.closes, data.highs, data.lows, params.n),
  BIAS: (data, params) => calcBIAS(data.closes, params.period),
  VWAP: (data, params) => calcVWAP(data.closes, data.volumes),
  SAR: (data, params) => calcSAR(data.highs, data.lows, params.afStep, params.afMax),
  MAIN: (data, params) => ({
    ma5: calcMA(data.closes, 5),
    ma10: calcMA(data.closes, 10),
    ma20: calcMA(data.closes, 20),
    ma60: params.ma60 ? calcMA(data.closes, 60) : null,
    boll: calcBOLL(data.closes, params.bollPeriod || 20, params.bollStdDev || 2),
  }),
  SUB: (data, params) => ({
    macd: calcMACD(data.closes, params.macdFast || 12, params.macdSlow || 26, params.macdSignal || 9),
    kdj: calcKDJ(data.closes, data.highs, data.lows, params.kdjN || 9),
    rsi: calcRSI(data.closes, params.rsiPeriod || 14),
    obv: calcOBV(data.closes, data.volumes),
    dmi: calcDMI(data.highs, data.lows, data.closes, params.dmiPeriod || 14),
    cci: calcCCI(data.closes, data.highs, data.lows, params.cciPeriod || 14),
  }),
  ALL: (data, params) => ({
    ma5: calcMA(data.closes, 5),
    ma10: calcMA(data.closes, 10),
    ma20: calcMA(data.closes, 20),
    ma60: params.ma60 ? calcMA(data.closes, 60) : null,
    boll: calcBOLL(data.closes, params.bollPeriod || 20, params.bollStdDev || 2),
    macd: calcMACD(data.closes, params.macdFast || 12, params.macdSlow || 26, params.macdSignal || 9),
    kdj: calcKDJ(data.closes, data.highs, data.lows, params.kdjN || 9),
    rsi: calcRSI(data.closes, params.rsiPeriod || 14),
    obv: calcOBV(data.closes, data.volumes),
    dmi: calcDMI(data.highs, data.lows, data.closes, params.dmiPeriod || 14),
    cci: calcCCI(data.closes, data.highs, data.lows, params.cciPeriod || 14),
  }),
}

/**
 * Calculate indicator with automatic fallback
 * @param {string} type - Indicator type
 * @param {Object} data - Input data
 * @param {Object} params - Parameters
 * @param {Object} options - { preferWorker: boolean, timeout: number }
 * @returns {Promise} Calculation result
 */
async function calculate(type, data, params = {}, options = {}) {
  const { preferWorker = true, timeout = 10000 } = options
  
  // Try worker first if preferred and available
  if (preferWorker && workerSupported) {
    if (!worker) initWorker()
    
    if (isWorkerReady.value) {
      try {
        return await calculateInWorker(type, data, params, timeout)
      } catch (e) {
        console.warn(`[IndicatorWorker] Worker failed, falling back to main thread:`, e.message)
      }
    }
  }
  
  // Fallback to main thread
  const calculator = fallbackCalculators[type]
  if (!calculator) {
    throw new Error(`Unknown indicator type: ${type}`)
  }
  
  return calculator(data, params)
}

/**
 * Calculate all indicators at once
 * @param {Object} data - { closes, highs, lows, volumes }
 * @param {Object} params - Indicator parameters
 * @param {Object} options - Calculation options
 * @returns {Promise<Object>} All indicator results
 */
async function calculateAll(data, params = {}, options = {}) {
  return calculate('ALL', data, params, options)
}

/**
 * Calculate main chart indicators only (MA, BOLL)
 * @param {Object} data - { closes }
 * @param {Object} params - Indicator parameters
 * @param {Object} options - Calculation options
 * @returns {Promise<Object>} Main chart indicators
 */
async function calculateMain(data, params = {}, options = {}) {
  return calculate('MAIN', data, params, options)
}

/**
 * Calculate sub chart indicators only (MACD, KDJ, RSI, etc.)
 * @param {Object} data - { closes, highs, lows, volumes }
 * @param {Object} params - Indicator parameters
 * @param {Object} options - Calculation options
 * @returns {Promise<Object>} Sub chart indicators
 */
async function calculateSub(data, params = {}, options = {}) {
  return calculate('SUB', data, params, options)
}

/**
 * Check if worker is available and ready
 * @returns {boolean}
 */
function isAvailable() {
  return workerSupported && isWorkerReady.value
}

/**
 * Get worker statistics
 * @returns {Object} { supported, ready, lastCalcTime, pendingCount }
 */
function getStats() {
  return {
    supported: workerSupported,
    ready: isWorkerReady.value,
    lastCalcTime: lastCalcTime.value,
    pendingCount: pendingRequests.size,
    error: workerError,
  }
}

/**
 * Vue composable for indicator calculations
 * @returns {Object} { calculate, calculateAll, calculateMain, calculateSub, isReady, isAvailable, getStats }
 */
export function useIndicatorWorker() {
  // Initialize worker lazily on first use
  if (workerSupported && !worker) {
    initWorker()
  }
  
  // Clean up on component unmount (but don't terminate shared worker)
  onUnmounted(() => {
    // Worker is shared, don't terminate
  })
  
  return {
    // Calculation methods
    calculate,
    calculateAll,
    calculateMain,
    calculateSub,
    
    // State
    isReady: isWorkerReady,
    isAvailable,
    
    // Stats
    getStats,
    lastCalcTime,
  }
}

// Export singleton methods for non-composable usage
export const indicatorWorker = {
  calculate,
  calculateAll,
  calculateMain,
  calculateSub,
  isAvailable,
  getStats,
  terminate: terminateWorker,
}
