<template>
  <div class="drawing-layer" :class="{ 'locked': props.locked }">
    <canvas
      ref="canvasRef"
      class="drawing-canvas"
      :style="{ cursor: cursorStyle }"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @dblclick="onDblClick"
      @contextmenu.prevent="onContextMenu"
      @mouseleave="onMouseLeave"
      aria-label="画布绘图区域"
      role="img"
    />

    <div v-if="hoverInfo.show" class="hover-tooltip" :style="{ left: hoverInfo.x + 'px', top: hoverInfo.y + 'px' }">
      {{ hoverInfo.text }}
    </div>

    <div
      v-if="inlineEdit.visible"
      class="inline-text-overlay"
      :style="{ left: inlineEdit.x + 'px', top: inlineEdit.y + 'px' }"
    >
      <input
        ref="inlineInputRef"
        v-model="inlineEdit.text"
        class="inline-text-input"
        placeholder="输入文字..."
        maxlength="100"
        @keydown.enter="commitInlineEdit"
        @keydown.escape="cancelInlineEdit"
        @blur="commitInlineEdit"
        aria-label="画布上的内联文本"
      />
    </div>

    <div v-if="ctxMenu.show" class="context-menu" :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }">
      <div class="menu-item" @click="editSelected">
        <span class="icon">✏️</span> 编辑样式
      </div>
      <div class="menu-item" @click="startEditText">
        <span class="icon">📝</span> 编辑文字
      </div>
      <div class="menu-item" @click="duplicateSelected">
        <span class="icon">📋</span> 复制
      </div>
      <div class="menu-divider"></div>
      <div class="menu-item delete" @click="ctxDeleteShape">
        <span class="icon">🗑️</span> 删除
      </div>
      <div class="menu-divider"></div>
      <div class="menu-item" @click="ctxMenu.show = false">
        <span class="icon">✕</span> 取消
      </div>
    </div>

    <div v-if="styleEditor.show" class="style-editor" :style="{ left: styleEditor.x + 'px', top: styleEditor.y + 'px' }" role="dialog" aria-label="编辑画线样式">
      <div class="editor-title">编辑画线样式</div>
      <div class="editor-row">
        <label>颜色</label>
        <input type="color" v-model="styleEditor.color" @change="applyStyle" aria-label="画线颜色">
      </div>
      <div class="editor-row">
        <label>线宽</label>
        <input type="range" v-model.number="styleEditor.lineWidth" min="1" max="5" step="0.5" @input="applyStyle" aria-label="画线宽度" :aria-valuenow="styleEditor.lineWidth">
        <span>{{ styleEditor.lineWidth }}px</span>
      </div>
      <div class="editor-row">
        <label>线型</label>
        <select v-model="styleEditor.lineDash" @change="applyStyle" aria-label="画线线型">
          <option value="">实线</option>
          <option value="5,3">虚线</option>
          <option value="10,3,2,3">点划线</option>
          <option value="2,2">点线</option>
        </select>
      </div>
      <div class="editor-row" v-if="styleEditor.shape?.type === 'text'">
        <label>文字</label>
        <input type="text" v-model="styleEditor.text" @change="applyStyle" aria-label="画线文字">
      </div>
      <div class="editor-actions">
        <button @click="styleEditor.show = false" aria-label="关闭样式编辑器">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useDrawingState, DrawState } from '../composables/useDrawingState.js'
import { useDrawingRenderer } from '../composables/useDrawingRenderer.js'
import { useDrawingEvents } from '../composables/useDrawingEvents.js'
import { useDrawingStorage } from '../composables/useDrawingStorage.js'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  chartInstance:  { type: Object,  default: null },
  activeTool:     { type: String,  default: '' },
  activeColor:    { type: String,  default: '#fbbf24' },
  magnetMode:     { type: Boolean, default: true },
  locked:         { type: Boolean, default: false },
  symbol:         { type: String,  default: '' },
  period:         { type: String,  default: 'daily' },
})

const emit = defineEmits(['drawn', 'deleted', 'cleared', 'undo', 'redo'])

const state = useDrawingState()
const renderer = useDrawingRenderer()
const events = useDrawingEvents()
const storage = useDrawingStorage()

const canvasRef = ref(null)
const inlineInputRef = ref(null)

const inlineEdit = ref({ visible: false, x: 0, y: 0, text: '', shapeId: null })
const ctxMenu = ref({ show: false, x: 0, y: 0, targetId: null })
const styleEditor = ref({ show: false, x: 0, y: 0, shape: null, color: '', lineWidth: 1.5, lineDash: '', text: '' })
const hoverInfo = ref({ show: false, x: 0, y: 0, text: '' })

function startInlineEdit(shape, screenX, screenY) {
  inlineEdit.value = { visible: true, x: screenX, y: screenY, text: shape.text || '', shapeId: shape.id }
  state.setState(DrawState.EDITING)
  nextTick(() => inlineInputRef.value?.focus())
}

