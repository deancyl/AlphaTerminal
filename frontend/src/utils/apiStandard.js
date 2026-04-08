/**
 * API 响应格式统一封装
 * 
 * 统一前后端数据交互格式，消除数据解析不一致问题
 */

/**
 * 标准 API 响应结构
 * @template T
 * @typedef {Object} ApiResponse
 * @property {number} code - 状态码 (0 表示成功)
 * @property {string} message - 消息
 * @property {T} data - 数据 payload
 * @property {string} [requestId] - 请求追踪 ID
 * @property {number} [timestamp] - 服务器时间戳
 */

/**
 * 创建成功响应
 * @template T
 * @param {T} data - 响应数据
 * @param {string} [message='success'] - 成功消息
 * @returns {ApiResponse<T>}
 */
export function createSuccessResponse(data, message = 'success') {
  return {
    code: 0,
    message,
    data,
    timestamp: Date.now()
  }
}

/**
 * 创建错误响应
 * @param {number} code - 错误码
 * @param {string} message - 错误消息
 * @param {*} [details] - 错误详情
 * @returns {ApiResponse<null>}
 */
export function createErrorResponse(code, message, details = null) {
  return {
    code,
    message,
    data: details,
    timestamp: Date.now()
  }
}

/**
 * 标准错误码
 */
export const ErrorCodes = {
  // 成功
  SUCCESS: 0,
  
  // 客户端错误 (1xx)
  BAD_REQUEST: 100,
  UNAUTHORIZED: 101,
  FORBIDDEN: 103,
  NOT_FOUND: 104,
  VALIDATION_ERROR: 105,
  RATE_LIMITED: 106,
  
  // 服务端错误 (2xx)
  INTERNAL_ERROR: 200,
  SERVICE_UNAVAILABLE: 201,
  TIMEOUT: 202,
  
  // 业务错误 (3xx)
  DATA_NOT_FOUND: 300,
  DATA_EXPIRED: 301,
  THIRD_PARTY_ERROR: 302
}

/**
 * 市场数据字段标准化
 * 统一不同 API 返回的字段差异
 */
export const MarketDataFields = {
  // 字段映射表
  mappings: {
    // 价格相关
    'price': ['price', 'current', 'index', 'latest'],
    'change': ['change', 'chg', 'change_amount'],
    'changePct': ['change_pct', 'chg_pct', 'changePercent', 'percent'],
    
    // 成交量相关
    'volume': ['volume', 'vol', 'turnover'],
    'amount': ['amount', 'turnover_amount', 'money'],
    
    // 基本信息
    'symbol': ['symbol', 'code', 'stock_code'],
    'name': ['name', 'stock_name', 'security_name'],
    'market': ['market', 'exchange', 'type'],
    
    // 时间相关
    'timestamp': ['timestamp', 'time', 'update_time', 'datetime']
  },
  
  /**
   * 标准化数据对象
   * @param {Object} raw - 原始数据
   * @returns {Object} 标准化后的数据
   */
  normalize(raw) {
    if (!raw || typeof raw !== 'object') return null
    
    const result = {}
    
    for (const [standardField, possibleKeys] of Object.entries(this.mappings)) {
      for (const key of possibleKeys) {
        if (key in raw) {
          result[standardField] = raw[key]
          break
        }
      }
    }
    
    // 保留原始数据中未映射的字段
    for (const [key, value] of Object.entries(raw)) {
      if (!(key in result)) {
        result[key] = value
      }
    }
    
    return result
  },
  
  /**
   * 批量标准化
   * @param {Array} list - 原始数据列表
   * @returns {Array} 标准化后的列表
   */
  normalizeList(list) {
    if (!Array.isArray(list)) return []
    return list.map(item => this.normalize(item))
  }
}

/**
 * API 响应验证器
 */
export const ResponseValidator = {
  /**
   * 验证是否为标准响应
   * @param {*} response 
   * @returns {boolean}
   */
  isValidResponse(response) {
    return response && 
           typeof response === 'object' && 
           'code' in response && 
           'message' in response &&
           'data' in response
  },
  
  /**
   * 验证是否成功响应
   * @param {*} response 
   * @returns {boolean}
   */
  isSuccess(response) {
    return this.isValidResponse(response) && response.code === ErrorCodes.SUCCESS
  },
  
  /**
   * 安全获取数据
   * @template T
   * @param {*} response 
   * @param {T} [defaultValue=null] 
   * @returns {T}
   */
  getData(response, defaultValue = null) {
    if (this.isSuccess(response)) {
      return response.data
    }
    return defaultValue
  }
}
