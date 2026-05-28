// WebSocket connection lock utility for preventing race conditions
// Auto-releases after 5 seconds to prevent indefinite lock holding

let _locked = false
let _lockTimeout = null

/**
 * Acquire the connection lock.
 * @returns {boolean} True if lock acquired, false if already locked.
 * @description Lock auto-releases after 5 seconds to prevent indefinite holding.
 */
export function acquireLock() {
  if (_locked) {
    return false
  }
  _locked = true
  
  // Auto-release after 5 seconds to prevent indefinite lock holding
  _lockTimeout = setTimeout(() => {
    if (_locked) {
      releaseLock()
      console.warn('[ConnectionLock] Auto-released after 5s timeout')
    }
  }, 5000)
  
  return true
}

/**
 * Release the connection lock.
 * @description Clears the auto-release timeout if lock is manually released.
 */
export function releaseLock() {
  if (_lockTimeout) {
    clearTimeout(_lockTimeout)
    _lockTimeout = null
  }
  _locked = false
}

export function isLocked() {
  return _locked
}
