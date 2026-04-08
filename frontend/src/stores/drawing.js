import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

/**
 * 画线工具状态管理 Store
 * 
 * 管理画线工具的全局状态，支持跨组件共享
 */
export const useDrawingStore = defineStore('drawing', () => {
  // ========== State ==========
  
  /** 当前激活的画线工具 */
  const activeTool = ref('')
  
  /** 当前画线颜色 */
  const activeColor = ref('#fbbf24')
  
  /** 磁吸模式开关 */
  const magnetMode = ref(true)
  
  /** 画线层可见性 */
  const visible = ref(true)
  
  /** 画线层锁定状态 */
  const locked = ref(false)
  
  /** 预设颜色列表 */
  const presetColors = [
    '#fbbf24', '#ef4444', '#22c55e', '#3b82f6', '#a855f7',
    '#f97316', '#ec4899', '#14b8a6', '#94a3b8', '#ffffff',
  ]
  
  /** 工具定义列表 */
  const tools = [
    { key: 'trend',   label: '趋势线',   shortcut: 'T', desc: '带箭头的趋势线' },
    { key: 'line',    label: '直线',     shortcut: 'L', desc: '双向无限延伸' },
    { key: 'ray',     label: '射线',     shortcut: 'R', desc: '单向延伸' },
    { key: 'segment', label: '线段',     shortcut: 'S', desc: '固定长度' },
    { key: 'hray',    label: '水平线',   shortcut: 'H', desc: '带价格标签' },
    { key: 'vline',   label: '垂直线',   shortcut: 'V', desc: '带日期标签' },
    { key: 'channel', label: '平行通道', shortcut: 'C', desc: '上轨/中轨/下轨' },
    { key: 'fib',     label: '斐波那契', shortcut: 'F', desc: '黄金分割线' },
    { key: 'rect',    label: '矩形',     shortcut: 'Q', desc: '填充半透明' },
    { key: 'circle',  label: '圆形',     shortcut: 'O', desc: '圆心+半径' },
    { key: 'text',    label: '文本',     shortcut: 'A', desc: '文字标注' },
  ]
  
  // ========== Getters ==========
  
  /** 当前激活的工具信息 */
  const currentTool = computed(() => {
    return tools.find(t => t.key === activeTool.value) || null
  })
  
  /** 是否正在画线中 */
  const isDrawing = computed(() => activeTool.value !== '')
  
  /** 是否可以操作 */
  const canInteract = computed(() => visible.value && !locked.value)
  
  // ========== Actions ==========
  
  /**
   * 设置当前激活的工具
   * @param {string} tool - 工具key，为空字符串时取消选择
   */
  function setTool(tool) {
    activeTool.value = tool
  }
  
  /**
   * 切换工具（如果已选中则取消）
   * @param {string} tool - 工具key
   */
  function toggleTool(tool) {
    activeTool.value = activeTool.value === tool ? '' : tool
  }
  
  /**
   * 设置画线颜色
   * @param {string} color - 颜色值
   */
  function setColor(color) {
    activeColor.value = color
  }
  
  /**
   * 切换磁吸模式
   */
  function toggleMagnet() {
    magnetMode.value = !magnetMode.value
  }
  
  /**
   * 切换画线层可见性
   */
  function toggleVisible() {
    visible.value = !visible.value
  }
  
  /**
   * 切换画线层锁定状态
   */
  function toggleLocked() {
    locked.value = !locked.value
  }
  
  /**
   * 重置所有状态
   */
  function reset() {
    activeTool.value = ''
    activeColor.value = '#fbbf24'
    magnetMode.value = true
    visible.value = true
    locked.value = false
  }
  
  /**
   * 根据快捷键获取工具
   * @param {string} key - 快捷键字符
   * @returns {object|null}
   */
  function getToolByShortcut(key) {
    return tools.find(t => t.shortcut.toLowerCase() === key.toLowerCase()) || null
  }
  
  return {
    // State
    activeTool,
    activeColor,
    magnetMode,
    visible,
    locked,
    presetColors,
    tools,
    
    // Getters
    currentTool,
    isDrawing,
    canInteract,
    
    // Actions
    setTool,
    toggleTool,
    setColor,
    toggleMagnet,
    toggleVisible,
    toggleLocked,
    reset,
    getToolByShortcut,
  }
})
