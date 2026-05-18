/**
 * Retry utility with exponential backoff for transient failures
 * 
 * @param {Function} fn - Async function to retry
 * @param {Object} options - Retry options
 * @param {number} options.maxAttempts - Maximum retry attempts (default: 3)
 * @param {number} options.baseDelay - Base delay in ms (default: 1000)
 * @param {number} options.maxDelay - Maximum delay in ms (default: 10000)
 * @param {Function} options.onRetry - Callback on each retry: (attempt, error, delay) => void
 * @param {Function} options.isRetryable - Custom retryable check: (error) => boolean
 * @returns {Promise<any>} - Result of fn()
 */
export async function withRetry(fn, options = {}) {
  const {
    maxAttempts = 3,
    baseDelay = 1000,
    maxDelay = 10000,
    onRetry = null,
    isRetryable = defaultIsRetryable
  } = options

  let lastError = null

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn()
    } catch (err) {
      lastError = err

      // Don't retry if max attempts reached
      if (attempt === maxAttempts) {
        throw err
      }

      // Don't retry non-retryable errors
      if (!isRetryable(err)) {
        throw err
      }

      // Calculate exponential backoff delay
      const delay = Math.min(baseDelay * Math.pow(2, attempt - 1), maxDelay)

      // Notify callback if provided
      if (onRetry) {
        onRetry(attempt, err, delay)
      }

      // Wait before next attempt
      await new Promise(resolve => setTimeout(resolve, delay))
    }
  }

  // Should never reach here, but TypeScript/ESLint needs it
  throw lastError
}

/**
 * Default retryable error check
 * Retry on: 429 (rate limit), 502/503/504 (server errors), network errors
 * Don't retry on: 4xx client errors (except 429)
 * 
 * @param {Error} err - Error to check
 * @returns {boolean} - True if error is retryable
 */
function defaultIsRetryable(err) {
  // Check for HTTP status code
  const status = err.status || err.response?.status

  // Retry on rate limit (429)
  if (status === 429) return true

  // Retry on server errors (502, 503, 504)
  if (status >= 502 && status <= 504) return true

  // Retry on network errors (TypeError from fetch)
  if (err.name === 'TypeError' && (
    err.message.includes('fetch') ||
    err.message.includes('network') ||
    err.message.includes('Failed to fetch')
  )) {
    return true
  }

  // Retry on abort errors (might be transient)
  if (err.name === 'AbortError') return false

  // Don't retry other errors
  return false
}

/**
 * Create a retryable fetch wrapper
 * 
 * @param {Object} retryOptions - Retry options (passed to withRetry)
 * @returns {Function} - Wrapped fetch function
 */
export function createRetryableFetch(retryOptions = {}) {
  return async function retryableFetch(url, fetchOptions = {}) {
    return withRetry(
      async () => {
        const response = await fetch(url, fetchOptions)
        
        // Attach status to error for retry logic
        if (!response.ok) {
          const error = new Error(`HTTP ${response.status}: ${response.statusText}`)
          error.status = response.status
          error.response = response
          throw error
        }
        
        return response
      },
      retryOptions
    )
  }
}

/**
 * Retry configuration presets
 */
export const RETRY_PRESETS = {
  // For LLM API calls (longer delays, fewer retries)
  llm: {
    maxAttempts: 3,
    baseDelay: 1000,
    maxDelay: 10000
  },
  
  // For data API calls (shorter delays, more retries)
  data: {
    maxAttempts: 5,
    baseDelay: 500,
    maxDelay: 5000
  },
  
  // For critical operations (aggressive retry)
  critical: {
    maxAttempts: 5,
    baseDelay: 2000,
    maxDelay: 30000
  }
}