function commitInlineEdit() {
  const { text, shapeId } = inlineEdit.value
  if (text && shapeId) {
    state.saveHistory()
    const shape = state.getShape(shapeId)
    if (shape) {
      shape.text = storage.sanitizeText(text)
      emit('drawn', shape)
      storage.saveToStorage(props.symbol, props.period, state.shapes.value)
    }
  }
  inlineEdit.value.visible = false
  state.setState(DrawState.IDLE)
}

function cancelInlineEdit() {
  inlineEdit.value.visible = false
  state.setState(DrawState.IDLE)
}

function redraw() {
  renderer.redraw(props.chartInstance, state.shapes.value, {
    hoveredId: state.hoveredId.value,
    selectedId: state.selectedId.value,
    drawing: state.drawing.value,
    mouseX: state.mouseX.value,
    mouseY: state.mouseY.value,
    snappedPoint: state.snappedPoint.value,
  })
}

const mouseHandlers = events.createMouseHandlers({
  get canvasRef() { return canvasRef.value },
  get chartInstance() { return props.chartInstance },
  state,
  renderer,
  storage: {
    saveToStorage: () => storage.saveToStorage(props.symbol, props.period, state.shapes.value)
  },
  props,
  emit,
  startInlineEdit,
})

function onMouseDown(e) {
  const result = mouseHandlers.onMouseDown(e)
  if (result?.needRedraw) redraw()
}

function onMouseMove(e) {
  const result = mouseHandlers.onMouseMove(e)
  if (result?.needRedraw) redraw()
  if (result?.hoverInfo) hoverInfo.value = result.hoverInfo
}

function onMouseUp(e) {
  const result = mouseHandlers.onMouseUp(e)
  if (result?.needRedraw) redraw()
}

function onDblClick(e) {
  const result = mouseHandlers.onDblClick(e)
  if (result?.needRedraw) redraw()
  if (result?.openStyleEditor) {
    editSelected()
    redraw()
  }
}

function onContextMenu(e) {
  const result = mouseHandlers.onContextMenu(e)
  if (result?.showMenu) {
    ctxMenu.value = { show: true, x: result.x, y: result.y, targetId: result.targetId }
  }
}

function onMouseLeave() {
  const result = mouseHandlers.onMouseLeave()
  if (result?.hoverInfo) hoverInfo.value = result.hoverInfo
}

function startEditText() {
  const shape = state.getShape(state.selectedId.value)
  if (!shape || shape.type !== 'text') return
  ctxMenu.value.show = false
  const pixel = shape.points?.[0] ? renderer.toPixel(props.chartInstance, shape.points[0].price, shape.points[0].timestamp) : null
  const rect = canvasRef.value?.getBoundingClientRect()
  startInlineEdit(shape, (pixel?.x ?? 100) + (rect?.left ?? 0), (pixel?.y ?? 100) + (rect?.top ?? 0) - 24)
}

function editSelected() {
  const shape = state.getShape(state.selectedId.value)
  if (!shape) return
  
  styleEditor.value = {
    show: true,
    x: Math.min(ctxMenu.value.x || 200, window.innerWidth - 200),
    y: Math.min(ctxMenu.value.y || 200, window.innerHeight - 200),
    shape,
    color: shape.color || '#fbbf24',
    lineWidth: shape.lineWidth || 1.5,
    lineDash: shape.lineDash || '',
    text: shape.text || ''
  }
  ctxMenu.value.show = false
}

function applyStyle() {
  const shape = styleEditor.value.shape
  if (!shape) return
  
  state.saveHistory()
  shape.color = styleEditor.value.color
  shape.lineWidth = styleEditor.value.lineWidth
  shape.lineDash = styleEditor.value.lineDash
  if (shape.type === 'text') {
    const sanitized = storage.sanitizeText(styleEditor.value.text)
    shape.text = sanitized
    styleEditor.value.text = sanitized
  }
  
  storage.saveToStorage(props.symbol, props.period, state.shapes.value)
  redraw()
}

function duplicateSelected() {
  const shape = state.getShape(state.selectedId.value)
  if (!shape) return
  
  state.saveHistory()
  const newShape = {
    ...JSON.parse(JSON.stringify(shape)),
    id: state.genId(),
    points: shape.points.map(p => ({
      ...p,
      timestamp: p.timestamp + 86400000
    })),
    createdAt: Date.now()
  }
  state.addShape(newShape)
  state.select(newShape.id)
  
  storage.saveToStorage(props.symbol, props.period, state.shapes.value)
  redraw()
  ctxMenu.value.show = false
}

function ctxDeleteShape() {
  const id = ctxMenu.value.targetId || state.selectedId.value
  if (!id) return
  
  state.saveHistory()
  state.removeShape(id)
  state.deselect()
  emit('deleted', id)
  storage.saveToStorage(props.symbol, props.period, state.shapes.value)
  redraw()
  ctxMenu.value.show = false
}

function clearAll() {
  state.clearShapes()
  emit('cleared')
  storage.saveToStorage(props.symbol, props.period, state.shapes.value)
  redraw()
}

function deleteSelected() {
  if (state.selectedId.value) {
    state.saveHistory()
    state.removeShape(state.selectedId.value)
    emit('deleted', state.selectedId.value)
    state.deselect()
    storage.saveToStorage(props.symbol, props.period, state.shapes.value)
    redraw()
  }
}

