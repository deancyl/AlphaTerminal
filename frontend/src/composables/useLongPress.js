/**
 * useLongPress — 长按交互 composable
 * 
 * v0.6.62: 移动端长按替代 PC 端 Hover
 * 解决移动端 Hover 状态穿透问题
 * 
 * 用法:
 *   const { isLongPressing, bindLongPress } = useLongPress()
 *   bindLongPress(elementRef, () => { showContextMenu() })
 */

import { ref, onMounted, onUnmounted } from 'vue'

const LONG_PRESS_DURATION = 500  // 500ms 触发长按
const TAP_THRESHOLD = 10         // 10px 移动阈值

export function useLongPress() {
  const isLongPressing = ref(false)
  let timer = null
  let startPos = { x: 0, y: 0 }

  function handleTouchStart(event, callback) {
    if (event.touches.length !== 1) return
    
    const touch = event.touches[0]
    startPos = { x: touch.clientX, y: touch.clientY }
    
    timer = setTimeout(() => {
      isLongPressing.value = true
      // 触发触觉反馈
      if (navigator.vibrate) {
        navigator.vibrate(50)
      }
      if (callback) {
        callback(event)
      }
    }, LONG_PRESS_DURATION)
  }

  function handleTouchMove(event) {
    if (!timer) return
    
    const touch = event.touches[0]
    const dx = Math.abs(touch.clientX - startPos.x)
    const dy = Math.abs(touch.clientY - startPos.y)
    
    // 如果移动超过阈值，取消长按
    if (dx > TAP_THRESHOLD || dy > TAP_THRESHOLD) {
      clearTimeout(timer)
      timer = null
      isLongPressing.value = false
    }
  }

  function handleTouchEnd() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    isLongPressing.value = false
  }

  function bindLongPress(elementRef, callback) {
    if (!elementRef.value) return
    
    const el = elementRef.value
    
    const startHandler = (e) => handleTouchStart(e, callback)
    const moveHandler = (e) => handleTouchMove(e)
    const endHandler = () => handleTouchEnd()
    
    el.addEventListener('touchstart', startHandler, { passive: true })
    el.addEventListener('touchmove', moveHandler, { passive: true })
    el.addEventListener('touchend', endHandler, { passive: true })
    el.addEventListener('touchcancel', endHandler, { passive: true })
    
    // 返回清理函数
    return () => {
      el.removeEventListener('touchstart', startHandler)
      el.removeEventListener('touchmove', moveHandler)
      el.removeEventListener('touchend', endHandler)
      el.removeEventListener('touchcancel', endHandler)
    }
  }

  return {
    isLongPressing,
    bindLongPress,
    LONG_PRESS_DURATION
  }
}

/**
 * 检测是否为触摸设备
 */
export function isTouchDevice() {
  return 'ontouchstart' in window || navigator.maxTouchPoints > 0
}

/**
 * 检测是否支持 Hover（PC 端）
 */
export function supportsHover() {
  return window.matchMedia('(hover: hover)').matches
}
