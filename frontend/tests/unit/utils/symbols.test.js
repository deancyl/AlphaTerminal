import { describe, it, expect } from 'vitest'
import {
  normalizeSymbol,
  isAShare,
  isIntradayPeriod,
  extractCode,
  formatDate,
  buildXAxisLabels,
} from '../../../src/utils/symbols.js'

describe('normalizeSymbol', () => {
  it('should normalize A-share numeric codes', () => {
    expect(normalizeSymbol('000001')).toBe('sz000001')
    expect(normalizeSymbol('600519')).toBe('sh600519')
    expect(normalizeSymbol('900001')).toBe('sh900001')
  })

  it('should keep already prefixed symbols', () => {
    expect(normalizeSymbol('sh000001')).toBe('sh000001')
    expect(normalizeSymbol('sz000001')).toBe('sz000001')
    expect(normalizeSymbol('usAAPL')).toBe('usaapl')
  })

  it('should normalize US symbols', () => {
    expect(normalizeSymbol('NDX')).toBe('usNDX')
    expect(normalizeSymbol('SPX')).toBe('usSPX')
    expect(normalizeSymbol('AAPL')).toBe('usAAPL')
  })

  it('should normalize HK symbols', () => {
    expect(normalizeSymbol('HSI')).toBe('hkHSI')
  })

  it('should normalize JP symbols', () => {
    expect(normalizeSymbol('N225')).toBe('jpN225')
  })

  it('should normalize macro symbols', () => {
    expect(normalizeSymbol('GOLD')).toBe('GOLD')
    expect(normalizeSymbol('VIX')).toBe('VIX')
    expect(normalizeSymbol('CNHUSD')).toBe('CNHUSD')
  })

  it('should handle edge cases', () => {
    expect(normalizeSymbol('')).toBe('')
    expect(normalizeSymbol('  ')).toBe('')
  })
})

describe('isAShare', () => {
  it('should return true for A-share symbols', () => {
    expect(isAShare('000001')).toBe(true)
    expect(isAShare('600519')).toBe(true)
    expect(isAShare('sh000001')).toBe(true)
    expect(isAShare('sz000001')).toBe(true)
  })

  it('should return false for non-A-share symbols', () => {
    expect(isAShare('NDX')).toBe(false)
    expect(isAShare('HSI')).toBe(false)
    expect(isAShare('AAPL')).toBe(false)
  })
})

describe('isIntradayPeriod', () => {
  it('should return true for intraday periods', () => {
    expect(isIntradayPeriod('minutely')).toBe(true)
    expect(isIntradayPeriod('1min')).toBe(true)
    expect(isIntradayPeriod('5min')).toBe(true)
    expect(isIntradayPeriod('15min')).toBe(true)
    expect(isIntradayPeriod('30min')).toBe(true)
    expect(isIntradayPeriod('60min')).toBe(true)
  })

  it('should return false for non-intraday periods', () => {
    expect(isIntradayPeriod('daily')).toBe(false)
    expect(isIntradayPeriod('weekly')).toBe(false)
    expect(isIntradayPeriod('monthly')).toBe(false)
  })
})

describe('extractCode', () => {
  it('should extract code from prefixed symbols', () => {
    expect(extractCode('sh000001')).toBe('000001')
    expect(extractCode('sz000001')).toBe('000001')
    expect(extractCode('usAAPL')).toBe('AAPL')
    expect(extractCode('hkHSI')).toBe('HSI')
  })

  it('should return uppercase for plain codes', () => {
    expect(extractCode('000001')).toBe('000001')
    expect(extractCode('aapl')).toBe('AAPL')
  })
})

describe('formatDate', () => {
  it('should format minute data', () => {
    expect(formatDate('2024-01-15 10:30:00', 'minutely')).toBe('2024-01-15 10:30')
    expect(formatDate('2024-01-15 10:30:00', '5min')).toBe('2024-01-15 10:30')
  })

  it('should format daily data', () => {
    expect(formatDate('2024-01-15', 'daily')).toBe('2024-01-15')
    // When date has time component and period is daily, it should still return date part
    expect(formatDate('2024-01-15 10:30:00', 'daily')).toBe('2024-01-15 10:30')
  })

  it('should handle empty input', () => {
    expect(formatDate('', 'daily')).toBe('')
    expect(formatDate(null, 'daily')).toBe('')
  })
})

describe('buildXAxisLabels', () => {
  it('should build labels for minute data', () => {
    const hist = [
      { date: '2024-01-15 10:30:00' },
      { date: '2024-01-15 10:31:00' },
    ]
    const labels = buildXAxisLabels(hist, 'minutely')
    expect(labels).toEqual(['2024-01-15 10:30', '2024-01-15 10:31'])
  })

  it('should build labels for daily data', () => {
    const hist = [
      { date: '2024-01-15' },
      { date: '2024-01-16' },
    ]
    const labels = buildXAxisLabels(hist, 'daily')
    expect(labels).toEqual(['2024-01-15', '2024-01-16'])
  })

  it('should handle empty history', () => {
    expect(buildXAxisLabels([], 'daily')).toEqual([])
  })
})