/**
 * 带超时、错误兜底的 fetch 封装
 * 
 * 功能:
 * - 超时控制
 * - 自动重试 (可选)
 * - 标准 API 格式解包
 * 
 * @param {string} url - 请求 URL
 * @param {Object} options - 选项
 * @param {number} options.timeoutMs - 超时时间 (默认 8000ms)
 * @param {number} options.retries - 重试次数 (默认 0)
 * @returns {Promise<any>}
 */

export async function apiFetch(url, options = {}) {
  const {
    timeoutMs = 8000,
    retries = 0,
  } = options

  let lastError = null

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    
    try {
      const res = await fetch(url, { signal: controller.signal })
      clearTimeout(timer)
      
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      
      const d = await res.json()
      
      // 兼容新旧格式：标准格式 d.data.xxx，或旧格式 d.xxx
      return d.data !== undefined ? d.data : d
      
    } catch (e) {
      clearTimeout(timer)
      lastError = e
      
      // 如果不是最后一次尝试，记录错误并重试
      if (attempt < retries) {
        console.warn(`[apiFetch] ${url} failed (attempt ${attempt + 1}), retrying...`)
        await sleep(500 * (attempt + 1))
        continue
      }
      
    } finally {
      clearTimeout(timer)
    }
  }
  
  // 所有重试都失败了
  if (lastError) {
    if (lastError.name === 'AbortError') {
      throw new Error(`请求超时（${timeoutMs / 1000}s）`)
    }
    throw lastError
  }
  throw new Error('请求失败')
}

// 睡眠函数
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}
