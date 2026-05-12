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
  
  // 视图切换（Ctrl+字母）
  { key: 'o',         ctrl: true,  alt: false, shift: false, action: 'view',        param: 'options',   description: '期权分析', category: '视图切换' },
  { key: 'g',         ctrl: true,  alt: false, shift: false, action: 'view',        param: 'global-index', description: '全球指数', category: '视图切换' },
  { key: 'b',         ctrl: true,  alt: false, shift: false, action: 'view',        param: 'bond',      description: '债券综合', category: '视图切换' },
  { key: 'm',         ctrl: true,  alt: false, shift: false, action: 'view',        param: 'macro',     description: '宏观经济', category: '视图切换' },
  { key: 'p',         ctrl: true,  alt: false, shift: false, action: 'view',        param: 'portfolio', description: '投资组合', category: '视图切换' },
  { key: 'f',         ctrl: true,  alt: false, shift: false, action: 'view',        param: 'fund',      description: '基金分析', category: '视图切换' },
  { key: 'r',         ctrl: true,  alt: false, shift: false, action: 'view',        param: 'backtest',  description: '回测实验室', category: '视图切换' },
  
  // 视图切换（Ctrl+Shift+字母 - 管理功能）
  { key: 'a',         ctrl: true,  alt: false, shift: true,  action: 'view',        param: 'admin',     description: '系统管理', category: '管理功能' },
  { key: 't',         ctrl: true,  alt: false, shift: true,  action: 'view',        param: 'agent_tokens', description: 'API Token管理', category: '管理功能' },
  { key: 'm',         ctrl: true,  alt: false, shift: true,  action: 'view',        param: 'mcp',       description: 'AI工具配置', category: '管理功能' },
  { key: 's',         ctrl: true,  alt: false, shift: true,  action: 'view',        param: 'strategy-center', description: '策略中心', category: '管理功能' },
  
  // 功能键
  { key: 'f1',        ctrl: false, alt: false, shift: false, action: 'help',        param: null,        description: '帮助文档', category: '功能' },
  { key: 'f2',        ctrl: false, alt: false, shift: false, action: 'rename',      param: null,        description: '重命名', category: '功能' },
  { key: 'f3',        ctrl: false, alt: false, shift: false, action: 'view',        param: 'stock',     description: '上证指数', category: '功能' },
  { key: 'f4',        ctrl: false, alt: false, shift: false, action: 'view',        param: 'stock',     description: '深证成指', category: '功能' },
  { key: 'f5',        ctrl: false, alt: false, shift: false, action: 'refresh',     param: null,        description: '刷新数据', category: '功能' },
  { key: 'f6',        ctrl: false, alt: false, shift: false, action: 'watchlist',   param: null,        description: '自选股', category: '功能' },
  { key: 'f7',        ctrl: false, alt: false, shift: false, action: 'screener',    param: null,        description: '条件选股', category: '功能' },
  { key: 'f8',        ctrl: false, alt: false, shift: false, action: 'view',        param: 'backtest',  description: '回测实验室', category: '功能' },
  { key: 'f9',        ctrl: false, alt: false, shift: false, action: 'deep-info',   param: null,        description: '深度资料', category: '功能' },
  { key: 'f10',       ctrl: false, alt: false, shift: false, action: 'view',        param: 'admin',     description: '系统管理', category: '功能' },
  { key: 'f11',       ctrl: false, alt: false, shift: false, action: 'fullscreen',  param: null,        description: '全屏切换', category: '功能' },
  { key: 'f12',       ctrl: false, alt: false, shift: false, action: 'dev-tools',   param: null,        description: '开发者工具', category: '功能' },
  
  // 导航与搜索
  { key: '/',         ctrl: false, alt: false, shift: false, action: 'search',      param: null,        description: '全局搜索/键盘精灵', category: '导航' },
  { key: 'k',         ctrl: true,  alt: false, shift: false, action: 'search',      param: null,        description: '全局搜索/键盘精灵', category: '导航' },
  { key: '?',         ctrl: false, alt: false, shift: true,  action: 'help',        param: null,        description: '快捷键帮助', category: '系统' },
  { key: 'Escape',    ctrl: false, alt: false, shift: false, action: 'escape',      param: null,        description: '关闭弹窗/退出全屏', category: '系统' },
  
  // 系统功能
  { key: ',',         ctrl: true,  alt: false, shift: false, action: 'settings',    param: null,        description: '系统设置', category: '系统' },
  { key: 'd',         ctrl: true,  alt: false, shift: true,  action: 'toggle-theme',param: null,        description: '切换深色/浅色模式', category: '系统' },
  
  // 快速操作（Alt+数字）
  { key: '1',         ctrl: false, alt: true,  shift: false, action: 'quick-action',param: 'buy',        description: '快速买入', category: '快速操作' },
  { key: '2',         ctrl: false, alt: true,  shift: false, action: 'quick-action',param: 'sell',       description: '快速卖出', category: '快速操作' },
  { key: '3',         ctrl: false, alt: true,  shift: false, action: 'quick-action',param: 'alert',      description: '设置预警', category: '快速操作' },
  { key: '4',         ctrl: false, alt: true,  shift: false, action: 'quick-action',param: 'note',       description: '添加笔记', category: '快速操作' },
  
  // 数据操作
  { key: 'e',         ctrl: true,  alt: false, shift: false, action: 'export',      param: null,        description: '导出数据', category: '数据' },
  { key: 'i',         ctrl: true,  alt: false, shift: false, action: 'import',      param: null,        description: '导入数据', category: '数据' },
  { key: 's',         ctrl: true,  alt: false, shift: false, action: 'save',        param: null,        description: '保存', category: '数据' },
  { key: 'n',         ctrl: true,  alt: false, shift: false, action: 'new',         param: null,        description: '新建', category: '数据' },
  
  // 编辑操作
  { key: 'z',         ctrl: true,  alt: false, shift: false, action: 'undo',        param: null,        description: '撤销', category: '编辑' },
  { key: 'z',         ctrl: true,  alt: false, shift: true,  action: 'redo',        param: null,        description: '重做', category: '编辑' },
  { key: 'y',         ctrl: true,  alt: false, shift: false, action: 'redo',        param: null,        description: '重做', category: '编辑' },
  { key: 'Delete',    ctrl: false, alt: false, shift: false, action: 'delete',      param: null,        description: '删除', category: '编辑' },
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
