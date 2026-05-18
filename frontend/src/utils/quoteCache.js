import { CACHE_TTL } from './constants.js'

class QuoteCache {
  constructor(maxSize = 100) {
    this.cache = new Map()
    this.maxSize = maxSize
  }
  
  get(key) {
    const entry = this.cache.get(key)
    if (!entry) return null
    
    if (Date.now() > entry.expiry) {
      this.cache.delete(key)
      return null
    }
    
    // LRU eviction: move accessed item to end
    this.cache.delete(key)
    this.cache.set(key, entry)
    
    return entry.data
  }
  
  set(key, data, ttl = CACHE_TTL.QUOTE) {
    if (this.cache.size >= this.maxSize) {
      const oldestKey = this.cache.keys().next().value
      this.cache.delete(oldestKey)
    }
    
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      expiry: Date.now() + ttl,
    })
  }
  
  invalidate(pattern) {
    for (const key of this.cache.keys()) {
      if (key.includes(pattern)) {
        this.cache.delete(key)
      }
    }
  }
  
  clear() {
    this.cache.clear()
  }
  
  getStats() {
    return {
      size: this.cache.size,
      maxSize: this.maxSize,
    }
  }
}

export const quoteCache = new QuoteCache()

if (import.meta.env.DEV) {
  window.__quoteCache = quoteCache
}
