import { describe, it, expect } from 'vitest'
import { calcMA, calcEMA, calcMACD, calcKDJ, calcRSI, calcBOLL, calcDMI, calcWR, calcCCI, calcBIAS, calcVWAP, calcOBV, calcSAR } from '../../src/utils/indicators.js'

/**
 * Helper: Check if value is valid number (not NaN, not Infinity)
 */
function isValidNumber(v) {
  return typeof v === 'number' && !isNaN(v) && isFinite(v)
}

/**
 * Helper: Check if all values in array are valid numbers (null allowed)
 */
function allValidNumbers(arr) {
  return arr.every(v => v === null || isValidNumber(v))
}

/**
 * Helper: Check if object values are all valid number arrays
 */
function allValidInObject(obj) {
  return Object.values(obj).every(arr => allValidNumbers(arr))
}

describe('Indicator edge cases', () => {
  describe('calcMA', () => {
    it('should handle empty array', () => {
      const result = calcMA([], 5)
      expect(result).toEqual([])
    })

    it('should handle single value', () => {
      const result = calcMA([100], 5)
      expect(result).toEqual([null])
    })

    it('should handle all zeros', () => {
      const result = calcMA([0, 0, 0, 0, 0], 5)
      expect(result).toEqual([null, null, null, null, 0])
      expect(allValidNumbers(result)).toBe(true)
    })

    it('should handle array shorter than period', () => {
      const result = calcMA([10, 20, 30], 5)
      expect(result).toEqual([null, null, null])
    })

    it('should handle normal case', () => {
      const result = calcMA([10, 20, 30, 40, 50], 3)
      expect(result[0]).toBe(null)
      expect(result[1]).toBe(null)
      expect(result[2]).toBe(20)  // (10+20+30)/3
      expect(result[3]).toBe(30)  // (20+30+40)/3
      expect(result[4]).toBe(40)  // (30+40+50)/3
    })
  })

  describe('calcEMA', () => {
    it('should handle empty array', () => {
      const result = calcEMA([], 5)
      expect(result).toEqual([])
    })

    it('should handle single value', () => {
      const result = calcEMA([100], 5)
      expect(result).toEqual([100])
      expect(allValidNumbers(result)).toBe(true)
    })

    it('should handle all zeros', () => {
      const result = calcEMA([0, 0, 0, 0, 0], 5)
      expect(allValidNumbers(result)).toBe(true)
      expect(result.every(v => v === 0)).toBe(true)
    })

    it('should handle constant prices', () => {
      const result = calcEMA([50, 50, 50, 50, 50], 5)
      expect(allValidNumbers(result)).toBe(true)
      expect(result.every(v => v === 50)).toBe(true)
    })
  })

  describe('calcMACD', () => {
    it('should handle constant prices (no volatility)', () => {
      const closes = Array(30).fill(100)
      const result = calcMACD(closes)
      
      expect(allValidInObject(result)).toBe(true)
      // With constant prices, DIF should be 0
      expect(result.dif.every(v => v === 0)).toBe(true)
      expect(result.dea.every(v => v === 0)).toBe(true)
      expect(result.macd.every(v => v === 0)).toBe(true)
    })

    it('should handle all zeros', () => {
      const closes = Array(30).fill(0)
      const result = calcMACD(closes)
      
      expect(allValidInObject(result)).toBe(true)
      // No NaN or Infinity
      expect(result.dif.every(v => isValidNumber(v))).toBe(true)
      expect(result.dea.every(v => isValidNumber(v))).toBe(true)
      expect(result.macd.every(v => isValidNumber(v))).toBe(true)
    })

    it('should not return NaN with extreme values', () => {
      const closes = [1e10, 1e10, 1e10, 1e10, 1e10, 1e10, 1e10, 1e10, 1e10, 1e10,
                      1e10, 1e10, 1e10, 1e10, 1e10, 1e10, 1e10, 1e10, 1e10, 1e10,
                      1e10, 1e10, 1e10, 1e10, 1e10, 1e10, 1e10, 1e10, 1e10, 1e10]
      const result = calcMACD(closes)
      
      expect(allValidInObject(result)).toBe(true)
    })

    it('should handle small array', () => {
      const closes = [10, 20, 30]
      const result = calcMACD(closes)
      
      expect(allValidInObject(result)).toBe(true)
      expect(result.dif.length).toBe(3)
      expect(result.dea.length).toBe(3)
      expect(result.macd.length).toBe(3)
    })
  })

  describe('calcKDJ', () => {
    it('should handle constant prices (high === low)', () => {
      // All candles have same high/low/close
      const closes = Array(15).fill(100)
      const highs = Array(15).fill(100)
      const lows = Array(15).fill(100)
      
      const result = calcKDJ(closes, highs, lows, 9)
      
      expect(allValidInObject(result)).toBe(true)
      // No NaN or Infinity
      expect(result.k.every(v => v === null || isValidNumber(v))).toBe(true)
      expect(result.d.every(v => v === null || isValidNumber(v))).toBe(true)
      expect(result.j.every(v => v === null || isValidNumber(v))).toBe(true)
    })

    it('should handle single candle', () => {
      const result = calcKDJ([100], [105], [95], 9)
      
      expect(allValidInObject(result)).toBe(true)
      expect(result.k).toEqual([null])
      expect(result.d).toEqual([null])
      expect(result.j).toEqual([null])
    })

    it('should not return NaN or Infinity with zero range', () => {
      // RSV calculation: (close - low) / (high - low) * 100
      // When high === low, this would be division by zero
      const closes = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
      const highs = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
      const lows = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
      
      const result = calcKDJ(closes, highs, lows, 9)
      
      expect(allValidInObject(result)).toBe(true)
      // Should use safeDivide default value
      expect(result.k.every(v => v === null || isValidNumber(v))).toBe(true)
    })

    it('should handle normal case', () => {
      const closes = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109]
      const highs = [105, 107, 106, 108, 110, 109, 111, 113, 112, 114]
      const lows = [95, 97, 96, 98, 100, 99, 101, 103, 102, 104]
      
      const result = calcKDJ(closes, highs, lows, 9)
      
      expect(allValidInObject(result)).toBe(true)
      expect(result.k.length).toBe(10)
      expect(result.d.length).toBe(10)
      expect(result.j.length).toBe(10)
    })
  })

  describe('calcRSI', () => {
    it('should handle constant prices', () => {
      const closes = Array(20).fill(100)
      const result = calcRSI(closes, 14)
      
      expect(allValidNumbers(result)).toBe(true)
      // With no price changes, RSI should be 100 (no losses)
      expect(result[result.length - 1]).toBe(100)
    })

    it('should handle all positive changes', () => {
      // Prices always go up
      const closes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
                      110, 111, 112, 113, 114, 115, 116, 117, 118, 119]
      const result = calcRSI(closes, 14)
      
      expect(allValidNumbers(result)).toBe(true)
      // RSI should be 100 (no losses)
      expect(result[result.length - 1]).toBe(100)
    })

    it('should handle all negative changes', () => {
      // Prices always go down
      const closes = [100, 99, 98, 97, 96, 95, 94, 93, 92, 91,
                      90, 89, 88, 87, 86, 85, 84, 83, 82, 81]
      const result = calcRSI(closes, 14)
      
      expect(allValidNumbers(result)).toBe(true)
      // RSI should be 0 (no gains)
      expect(result[result.length - 1]).toBe(0)
    })

    it('should not return NaN with short array', () => {
      const closes = [100, 101, 102]
      const result = calcRSI(closes, 14)
      
      expect(allValidNumbers(result)).toBe(true)
      expect(result.every(v => v === null)).toBe(true)
    })

    it('should handle array with exactly period+1 elements', () => {
      const closes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
                      110, 111, 112, 113, 114]
      const result = calcRSI(closes, 14)
      
      expect(allValidNumbers(result)).toBe(true)
      expect(result.filter(v => v !== null).length).toBe(1)
    })
  })

  describe('calcBOLL', () => {
    it('should handle zero stdDev (constant prices)', () => {
      const closes = Array(25).fill(100)
      const result = calcBOLL(closes, 20, 2)
      
      expect(allValidInObject(result)).toBe(true)
      // Upper and lower should equal mid when stdDev is 0
      const lastIdx = closes.length - 1
      expect(result.mid[lastIdx]).toBe(100)
      expect(result.upper[lastIdx]).toBe(100)
      expect(result.lower[lastIdx]).toBe(100)
    })

    it('should handle constant prices', () => {
      const closes = [50, 50, 50, 50, 50, 50, 50, 50, 50, 50,
                      50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50]
      const result = calcBOLL(closes, 20, 2)
      
      expect(allValidInObject(result)).toBe(true)
      // All values should be 50
      expect(result.mid.filter(v => v !== null).every(v => v === 50)).toBe(true)
      expect(result.upper.filter(v => v !== null).every(v => v === 50)).toBe(true)
      expect(result.lower.filter(v => v !== null).every(v => v === 50)).toBe(true)
    })

    it('should not return NaN with all zeros', () => {
      const closes = Array(25).fill(0)
      const result = calcBOLL(closes, 20, 2)
      
      expect(allValidInObject(result)).toBe(true)
    })

    it('should handle short array', () => {
      const closes = [10, 20, 30]
      const result = calcBOLL(closes, 20, 2)
      
      expect(allValidInObject(result)).toBe(true)
      expect(result.mid.every(v => v === null)).toBe(true)
    })

    it('should handle normal case', () => {
      const closes = Array(25).fill(0).map((_, i) => 100 + Math.sin(i) * 10)
      const result = calcBOLL(closes, 20, 2)
      
      expect(allValidInObject(result)).toBe(true)
      // Upper > Mid > Lower
      const lastIdx = closes.length - 1
      expect(result.upper[lastIdx]).toBeGreaterThan(result.mid[lastIdx])
      expect(result.mid[lastIdx]).toBeGreaterThan(result.lower[lastIdx])
    })
  })

  describe('calcDMI', () => {
    it('should handle constant prices', () => {
      const closes = Array(30).fill(100)
      const highs = Array(30).fill(105)
      const lows = Array(30).fill(95)
      
      const result = calcDMI(highs, lows, closes, 14)
      
      expect(allValidInObject(result)).toBe(true)
      // No NaN or Infinity
      expect(result.pdi.every(v => v === null || isValidNumber(v))).toBe(true)
      expect(result.mdi.every(v => v === null || isValidNumber(v))).toBe(true)
      expect(result.adx.every(v => v === null || isValidNumber(v))).toBe(true)
    })

    it('should not return NaN or Infinity with zero TR', () => {
      // All candles are identical (no movement)
      const closes = Array(30).fill(100)
      const highs = Array(30).fill(100)
      const lows = Array(30).fill(100)
      
      const result = calcDMI(highs, lows, closes, 14)
      
      expect(allValidInObject(result)).toBe(true)
    })

    it('should handle short array', () => {
      const result = calcDMI([105], [95], [100], 14)
      
      expect(allValidInObject(result)).toBe(true)
    })

    it('should handle normal case', () => {
      const closes = Array(30).fill(0).map((_, i) => 100 + Math.sin(i * 0.5) * 10)
      const highs = closes.map((v, i) => v + 5)
      const lows = closes.map((v, i) => v - 5)
      
      const result = calcDMI(highs, lows, closes, 14)
      
      expect(allValidInObject(result)).toBe(true)
      // PDI and MDI should be 0-100
      const validPdi = result.pdi.filter(v => v !== null)
      const validMdi = result.mdi.filter(v => v !== null)
      expect(validPdi.every(v => v >= 0 && v <= 100)).toBe(true)
      expect(validMdi.every(v => v >= 0 && v <= 100)).toBe(true)
    })
  })

  describe('calcWR', () => {
    it('should handle constant prices', () => {
      const closes = Array(20).fill(100)
      const highs = Array(20).fill(105)
      const lows = Array(20).fill(95)
      
      const result = calcWR(closes, highs, lows, 14)
      
      expect(allValidNumbers(result)).toBe(true)
    })

    it('should handle zero range (high === low)', () => {
      const closes = Array(20).fill(100)
      const highs = Array(20).fill(100)
      const lows = Array(20).fill(100)
      
      const result = calcWR(closes, highs, lows, 14)
      
      expect(allValidNumbers(result)).toBe(true)
      // Should use safeDivide default value (0)
      expect(result.filter(v => v !== null).every(v => v === 0)).toBe(true)
    })

    it('should handle short array', () => {
      const result = calcWR([100], [105], [95], 14)
      
      expect(allValidNumbers(result)).toBe(true)
      expect(result).toEqual([null])
    })
  })

  describe('calcCCI', () => {
    it('should handle constant prices', () => {
      const closes = Array(20).fill(100)
      const highs = Array(20).fill(105)
      const lows = Array(20).fill(95)
      
      const result = calcCCI(closes, highs, lows, 14)
      
      expect(allValidNumbers(result)).toBe(true)
    })

    it('should handle zero MAD', () => {
      // All prices identical
      const closes = Array(20).fill(100)
      const highs = Array(20).fill(100)
      const lows = Array(20).fill(100)
      
      const result = calcCCI(closes, highs, lows, 14)
      
      expect(allValidNumbers(result)).toBe(true)
      // Should return 0 when MAD is 0
      expect(result.filter(v => v !== null).every(v => v === 0)).toBe(true)
    })

    it('should handle short array', () => {
      const result = calcCCI([100], [105], [95], 14)
      
      expect(allValidNumbers(result)).toBe(true)
      expect(result).toEqual([null])
    })
  })

  describe('calcBIAS', () => {
    it('should handle constant prices', () => {
      const closes = Array(25).fill(100)
      const result = calcBIAS(closes, 20)
      
      expect(allValidNumbers(result)).toBe(true)
      // BIAS should be 0 when price equals MA
      expect(result.filter(v => v !== null).every(v => v === 0)).toBe(true)
    })

    it('should handle all zeros', () => {
      const closes = Array(25).fill(0)
      const result = calcBIAS(closes, 20)
      
      expect(allValidNumbers(result)).toBe(true)
    })

    it('should handle short array', () => {
      const result = calcBIAS([100, 101, 102], 20)
      
      expect(allValidNumbers(result)).toBe(true)
      expect(result.every(v => v === null)).toBe(true)
    })
  })

  describe('calcVWAP', () => {
    it('should handle empty arrays', () => {
      const result = calcVWAP([], [])
      expect(result).toEqual([])
    })

    it('should handle zero volumes', () => {
      const closes = [100, 101, 102]
      const volumes = [0, 0, 0]
      const result = calcVWAP(closes, volumes)
      
      expect(allValidNumbers(result)).toBe(true)
      // Should return null when volume is 0
      expect(result.every(v => v === null)).toBe(true)
    })

    it('should handle normal case', () => {
      const closes = [100, 101, 102]
      const volumes = [1000, 2000, 3000]
      const result = calcVWAP(closes, volumes)
      
      expect(allValidNumbers(result)).toBe(true)
      // VWAP = cumulative PV / cumulative Volume
      // Day 1: 100*1000 / 1000 = 100
      // Day 2: (100*1000 + 101*2000) / 3000 = 100.67
      // Day 3: (100*1000 + 101*2000 + 102*3000) / 6000 = 101.33
      expect(result[0]).toBe(100)
      expect(result[1]).toBeCloseTo(100.67, 1)
      expect(result[2]).toBeCloseTo(101.33, 1)
    })
  })

  describe('calcOBV', () => {
    it('should handle empty array', () => {
      const result = calcOBV([], [])
      expect(result).toEqual([])
    })

    it('should handle constant prices', () => {
      const closes = [100, 100, 100, 100]
      const volumes = [1000, 1000, 1000, 1000]
      const result = calcOBV(closes, volumes)
      
      expect(allValidNumbers(result)).toBe(true)
      // OBV should stay constant when prices don't change
      expect(result[0]).toBe(1000)
      expect(result[1]).toBe(1000)
      expect(result[2]).toBe(1000)
      expect(result[3]).toBe(1000)
    })

    it('should handle normal case', () => {
      const closes = [100, 101, 100, 102]
      const volumes = [1000, 1000, 1000, 1000]
      const result = calcOBV(closes, volumes)
      
      expect(allValidNumbers(result)).toBe(true)
      expect(result[0]).toBe(1000)
      expect(result[1]).toBe(2000)  // Price up, add volume
      expect(result[2]).toBe(1000)  // Price down, subtract volume
      expect(result[3]).toBe(2000)  // Price up, add volume
    })
  })

  describe('calcSAR', () => {
    it('should handle empty array', () => {
      const result = calcSAR([], [])
      expect(result).toEqual([])
    })

    it('should handle single value', () => {
      const result = calcSAR([100], [95])
      expect(result).toEqual([null])
    })

    it('should handle constant prices', () => {
      const highs = Array(20).fill(100)
      const lows = Array(20).fill(95)
      const result = calcSAR(highs, lows)
      
      expect(allValidNumbers(result)).toBe(true)
    })

    it('should handle normal case', () => {
      const highs = [105, 107, 106, 108, 110, 109, 111, 113, 112, 114]
      const lows = [95, 97, 96, 98, 100, 99, 101, 103, 102, 104]
      const result = calcSAR(highs, lows)
      
      expect(allValidNumbers(result)).toBe(true)
      expect(result.length).toBe(10)
    })
  })

  describe('Combined edge cases', () => {
    it('should handle all indicators with empty data', () => {
      expect(calcMA([], 5)).toEqual([])
      expect(calcEMA([], 5)).toEqual([])
      expect(allValidInObject(calcMACD([]))).toBe(true)
      expect(allValidInObject(calcKDJ([], [], []))).toBe(true)
      expect(calcRSI([], 14)).toEqual([])
      expect(allValidInObject(calcBOLL([]))).toBe(true)
      expect(allValidInObject(calcDMI([], [], []))).toBe(true)
    })

    it('should handle all indicators with single value', () => {
      const single = [100]
      const singleH = [105]
      const singleL = [95]
      
      expect(calcMA(single, 5)).toEqual([null])
      expect(calcEMA(single, 5)).toEqual([100])
      expect(allValidInObject(calcMACD(single))).toBe(true)
      expect(allValidInObject(calcKDJ(single, singleH, singleL))).toBe(true)
      expect(calcRSI(single, 14)).toEqual([null])
      expect(allValidInObject(calcBOLL(single))).toBe(true)
      expect(allValidInObject(calcDMI(singleH, singleL, single))).toBe(true)
    })

    it('should handle all indicators with constant prices', () => {
      const constant = Array(30).fill(100)
      const constantH = Array(30).fill(105)
      const constantL = Array(30).fill(95)
      
      // All should return valid numbers (no NaN/Infinity)
      expect(allValidNumbers(calcMA(constant, 5))).toBe(true)
      expect(allValidNumbers(calcEMA(constant, 5))).toBe(true)
      expect(allValidInObject(calcMACD(constant))).toBe(true)
      expect(allValidInObject(calcKDJ(constant, constantH, constantL))).toBe(true)
      expect(allValidNumbers(calcRSI(constant, 14))).toBe(true)
      expect(allValidInObject(calcBOLL(constant))).toBe(true)
      expect(allValidInObject(calcDMI(constantH, constantL, constant))).toBe(true)
    })

    it('should handle all indicators with extreme values', () => {
      const extreme = Array(30).fill(1e10)
      const extremeH = Array(30).fill(1e10 + 5)
      const extremeL = Array(30).fill(1e10 - 5)
      
      // All should return valid numbers (no NaN/Infinity)
      expect(allValidNumbers(calcMA(extreme, 5))).toBe(true)
      expect(allValidNumbers(calcEMA(extreme, 5))).toBe(true)
      expect(allValidInObject(calcMACD(extreme))).toBe(true)
      expect(allValidInObject(calcKDJ(extreme, extremeH, extremeL))).toBe(true)
      expect(allValidNumbers(calcRSI(extreme, 14))).toBe(true)
      expect(allValidInObject(calcBOLL(extreme))).toBe(true)
      expect(allValidInObject(calcDMI(extremeH, extremeL, extreme))).toBe(true)
    })
  })
})
