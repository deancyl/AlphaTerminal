/**
 * LRU (Least Recently Used) Cache implementation
 * Uses Map to maintain access order
 */
export class LRUCache {
  constructor(capacity, onEvict = null) {
    if (typeof capacity !== 'number' || capacity <= 0) {
      throw new Error('Capacity must be a positive number');
    }
    this.capacity = capacity;
    this.onEvict = onEvict;
    this.cache = new Map();
  }

  get(key) {
    if (!this.cache.has(key)) {
      return undefined;
    }
    const value = this.cache.get(key);
    this.cache.delete(key);
    this.cache.set(key, value);
    return value;
  }

  set(key, value) {
    if (this.cache.has(key)) {
      this.cache.delete(key);
    } else if (this.cache.size >= this.capacity) {
      const oldestKey = this.cache.keys().next().value;
      const oldestValue = this.cache.get(oldestKey);
      this.cache.delete(oldestKey);
      if (this.onEvict) {
        this.onEvict(oldestKey, oldestValue);
      }
    }
    this.cache.set(key, value);
    return this;
  }

  has(key) {
    return this.cache.has(key);
  }

  delete(key) {
    if (!this.cache.has(key)) {
      return false;
    }
    const value = this.cache.get(key);
    this.cache.delete(key);
    if (this.onEvict) {
      this.onEvict(key, value);
    }
    return true;
  }

  clear() {
    if (this.onEvict) {
      for (const [key, value] of this.cache) {
        this.onEvict(key, value);
      }
    }
    this.cache.clear();
  }

  get size() {
    return this.cache.size;
  }

  keys() {
    return [...this.cache.keys()];
  }

  values() {
    return [...this.cache.values()];
  }

  entries() {
    return [...this.cache.entries()];
  }
}

export default LRUCache;
