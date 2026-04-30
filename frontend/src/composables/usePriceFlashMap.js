/**
 * usePriceFlashMap.js — 列表价格刷新闪烁动画
 * 
 * 适用于股票列表、行情表格等场景
 * 为每个symbol独立跟踪价格变化
 * 
 * 使用方式：
 *   const { getFlashClass, updatePrice } = usePriceFlashMap()
 *   // 数据更新时：
 *   items.forEach(item => updatePrice(item.symbol, item.price))
 *   // 模板中：
 *   <span :class="getFlashClass(item.symbol)">{{ item.price }}</span>
 */
import { ref } from 'vue'

export function usePriceFlashMap() {
  const flashMap = ref(new Map())
  const priceMap = ref(new Map())
  const timers = new Map()
  
  function updatePrice(symbol, newPrice) {
    if (!symbol || newPrice === undefined || newPrice === null) return
    
    const oldPrice = priceMap.value.get(symbol)
    priceMap.value.set(symbol, newPrice)
    
    if (oldPrice === undefined || oldPrice === null || oldPrice === 0) {
      flashMap.value.set(symbol, '')
      return
    }
    
    let flashClass = ''
    if (newPrice > oldPrice) {
      flashClass = 'price-flash-up'
    } else if (newPrice < oldPrice) {
      flashClass = 'price-flash-down'
    } else {
      flashMap.value.set(symbol, '')
      return
    }
    
    flashMap.value.set(symbol, flashClass)
    
    // 清除之前的定时器
    if (timers.has(symbol)) {
      clearTimeout(timers.get(symbol))
    }
    
    // 300ms后移除闪烁类
    const timer = setTimeout(() => {
      flashMap.value.set(symbol, '')
      timers.delete(symbol)
    }, 300)
    
    timers.set(symbol, timer)
  }
  
  function getFlashClass(symbol) {
    return flashMap.value.get(symbol) || ''
  }
  
  function clearAll() {
    flashMap.value.clear()
    priceMap.value.clear()
    timers.forEach(timer => clearTimeout(timer))
    timers.clear()
  }
  
  return {
    getFlashClass,
    updatePrice,
    clearAll
  }
}
