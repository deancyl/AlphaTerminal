import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  extractData,
  normalizeFields,
  normalizeList,
  FIELD_MAP,
} from '../../../src/utils/api.js'

describe('extractData', () => {
  it('should extract data from new format response', () => {
    const response = { code: 0, data: { items: [1, 2, 3] }, message: 'success' }
    expect(extractData(response)).toEqual({ items: [1, 2, 3] })
  })

  it('should return old format response directly', () => {
    const response = { items: [1, 2, 3], total: 100 }
    expect(extractData(response)).toEqual({ items: [1, 2, 3], total: 100 })
  })

  it('should handle null response', () => {
    expect(extractData(null)).toBe(null)
  })

  it('should handle undefined response', () => {
    expect(extractData(undefined)).toBe(undefined)
  })

  it('should handle response without code', () => {
    const response = { data: { items: [] } }
    expect(extractData(response)).toEqual({ data: { items: [] } })
  })
})

describe('normalizeFields', () => {
  it('should normalize price fields', () => {
    const raw = { trade: 100.5 }
    const result = normalizeFields(raw)
    expect(result.price).toBe(100.5)
  })

  it('should normalize change fields', () => {
    const raw = { change: 5.2, change_pct: 2.5 }
    const result = normalizeFields(raw)
    expect(result.chg).toBe(5.2)
    expect(result.chg_pct).toBe(2.5)
  })

  it('should normalize volume fields', () => {
    const raw = { vol: 1000000 }
    const result = normalizeFields(raw)
    expect(result.volume).toBe(1000000)
  })

  it('should keep existing standard fields', () => {
    const raw = { price: 100, volume: 1000 }
    const result = normalizeFields(raw)
    expect(result.price).toBe(100)
    expect(result.volume).toBe(1000)
  })

  it('should handle empty object', () => {
    expect(normalizeFields({})).toEqual({})
  })

  it('should handle null input', () => {
    expect(normalizeFields(null)).toEqual({})
  })

  it('should handle undefined input', () => {
    expect(normalizeFields(undefined)).toEqual({})
  })
})

describe('normalizeList', () => {
  it('should normalize array of objects', () => {
    const list = [
      { trade: 100, change: 5 },
      { trade: 200, change: 10 },
    ]
    const result = normalizeList(list)
    expect(result).toHaveLength(2)
    expect(result[0].price).toBe(100)
    expect(result[0].chg).toBe(5)
    expect(result[1].price).toBe(200)
    expect(result[1].chg).toBe(10)
  })

  it('should return empty array for non-array input', () => {
    expect(normalizeList(null)).toEqual([])
    expect(normalizeList(undefined)).toEqual([])
    expect(normalizeList('string')).toEqual([])
    expect(normalizeList(123)).toEqual([])
  })

  it('should handle empty array', () => {
    expect(normalizeList([])).toEqual([])
  })
})

describe('FIELD_MAP', () => {
  it('should have all required field mappings', () => {
    expect(FIELD_MAP).toHaveProperty('price')
    expect(FIELD_MAP).toHaveProperty('chg')
    expect(FIELD_MAP).toHaveProperty('chg_pct')
    expect(FIELD_MAP).toHaveProperty('volume')
    expect(FIELD_MAP).toHaveProperty('amount')
    expect(FIELD_MAP).toHaveProperty('turnover')
    expect(FIELD_MAP).toHaveProperty('symbol')
    expect(FIELD_MAP).toHaveProperty('name')
  })

  it('should have arrays as values', () => {
    Object.values(FIELD_MAP).forEach(value => {
      expect(Array.isArray(value)).toBe(true)
    })
  })
})