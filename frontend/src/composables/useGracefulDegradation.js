import { ref, reactive, computed } from 'vue'
import { useApiError, getErrorCategory } from './useApiError.js'

export function useGracefulDegradation(options = {}) {
  const {
    onPartialSuccess = null,
    onAllFailed = null,
    showPartialErrors = true,
  } = options

  const { handleError } = useApiError({ showToast: false })

  const requestStates = reactive({})
  const errors = reactive({})
  const data = reactive({})

  function createRequest(key) {
    requestStates[key] = 'idle'
    errors[key] = null
    data[key] = null
  }

  async function fetchWithDegradation(key, fetchFn, context = {}) {
    if (!requestStates[key]) {
      createRequest(key)
    }

    requestStates[key] = 'loading'
    errors[key] = null

    try {
      const result = await fetchFn()
      data[key] = result
      requestStates[key] = 'success'
      return { success: true, data: result, error: null }
    } catch (error) {
      const errorInfo = handleError(error, { ...context, silent: true })
      errors[key] = {
        ...errorInfo,
        timestamp: Date.now(),
        context: context.context || key,
      }
      requestStates[key] = 'error'
      return { success: false, data: null, error: errorInfo }
    }
  }

  async function fetchAll(requests) {
    const results = await Promise.all(
      requests.map(({ key, fetchFn, context }) => 
        fetchWithDegradation(key, fetchFn, context)
      )
    )

    const successCount = results.filter(r => r.success).length
    const failCount = results.filter(r => !r.success).length
    const total = results.length

    if (successCount === 0 && onAllFailed) {
      onAllFailed(errors)
    } else if (failCount > 0 && successCount > 0 && onPartialSuccess) {
      onPartialSuccess({ successCount, failCount, total, errors })
    }

    return {
      results,
      successCount,
      failCount,
      total,
      hasPartialData: successCount > 0 && failCount > 0,
      allFailed: successCount === 0,
      allSuccess: failCount === 0,
    }
  }

  function isLoading(key) {
    return requestStates[key] === 'loading'
  }

  function hasError(key) {
    return requestStates[key] === 'error'
  }

  function isSuccess(key) {
    return requestStates[key] === 'success'
  }

  function getError(key) {
    return errors[key]
  }

  function getData(key) {
    return data[key]
  }

  function getAnyLoading() {
    return Object.values(requestStates).some(state => state === 'loading')
  }

  function getFailedKeys() {
    return Object.keys(requestStates).filter(key => requestStates[key] === 'error')
  }

  function getSuccessKeys() {
    return Object.keys(requestStates).filter(key => requestStates[key] === 'success')
  }

  function getErrorSummary() {
    const failedKeys = getFailedKeys()
    if (failedKeys.length === 0) return null

    return {
      count: failedKeys.length,
      keys: failedKeys,
      errors: failedKeys.map(key => ({
        key,
        ...errors[key],
      })),
    }
  }

  function retry(key, fetchFn, context) {
    return fetchWithDegradation(key, fetchFn, context)
  }

  function retryAll(requests) {
    return fetchAll(requests)
  }

  function reset(key) {
    if (key) {
      requestStates[key] = 'idle'
      errors[key] = null
      data[key] = null
    } else {
      Object.keys(requestStates).forEach(k => {
        requestStates[k] = 'idle'
        errors[k] = null
        data[k] = null
      })
    }
  }

  return {
    requestStates,
    errors,
    data,
    
    fetchWithDegradation,
    fetchAll,
    
    isLoading,
    hasError,
    isSuccess,
    getError,
    getData,
    
    getAnyLoading,
    getFailedKeys,
    getSuccessKeys,
    getErrorSummary,
    
    retry,
    retryAll,
    reset,
    
    hasAnyError: computed(() => Object.values(requestStates).some(state => state === 'error')),
    hasAnyLoading: computed(() => Object.values(requestStates).some(state => state === 'loading')),
    hasAnySuccess: computed(() => Object.values(requestStates).some(state => state === 'success')),
  }
}
