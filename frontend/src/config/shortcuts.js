/**
 * 全局快捷键配置
 * 参考 Wind 终端快捷键体系
 */

export const SHORTCUT_CATEGORIES = {
  VIEW: '视图切换',
  NAVIGATION: '导航',
  FUNCTION: '功能',
  SYSTEM: '系统',
}

/**
 * 快捷键映射表
 * key: 快捷键组合（支持 Ctrl/Alt/Shift 修饰符）
 * action: 动作标识符
 * description: 描述
 * category: 分类
 */
export const SHORTCUTS = [
  // ── 视图切换（数字键 0-9）──────────────────────────────────
  {
    key: '0',
    action: 'view:global-market',
    description: '全球市场概览',
    category: SHORTCUT_CATEGORIES.VIEW,
  },
  {
    key: '1',
    action: 'view:a-share',
    description: '沪深股票',
    category: SHORTCUT_CATEGORIES.VIEW,
  },
  {
    key: '2',
    action: 'view:hk-stock',
    description: '港股市场',
    category: SHORTCUT_CATEGORIES.VIEW,
  },
  {
    key: '3',
    action: 'view:us-stock',
    description: '美股市场',
    category: SHORTCUT_CATEGORIES.VIEW,
  },
  {
    key: '4',
    action: 'view:fund',
    description: '基金市场',
    category: SHORTCUT_CATEGORIES.VIEW,
  },
  {
    key: '5',
    action: 'view:bond',
    description: '债券综合',
    category: SHORTCUT_CATEGORIES.VIEW,
  },
  {
    key: '6',
    action: 'view:futures',
    description: '股指期货',
    category: SHORTCUT_CATEGORIES.VIEW,
  },
  {
    key: '7',
    action: 'view:macro',
    description: '宏观经济',
    category: SHORTCUT_CATEGORIES.VIEW,
  },
  {
    key: '8',
    action: 'view:portfolio',
    description: '组合管理',
    category: SHORTCUT_CATEGORIES.VIEW,
  },
  {
    key: '9',
    action: 'view:backtest',
    description: '回测实验室',
    category: SHORTCUT_CATEGORIES.VIEW,
  },

  // ── 功能键（F1-F12）────────────────────────────────────────
  {
    key: 'F1',
    action: 'help',
    description: '帮助文档',
    category: SHORTCUT_CATEGORIES.SYSTEM,
  },
  {
    key: 'F5',
    action: 'refresh',
    description: '刷新数据',
    category: SHORTCUT_CATEGORIES.FUNCTION,
  },
  {
    key: 'F6',
    action: 'watchlist',
    description: '自选股',
    category: SHORTCUT_CATEGORIES.FUNCTION,
  },
  {
    key: 'F9',
    action: 'deep-info',
    description: '深度资料（预留）',
    category: SHORTCUT_CATEGORIES.FUNCTION,
  },
  {
    key: 'F11',
    action: 'fullscreen',
    description: '全屏切换',
    category: SHORTCUT_CATEGORIES.SYSTEM,
  },

  // ── 导航与搜索────────────────────────────────────────────
  {
    key: '/',
    action: 'search',
    description: '全局搜索/键盘精灵',
    category: SHORTCUT_CATEGORIES.NAVIGATION,
  },
  {
    key: 'Ctrl+K',
    action: 'search',
    description: '全局搜索/键盘精灵',
    category: SHORTCUT_CATEGORIES.NAVIGATION,
  },
  {
    key: '?',
    action: 'shortcuts-help',
    description: '快捷键帮助',
    category: SHORTCUT_CATEGORIES.SYSTEM,
  },
  {
    key: 'Escape',
    action: 'close-modal',
    description: '关闭弹窗/退出全屏',
    category: SHORTCUT_CATEGORIES.SYSTEM,
  },

  // ── 系统功能────────────────────────────────────────────────
  {
    key: 'Ctrl+,',
    action: 'settings',
    description: '系统设置',
    category: SHORTCUT_CATEGORIES.SYSTEM,
  },
  {
    key: 'Ctrl+Shift+D',
    action: 'toggle-theme',
    description: '切换深色/浅色模式',
    category: SHORTCUT_CATEGORIES.SYSTEM,
  },
]

/**
 * 键盘精灵命令映射
 * 用户输入命令后跳转到对应功能
 */
