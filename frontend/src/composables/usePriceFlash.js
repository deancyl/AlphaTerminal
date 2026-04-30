/**
 * usePriceFlash.js — 价格刷新闪烁动画
 * 
 * 在价格变化时自动添加闪烁CSS类，300ms后移除
 * 
 * 使用方式：
 *   const { flashClass, triggerFlash } = usePriceFlash()
 *   // 价格更新时：
 *   triggerFlash(newPrice, oldPrice)
 *   // 模板中：
 *   <span :class="flashClass">{{ price }}</span>
 */
import { ref } from 'vue'

export function usePriceFlash() {
  const flashClass = ref('')
  let flashTimer = null
  
  function triggerFlash(newPrice, oldPrice) {
    if (oldPrice === undefined || oldPrice === null || oldPrice === 0) {
      flashClass.value = ''
      return
    }
    
    if (newPrice > oldPrice) {
      flashClass.value = 'price-flash-up'
    } else if (newPrice < oldPrice) {
      flashClass.value = 'price-flash-down'
    } else {
      flashClass.value = ''
      return
    }
    
    // 清除之前的定时器
    if (flashTimer) clearTimeout(flashTimer)
    
    // 300ms后移除闪烁类
    flashTimer = setTimeout(() => {
      flashClass.value = ''
    }, 300)
  }
  
  function clearFlash() {
    flashClass.value = ''
    if (flashTimer) {
      clearTimeout(flashTimer)
      flashTimer = null
    }
  }
  
  return {
    flashClass,
    triggerFlash,
    clearFlash
  }
}
