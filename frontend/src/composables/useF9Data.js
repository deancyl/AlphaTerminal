import { ref } from 'vue'
import { apiFetch } from '../utils/api.js'
import { useAbortableRequest } from './useAbortableRequest.js'

/**
 * Composable for F9 deep data fetching with abort support
 * Automatically cancels pending requests when symbol changes
 */
export function useF9Data() {
  const { createSignal, complete, abort, pending } = useAbortableRequest()

  /**
   * Fetch F9 data with abort support
   * @param {string} endpoint - F9 endpoint (e.g., 'financial', 'institution')
   * @param {string} bareSymbol - Stock symbol without sh/sz prefix
   * @param {Object} options - Additional options
   * @param {number} options.timeoutMs - Timeout in ms (default 30000)
   * @param {string} options.errorMsg - Custom error message
   * @param {Function} options.validate - Validation function (data => boolean)
   * @returns {Promise<{data: any, error: string|null}>}
   */
  async function fetchF9Data(endpoint, bareSymbol, options = {}) {
    const { timeoutMs = 30000, errorMsg = '获取数据失败', validate } = options

    if (!bareSymbol) {
      return { data: null, error: '股票代码不能为空' }
    }

    const signal = createSignal()

    try {
      const data = await apiFetch(`/api/v1/f9/${bareSymbol}/${endpoint}`, {
        timeoutMs,
        signal
      })

      if (validate && !validate(data)) {
        return { data: null, error: errorMsg }
      }

      return { data, error: null }
    } catch (e) {
      // Don't show error for aborted requests
      if (e.name === 'AbortError' || e.message?.includes('aborted')) {
        return { data: null, error: null, aborted: true }
      }
      return { data: null, error: e.message || errorMsg }
    } finally {
      complete()
    }
  }

  /**
   * Create a reactive F9 data fetcher for a specific endpoint
   * @param {string} endpoint - F9 endpoint
   * @param {Function} validate - Validation function
   * @param {string} errorMsg - Error message when validation fails
   * @returns {Object} - { data, loading, error, fetch }
   */
  function createF9Fetcher(endpoint, validate, errorMsg) {
    const data = ref(null)
    const loading = ref(false)
    const error = ref(null)

    async function fetch(bareSymbol) {
      if (!bareSymbol) {
        data.value = null
        error.value = null
        return
      }

      loading.value = true
      error.value = null

      const result = await fetchF9Data(endpoint, bareSymbol, {
        errorMsg,
        validate
      })

      // Ignore aborted requests
      if (result.aborted) {
        return
      }

      data.value = result.data
      error.value = result.error
      loading.value = false
    }

    return { data, loading, error, fetch }
  }

  /**
   * Fetch with pagination support
   */
  async function fetchF9Paginated(endpoint, bareSymbol, page = 1, pageSize = 20, options = {}) {
    const { timeoutMs = 30000, errorMsg = '获取数据失败', validate } = options

    if (!bareSymbol) {
      return { data: null, error: '股票代码不能为空' }
    }

    const signal = createSignal()

    try {
      const data = await apiFetch(
        `/api/v1/f9/${bareSymbol}/${endpoint}?page=${page}&page_size=${pageSize}`,
        { timeoutMs, signal }
      )

      if (validate && !validate(data)) {
        return { data: null, error: errorMsg }
      }

      return { data, error: null }
    } catch (e) {
      if (e.name === 'AbortError' || e.message?.includes('aborted')) {
        return { data: null, error: null, aborted: true }
      }
      return { data: null, error: e.message || errorMsg }
    } finally {
      complete()
    }
  }

  return {
    fetchF9Data,
    fetchF9Paginated,
    createF9Fetcher,
    abort,
    pending
  }
}
