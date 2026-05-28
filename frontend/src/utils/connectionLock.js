// WebSocket connection lock utility for preventing race conditions

let _locked = false

export function acquireLock() {
  if (_locked) {
    return false
  }
  _locked = true
  // No auto-release timeout - lock must be explicitly released
  return true
}

export function releaseLock() {
  _locked = false
}

export function isLocked() {
  return _locked
}