function getShapes() {
  return state.shapes.value
}

function undo() {
  if (state.undo()) {
    storage.saveToStorage(props.symbol, props.period, state.shapes.value)
    redraw()
    emit('undo')
  }
}

function redo() {
  if (state.redo()) {
    storage.saveToStorage(props.symbol, props.period, state.shapes.value)
    redraw()
    emit('redo')
  }
}

async function loadFromStorage() {
  const loaded = await storage.loadFromStorage(props.symbol, props.period)
  state.setShapes(loaded)
  state.clearHistory()
  redraw()
}

function resizeCanvas() {
  renderer.resizeCanvas()
  redraw()
}

onMounted(() => {
  renderer.initCanvas(canvasRef.value)
  resizeCanvas()
  loadFromStorage()
  
  const handleDocClick = (e) => {
    if (!e.target.closest('.context-menu') && !e.target.closest('.style-editor')) {
      ctxMenu.value.show = false
    }
  }
  
  window.addEventListener('resize', resizeCanvas)
  document.addEventListener('click', handleDocClick)
  
  if (canvasRef.value?.parentElement) {
    const ro = new ResizeObserver(() => resizeCanvas())
    ro.observe(canvasRef.value.parentElement)
  }
  
  onUnmounted(() => {
    renderer.cancelAnimation()
    window.removeEventListener('resize', resizeCanvas)
    document.removeEventListener('click', handleDocClick)
  })
})

watch(() => [props.symbol, props.period], () => loadFromStorage(), { immediate: true })

watch(() => props.activeTool, (tool) => {
  if (tool && tool !== 'select') {
    state.setState(DrawState.DRAWING)
  } else {
    state.setState(DrawState.IDLE)
  }
  redraw()
})

watch([() => props.activeTool, () => props.activeColor, () => props.magnetMode], () => redraw())
watch(state.shapes, () => redraw(), { deep: true })

defineExpose({ 
  clearAll, deleteSelected, getShapes, undo, redo,
  canUndo: () => state.canUndo(),
  canRedo: () => state.canRedo()
})
</script>

<style scoped>
.drawing-layer {
  position: absolute;
  top: 48px;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 5;
}

.drawing-layer.locked {
  pointer-events: none;
}

.drawing-canvas {
  width: 100%;
  height: 100%;
}

.hover-tooltip {
  position: fixed;
  background: rgba(17, 24, 39, 0.95);
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 11px;
  color: #e5e7eb;
  pointer-events: none;
  z-index: 1000;
  white-space: nowrap;
}

.context-menu {
  position: fixed;
  background: rgba(17, 24, 39, 0.98);
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-radius: 6px;
  padding: 4px 0;
  min-width: 140px;
  z-index: 1001;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 12px;
  color: #e5e7eb;
  cursor: pointer;
  transition: background 0.15s;
}

.menu-item:hover {
  background: rgba(75, 85, 99, 0.3);
}

.menu-item.delete {
  color: #f87171;
}

.menu-item.delete:hover {
  background: rgba(248, 113, 113, 0.15);
}

.menu-divider {
  height: 1px;
  background: rgba(75, 85, 99, 0.3);
  margin: 4px 0;
}

.icon {
  font-size: 12px;
}

.style-editor {
  position: fixed;
  background: rgba(17, 24, 39, 0.98);
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-radius: 8px;
  padding: 12px;
  min-width: 180px;
  z-index: 1002;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

.editor-title {
  font-size: 13px;
  font-weight: 600;
  color: #f3f4f6;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(75, 85, 99, 0.3);
}

.editor-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.editor-row label {
  font-size: 11px;
  color: #9ca3af;
  min-width: 40px;
}

.editor-row input[type="color"] {
  width: 28px;
  height: 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.editor-row input[type="range"] {
  flex: 1;
  height: 4px;
}

.editor-row input[type="text"] {
  flex: 1;
  background: rgba(31, 41, 55, 0.8);
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 11px;
  color: #e5e7eb;
}

.editor-row select {
  flex: 1;
  background: rgba(31, 41, 55, 0.8);
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-radius: 4px;
  padding: 4px;
  font-size: 11px;
  color: #e5e7eb;
}

.editor-row span {
  font-size: 10px;
  color: #6b7280;
  min-width: 24px;
}

.editor-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid rgba(75, 85, 99, 0.3);
}

.editor-actions button {
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.5);
  border-radius: 4px;
  padding: 4px 12px;
  font-size: 11px;
  color: #60a5fa;
  cursor: pointer;
  transition: all 0.15s;
}

.editor-actions button:hover {
  background: rgba(59, 130, 246, 0.3);
}

.inline-text-overlay {
  position: fixed;
  z-index: 2000;
  transform: translate(-50%, -100%);
}

.inline-text-input {
  background: rgba(10, 14, 23, 0.95);
  border: 1.5px solid #60a5fa;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  color: #f3f4f6;
  font-family: monospace;
  outline: none;
  min-width: 120px;
  max-width: 280px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
}

.inline-text-input::placeholder {
  color: #6b7280;
}
</style>
