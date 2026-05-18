/**
 * Request Queue - Limits concurrent API requests to avoid browser connection limits
 *
 * Browsers limit HTTP/1.1 connections per domain to 6.
 * This queue ensures max 4 concurrent requests, leaving 2 for other needs.
 *
 * Usage:
 *   import { queuedFetch } from './requestQueue.js'
 *   const data = await queuedFetch('/api/v1/macro/overview')
 */

const MAX_CONCURRENT = 4
const queue = []
let activeCount = 0

/**
 * Execute a fetch function with queueing
 * @param {Function} fetchFn - Async function that performs the actual fetch
 * @param {string} [priority='normal'] - 'high' | 'normal' | 'low'
 * @returns {Promise<any>}
 */
export async function queuedFetch(fetchFn, priority = 'normal') {
  return new Promise((resolve, reject) => {
    const task = {
      fetchFn,
      resolve,
      reject,
      priority: priority === 'high' ? 0 : priority === 'low' ? 2 : 1
    }
    
    // High priority requests go to front of queue
    if (priority === 'high' && queue.length > 0) {
      const insertIndex = queue.findIndex(t => t.priority > 0)
      if (insertIndex === -1) {
        queue.push(task)
      } else {
        queue.splice(insertIndex, 0, task)
      }
    } else {
      queue.push(task)
    }
    
    processQueue()
  })
}

/**
 * Wrapper for apiFetch that uses the queue
 * @param {string} url - URL to fetch
 * @param {Object} options - Fetch options
 * @param {string} [options.priority='normal'] - 'high' | 'normal' | 'low'
 * @returns {Promise<any>}
 */
export async function apiFetchQueued(url, options = {}) {
  const { priority = 'normal', ...fetchOptions } = options
  
  // Dynamic import to avoid circular dependency
  const { apiFetch } = await import('./api.js')
  
  return queuedFetch(() => apiFetch(url, fetchOptions), priority)
}

/**
 * Batch fetch multiple URLs with queueing
 * @param {Array<{url: string, options?: Object}>} requests
 * @param {string} [priority='normal']
 * @returns {Promise<Array<any>>}
 */
export async function batchFetchQueued(requests, priority = 'normal') {
  const { apiFetch } = await import('./api.js')
  
  const promises = requests.map(({ url, options = {} }) =>
    queuedFetch(() => apiFetch(url, options), priority)
  )
  
  return Promise.all(promises)
}

function processQueue() {
  while (activeCount < MAX_CONCURRENT && queue.length > 0) {
    const task = queue.shift()
    activeCount++
    
    task.fetchFn()
      .then(result => {
        task.resolve(result)
      })
      .catch(error => {
        task.reject(error)
      })
      .finally(() => {
        activeCount--
        processQueue()
      })
  }
}

/**
 * Get queue statistics
 */
export function getQueueStats() {
  return {
    active: activeCount,
    queued: queue.length,
    total: activeCount + queue.length
  }
}

/**
 * Clear all queued requests (does not affect active requests)
 */
export function clearQueue() {
  queue.length = 0
}
