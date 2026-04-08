/**
 * API 请求工具 - 统一处理响应格式
 * 
 * 标准响应格式: {code, message, data, timestamp}
 * code: 0 表示成功
 */

/**
 * 解析标准API响应
 * @param {Response} response - fetch Response 对象
 * @returns {Promise<{success: boolean, data: any, message: string, code: number}>}
 */
export async function parseApiResponse(response) {
  if (!response.ok) {
    return {
      success: false,
      data: null,
      message: `HTTP ${response.status}: ${response.statusText}`,
      code: response.status
    }
  }

  try {
    const result = await response.json()
    
    // 检查是否为标准格式
    if (result && typeof result.code === 'number') {
      return {
        success: result.code === 0,
        data: result.data,
        message: result.message,
        code: result.code,
        timestamp: result.timestamp
      }
    }
    
    // 兼容旧格式（直接返回数据）
    return {
      success: true,
      data: result,
      message: 'success',
      code: 0
    }
  } catch (e) {
    return {
      success: false,
      data: null,
      message: `解析响应失败: ${e.message}`,
      code: -1
    }
  }
}

/**
 * 安全的API请求
 * @param {string} url - 请求URL
 * @param {Object} options - fetch选项
 * @returns {Promise<{success: boolean, data: any, message: string}>}
 */
export async function apiRequest(url, options = {}) {
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    })
    return await parseApiResponse(response)
  } catch (e) {
    return {
      success: false,
      data: null,
      message: `请求失败: ${e.message}`,
      code: -1
    }
  }
}

/**
 * 获取API数据（简化版，直接返回数据或默认值）
 * @param {string} url - 请求URL
 * @param {*} defaultValue - 失败时的默认值
 * @returns {Promise<any>}
 */
export async function fetchApiData(url, defaultValue = null) {
  const result = await apiRequest(url)
  return result.success ? result.data : defaultValue
}

/**
 * 批量获取API数据
 * @param {Array<{url: string, key: string, default?: any}>} requests 
 * @returns {Promise<Object>}
 */
export async function fetchApiBatch(requests) {
  const results = await Promise.all(
    requests.map(async ({ url, key, default: defaultValue = null }) => {
      const data = await fetchApiData(url, defaultValue)
      return { key, data }
    })
  )
  
  return results.reduce((acc, { key, data }) => {
    acc[key] = data
    return acc
  }, {})
}
