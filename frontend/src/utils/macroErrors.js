/**
 * Error classification for macro module
 * Maps technical errors to user-friendly messages
 */

export const MacroErrorType = {
  TIMEOUT: 'timeout',
  NETWORK: 'network',
  RATE_LIMIT: 'rate_limit',
  VALIDATION: 'validation',
  NO_DATA: 'no_data',
  UNKNOWN: 'unknown'
}

export function classifyMacroError(error) {
  const message = error.message?.toLowerCase() || ''
  
  if (message.includes('timeout') || message.includes('超时')) {
    return {
      type: MacroErrorType.TIMEOUT,
      userMessage: '数据加载超时，正在显示缓存数据',
      action: 'retry',
      actionLabel: '刷新'
    }
  }
  
  if (message.includes('network') || message.includes('fetch') || 
      message.includes('econnrefused') || message.includes('networkerror')) {
    return {
      type: MacroErrorType.NETWORK,
      userMessage: '网络连接不稳定，正在自动重试...',
      action: 'retry',
      actionLabel: '重试'
    }
  }
  
  if (message.includes('rate') || message.includes('429') || message.includes('too many')) {
    return {
      type: MacroErrorType.RATE_LIMIT,
      userMessage: '请求过于频繁，请等待30秒后重试',
      action: 'wait',
      waitTime: 30
    }
  }
  
  if (message.includes('validation') || message.includes('invalid') || message.includes('422')) {
    return {
      type: MacroErrorType.VALIDATION,
      userMessage: '请求参数无效，请检查输入',
      action: 'none'
    }
  }
  
  if (message.includes('empty') || message.includes('no data') || message.includes('暂无')) {
    return {
      type: MacroErrorType.NO_DATA,
      userMessage: '暂无数据，请稍后再试',
      action: 'retry',
      actionLabel: '刷新'
    }
  }
  
  return {
    type: MacroErrorType.UNKNOWN,
    userMessage: '数据加载失败，请稍后重试',
    action: 'retry',
    actionLabel: '重试'
  }
}

export function formatMacroError(error) {
  const classified = classifyMacroError(error)
  return {
    ...classified,
    originalMessage: error.message,
    timestamp: new Date().toISOString()
  }
}