export const KEYBOARD_GENIE_COMMANDS = {
  // Wind 风格命令
  'F5': { action: 'view:quote', description: '个股行情页' },
  'F9': { action: 'view:deep-info', description: '深度资料' },
  'WQ': { action: 'view:bond-quote', description: '债券报价' },
  'BBQ': { action: 'view:broker-quote', description: '经纪商行情' },
  'EDB': { action: 'view:macro', description: '经济数据库' },
  'PMS': { action: 'view:portfolio', description: '组合管理系统' },
  'NEWS': { action: 'view:news', description: '新闻资讯' },
  'RPP': { action: 'view:research', description: '研报平台' },
  
  // 中文命令
  '自选': { action: 'watchlist', description: '自选股' },
  '组合': { action: 'view:portfolio', description: '组合管理' },
  '回测': { action: 'view:backtest', description: '回测实验室' },
  '新闻': { action: 'view:news', description: '新闻资讯' },
  '债券': { action: 'view:bond', description: '债券市场' },
  '基金': { action: 'view:fund', description: '基金市场' },
  '期货': { action: 'view:futures', description: '期货市场' },
  '宏观': { action: 'view:macro', description: '宏观经济' },
  '设置': { action: 'settings', description: '系统设置' },
  '帮助': { action: 'help', description: '帮助文档' },
}

/**
 * 构建快捷键索引（用于快速查找）
 */
export function buildShortcutIndex() {
  const index = new Map()
  SHORTCUTS.forEach(shortcut => {
    const normalizedKey = normalizeShortcutKey(shortcut.key)
    index.set(normalizedKey, shortcut)
  })
  return index
}

/**
 * 标准化快捷键字符串
 * 例如: "ctrl+k" -> "Control+k", "?" -> "?"
 */
export function normalizeShortcutKey(key) {
  const parts = key.split('+').map(p => p.trim())
  const modifiers = []
  let mainKey = ''
  
  parts.forEach(part => {
    const lower = part.toLowerCase()
    if (lower === 'ctrl' || lower === 'control') {
      modifiers.push('Control')
    } else if (lower === 'alt') {
      modifiers.push('Alt')
    } else if (lower === 'shift') {
      modifiers.push('Shift')
    } else if (lower === 'meta' || lower === 'cmd') {
      modifiers.push('Meta')
    } else {
      mainKey = part
    }
  })
  
  // 按固定顺序排列修饰符: Control > Alt > Shift > Meta
  const order = ['Control', 'Alt', 'Shift', 'Meta']
  modifiers.sort((a, b) => order.indexOf(a) - order.indexOf(b))
  
  return modifiers.length > 0 ? `${modifiers.join('+')}+${mainKey}` : mainKey
}

/**
 * 从键盘事件生成快捷键字符串
 */
export function getShortcutFromEvent(event) {
  const modifiers = []
  if (event.ctrlKey || event.metaKey) modifiers.push('Control')
  if (event.altKey) modifiers.push('Alt')
  if (event.shiftKey) modifiers.push('Shift')
  
  let key = event.key
  
  // 特殊键映射
  if (key === ' ') key = 'Space'
  if (key === 'Esc') key = 'Escape'
  
  // F键保持大写
  if (/^F\d+$/.test(key)) {
    key = key.toUpperCase()
  }
  
  return modifiers.length > 0 ? `${modifiers.join('+')}+${key}` : key
}

/**
 * 检查是否应该忽略快捷键（在输入框中）
 */
export function shouldIgnoreShortcut(event) {
  const target = event.target
  const tagName = target.tagName.toLowerCase()
  
  // 在输入框、文本域、可编辑元素中忽略大部分快捷键
  if (tagName === 'input' || tagName === 'textarea' || target.isContentEditable) {
    // 但允许 Escape 和 Ctrl+K
    if (event.key === 'Escape') return false
    if ((event.ctrlKey || event.metaKey) && event.key === 'k') return false
    return true
  }
  
  return false
}

export default {
  SHORTCUTS,
  SHORTCUT_CATEGORIES,
  KEYBOARD_GENIE_COMMANDS,
  buildShortcutIndex,
  normalizeShortcutKey,
  getShortcutFromEvent,
  shouldIgnoreShortcut,
}
