import { ref, computed, readonly } from 'vue'

// 全局单例状态
const _isOnline = ref(navigator.onLine)
const _dataSourceStatus = ref('ok')  // 'ok' | 'degraded' | 'down'
const _dataSourceMessage = ref('')
const _retryCount = ref(0)
const _maxRetries = 3

let _listenerCount = 0
let _onlineHandler = null
let _offlineHandler = null

/**
 * TimeMachine 网络状态管理 composable
 * 
 * 封装网络状态检测、数据源状态管理、重试计数功能
 * 使用全局单例模式避免重复监听
 */
export function useTimemachineNetwork() {
  // 首次使用时注册全局监听器
  if (_listenerCount === 0) {
    _onlineHandler = () => {
      _isOnline.value = true
      if (_dataSourceStatus.value === 'down') {
        _dataSourceStatus.value = 'ok'
        _dataSourceMessage.value = ''
      }
    }
    
    _offlineHandler = () => {
      _isOnline.value = false
      _dataSourceStatus.value = 'degraded'
      _dataSourceMessage.value = '网络连接已断开'
    }
    
    window.addEventListener('online', _onlineHandler)
    window.addEventListener('offline', _offlineHandler)
    _listenerCount++
  }
  
  // 计算属性
  const statusLabel = computed(() => {
    const labels = {
      ok: '🟢 正常',
      degraded: '🟡 降级',
      down: '🔴 熔断'
    }
    return labels[_dataSourceStatus.value] || '未知'
  })
  
  const canRetry = computed(() => {
    return _retryCount.value < _maxRetries
  })
  
  const retryMessage = computed(() => {
    if (_retryCount.value === 0) return ''
    if (!canRetry.value) return '已达最大重试次数'
    return `重试中 (第${_retryCount.value}次)...`
  })
  
  /**
   * 广播数据源状态变化
   * @param {string} newStatus - 新状态 ('ok' | 'degraded' | 'down')
   * @param {string} message - 状态消息
   */
  function broadcastStatus(newStatus, message = '') {
    _dataSourceStatus.value = newStatus
    _dataSourceMessage.value = message
  }
  
  /**
   * 增加重试计数
   */
  function incrementRetry() {
    if (_retryCount.value < _maxRetries) {
      _retryCount.value++
    }
  }
  
  /**
   * 重置重试计数
   */
  function resetRetry() {
    _retryCount.value = 0
  }
  
  /**
   * 检查服务连接性
   * @returns {Promise<boolean>} 连接是否成功
   */
  async function checkConnectivity() {
    try {
      const response = await fetch('/api/v1/timemachine/health', { 
        method: 'HEAD',
        cache: 'no-cache'
      })
      
      if (response.ok) {
        broadcastStatus('ok', '')
        resetRetry()
        return true
      } else {
        broadcastStatus('down', '服务返回错误')
        return false
      }
    } catch (error) {
      broadcastStatus('down', '服务不可用')
      return false
    }
  }
  
  // 暴露给组件
  return {
    // 状态（只读）
    isOnline: readonly(_isOnline),
    dataSourceStatus: readonly(_dataSourceStatus),
    dataSourceMessage: readonly(_dataSourceMessage),
    retryCount: readonly(_retryCount),
    
    // 计算属性
    statusLabel,
    canRetry,
    retryMessage,
    
    // 方法
    broadcastStatus,
    incrementRetry,
    resetRetry,
    checkConnectivity
  }
}

/**
 * 清理全局监听器（可选）
 * 仅在应用卸载时调用
 */
export function cleanupTimemachineNetwork() {
  if (_listenerCount > 0) {
    window.removeEventListener('online', _onlineHandler)
    window.removeEventListener('offline', _offlineHandler)
    _listenerCount = 0
  }
}
