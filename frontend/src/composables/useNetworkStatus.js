/**
 * 网络状态检测 Composable
 * 
 * 功能:
 * - 实时追踪 navigator.onLine 状态
 * - 监听 online/offline 事件
 * - 提供响应式状态给组件使用
 */

import { ref, onMounted, onUnmounted } from 'vue'

// 全局单例状态（避免多个组件重复监听）
let _isOnline = ref(navigator.onLine)
let _listenerCount = 0
let _onlineHandler = null
let _offlineHandler = null

export function useNetworkStatus() {
  // 首次使用时注册全局监听器
  if (_listenerCount === 0) {
    _onlineHandler = () => {
      _isOnline.value = true
      console.log('[Network] 连接已恢复')
    }
    _offlineHandler = () => {
      _isOnline.value = false
      console.log('[Network] 连接已断开')
    }
    window.addEventListener('online', _onlineHandler)
    window.addEventListener('offline', _offlineHandler)
  }
  
  _listenerCount++
  
  onUnmounted(() => {
    _listenerCount--
    // 最后一个组件卸载时移除监听器
    if (_listenerCount === 0) {
      window.removeEventListener('online', _onlineHandler)
      window.removeEventListener('offline', _offlineHandler)
      _onlineHandler = null
      _offlineHandler = null
    }
  })
  
  return {
    isOnline: _isOnline
  }
}

/**
 * 检查网络是否在线
 * 用于 API 调用前的快速检查
 */
export function isNetworkOnline() {
  return navigator.onLine
}
