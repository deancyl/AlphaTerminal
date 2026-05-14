import { logger } from './logger.js'

const MAX_QUEUE_SIZE = 50
const FLUSH_INTERVAL = 30000
const MAX_RETRIES = 3

const errorQueue = []
let flushTimer = null
let isReporting = false

const rateLimiter = {
  errors: new Map(),
  maxPerMinute: 10,
  
  canReport(errorKey) {
    const now = Date.now()
    const minuteAgo = now - 60000
    
    if (!this.errors.has(errorKey)) {
      this.errors.set(errorKey, [])
    }
    
    const timestamps = this.errors.get(errorKey)
    const recentErrors = timestamps.filter(t => t > minuteAgo)
    
    if (recentErrors.length >= this.maxPerMinute) {
      return false
    }
    
    recentErrors.push(now)
    this.errors.set(errorKey, recentErrors)
    return true
  },
  
  cleanup() {
    const minuteAgo = Date.now() - 60000
    for (const [key, timestamps] of this.errors.entries()) {
      const recent = timestamps.filter(t => t > minuteAgo)
      if (recent.length === 0) {
        this.errors.delete(key)
      } else {
        this.errors.set(key, recent)
      }
    }
  },
}

function generateErrorKey(error) {
  const message = error?.message || 'unknown'
  const name = error?.name || 'Error'
  return `${name}:${message.substring(0, 50)}`
}

function generateTraceId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).substring(2, 8)}`
}

function getErrorContext() {
  return {
    url: window.location.href,
    userAgent: navigator.userAgent,
    timestamp: new Date().toISOString(),
    screenSize: `${window.innerWidth}x${window.innerHeight}`,
    language: navigator.language,
    referrer: document.referrer || 'direct',
  }
}

function normalizeError(error, context = {}) {
  const normalized = {
    traceId: context.traceId || generateTraceId(),
    timestamp: new Date().toISOString(),
    
    error: {
      name: error?.name || 'Error',
      message: error?.message || 'Unknown error',
      stack: error?.stack || null,
      code: error?.code || null,
    },
    
    context: {
      ...context,
      ...getErrorContext(),
    },
  }
  
  if (error?.response) {
    normalized.error.response = {
      status: error.response.status,
      statusText: error.response.statusText,
      url: error.response.config?.url,
      method: error.response.config?.method,
    }
  }
  
  return normalized
}

export async function reportToBackend(errorReport) {
  const endpoint = '/api/v1/errors/report'
  
  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(errorReport),
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    
    return { success: true }
  } catch (err) {
    logger.warn('[ErrorReporter] Failed to report to backend:', err.message)
    return { success: false, error: err }
  }
}

export function queueError(error, context = {}) {
  const errorKey = generateErrorKey(error)
  
  if (!rateLimiter.canReport(errorKey)) {
    logger.warn('[ErrorReporter] Rate limited, skipping error:', errorKey)
    return null
  }
  
  const normalized = normalizeError(error, context)
  
  if (errorQueue.length >= MAX_QUEUE_SIZE) {
    errorQueue.shift()
  }
  
  errorQueue.push(normalized)
  
  logger.info('[ErrorReporter] Queued error:', normalized.traceId)
  
  if (!flushTimer) {
    startFlushTimer()
  }
  
  return normalized.traceId
}

export async function flushErrors() {
  if (isReporting || errorQueue.length === 0) {
    return
  }
  
  isReporting = true
  
  const errorsToSend = [...errorQueue]
  errorQueue.length = 0
  
  try {
    const response = await reportToBackend({
      errors: errorsToSend,
      batch: true,
      count: errorsToSend.length,
    })
    
    if (!response.success) {
      if (errorsToSend.length < MAX_QUEUE_SIZE) {
        errorQueue.unshift(...errorsToSend)
      }
    }
  } catch (err) {
    logger.error('[ErrorReporter] Flush failed:', err)
  } finally {
    isReporting = false
  }
}

function startFlushTimer() {
  if (flushTimer) {
    clearInterval(flushTimer)
  }
  
  flushTimer = setInterval(() => {
    flushErrors()
    rateLimiter.cleanup()
  }, FLUSH_INTERVAL)
}

function stopFlushTimer() {
  if (flushTimer) {
    clearInterval(flushTimer)
    flushTimer = null
  }
}

export function reportError(error, context = {}) {
  const traceId = queueError(error, context)
  
  logger.error('[ErrorReporter]', {
    traceId,
    error: error?.message,
    context,
  })
  
  return traceId
}

export function getErrorQueue() {
  return [...errorQueue]
}

export function clearErrorQueue() {
  errorQueue.length = 0
}

export function initErrorReporter() {
  window.addEventListener('beforeunload', () => {
    if (errorQueue.length > 0) {
      navigator.sendBeacon('/api/v1/errors/report', JSON.stringify({
        errors: errorQueue,
        batch: true,
        beacon: true,
      }))
    }
  })
  
  window.addEventListener('unhandledrejection', (event) => {
    reportError(event.reason, {
      type: 'unhandledrejection',
      source: 'promise',
    })
  })
  
  window.addEventListener('error', (event) => {
    if (event.error) {
      reportError(event.error, {
        type: 'uncaught',
        source: 'window',
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
      })
    }
  })
  
  startFlushTimer()
  
  logger.info('[ErrorReporter] Initialized')
}

export const errorReporter = {
  report: reportError,
  queue: queueError,
  flush: flushErrors,
  getQueue: getErrorQueue,
  clearQueue: clearErrorQueue,
  init: initErrorReporter,
}

export default errorReporter