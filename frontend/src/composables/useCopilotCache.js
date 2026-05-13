// 云端 Copilot 缓存管理
import LRUCache from '../utils/lruCache.js'

const RESPONSE_CACHE = new LRUCache(100)  // LRU缓存，最多100条
const CACHE_TTL = 5 * 60 * 1000   // 5分钟缓存
let currentAbortController = null  // 用于取消请求

// 清理过期缓存
export function cleanCache() {
  const now = Date.now()
  for (const [key, value] of RESPONSE_CACHE.entries()) {
    if (now - value.timestamp > CACHE_TTL) {
      RESPONSE_CACHE.delete(key)
    }
  }
}

// 获取缓存
export function getCachedResponse(prompt) {
  const key = prompt.trim().toLowerCase()
  const cached = RESPONSE_CACHE.get(key)
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.response
  }
  return null
}

// 设置缓存
export function setCachedResponse(prompt, response) {
  const key = prompt.trim().toLowerCase()
  RESPONSE_CACHE.set(key, {
    response,
    timestamp: Date.now()
  })
}

// 获取缓存统计信息
export function getCacheStats() {
  return {
    size: RESPONSE_CACHE.size,
    capacity: RESPONSE_CACHE.capacity,
    utilization: RESPONSE_CACHE.size / RESPONSE_CACHE.capacity
  }
}

export { currentAbortController }
