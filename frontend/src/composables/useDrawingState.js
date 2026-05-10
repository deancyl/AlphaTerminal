/**
 * useDrawingState.js — DrawingCanvas 状态管理
 * 
 * 负责：
 * - shapes 数据管理
 * - undo/redo 历史
 * - 选中/悬停状态
 * - 绘制中状态
 * - 拖拽状态
 */
import { ref } from 'vue'

// ═══════════════════════════════════════════════════════════════
// 状态机：三种互斥状态
// ═══════════════════════════════════════════════════════════════
export const DrawState = {
  IDLE:    'IDLE',    // 空闲/选择模式
  DRAWING: 'DRAWING', // 正在绘制新图形
  EDITING: 'EDITING', // 正在编辑文字
}

const MAX_HISTORY = 50

/**
 * 绘图状态管理 composable
 */
export function useDrawingState() {
  // ── 核心状态 ──
  const currentState = ref(DrawState.IDLE)
  const shapes = ref([])
  const drawing = ref(null)
  const selectedId = ref(null)
  const hoveredId = ref(null)

  // ── 历史记录 ──
  const undoStack = ref([])
  const redoStack = ref([])

  // ── 拖拽状态 ──
  const dragging = ref(null)
  const dragStartPos = ref(null)

  // ── 鼠标位置 ──
  const mouseX = ref(0)
  const mouseY = ref(0)
  const snappedPoint = ref(null)
  const cursorStyle = ref('default')

  // ═══════════════════════════════════════════════════════════════
  // 状态机
  // ═══════════════════════════════════════════════════════════════
  function setState(newState) {
    if (currentState.value === newState) return
    console.debug(`[DrawingCanvas] state: ${currentState.value} → ${newState}`)
    currentState.value = newState
  }

  // ═══════════════════════════════════════════════════════════════
  // 历史记录
  // ═══════════════════════════════════════════════════════════════
  function saveHistory() {
    undoStack.value.push(JSON.stringify(shapes.value))
    if (undoStack.value.length > MAX_HISTORY) undoStack.value.shift()
    redoStack.value = []
  }

  function undo() {
    if (undoStack.value.length === 0) return false
    redoStack.value.push(JSON.stringify(shapes.value))
    shapes.value = JSON.parse(undoStack.value.pop())
    return true
  }

  function redo() {
    if (redoStack.value.length === 0) return false
    undoStack.value.push(JSON.stringify(shapes.value))
    shapes.value = JSON.parse(redoStack.value.pop())
    return true
  }

  function canUndo() {
    return undoStack.value.length > 0
  }

  function canRedo() {
    return redoStack.value.length > 0
  }

  function clearHistory() {
    undoStack.value = []
    redoStack.value = []
  }

  // ═══════════════════════════════════════════════════════════════
  // 图形操作
  // ═══════════════════════════════════════════════════════════════
  function addShape(shape) {
    shapes.value.push(shape)
  }

  function removeShape(id) {
    shapes.value = shapes.value.filter(s => s.id !== id)
  }

  function getShape(id) {
    return shapes.value.find(s => s.id === id)
  }

  function clearShapes() {
    saveHistory()
    shapes.value = []
    selectedId.value = null
    drawing.value = null
  }

  function setShapes(newShapes) {
    shapes.value = newShapes
  }

  // ═══════════════════════════════════════════════════════════════
  // 选中/悬停
  // ═══════════════════════════════════════════════════════════════
  function select(id) {
    selectedId.value = id
  }

  function deselect() {
    selectedId.value = null
  }

  function hover(id) {
    hoveredId.value = id
  }

  // ═══════════════════════════════════════════════════════════════
  // 拖拽
  // ═══════════════════════════════════════════════════════════════
  function startDrag(id, pointIdx, x, y, points = null) {
    dragging.value = { id, pointIdx }
    dragStartPos.value = points 
      ? { x, y, points: JSON.parse(JSON.stringify(points)) }
      : { x, y }
  }

  function endDrag() {
    dragging.value = null
    dragStartPos.value = null
  }

  // ═══════════════════════════════════════════════════════════════
  // 绘制中
  // ═══════════════════════════════════════════════════════════════
  function startDrawing(shape) {
    drawing.value = shape
    setState(DrawState.DRAWING)
  }

  function updateDrawing(point) {
    if (drawing.value) {
      drawing.value.points.push(point)
    }
  }

  function finishDrawing() {
    const shape = drawing.value
    drawing.value = null
    setState(DrawState.IDLE)
    return shape
  }

  // ═══════════════════════════════════════════════════════════════
  // 工具函数
  // ═══════════════════════════════════════════════════════════════
  function genId() {
    return Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4)
  }

  function getToolLabel(type) {
    const labels = {
      trend: '趋势线', line: '直线', ray: '射线', segment: '线段',
      hray: '水平线', vline: '垂直线', channel: '平行通道', fib: '斐波那契',
      rect: '矩形', circle: '圆形', text: '文本'
    }
    return labels[type] || type
  }

  return {
    // 状态
    currentState,
    shapes,
    drawing,
    selectedId,
    hoveredId,
    undoStack,
    redoStack,
    dragging,
    dragStartPos,
    mouseX,
    mouseY,
    snappedPoint,
    cursorStyle,

    // 状态机
    setState,
    DrawState,

    // 历史记录
    saveHistory,
    undo,
    redo,
    canUndo,
    canRedo,
    clearHistory,

    // 图形操作
    addShape,
    removeShape,
    getShape,
    clearShapes,
    setShapes,

    // 选中/悬停
    select,
    deselect,
    hover,

    // 拖拽
    startDrag,
    endDrag,

    // 绘制
    startDrawing,
    updateDrawing,
    finishDrawing,

    // 工具
    genId,
    getToolLabel,
  }
}
