/**
 * useKlineCache - K线数据短期内存缓存
 *
 * 解决问题：
 * - AdvancedKlinePanel 每次切换股票都重新请求API
 * - 前端无K线缓存层，导致重复请求
 *
 * 设计原则：
 * - TTL=30秒，小于后端60秒TTL，确保数据新鲜度
 * - 使用 Map 存储，key = symbol:period:adjustment
 * - 支持缓存失效和手动清除
 *
 * 用法:
 *   const { get, set, invalidate } = useKlineCache()
 *   const cached = get('sh600519', 'daily', 'none')
 *   if (!cached) {
 *     const data = await fetchHistory()
 *     set('sh600519', 'daily', 'none', data)
 *   }
 */

import { shallowRef } from 'vue'

// K线缓存TTL：30秒（小于后端60秒，确保数据新鲜）
const KLINE_CACHE_TTL = 30 * 1000

// 全局缓存Map
const klineCache = new Map()

/**
 * 生成缓存键
 * @param {string} symbol - 股票代码
 * @param {string} period - 周期 (daily, weekly, monthly, 1min, 5min, etc.)
 * @param {string} adjustment - 复权类型 (none, qfq, hfq)
 * @returns {string} 缓存键
 */
function getCacheKey(symbol, period, adjustment = 'none') {
  return `${symbol}:${period}:${adjustment}`
}

/**
 * K线缓存 composable
 */
export function useKlineCache() {
  /**
   * 获取缓存的K线数据
   * @param {string} symbol - 股票代码
   * @param {string} period - 周期
   * @param {string} adjustment - 复权类型
   * @returns {object|null} 缓存数据或null
   */
  function get(symbol, period, adjustment = 'none') {
    const key = getCacheKey(symbol, period, adjustment)
    const cached = klineCache.get(key)

    if (!cached) {
      return null
    }

    // 检查是否过期
    if (Date.now() - cached.timestamp > KLINE_CACHE_TTL) {
      klineCache.delete(key)
      return null
    }

    return cached.data
  }

  /**
   * 设置K线缓存
   * @param {string} symbol - 股票代码
   * @param {string} period - 周期
   * @param {string} adjustment - 复权类型
   * @param {object} data - 缓存数据 { history, has_more }
   */
  function set(symbol, period, adjustment, data) {
    const key = getCacheKey(symbol, period, adjustment)
    klineCache.set(key, {
      data,
      timestamp: Date.now()
    })
  }

  /**
   * 使指定股票的所有缓存失效
   * @param {string} symbol - 股票代码
   */
  function invalidate(symbol) {
    for (const key of klineCache.keys()) {
      if (key.startsWith(symbol + ':')) {
        klineCache.delete(key)
      }
    }
  }

  /**
   * 清空所有缓存
   */
  function clear() {
    klineCache.clear()
  }

  /**
   * 获取缓存统计信息
   */
  function getStats() {
    let validCount = 0
    let expiredCount = 0
    const now = Date.now()

    for (const [key, cached] of klineCache.entries()) {
      if (now - cached.timestamp > KLINE_CACHE_TTL) {
        expiredCount++
      } else {
        validCount++
      }
    }

    return {
      total: klineCache.size,
      valid: validCount,
      expired: expiredCount,
      ttlMs: KLINE_CACHE_TTL
    }
  }

  return {
    get,
    set,
    invalidate,
    clear,
    getStats,
    KLINE_CACHE_TTL
  }
}

/**
 * 清理过期缓存（可定期调用）
 */
export function cleanupExpiredKlineCache() {
  const now = Date.now()
  let cleaned = 0

  for (const [key, cached] of klineCache.entries()) {
    if (now - cached.timestamp > KLINE_CACHE_TTL) {
      klineCache.delete(key)
      cleaned++
    }
  }

  return cleaned
}
