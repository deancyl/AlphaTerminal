/**
 * useDrawingStorage.js — DrawingCanvas 持久化
 * 
 * 负责：
 * - localforage 存储管理
 * - 图形数据保存/加载
 * - XSS 防护
 */
import localforage from 'localforage'
import { logger } from '../utils/logger.js'

/**
 * 存储管理 composable
 */
export function useDrawingStorage() {
  const storage = localforage.createInstance({ name: 'AlphaTerminal', storeName: 'drawings_v3' })

  // ═══════════════════════════════════════════════════════════════
  // XSS 防护
  // ═══════════════════════════════════════════════════════════════
  function escapeHtml(text) {
    if (!text || typeof text !== 'string') return text
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
  }

  function sanitizeText(text) {
    if (!text || typeof text !== 'string') return ''
    const maxLength = 100
    let sanitized = text.slice(0, maxLength)
    sanitized = sanitized.replace(/[\x00-\x1F\x7F]/g, '')
    return escapeHtml(sanitized)
  }

  // ═══════════════════════════════════════════════════════════════
  // 存储 API
  // ═══════════════════════════════════════════════════════════════
  async function saveToStorage(symbol, period, shapes) {
    try {
      const key = `${symbol}_${period}`
      await storage.setItem(key, JSON.stringify(shapes))
    } catch (e) { 
      logger.error('保存画线失败:', e) 
    }
  }

  async function loadFromStorage(symbol, period) {
    try {
      const key = `${symbol}_${period}`
      const raw = await storage.getItem(key)
      if (raw) {
        return JSON.parse(raw)
      } else {
        return await loadFromOtherPeriods(symbol)
      }
    } catch (e) {
      return []
    }
  }

  async function loadFromOtherPeriods(symbol) {
    try {
      const allKeys = await storage.keys()
      const symbolKeys = allKeys.filter(k => k.startsWith(`${symbol}_`))
      
      if (symbolKeys.length === 0) return []
      
      const allShapes = []
      for (const key of symbolKeys) {
        const raw = await storage.getItem(key)
        if (raw) allShapes.push(...JSON.parse(raw))
      }
      
      const seen = new Set()
      return allShapes.filter(s => {
        if (seen.has(s.id)) return false
        seen.add(s.id)
        return true
      })
    } catch (e) {
      logger.error('[DrawingCanvas] filter error:', e.message)
      return []
    }
  }

  async function clearStorage(symbol, period) {
    try {
      const key = `${symbol}_${period}`
      await storage.removeItem(key)
    } catch (e) {
      logger.error('清除画线失败:', e)
    }
  }

  return {
    escapeHtml,
    sanitizeText,
    saveToStorage,
    loadFromStorage,
    loadFromOtherPeriods,
    clearStorage,
  }
}
