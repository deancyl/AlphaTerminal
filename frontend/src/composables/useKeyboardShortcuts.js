/**
 * useKeyboardShortcuts.js — 全局键盘快捷键系统
 * 
 * Wind风格快捷键映射：
 * - 0: 全球市场概览
 * - 1: 沪深股票
 * - 5: 债券综合
 * - 6: 股指期货
 * - F6: 自选股
 * - F9: 深度资料
 * - ESC: 关闭弹窗/退出全屏
 * - / 或 Ctrl+K: 全局搜索
 * - Ctrl+数字: 切换视图
 */
import { ref, onMounted, onUnmounted } from 'vue'

// ── 快捷键配置表 ───────────────────────────────────────────────────
export const SHORTCUTS = [
  { key: '0',         ctrl: false, alt: false, shift: false, action: 'view',        param: 'stock',     description: '股票市场' },
  { key: '1',         ctrl: false, alt: false, shift: false, action: 'view',        param: 'stock',     description: '沪深股票' },
  { key: '5',         ctrl: false, alt: false, shift: false, action: 'view',        param: 'bond',      description: '债券综合' },
  { key: '6',         ctrl: false, alt: false, shift: false, action: 'view',        param: 'futures',   description: '股指期货' },
  { key: 'f6',        ctrl: false, alt: false, shift: false, action: 'view',        param: 'stock',     description: '自选股' },
  { key: 'f9',        ctrl: false, alt: false, shift: false, action: 'fullscreen',  param: null,        description: '深度资料' },
  { key: 'Escape',    ctrl: false, alt: false, shift: false, action: 'escape',      param: null,        description: '关闭/退出' },
  { key: '/',         ctrl: false, alt: false, shift: false, action: 'search',      param: null,        description: '全局搜索' },
  { key: 'k',         ctrl: true,  alt: false, shift: false, action: 'search',      param: null,        description: '全局搜索 (Ctrl+K)' },
  { key: 'b',         ctrl: true,  alt: false, shift: false, action: 'view',        param: 'bond',      description: '债券 (Ctrl+B)' },
  { key: 'f',         ctrl: true,  alt: false, shift: false, action: 'view',        param: 'fund',      description: '基金 (Ctrl+F)' },
  { key: 'p',         ctrl: true,  alt: false, shift: false, action: 'view',        param: 'portfolio', description: '组合 (Ctrl+P)' },
  { key: 'm',         ctrl: true,  alt: false, shift: false, action: 'view',        param: 'macro',     description: '宏观 (Ctrl+M)' },
  { key: 'r',         ctrl: true,  alt: false, shift: false, action: 'view',        param: 'backtest',  description: '回测 (Ctrl+R)' },
  { key: '?',         ctrl: false, alt: false, shift: true,  action: 'help',        param: null,        description: '快捷键帮助' },
]

// ── 当前激活的快捷键帮助面板状态 ──────────────────────────────────
const helpVisible = ref(false)

export function useKeyboardShortcuts(options = {}) {
  const {
    onViewChange = () => {},
    onSearch = () => {},
    onEscape = () => {},
    onFullscreen = () => {},
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
        onSearch()
        break
      case 'escape':
        // 如果帮助面板打开，先关闭它
        if (helpVisible.value) {
          helpVisible.value = false
        } else {
          onEscape()
        }
        break
      case 'fullscreen':
        onFullscreen()
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
    shortcuts: SHORTCUTS,
    showHelp: () => { helpVisible.value = true },
    hideHelp: () => { helpVisible.value = false }
  }
}
