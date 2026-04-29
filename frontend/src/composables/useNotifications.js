/**
 * 浏览器通知管理
 * 处理通知权限申请、通知发送、预警规则管理
 */
import { ref, onMounted } from 'vue'

const NOTIFICATION_STORAGE_KEY = 'alphaterminal_alerts'

// 通知权限状态
export const notificationPermission = ref('default') // 'default' | 'granted' | 'denied'

// 预警规则列表
export const alertRules = ref([])

// 预警历史
export const alertHistory = ref([])

/**
 * 请求浏览器通知权限
 */
export async function requestNotificationPermission() {
  if (!('Notification' in window)) {
    console.warn('[Notifications] Browser does not support notifications')
    return false
  }

  try {
    const permission = await Notification.requestPermission()
    notificationPermission.value = permission
    return permission === 'granted'
  } catch (error) {
    console.error('[Notifications] Failed to request permission:', error)
    return false
  }
}

/**
 * 检查通知权限状态
 */
export function checkNotificationPermission() {
  if (!('Notification' in window)) {
    notificationPermission.value = 'denied'
    return false
  }
  
  notificationPermission.value = Notification.permission
  return Notification.permission === 'granted'
}

/**
 * 发送浏览器通知
 */
export function sendNotification(title, options = {}) {
  if (!checkNotificationPermission()) {
    console.warn('[Notifications] Permission not granted')
    return false
  }

  try {
    const notification = new Notification(title, {
      icon: '/favicon.ico',
      badge: '/favicon.ico',
      tag: options.tag || 'alphaterminal-alert',
      requireInteraction: options.requireInteraction || false,
      ...options
    })

    // 点击通知时聚焦窗口
    notification.onclick = () => {
      window.focus()
      notification.close()
    }

    return true
  } catch (error) {
    console.error('[Notifications] Failed to send notification:', error)
    return false
  }
}

/**
 * 从 localStorage 加载预警规则
 */
export function loadAlertRules() {
  try {
    const stored = localStorage.getItem(NOTIFICATION_STORAGE_KEY)
    if (stored) {
      alertRules.value = JSON.parse(stored)
    }
  } catch (error) {
    console.error('[Notifications] Failed to load alert rules:', error)
    alertRules.value = []
  }
}

/**
 * 保存预警规则到 localStorage
 */
export function saveAlertRules() {
  try {
    localStorage.setItem(NOTIFICATION_STORAGE_KEY, JSON.stringify(alertRules.value))
  } catch (error) {
    console.error('[Notifications] Failed to save alert rules:', error)
  }
}

/**
 * 添加预警规则
 */
export function addAlertRule(rule) {
  const newRule = {
    id: Date.now().toString(),
    enabled: true,
    createdAt: new Date().toISOString(),
    triggeredAt: null,
    triggerCount: 0,
    ...rule
  }
  
  alertRules.value.push(newRule)
  saveAlertRules()
  return newRule
}

/**
 * 删除预警规则
 */
export function removeAlertRule(ruleId) {
  alertRules.value = alertRules.value.filter(r => r.id !== ruleId)
  saveAlertRules()
}

/**
 * 更新预警规则
 */
export function updateAlertRule(ruleId, updates) {
  const index = alertRules.value.findIndex(r => r.id === ruleId)
  if (index !== -1) {
    alertRules.value[index] = { ...alertRules.value[index], ...updates }
    saveAlertRules()
  }
}

/**
 * 启用/禁用预警规则
 */
export function toggleAlertRule(ruleId) {
  const rule = alertRules.value.find(r => r.id === ruleId)
  if (rule) {
    rule.enabled = !rule.enabled
    saveAlertRules()
  }
}

/**
 * 记录预警触发历史
 */
export function recordAlertTrigger(rule, price) {
  const record = {
    id: Date.now().toString(),
    ruleId: rule.id,
    symbol: rule.symbol,
    condition: rule.condition,
    targetPrice: rule.targetPrice,
    triggeredPrice: price,
    triggeredAt: new Date().toISOString()
  }
  
  alertHistory.value.unshift(record)
  
  // 只保留最近100条记录
  if (alertHistory.value.length > 100) {
    alertHistory.value = alertHistory.value.slice(0, 100)
  }
  
  // 更新规则触发信息
  const ruleIndex = alertRules.value.findIndex(r => r.id === rule.id)
  if (ruleIndex !== -1) {
    alertRules.value[ruleIndex].triggeredAt = record.triggeredAt
    alertRules.value[ruleIndex].triggerCount++
    saveAlertRules()
  }
  
  // 保存历史到 localStorage
  try {
    localStorage.setItem('alphaterminal_alert_history', JSON.stringify(alertHistory.value))
  } catch (error) {
    console.error('[Notifications] Failed to save alert history:', error)
  }
}

/**
 * 加载预警历史
 */
export function loadAlertHistory() {
  try {
    const stored = localStorage.getItem('alphaterminal_alert_history')
    if (stored) {
      alertHistory.value = JSON.parse(stored)
    }
  } catch (error) {
    console.error('[Notifications] Failed to load alert history:', error)
    alertHistory.value = []
  }
}

/**
 * 检查价格是否触发预警
 */
export function checkPriceAlerts(symbol, price) {
  const triggered = []
  
  for (const rule of alertRules.value) {
    if (!rule.enabled || rule.symbol !== symbol) continue
    
    let shouldTrigger = false
    
    switch (rule.condition) {
      case 'above':
        shouldTrigger = price >= rule.targetPrice
        break
      case 'below':
        shouldTrigger = price <= rule.targetPrice
        break
      case 'equals':
        shouldTrigger = Math.abs(price - rule.targetPrice) < 0.01
        break
    }
    
    if (shouldTrigger) {
      // 检查是否已经触发过（避免重复通知）
      const lastTriggered = rule.triggeredAt ? new Date(rule.triggeredAt) : null
      const now = new Date()
      
      // 如果5分钟内已经触发过，不再重复通知
      if (lastTriggered && (now - lastTriggered) < 5 * 60 * 1000) {
        continue
      }
      
      triggered.push({ rule, price })
    }
  }
  
  return triggered
}

/**
 * 初始化通知系统
 */
export function initNotifications() {
  onMounted(() => {
    checkNotificationPermission()
    loadAlertRules()
    loadAlertHistory()
  })
}

/**
 * 格式化预警条件文本
 */
export function formatAlertCondition(rule) {
  const conditionMap = {
    'above': '高于',
    'below': '低于',
    'equals': '等于'
  }
  
  return `${rule.symbol} 价格${conditionMap[rule.condition] || rule.condition} ¥${rule.targetPrice}`
}
