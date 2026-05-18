/**
 * CircularBuffer - Fixed-size circular buffer for efficient data management
 *
 * Unlike array.shift() which is O(n), this implementation provides O(1) push operations.
 * Used for limiting message history without memory pressure from array reallocation.
 *
 * === BUSINESS CONTEXT ===
 * 
 * MAX_TICK_HISTORY = 1000 条 ≈ 16秒历史（假设60tick/s）
 * 
 * Usage Scenarios:
 * 1. 实时行情历史 (useMarketStream.js)
 *    - 存储最近1000条tick用于图表回放和断连恢复
 *    - 内存占用: ~100KB (1000 ticks × ~100 bytes each)
 * 
 * 2. WebSocket消息队列
 *    - 防止消息堆积导致的内存泄漏
 *    - 自动丢弃最旧的消息
 * 
 * 3. 分笔成交缓冲 (TickBuffer in backend)
 *    - 用于WebSocket断连恢复
 *    - 重连时发送last_seq请求缺失的tick
 *
 * === PERFORMANCE ===
 * 
 * - Push: O(1) - constant time, no array reallocation
 * - Get: O(1) - direct index access
 * - ToArray: O(n) - linear scan, use sparingly
 * 
 * === MEMORY SAFETY ===
 * 
 * - Fixed size: prevents unbounded growth
 * - Ring buffer: oldest data automatically discarded
 * - No garbage collection pressure from array.splice()
 */
export class CircularBuffer {
  /**
   * Create a circular buffer
   * @param {number} maxSize - Maximum number of items (default: 1000)
   * 
   * Business Note: 1000 items ≈ 16 seconds of tick history
   * This is sufficient for most disconnection recovery scenarios
   */
  constructor(maxSize = 1000) {
    this.maxSize = maxSize
    this.buffer = new Array(maxSize)
    this.head = 0
    this.tail = 0
    this.length = 0
  }

  /**
   * Add an item to the buffer
   * If buffer is full, oldest item is automatically discarded
   * @param {*} item - Item to add
   */
  push(item) {
    this.buffer[this.tail] = item
    this.tail = (this.tail + 1) % this.maxSize

    if (this.length < this.maxSize) {
      this.length++
    } else {
      // Buffer full: discard oldest item
      this.head = (this.head + 1) % this.maxSize
    }
  }

  /**
   * Convert buffer to array (preserves order from oldest to newest)
   * @returns {Array} Array of all items
   * 
   * Warning: O(n) operation, use sparingly
   */
  toArray() {
    const result = []
    for (let i = 0; i < this.length; i++) {
      result.push(this.buffer[(this.head + i) % this.maxSize])
    }
    return result
  }

  /**
   * Get item at specific index
   * @param {number} index - Index (0 = oldest, length-1 = newest)
   * @returns {*} Item or undefined if index out of bounds
   */
  get(index) {
    if (index < 0 || index >= this.length) return undefined
    return this.buffer[(this.head + index) % this.maxSize]
  }

  /**
   * Clear all items
   */
  clear() {
    this.head = 0
    this.tail = 0
    this.length = 0
  }

  /**
   * Get the most recent item
   * @returns {*} Latest item or undefined if buffer empty
   */
  get latest() {
    if (this.length === 0) return undefined
    return this.buffer[(this.tail - 1 + this.maxSize) % this.maxSize]
  }
}
