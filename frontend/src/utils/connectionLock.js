// WebSocket connection lock utility for preventing race conditions
// Auto-releases after 15 seconds to prevent indefinite lock holding

let _locked = false
let _lockTimeout = null

const AUTO_RELEASE_TIMEOUT = 15000 // v0.6.212: Increased from 5s to 15s for slow networks

export function acquireLock() {
  if (_locked) {
    return false
  }
  _locked = true
  
  _lockTimeout = setTimeout(() => {
    if (_locked) {
      releaseLock()
      console.warn('[ConnectionLock] Auto-released after 15s timeout')
    }
  }, AUTO_RELEASE_TIMEOUT)
  
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
