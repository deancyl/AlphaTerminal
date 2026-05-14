import { describe, it, expect } from 'vitest'
import { safeDivide, safePercent, safeAverage } from '../../src/utils/safeMath.js'

describe('safeMath utilities', () => {
  describe('safeDivide', () => {
    it('returns correct result for valid inputs', () => {
      expect(safeDivide(100, 10, 0)).toBe(10)
      expect(safeDivide(50, 2, 0)).toBe(25)
      expect(safeDivide(1, 3, 0)).toBeCloseTo(0.333, 2)
    })

    it('returns default value when divisor is zero', () => {
      expect(safeDivide(100, 0, 0)).toBe(0)
      expect(safeDivide(100, 0, null)).toBe(null)
      expect(safeDivide(100, 0, -1)).toBe(-1)
    })

    it('returns default value when divisor is null or undefined', () => {
      expect(safeDivide(100, null, 0)).toBe(0)
      expect(safeDivide(100, undefined, 0)).toBe(0)
    })

    it('returns default value when numerator is null or undefined', () => {
      expect(safeDivide(null, 10, 0)).toBe(0)
      expect(safeDivide(undefined, 10, 0)).toBe(0)
    })

    it('handles NaN inputs', () => {
      expect(safeDivide(NaN, 10, 0)).toBe(0)
      expect(safeDivide(100, NaN, 0)).toBe(0)
    })

    it('handles Infinity inputs', () => {
      expect(safeDivide(Infinity, 10, 0)).toBe(0)
      expect(safeDivide(100, Infinity, 0)).toBe(0)
    })
  })

  describe('safePercent', () => {
    it('returns correct percentage for valid inputs', () => {
      expect(safePercent(50, 100, 0)).toBe(50)
      expect(safePercent(25, 100, 0)).toBe(25)
      expect(safePercent(1, 3, 0)).toBeCloseTo(33.33, 1)
    })

    it('returns default value when total is zero', () => {
      expect(safePercent(50, 0, 0)).toBe(0)
      expect(safePercent(50, 0, null)).toBe(null)
    })

    it('returns default value for null/undefined inputs', () => {
      expect(safePercent(null, 100, 0)).toBe(0)
      expect(safePercent(50, null, 0)).toBe(0)
    })
  })

  describe('safeAverage', () => {
    it('returns correct average for valid array', () => {
      expect(safeAverage([1, 2, 3, 4, 5], 0)).toBe(3)
      expect(safeAverage([10, 20], 0)).toBe(15)
    })

    it('returns default value for empty array', () => {
      expect(safeAverage([], 0)).toBe(0)
      expect(safeAverage([], null)).toBe(null)
    })

    it('filters out null and undefined values', () => {
      expect(safeAverage([1, null, 3, undefined, 5], 0)).toBe(3)
    })

    it('returns default value for array with only null values', () => {
      expect(safeAverage([null, null, null], 0)).toBe(0)
    })

    it('handles null array input', () => {
      expect(safeAverage(null, 0)).toBe(0)
      expect(safeAverage(undefined, 0)).toBe(0)
    })
  })
})