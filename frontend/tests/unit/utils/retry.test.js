import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { withRetry, createRetryableFetch, RETRY_PRESETS } from '@/utils/retry.js'

describe('withRetry', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should return result on first successful attempt', async () => {
    const fn = vi.fn().mockResolvedValue('success')
    
    const result = await withRetry(fn)
    
    expect(result).toBe('success')
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('should retry on retryable errors (429)', async () => {
    const error = new Error('Rate limited')
    error.status = 429
    
    const fn = vi.fn()
      .mockRejectedValueOnce(error)
      .mockResolvedValue('success')
    
    const resultPromise = withRetry(fn, { baseDelay: 100 })
    
    await vi.advanceTimersByTimeAsync(100)
    
    const result = await resultPromise
    
    expect(result).toBe('success')
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it('should retry on retryable errors (502)', async () => {
    const error = new Error('Bad Gateway')
    error.status = 502
    
    const fn = vi.fn()
      .mockRejectedValueOnce(error)
      .mockResolvedValue('success')
    
    const resultPromise = withRetry(fn, { baseDelay: 100 })
    
    await vi.advanceTimersByTimeAsync(100)
    
    const result = await resultPromise
    
    expect(result).toBe('success')
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it('should retry on retryable errors (503)', async () => {
    const error = new Error('Service Unavailable')
    error.status = 503
    
    const fn = vi.fn()
      .mockRejectedValueOnce(error)
      .mockResolvedValue('success')
    
    const resultPromise = withRetry(fn, { baseDelay: 100 })
    
    await vi.advanceTimersByTimeAsync(100)
    
    const result = await resultPromise
    
    expect(result).toBe('success')
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it('should retry on retryable errors (504)', async () => {
    const error = new Error('Gateway Timeout')
    error.status = 504
    
    const fn = vi.fn()
      .mockRejectedValueOnce(error)
      .mockResolvedValue('success')
    
    const resultPromise = withRetry(fn, { baseDelay: 100 })
    
    await vi.advanceTimersByTimeAsync(100)
    
    const result = await resultPromise
    
    expect(result).toBe('success')
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it('should retry on network errors (TypeError)', async () => {
    const error = new TypeError('Failed to fetch')
    
    const fn = vi.fn()
      .mockRejectedValueOnce(error)
      .mockResolvedValue('success')
    
    const resultPromise = withRetry(fn, { baseDelay: 100 })
    
    await vi.advanceTimersByTimeAsync(100)
    
    const result = await resultPromise
    
    expect(result).toBe('success')
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it('should NOT retry on non-retryable errors (400)', async () => {
    const error = new Error('Bad Request')
    error.status = 400
    
    const fn = vi.fn().mockRejectedValue(error)
    
    await expect(withRetry(fn)).rejects.toThrow('Bad Request')
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('should NOT retry on non-retryable errors (401)', async () => {
    const error = new Error('Unauthorized')
    error.status = 401
    
    const fn = vi.fn().mockRejectedValue(error)
    
    await expect(withRetry(fn)).rejects.toThrow('Unauthorized')
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('should NOT retry on non-retryable errors (404)', async () => {
    const error = new Error('Not Found')
    error.status = 404
    
    const fn = vi.fn().mockRejectedValue(error)
    
    await expect(withRetry(fn)).rejects.toThrow('Not Found')
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('should throw after max attempts', async () => {
    const error = new Error('Rate limited')
    error.status = 429
    
    const fn = vi.fn().mockRejectedValue(error)
    
    const resultPromise = withRetry(fn, { maxAttempts: 3, baseDelay: 100 })
    
    await vi.advanceTimersByTimeAsync(100)
    await vi.advanceTimersByTimeAsync(200)
    
    await expect(resultPromise).rejects.toThrow('Rate limited')
    expect(fn).toHaveBeenCalledTimes(3)
  })

  it('should use exponential backoff', async () => {
    const error = new Error('Rate limited')
    error.status = 429
    
    const fn = vi.fn().mockRejectedValue(error)
    const onRetry = vi.fn()
    
    const resultPromise = withRetry(fn, { maxAttempts: 3, baseDelay: 100, onRetry })
    
    await vi.advanceTimersByTimeAsync(100)
    expect(onRetry).toHaveBeenCalledWith(1, error, 100)
    
    await vi.advanceTimersByTimeAsync(200)
    expect(onRetry).toHaveBeenCalledWith(2, error, 200)
    
    await expect(resultPromise).rejects.toThrow('Rate limited')
  })

  it('should call onRetry callback with correct parameters', async () => {
    const error = new Error('Rate limited')
    error.status = 429
    
    const fn = vi.fn()
      .mockRejectedValueOnce(error)
      .mockResolvedValue('success')
    
    const onRetry = vi.fn()
    
    const resultPromise = withRetry(fn, { baseDelay: 100, onRetry })
    
    await vi.advanceTimersByTimeAsync(100)
    
    await resultPromise
    
    expect(onRetry).toHaveBeenCalledWith(1, error, 100)
  })

  it('should respect maxDelay option', async () => {
    const error = new Error('Rate limited')
    error.status = 429
    
    const fn = vi.fn().mockRejectedValue(error)
    const onRetry = vi.fn()
    
    const resultPromise = withRetry(fn, { maxAttempts: 5, baseDelay: 1000, maxDelay: 2000, onRetry })
    
    await vi.advanceTimersByTimeAsync(1000)
    expect(onRetry).toHaveBeenCalledWith(1, error, 1000)
    
    await vi.advanceTimersByTimeAsync(2000)
    expect(onRetry).toHaveBeenCalledWith(2, error, 2000)
    
    await vi.advanceTimersByTimeAsync(2000)
    expect(onRetry).toHaveBeenCalledWith(3, error, 2000)
    
    await vi.advanceTimersByTimeAsync(2000)
    expect(onRetry).toHaveBeenCalledWith(4, error, 2000)
    
    await expect(resultPromise).rejects.toThrow('Rate limited')
  })

  it('should use custom isRetryable function', async () => {
    const error = new Error('Custom error')
    error.status = 418
    
    const fn = vi.fn()
      .mockRejectedValueOnce(error)
      .mockResolvedValue('success')
    
    const isRetryable = vi.fn().mockReturnValue(true)
    
    const resultPromise = withRetry(fn, { baseDelay: 100, isRetryable })
    
    await vi.advanceTimersByTimeAsync(100)
    
    const result = await resultPromise
    
    expect(result).toBe('success')
    expect(isRetryable).toHaveBeenCalledWith(error)
  })
})

describe('createRetryableFetch', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should create a retryable fetch wrapper', async () => {
    const retryableFetch = createRetryableFetch({ baseDelay: 100 })
    
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 503, statusText: 'Service Unavailable' })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ data: 'success' }) })
    
    const resultPromise = retryableFetch('https://api.example.com/data')
    
    await vi.advanceTimersByTimeAsync(100)
    
    const result = await resultPromise
    
    expect(result.ok).toBe(true)
    expect(global.fetch).toHaveBeenCalledTimes(2)
  })

  it('should throw error with status attached', async () => {
    const retryableFetch = createRetryableFetch({ maxAttempts: 1 })
    
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, statusText: 'Internal Server Error' })
    
    await expect(retryableFetch('https://api.example.com/data')).rejects.toThrow('HTTP 500')
  })
})

describe('RETRY_PRESETS', () => {
  it('should have llm preset', () => {
    expect(RETRY_PRESETS.llm).toEqual({
      maxAttempts: 3,
      baseDelay: 1000,
      maxDelay: 10000
    })
  })

  it('should have data preset', () => {
    expect(RETRY_PRESETS.data).toEqual({
      maxAttempts: 5,
      baseDelay: 500,
      maxDelay: 5000
    })
  })

  it('should have critical preset', () => {
    expect(RETRY_PRESETS.critical).toEqual({
      maxAttempts: 5,
      baseDelay: 2000,
      maxDelay: 30000
    })
  })
})
