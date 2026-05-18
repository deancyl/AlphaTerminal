/**
 * usePersistentCache - IndexedDB 持久化缓存
 * L3 浏览器端缓存层，支持离线访问
 *
 * 功能特性:
 * - IndexedDB 存储（浏览器原生持久化）
 * - TTL 过期机制
 * - 自动清理过期条目
 * - 支持离线访问
 *
 * 使用示例:
 * ```javascript
 * const cache = usePersistentCache()
 *
 * // 设置缓存（5分钟 TTL）
 * await cache.set('kline:sh600519:daily', data, 5 * 60 * 1000)
 *
 * // 获取缓存
 * const data = await cache.get('kline:sh600519:daily')
 *
 * // 清空缓存
 * await cache.clear()
 * ```
 */

import { openDB } from 'idb'

const DB_NAME = 'AlphaTerminalCache'
const DB_VERSION = 1
const STORE_NAME = 'cache'

/**
 * 缓存条目结构
 * @typedef {Object} CacheEntry
 * @property {string} key - 缓存键
 * @property {any} value - 缓存值
 * @property {number} created_at - 创建时间戳（毫秒）
 * @property {number} expires_at - 过期时间戳（毫秒）
 */

let dbPromise = null

/**
 * 获取 IndexedDB 实例（懒加载）
 */
function getDB() {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        // 创建 cache store
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'key' })
          // 创建过期时间索引（用于清理）
          store.createIndex('expires_at', 'expires_at', { unique: false })
        }
      }
    })
  }
  return dbPromise
}

/**
 * IndexedDB 持久化缓存
 * @returns {Object} 缓存操作方法
 */
export function usePersistentCache() {
  /**
   * 获取缓存值
   * @param {string} key - 缓存键
   * @returns {Promise<any|null>} 缓存值或 null
   */
  async function get(key) {
    try {
      const db = await getDB()
      const entry = await db.get(STORE_NAME, key)

      if (!entry) {
        return null
      }

      // 检查是否过期
      const now = Date.now()
      if (now > entry.expires_at) {
        // 过期，删除并返回 null
        await db.delete(STORE_NAME, key)
        return null
      }

      return entry.value
    } catch (error) {
      console.warn('[usePersistentCache] Get failed:', key, error)
      return null
    }
  }

  /**
   * 设置缓存值
   * @param {string} key - 缓存键
   * @param {any} value - 缓存值
   * @param {number} ttlMs - TTL（毫秒）
   * @returns {Promise<boolean>} 是否成功
   */
  async function set(key, value, ttlMs) {
    try {
      const db = await getDB()
      const now = Date.now()

      const entry = {
        key,
        value,
        created_at: now,
        expires_at: now + ttlMs
      }

      await db.put(STORE_NAME, entry)
      return true
    } catch (error) {
      console.warn('[usePersistentCache] Set failed:', key, error)
      return false
    }
  }

  /**
   * 删除缓存值
   * @param {string} key - 缓存键
   * @returns {Promise<boolean>} 是否成功删除
   */
  async function deleteKey(key) {
    try {
      const db = await getDB()
      await db.delete(STORE_NAME, key)
      return true
    } catch (error) {
      console.warn('[usePersistentCache] Delete failed:', key, error)
      return false
    }
  }

  /**
   * 清空所有缓存
   * @returns {Promise<number>} 清理的条目数
   */
  async function clear() {
    try {
      const db = await getDB()
      const tx = db.transaction(STORE_NAME, 'readwrite')
      const store = tx.objectStore(STORE_NAME)

      // 获取所有条目数
      const count = await store.count()

      // 清空
      await store.clear()
      await tx.done

      return count
    } catch (error) {
      console.warn('[usePersistentCache] Clear failed:', error)
      return 0
    }
  }

  /**
   * 清理过期条目
   * @returns {Promise<number>} 清理的条目数
   */
  async function cleanupExpired() {
    try {
      const db = await getDB()
      const tx = db.transaction(STORE_NAME, 'readwrite')
      const store = tx.objectStore(STORE_NAME)
      const index = store.index('expires_at')

      const now = Date.now()
      const range = IDBKeyRange.upperBound(now)

      // 获取所有过期条目
      const expiredEntries = await index.getAll(range)

      // 删除过期条目
      for (const entry of expiredEntries) {
        await store.delete(entry.key)
      }

      await tx.done
      return expiredEntries.length
    } catch (error) {
      console.warn('[usePersistentCache] Cleanup failed:', error)
      return 0
    }
  }

  /**
   * 获取缓存统计信息
   * @returns {Promise<Object>} 统计信息
   */
  async function getStats() {
    try {
      const db = await getDB()
      const tx = db.transaction(STORE_NAME, 'readonly')
      const store = tx.objectStore(STORE_NAME)

      const allEntries = await store.getAll()
      const now = Date.now()

      const validEntries = allEntries.filter(e => e.expires_at > now)
      const expiredEntries = allEntries.filter(e => e.expires_at <= now)

      return {
        total: allEntries.length,
        valid: validEntries.length,
        expired: expiredEntries.length,
        keys: validEntries.map(e => e.key)
      }
    } catch (error) {
      console.warn('[usePersistentCache] Get stats failed:', error)
      return { total: 0, valid: 0, expired: 0, keys: [] }
    }
  }

  return {
    get,
    set,
    delete: deleteKey,
    clear,
    cleanupExpired,
    getStats
  }
}

// 导出默认实例
export default usePersistentCache