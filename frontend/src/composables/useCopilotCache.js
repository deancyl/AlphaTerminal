// 云端 Copilot 缓存管理

const RESPONSE_CACHE = new Map()  // 简单内存缓存
const CACHE_TTL = 5 * 60 * 1000   // 5分钟缓存
let currentAbortController = null  // 用于取消请求

// 清理过期缓存
export function cleanCache() {
  const now = Date.now()
  for (const [key, value] of RESPONSE_CACHE) {
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

export { currentAbortController }
