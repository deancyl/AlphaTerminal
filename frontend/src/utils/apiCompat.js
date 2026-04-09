/**
 * API 响应兼容提取器
 * Phase B: 后端统一使用 {code, message, data, timestamp} 包装
 * 此工具自动兼容新旧两种格式，前端无需修改。
 */

/**
 * 从 API 响应中提取 data 字段
 * 兼容：
 *   新格式 {code:0, data: {...}} → 返回 data
 *   旧格式 {...} → 直接返回（向后兼容）
 */
export function extractData(response) {
  if (response && typeof response.code === 'number' && 'data' in response) {
    if (response.code !== 0) {
      console.warn('[API] 非0响应码:', response.code, response.message)
    }
    return response.data
  }
  // 旧格式或直接返回的数据（向后兼容）
  return response
}

/**
 * 封装的 fetch，替代普通 fetch
 * 自动处理统一响应格式 {code, message, data, timestamp}
 */
export async function apiFetch(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
  
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  }
  
  const json = await res.json()
  return extractData(json)
}
