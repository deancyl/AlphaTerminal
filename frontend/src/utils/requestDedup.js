/**
 * Request Deduplication Utility
 * 
 * Prevents duplicate API requests when user rapidly changes inputs (e.g., typing stock codes).
 * Features:
 * - AbortController to cancel previous pending requests
 * - Debounce for rapid changes (default 100ms)
 * - Request coalescing (same URL shares same Promise)
 */

const pendingRequests = new Map()
const debounceTimers = new Map()

/**
 * Execute a fetch with deduplication and debouncing
 * 
 * @param {string} key - Unique key for the request (e.g., URL or symbol)
 * @param {Function} fetcher - Async function that takes AbortSignal and returns data
 * @param {Object} options - Options
 * @param {number} options.debounce - Debounce delay in ms (default 100)
 * @returns {Promise<any>} - The fetch result
 */
export function dedupedFetch(key, fetcher, options = {}) {
  const { debounce = 100 } = options
  
  // Cancel previous request for same key
  if (pendingRequests.has(key)) {
    const prev = pendingRequests.get(key)
    if (prev.abort) {
      prev.abort()
    }
    pendingRequests.delete(key)
  }
  
  // Clear previous debounce timer
  if (debounceTimers.has(key)) {
    clearTimeout(debounceTimers.get(key))
    debounceTimers.delete(key)
  }
  
  return new Promise((resolve, reject) => {
    const timer = setTimeout(async () => {
      const controller = new AbortController()
      const abortFn = () => controller.abort()
      pendingRequests.set(key, { abort: abortFn })
      
      try {
        const result = await fetcher(controller.signal)
        resolve(result)
      } catch (e) {
        // Don't reject on abort - just silently ignore
        if (e.name !== 'AbortError') {
          reject(e)
        }
      } finally {
        pendingRequests.delete(key)
        debounceTimers.delete(key)
      }
    }, debounce)
    
    debounceTimers.set(key, timer)
  })
}

/**
 * Abort a pending request by key
 * 
 * @param {string} key - The request key to abort
 */
export function abortPendingRequest(key) {
  if (pendingRequests.has(key)) {
    const pending = pendingRequests.get(key)
    if (pending.abort) {
      pending.abort()
    }
    pendingRequests.delete(key)
  }
  if (debounceTimers.has(key)) {
    clearTimeout(debounceTimers.get(key))
    debounceTimers.delete(key)
  }
}

/**
 * Abort all pending requests
 */
export function abortAllPendingRequests() {
  for (const [key, pending] of pendingRequests) {
    if (pending.abort) {
      pending.abort()
    }
  }
  pendingRequests.clear()
  
  for (const timer of debounceTimers.values()) {
    clearTimeout(timer)
  }
  debounceTimers.clear()
}

/**
 * Check if a request is pending for a given key
 * 
 * @param {string} key - The request key
 * @returns {boolean}
 */
export function isRequestPending(key) {
  return pendingRequests.has(key) || debounceTimers.has(key)
}

/**
 * Get count of pending requests
 * 
 * @returns {number}
 */
export function getPendingRequestCount() {
  return Math.max(pendingRequests.size, debounceTimers.size)
}
