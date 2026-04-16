/**
 * useEventBus.js — 轻量级跨组件事件总线
 * Phase 4: NewsFeed 刷新完成后 → 通知 SentimentGauge 联动重拉
 */
import { ref } from 'vue'
import { logger } from '../utils/logger.js'

const listeners = {}

/**
 * 监听事件
 * on('news-refreshed', () => { ... })
 */
export function on(event, cb) {
  if (!listeners[event]) listeners[event] = []
  listeners[event].push(cb)
  return () => off(event, cb)  // 返回取消函数
}

/**
 * 触发事件
 * emit('news-refreshed', { count: 5, sources: [...] })
 */
export function emit(event, payload) {
  if (listeners[event]) {
    listeners[event].forEach(cb => {
      try { cb(payload) } catch (e) { logger.warn('[EventBus]', event, e) }
    })
  }
}

export function off(event, cb) {
  if (listeners[event]) {
    listeners[event] = listeners[event].filter(f => f !== cb)
  }
}
