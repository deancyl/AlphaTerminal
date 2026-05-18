// WebSocket connection lock utility for preventing race conditions

let _locked = false
let _lockTimeout = null

export function acquireLock() {
  if (_locked) {
    return false
  }
  _locked = true
  _lockTimeout = setTimeout(() => {
    console.warn('[connectionLock] Auto-releasing lock after 5s')
    releaseLock()
  }, 5000)
  return true
}

export function releaseLock() {
  _locked = false
  if (_lockTimeout) {
    clearTimeout(_lockTimeout)
    _lockTimeout = null
  }
}

export function isLocked() {
  return _locked
}
