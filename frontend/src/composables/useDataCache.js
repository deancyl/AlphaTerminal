/**
 * useDataCache - Short-term memory cache for API responses
 *
 * Prevents redundant API calls when switching between tabs/components.
 * Uses stale-while-revalidate pattern: returns cached data immediately,
 * then refreshes in background.
 *
 * Usage:
 *   const { data, loading, error, fetch } = useDataCache('/api/v1/macro/overview', {
 *     ttl: 5 * 60 * 1000, // 5 minutes
 *     staleWhileRevalidate: true
 *   })
 */

import { ref, onUnmounted } from 'vue'

const globalCache = new Map()

export function useDataCache(key, options = {}) {
  const {
    ttl = 5 * 60 * 1000,
    staleWhileRevalidate = true,
    fetchFn = null
  } = options

  const data = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const lastFetch = ref(null)

  let abortController = null

  function isStale() {
    if (!lastFetch.value) return true
    return Date.now() - lastFetch.value > ttl
  }

  async function fetch(force = false) {
    const cacheKey = typeof key === 'function' ? key() : key
    const cached = globalCache.get(cacheKey)

    if (cached && !force && !isStale()) {
      data.value = cached.data
      lastFetch.value = cached.timestamp
      return cached.data
    }

    if (cached && staleWhileRevalidate && !force) {
      data.value = cached.data
      backgroundRefresh(cacheKey, fetchFn)
      return cached.data
    }

    return await doFetch(cacheKey)
  }

  async function doFetch(cacheKey) {
    if (abortController) {
      abortController.abort()
    }

    abortController = new AbortController()
    loading.value = true
    error.value = null

    try {
      const { apiFetch } = await import('../utils/api.js')
      const url = typeof cacheKey === 'string' && cacheKey.startsWith('/') ? cacheKey : cacheKey
      const result = await apiFetch(url, { signal: abortController.signal })

      data.value = result
      lastFetch.value = Date.now()

      globalCache.set(cacheKey, {
        data: result,
        timestamp: Date.now()
      })

      return result
    } catch (e) {
      if (e.name === 'AbortError') return
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function backgroundRefresh(cacheKey, customFetchFn) {
    try {
      const { apiFetch } = await import('../utils/api.js')
      const url = typeof cacheKey === 'string' && cacheKey.startsWith('/') ? cacheKey : cacheKey
      const result = await (customFetchFn ? customFetchFn() : apiFetch(url))

      data.value = result
      lastFetch.value = Date.now()

      globalCache.set(cacheKey, {
        data: result,
        timestamp: Date.now()
      })
    } catch {
      // Silently fail background refresh
    }
  }

  function invalidate() {
    const cacheKey = typeof key === 'function' ? key() : key
    globalCache.delete(cacheKey)
    lastFetch.value = null
  }

  function clear() {
    globalCache.clear()
  }

  onUnmounted(() => {
    if (abortController) {
      abortController.abort()
    }
  })

  return {
    data,
    loading,
    error,
    lastFetch,
    fetch,
    invalidate,
    clear,
    isStale
  }
}

export function clearAllCache() {
  globalCache.clear()
}

export function getCacheStats() {
  return {
    size: globalCache.size,
    keys: Array.from(globalCache.keys())
  }
}
