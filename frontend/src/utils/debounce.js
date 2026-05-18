/**
 * Debounce function with leading/trailing options.
 */
export function debounce(fn, wait, options = {}) {
  let timeoutId = null
  let lastArgs = null
  let lastThis = null
  
  const { leading = false, trailing = true } = options
  
  function invoke() {
    if (lastArgs) {
      fn.apply(lastThis, lastArgs)
      lastArgs = null
      lastThis = null
    }
  }
  
  function debounced(...args) {
    lastArgs = args
    lastThis = this
    
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    
    if (leading && !timeoutId) {
      invoke()
    }
    
    timeoutId = setTimeout(() => {
      timeoutId = null
      if (trailing) {
        invoke()
      }
    }, wait)
  }
  
  debounced.cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
    lastArgs = null
    lastThis = null
  }
  
  return debounced
}
