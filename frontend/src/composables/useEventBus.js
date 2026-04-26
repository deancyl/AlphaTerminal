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
 * @returns {Array<Error>} 收集所有 listener 抛出的错误（空数组表示全部成功）
 */
export function emit(event, payload) {
  const errors = []
  if (listeners[event]) {
    listeners[event].forEach(cb => {
      try { 
        cb(payload) 
      } catch (e) { 
        logger.warn('[EventBus] listener error:', event, e)
        errors.push(e)
      }
    })
  }
  return errors  // 返回错误数组，调用方可据此判断是否有失败
}

export function off(event, cb) {
  if (listeners[event]) {
    listeners[event] = listeners[event].filter(f => f !== cb)
  }
}
