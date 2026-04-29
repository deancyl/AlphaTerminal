/**
 * API 响应缓存工具
 * 用于减少重复API请求，提升性能
 */

const defaultTTL = 30000 // 30秒默认缓存

const cache = new Map()

// 缓存统计
export const cacheStats = {
  hits: 0,
  misses: 0,
  size: 0,
}

/**
 * 获取缓存键
 */
function getCacheKey(url, params = {}) {
  const paramsStr = Object.keys(params).length ? JSON.stringify(params) : ''
  return `${url}::${paramsStr}`
}

/**
 * 从缓存获取
 */
export function getFromCache(url, params = {}) {
  const key = getCacheKey(url, params)
  const entry = cache.get(key)

  if (!entry) {
    cacheStats.misses++
    return null
  }

  if (Date.now() - entry.timestamp > entry.ttl) {
    cache.delete(key)
    cacheStats.size = cache.size
    cacheStats.misses++
    return null
  }

  cacheStats.hits++
  return entry.data
}

/**
 * 写入缓存
 */
export function setCache(url, data, params = {}, ttl = defaultTTL) {
  const key = getCacheKey(url, params)
  cache.set(key, { data, timestamp: Date.now(), ttl })
  cacheStats.size = cache.size

  // 防止内存泄漏 - 最多缓存500条
  if (cache.size > 500) {
    const oldestKey = cache.keys().next().value
    if (oldestKey) cache.delete(oldestKey)
    cacheStats.size = cache.size
  }
}

/**
 * 清除特定URL的缓存
 */
export function invalidateCache(urlPattern) {
  const regex = new RegExp(urlPattern)
  for (const key of cache.keys()) {
    if (regex.test(key)) {
      cache.delete(key)
    }
  }
  cacheStats.size = cache.size
}

/**
 * 清除所有缓存
 */
export function clearAllCache() {
  cache.clear()
  cacheStats.size = 0
  cacheStats.hits = 0
  cacheStats.misses = 0
}

/**
 * 带缓存的API请求
 * @param {Function} fetchFn - 实际的请求函数
 * @param {Object} options
 * @param {number} options.ttl - 缓存时间(ms)
 * @param {Function} options.keyFn - 自定义缓存键函数
 * @returns {Promise}
 */
export function withCache(fetchFn, options = {}) {
  const { ttl = defaultTTL, keyFn } = options
  const cacheKey = keyFn ? keyFn() : fetchFn.name || 'anonymous'

  return async (...args) => {
    const url = args[0] || cacheKey
    const cached = getFromCache(url, { ttl })

    if (cached !== null) {
      return cached
    }

    const result = await fetchFn(...args)

    setCache(url, result, { ttl }, ttl)
    return result
  }
}

/**
 * 创建防抖函数
 * @param {Function} fn
 * @param {number} delay
 * @returns {Function}
 */
export function debounce(fn, delay = 300) {
  let timer = null
  return function (...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn.apply(this, args), delay)
  }
}

/**
 * 创建节流函数
 * @param {Function} fn
 * @param {number} limit
 * @returns {Function}
 */
export function throttle(fn, limit = 300) {
  let inThrottle = false
  return function (...args) {
    if (!inThrottle) {
      fn.apply(this, args)
      inThrottle = true
      setTimeout(() => { inThrottle = false }, limit)
    }
  }
}
