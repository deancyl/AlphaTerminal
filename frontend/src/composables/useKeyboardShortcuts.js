/**
 * useKeyboardShortcuts.js — 全局键盘快捷键系统
 * 
 * Wind风格快捷键映射：
 * - 0-9: 视图切换
 * - F1-F12: 功能键
 * - ESC: 关闭弹窗/退出全屏
 * - / 或 Ctrl+K: 全局搜索
 * - ?: 快捷键帮助
 */
import { ref, onMounted, onUnmounted } from 'vue'

// ── 快捷键配置表 ───────────────────────────────────────────────────
export const SHORTCUTS = [
  // 视图切换（数字键 0-9）
  { key: '0',         ctrl: false, alt: false, shift: false, action: 'view',        param: 'stock',     description: '全球市场概览', category: '视图切换' },
  { key: '1',         ctrl: false, alt: false, shift: false, action: 'view',        param: 'stock',     description: '沪深股票', category: '视图切换' },
  { key: '2',         ctrl: false, alt: false, shift: false, action: 'view',        param: 'stock',     description: '港股市场', category: '视图切换' },
  { key: '3',         ctrl: false, alt: false, shift: false, action: 'view',        param: 'stock',     description: '美股市场', category: '视图切换' },
  { key: '4',         ctrl: false, alt: false, shift: false, action: 'view',        param: 'fund',      description: '基金市场', category: '视图切换' },
  { key: '5',         ctrl: false, alt: false, shift: false, action: 'view',        param: 'bond',      description: '债券综合', category: '视图切换' },
  { key: '6',         ctrl: false, alt: false, shift: false, action: 'view',        param: 'futures',   description: '股指期货', category: '视图切换' },
  { key: '7',         ctrl: false, alt: false, shift: false, action: 'view',        param: 'macro',     description: '宏观经济', category: '视图切换' },
  { key: '8',         ctrl: false, alt: false, shift: false, action: 'view',        param: 'portfolio', description: '组合管理', category: '视图切换' },
  { key: '9',         ctrl: false, alt: false, shift: false, action: 'view',        param: 'backtest',  description: '回测实验室', category: '视图切换' },
  
  // 功能键
  { key: 'f1',        ctrl: false, alt: false, shift: false, action: 'help',        param: null,        description: '帮助文档', category: '功能' },
  { key: 'f5',        ctrl: false, alt: false, shift: false, action: 'refresh',     param: null,        description: '刷新数据', category: '功能' },
  { key: 'f6',        ctrl: false, alt: false, shift: false, action: 'watchlist',   param: null,        description: '自选股', category: '功能' },
  { key: 'f9',        ctrl: false, alt: false, shift: false, action: 'deep-info',   param: null,        description: '深度资料（预留）', category: '功能' },
  { key: 'f11',       ctrl: false, alt: false, shift: false, action: 'fullscreen',  param: null,        description: '全屏切换', category: '功能' },
  
  // 导航与搜索
  { key: '/',         ctrl: false, alt: false, shift: false, action: 'search',      param: null,        description: '全局搜索/键盘精灵', category: '导航' },
  { key: 'k',         ctrl: true,  alt: false, shift: false, action: 'search',      param: null,        description: '全局搜索/键盘精灵', category: '导航' },
  { key: '?',         ctrl: false, alt: false, shift: true,  action: 'help',        param: null,        description: '快捷键帮助', category: '系统' },
  { key: 'Escape',    ctrl: false, alt: false, shift: false, action: 'escape',      param: null,        description: '关闭弹窗/退出全屏', category: '系统' },
  
  // 系统功能
  { key: ',',         ctrl: true,  alt: false, shift: false, action: 'settings',    param: null,        description: '系统设置', category: '系统' },
  { key: 'd',         ctrl: true,  alt: false, shift: true,  action: 'toggle-theme',param: null,        description: '切换深色/浅色模式', category: '系统' },
]

// ── 当前激活的快捷键帮助面板状态 ──────────────────────────────────
const helpVisible = ref(false)
const searchVisible = ref(false)

export function useKeyboardShortcuts(options = {}) {
  const {
    onViewChange = () => {},
    onSearch = () => {},
    onEscape = () => {},
    onFullscreen = () => {},
    onRefresh = () => {},
    onWatchlist = () => {},
    onSettings = () => {},
    onToggleTheme = () => {},
    enabled = true
  } = options

  function handleKeydown(event) {
    if (!enabled) return

    // 忽略输入框中的快捷键
    const target = event.target
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
      // 但允许 Escape 和 Ctrl+K
      if (event.key !== 'Escape' && !(event.ctrlKey && event.key === 'k')) {
        return
      }
    }

    // 匹配快捷键
    const key = event.key.toLowerCase()
    const matched = SHORTCUTS.find(s => {
      if (s.key.toLowerCase() !== key) return false
      if (s.ctrl !== event.ctrlKey) return false
      if (s.alt !== event.altKey) return false
      if (s.shift !== event.shiftKey) return false
      return true
    })

    if (!matched) return

    // 阻止默认行为
    event.preventDefault()
    event.stopPropagation()

    // 执行动作
    switch (matched.action) {
      case 'view':
        onViewChange(matched.param)
        break
      case 'search':
        searchVisible.value = true
        onSearch()
        break
      case 'escape':
        // 优先级：搜索面板 > 帮助面板 > 其他弹窗
        if (searchVisible.value) {
          searchVisible.value = false
        } else if (helpVisible.value) {
          helpVisible.value = false
        } else {
          onEscape()
        }
        break
      case 'fullscreen':
        onFullscreen()
        break
      case 'refresh':
        onRefresh()
        break
      case 'watchlist':
        onWatchlist()
        break
      case 'deep-info':
        // F9 深度资料
        onViewChange('f9')
        break
      case 'settings':
        onSettings()
        break
      case 'toggle-theme':
        onToggleTheme()
        break
      case 'help':
        helpVisible.value = !helpVisible.value
        break
    }
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeydown)
  })

  return {
    helpVisible,
    searchVisible,
    shortcuts: SHORTCUTS,
    showHelp: () => { helpVisible.value = true },
    hideHelp: () => { helpVisible.value = false },
    showSearch: () => { searchVisible.value = true },
    hideSearch: () => { searchVisible.value = false }
  }
}
