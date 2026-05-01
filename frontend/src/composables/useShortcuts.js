/**
 * 全局快捷键管理
 * 提供快捷键注册、监听和执行功能
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { 
  buildShortcutIndex, 
  getShortcutFromEvent, 
  shouldIgnoreShortcut 
} from '../config/shortcuts.js'
import { logger } from '../utils/logger.js'

// 全局快捷键索引
const shortcutIndex = buildShortcutIndex()

// 全局快捷键处理器映射
const actionHandlers = new Map()

// 快捷键启用状态
const shortcutsEnabled = ref(true)

/**
 * 注册快捷键处理器
 * @param {string} action - 动作标识符
 * @param {Function} handler - 处理函数
 */
export function registerShortcutHandler(action, handler) {
  if (typeof handler !== 'function') {
    logger.error(`[Shortcuts] Handler for action "${action}" must be a function`)
    return
  }
  actionHandlers.set(action, handler)
  logger.log(`[Shortcuts] Registered handler for action: ${action}`)
}

/**
 * 注销快捷键处理器
 * @param {string} action - 动作标识符
 */
export function unregisterShortcutHandler(action) {
  actionHandlers.delete(action)
  logger.log(`[Shortcuts] Unregistered handler for action: ${action}`)
}

/**
 * 执行快捷键动作
 * @param {string} action - 动作标识符
 * @param {Event} event - 原始键盘事件
 */
export function executeShortcutAction(action, event) {
  const handler = actionHandlers.get(action)
  if (handler) {
    try {
      handler(event)
      logger.log(`[Shortcuts] Executed action: ${action}`)
    } catch (error) {
      logger.error(`[Shortcuts] Error executing action "${action}":`, error)
    }
  } else {
    logger.warn(`[Shortcuts] No handler registered for action: ${action}`)
  }
}

/**
 * 全局键盘事件处理器
 */
function handleKeyDown(event) {
  // 快捷键被禁用
  if (!shortcutsEnabled.value) return
  
  // 在输入框中忽略（除了特殊键）
  if (shouldIgnoreShortcut(event)) return
  
  // 生成快捷键字符串
  const shortcutKey = getShortcutFromEvent(event)
  
  // 查找快捷键配置
  const shortcut = shortcutIndex.get(shortcutKey)
  
  if (shortcut) {
    // 阻止默认行为和冒泡
    event.preventDefault()
    event.stopPropagation()
    
    // 执行动作
    executeShortcutAction(shortcut.action, event)
  }
}

/**
 * 启用/禁用快捷键
 */
export function setShortcutsEnabled(enabled) {
  shortcutsEnabled.value = enabled
  logger.log(`[Shortcuts] Shortcuts ${enabled ? 'enabled' : 'disabled'}`)
}

/**
 * 获取快捷键启用状态
 */
export function getShortcutsEnabled() {
  return shortcutsEnabled.value
}

/**
 * 主 composable
 * 在根组件中使用，初始化全局快捷键监听
 */
export function useShortcuts() {
  onMounted(() => {
    document.addEventListener('keydown', handleKeyDown, true)
    logger.log('[Shortcuts] Global shortcut listener initialized')
  })
  
  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyDown, true)
    logger.log('[Shortcuts] Global shortcut listener destroyed')
  })
  
  return {
    shortcutsEnabled,
    setShortcutsEnabled,
    registerShortcutHandler,
    unregisterShortcutHandler,
    executeShortcutAction,
  }
}

/**
 * 组件级快捷键注册
 * 在组件中使用，自动在组件卸载时清理
 */
export function useComponentShortcuts(shortcuts) {
  onMounted(() => {
    Object.entries(shortcuts).forEach(([action, handler]) => {
      registerShortcutHandler(action, handler)
    })
  })
  
  onUnmounted(() => {
    Object.keys(shortcuts).forEach(action => {
      unregisterShortcutHandler(action)
    })
  })
}

export default useShortcuts
