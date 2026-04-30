/**
 * useToast.js — 全局 Toast 通知系统
 * 
 * 使用方式：
 *   import { useToast } from './composables/useToast.js'
 *   const { toast, success, error, warning, info } = useToast()
 *   success('操作成功')
 *   error('操作失败', '详细信息')
 */
import { ref, computed } from 'vue'

// ── 全局状态 ───────────────────────────────────────────────────────
const toasts = ref([])
let _id = 0

// ── 常量 ───────────────────────────────────────────────────────────
const MAX_TOASTS = 5
const DEFAULT_DURATION = 3500

// ── 类型配置 ───────────────────────────────────────────────────────
const TYPE_CONFIG = {
  success: { icon: '✅', class: 'toast-success' },
  error:   { icon: '❌', class: 'toast-error' },
  warning: { icon: '⚠️', class: 'toast-warning' },
  info:    { icon: 'ℹ️', class: 'toast-info' },
}

// ── 内部方法 ───────────────────────────────────────────────────────
function addToast(type, title, message = '', duration = DEFAULT_DURATION) {
  const config = TYPE_CONFIG[type]
  const id = ++_id
  
  const toast = {
    id,
    type,
    icon: config.icon,
    class: config.class,
    title,
    message,
    duration,
    createdAt: Date.now(),
  }
  
  // 限制最大数量，移除最旧的
  if (toasts.value.length >= MAX_TOASTS) {
    toasts.value = toasts.value.slice(-MAX_TOASTS + 1)
  }
  
  toasts.value.push(toast)
  
  // 自动移除
  if (duration > 0) {
    setTimeout(() => removeToast(id), duration)
  }
  
  return id
}

function removeToast(id) {
  const index = toasts.value.findIndex(t => t.id === id)
  if (index !== -1) {
    toasts.value.splice(index, 1)
  }
}

// ── 公开 API ───────────────────────────────────────────────────────
export function useToast() {
  return {
    toasts: computed(() => toasts.value),
    remove: removeToast,
    success: (title, message, duration) => addToast('success', title, message, duration),
    error:   (title, message, duration) => addToast('error', title, message, duration),
    warning: (title, message, duration) => addToast('warning', title, message, duration),
    info:    (title, message, duration) => addToast('info', title, message, duration),
  }
}

// 全局快捷访问（非组合式函数场景）
export const toast = {
  success: (title, message, duration) => addToast('success', title, message, duration),
  error:   (title, message, duration) => addToast('error', title, message, duration),
  warning: (title, message, duration) => addToast('warning', title, message, duration),
  info:    (title, message, duration) => addToast('info', title, message, duration),
}
