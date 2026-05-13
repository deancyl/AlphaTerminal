// WebSocket connection lock utility for preventing race conditions

let locked = false

export function acquireLock() {
  if (locked) {
    return false
  }
  locked = true
  return true
}

export function releaseLock() {
  locked = false
}

export function isLocked() {
  return locked
}
