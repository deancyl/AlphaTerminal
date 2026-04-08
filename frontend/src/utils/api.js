/**
 * 带超时和错误兜底的 fetch 封装
 * @param {string} url
 * @param {number} timeoutMs
 * @returns {Promise<any>}
 */
export async function apiFetch(url, timeoutMs = 8000) {
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
    if (e.name === 'AbortError') throw new Error(`请求超时（${timeoutMs / 1000}s）`)
    throw e
  }
}
