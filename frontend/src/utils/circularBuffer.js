/**
 * CircularBuffer - Fixed-size circular buffer for efficient data management
 *
 * Unlike array.shift() which is O(n), this implementation provides O(1) push operations.
 * Used for limiting message history without memory pressure from array reallocation.
 */
export class CircularBuffer {
  constructor(maxSize = 1000) {
    this.maxSize = maxSize
    this.buffer = new Array(maxSize)
    this.head = 0
    this.tail = 0
    this.length = 0
  }

  push(item) {
    this.buffer[this.tail] = item
    this.tail = (this.tail + 1) % this.maxSize

    if (this.length < this.maxSize) {
      this.length++
    } else {
      this.head = (this.head + 1) % this.maxSize
    }
  }

  toArray() {
    const result = []
    for (let i = 0; i < this.length; i++) {
      result.push(this.buffer[(this.head + i) % this.maxSize])
    }
    return result
  }

  get(index) {
    if (index < 0 || index >= this.length) return undefined
    return this.buffer[(this.head + index) % this.maxSize]
  }

  clear() {
    this.head = 0
    this.tail = 0
    this.length = 0
  }

  get latest() {
    if (this.length === 0) return undefined
    return this.buffer[(this.tail - 1 + this.maxSize) % this.maxSize]
  }
}
