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
    />

    <!-- 悬停提示 -->
    <div v-if="hoverInfo.show" class="hover-tooltip" :style="{ left: hoverInfo.x + 'px', top: hoverInfo.y + 'px' }">
      {{ hoverInfo.text }}
    </div>

    <!-- 内联文本编辑覆盖层（替代原生 prompt） -->
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
      />
    </div>

    <!-- 右键菜单 -->
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

    <!-- 样式编辑弹窗 -->
    <div v-if="styleEditor.show" class="style-editor" :style="{ left: styleEditor.x + 'px', top: styleEditor.y + 'px' }">
      <div class="editor-title">编辑画线样式</div>
      <div class="editor-row">
        <label>颜色</label>
        <input type="color" v-model="styleEditor.color" @change="applyStyle">
      </div>
      <div class="editor-row">
        <label>线宽</label>
        <input type="range" v-model.number="styleEditor.lineWidth" min="1" max="5" step="0.5" @input="applyStyle">
        <span>{{ styleEditor.lineWidth }}px</span>
      </div>
      <div class="editor-row">
        <label>线型</label>
        <select v-model="styleEditor.lineDash" @change="applyStyle">
          <option value="">实线</option>
          <option value="5,3">虚线</option>
          <option value="10,3,2,3">点划线</option>
          <option value="2,2">点线</option>
        </select>
      </div>
      <div class="editor-row" v-if="styleEditor.shape?.type === 'text'">
        <label>文字</label>
        <input type="text" v-model="styleEditor.text" @change="applyStyle">
      </div>
      <div class="editor-actions">
        <button @click="styleEditor.show = false">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { logger } from '../utils/logger.js'
import localforage from 'localforage'

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

// ═══════════════════════════════════════════════════════════════
// 状态机：三种互斥状态，统一入口分发
// ═══════════════════════════════════════════════════════════════
const DrawState = {
  IDLE:    'IDLE',    // 空闲/选择模式（可点击选中、拖拽）
  DRAWING: 'DRAWING', // 正在绘制新图形
  EDITING: 'EDITING', // 正在编辑文字（内联输入激活）
}

const currentState = ref(DrawState.IDLE)

function setState(newState) {
  if (currentState.value === newState) return
  console.debug(`[DrawingCanvas] state: ${currentState.value} → ${newState}`)
  currentState.value = newState
}

// ═══════════════════════════════════════════════════════════════
// 内联文本编辑
// ═══════════════════════════════════════════════════════════════
const inlineEdit     = ref({ visible: false, x: 0, y: 0, text: '', shapeId: null })
const inlineInputRef = ref(null)

function startInlineEdit(shape, screenX, screenY) {
  inlineEdit.value = { visible: true, x: screenX, y: screenY, text: shape.text || '', shapeId: shape.id }
  setState(DrawState.EDITING)
  nextTick(() => inlineInputRef.value?.focus())
}

function commitInlineEdit() {
  const { text, shapeId } = inlineEdit.value
  if (text && shapeId) {
    saveHistory()
    const shape = shapes.value.find(s => s.id === shapeId)
    if (shape) {
      shape.text = sanitizeText(text)
      emit('drawn', shape)
      saveToStorage()
    }
  }
  inlineEdit.value.visible = false
  setState(DrawState.IDLE)
}

function cancelInlineEdit() {
  inlineEdit.value.visible = false
  setState(DrawState.IDLE)
}

// 通用状态
const canvasRef = ref(null)
let ctx = null
let animationFrame = null

const shapes = ref([])
const undoStack = ref([])
const redoStack = ref([])
const MAX_HISTORY = 50

const drawing = ref(null)
const selectedId = ref(null)
const hoveredId = ref(null)

const ctxMenu = ref({ show: false, x: 0, y: 0, targetId: null })
const styleEditor = ref({ show: false, x: 0, y: 0, shape: null, color: '', lineWidth: 1.5, lineDash: '', text: '' })
const hoverInfo = ref({ show: false, x: 0, y: 0, text: '' })

const dragging = ref(null)
const dragStartPos = ref(null)

const mouseX = ref(0)
const mouseY = ref(0)
const snappedPoint = ref(null)
const cursorStyle = ref('default')

const storage = localforage.createInstance({ name: 'AlphaTerminal', storeName: 'drawings_v3' })

// XSS 防护：转义 HTML 特殊字符
function escapeHtml(text) {
  if (!text || typeof text !== 'string') return text
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// XSS 防护：验证文本输入
function sanitizeText(text) {
  if (!text || typeof text !== 'string') return ''
  // 限制长度
  const maxLength = 100
  let sanitized = text.slice(0, maxLength)
  // 移除控制字符
  sanitized = sanitized.replace(/[\x00-\x1F\x7F]/g, '')
  // 转义 HTML
  return escapeHtml(sanitized)
}

// 历史记录
function saveHistory() {
  undoStack.value.push(JSON.stringify(shapes.value))
  if (undoStack.value.length > MAX_HISTORY) undoStack.value.shift()
  redoStack.value = []
}

function undo() {
  if (undoStack.value.length === 0) return
  redoStack.value.push(JSON.stringify(shapes.value))
  shapes.value = JSON.parse(undoStack.value.pop())
  saveToStorage()
  redraw()
  emit('undo')
}

function redo() {
  if (redoStack.value.length === 0) return
  undoStack.value.push(JSON.stringify(shapes.value))
  shapes.value = JSON.parse(redoStack.value.pop())
  saveToStorage()
  redraw()
  emit('redo')
}

// 坐标转换
function getTimestampByIndex(idx) {
  try {
    const option = props.chartInstance.getOption()
    const times = option.xAxis?.[0]?.data
    if (times && times[idx]) return new Date(times[idx]).getTime()
  } catch (e) {
    // ignore parsing errors
  }
  return null
}

function getIndexByTimestamp(timestamp) {
  if (!timestamp) return null
  try {
    const option = props.chartInstance.getOption()
    const times = option.xAxis?.[0]?.data
    if (!times) return null
    
    let left = 0, right = times.length - 1
    let closestIdx = 0, minDiff = Infinity
    
    while (left <= right) {
      const mid = Math.floor((left + right) / 2)
      const midTime = new Date(times[mid]).getTime()
      const diff = Math.abs(midTime - timestamp)
      
      if (diff < minDiff) { minDiff = diff; closestIdx = mid }
      if (midTime < timestamp) left = mid + 1
      else if (midTime > timestamp) right = mid - 1
      else break
    }
    return closestIdx
  } catch (e) { return null }
}

function toPixel(price, timestamp) {
  if (!props.chartInstance) return null
  try {
    const idx = getIndexByTimestamp(timestamp)
    if (idx == null) return null
    const pixel = props.chartInstance.convertToPixel({ gridIndex: 0 }, [idx, price])
    return pixel ? { x: pixel[0], y: pixel[1] } : null
  } catch { return null }
}

function toData(x, y) {
  if (!props.chartInstance) return null
  try {
    const [idx, price] = props.chartInstance.convertFromPixel({ gridIndex: 0 }, [x, y])
    return { idx: Math.round(idx), price, timestamp: getTimestampByIndex(Math.round(idx)) }
  } catch { return null }
}

// 磁吸
function snapToKLine(x, y) {
  if (!props.chartInstance || !props.magnetMode) return { x, y }
  
  try {
    const converted = props.chartInstance.convertFromPixel({ gridIndex: 0 }, [x, y])
    if (!converted) return { x, y }
    
    const [idx, price] = converted
    const roundedIdx = Math.round(idx)
    
    const option = props.chartInstance.getOption()
    const candlestickData = option.series?.[0]?.data
    
    if (!candlestickData || roundedIdx < 0 || roundedIdx >= candlestickData.length) {
      return { x, y }
    }
    
    const [open, close, low, high] = candlestickData[roundedIdx]
    const SNAP_THRESHOLD = 20
    
    const candidates = [
      { price: open, label: '开' },
      { price: close, label: '收' },
      { price: low, label: '低' },
      { price: high, label: '高' }
    ]
    
    let closest = null, minDist = Infinity
    for (const c of candidates) {
      const pixelY = props.chartInstance.convertToPixel({ gridIndex: 0 }, [0, c.price])?.[1]
      if (pixelY == null) continue
      const dist = Math.abs(pixelY - y)
      if (dist < minDist && dist < SNAP_THRESHOLD) {
        minDist = dist
        closest = c
      }
    }
    
    if (closest) {
      const snappedY = props.chartInstance.convertToPixel({ gridIndex: 0 }, [0, closest.price])?.[1]
      return { 
        x, y: snappedY ?? y, price: closest.price, 
        timestamp: getTimestampByIndex(roundedIdx),
        idx: roundedIdx, magnetTo: closest.label
      }
    }
  } catch (e) {
    // ignore calculation errors
  }
  
  return { x, y }
}

// 绘图
function drawShape(ctx, shape, isHovered = false, isSelected = false) {
  if (!shape.points || shape.points.length < 1) return
  
  const pixelPoints = shape.points.map(p => toPixel(p.price, p.timestamp)).filter(Boolean)
  if (pixelPoints.length === 0) return
  
  ctx.save()
  
  ctx.strokeStyle = shape.color || '#fbbf24'
  ctx.lineWidth = shape.lineWidth || (isSelected ? 2.5 : isHovered ? 2 : 1.5)
  
  const dash = shape.lineDash ? shape.lineDash.split(',').map(Number) : []
  if (shape.type === 'hray' || shape.type === 'ray' || shape.type === 'trend') {
    ctx.setLineDash(dash.length ? dash : [5, 3])
  } else {
    ctx.setLineDash(dash)
  }
  
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  
  const p0 = pixelPoints[0]
  
  switch (shape.type) {
    case 'trend':
    case 'line':
      if (pixelPoints.length >= 2) {
        const p1 = pixelPoints[1]
        const dx = p1.x - p0.x, dy = p1.y - p0.y
        const scale = 10000
        ctx.beginPath()
        ctx.moveTo(p0.x - dx * scale, p0.y - dy * scale)
        ctx.lineTo(p1.x + dx * scale, p1.y + dy * scale)
        ctx.stroke()
        
        if (shape.type === 'trend' || shape.arrow) {
          drawArrow(ctx, p0.x - dx * scale, p0.y - dy * scale, p1.x + dx * scale, p1.y + dy * scale)
        }
      } else if (drawing.value?.id === shape.id) {
        const snap = snappedPoint.value || { x: mouseX.value, y: mouseY.value }
        ctx.beginPath()
        ctx.moveTo(p0.x, p0.y)
        ctx.lineTo(snap.x, snap.y)
        ctx.stroke()
      }
      break
      
    case 'segment':
      if (pixelPoints.length >= 2) {
        const p1 = pixelPoints[1]
        ctx.beginPath()
        ctx.moveTo(p0.x, p0.y)
        ctx.lineTo(p1.x, p1.y)
        ctx.stroke()
        
        if (shape.arrow) drawArrow(ctx, p0.x, p0.y, p1.x, p1.y)
        
        ctx.fillStyle = shape.color
        ctx.beginPath(); ctx.arc(p0.x, p0.y, 3, 0, Math.PI * 2); ctx.fill()
        ctx.beginPath(); ctx.arc(p1.x, p1.y, 3, 0, Math.PI * 2); ctx.fill()
      } else if (drawing.value?.id === shape.id) {
        const snap = snappedPoint.value || { x: mouseX.value, y: mouseY.value }
        ctx.beginPath()
        ctx.moveTo(p0.x, p0.y)
        ctx.lineTo(snap.x, snap.y)
        ctx.stroke()
      }
      break
      
    case 'ray':
      if (pixelPoints.length >= 2) {
        const p1 = pixelPoints[1]
        const dx = p1.x - p0.x, dy = p1.y - p0.y
        const scale = 10000
        ctx.beginPath()
        ctx.moveTo(p0.x, p0.y)
        ctx.lineTo(p0.x + dx * scale, p0.y + dy * scale)
        ctx.stroke()
        
        if (shape.arrow) drawArrow(ctx, p0.x, p0.y, p0.x + dx * scale, p0.y + dy * scale)
        
        ctx.fillStyle = shape.color
        ctx.beginPath(); ctx.arc(p0.x, p0.y, 3, 0, Math.PI * 2); ctx.fill()
      } else if (drawing.value?.id === shape.id) {
        const snap = snappedPoint.value || { x: mouseX.value, y: mouseY.value }
        ctx.beginPath()
        ctx.moveTo(p0.x, p0.y)
        ctx.lineTo(snap.x, snap.y)
        ctx.stroke()
      }
      break
      
    case 'hray':
      {
        const canvasWidth = canvasRef.value?.width || 1000
        ctx.beginPath()
        ctx.moveTo(0, p0.y)
        ctx.lineTo(canvasWidth, p0.y)
        ctx.stroke()
        
        ctx.fillStyle = shape.color
        ctx.font = '11px monospace'
        const priceText = shape.points[0].price.toFixed(2)
        ctx.fillText(priceText, 4, p0.y - 4)
      }
      break
      
    case 'vline':
      {
        const canvasHeight = canvasRef.value?.height || 1000
        ctx.beginPath()
        ctx.moveTo(p0.x, 0)
        ctx.lineTo(p0.x, canvasHeight)
        ctx.stroke()
        
        const date = new Date(shape.points[0].timestamp)
        const dateText = `${date.getMonth() + 1}/${date.getDate()}`
        ctx.fillStyle = shape.color
        ctx.font = '10px monospace'
        ctx.fillText(dateText, p0.x + 4, 12)
      }
      break
      
    case 'channel':
      if (pixelPoints.length >= 2) {
        const p1 = pixelPoints[1]
        const dy = p1.y - p0.y
        
        ctx.beginPath()
        ctx.moveTo(p0.x, p0.y - dy)
        ctx.lineTo(p1.x, p1.y - dy)
        ctx.stroke()
        
        ctx.setLineDash([3, 2])
        ctx.beginPath()
        ctx.moveTo(p0.x, p0.y + dy)
        ctx.lineTo(p1.x, p1.y + dy)
        ctx.stroke()
        
        ctx.setLineDash(dash)
        ctx.beginPath()
        ctx.moveTo(p0.x, p0.y)
        ctx.lineTo(p1.x, p1.y)
        ctx.stroke()
      } else if (drawing.value?.id === shape.id) {
        const snap = snappedPoint.value || { x: mouseX.value, y: mouseY.value }
        const dy = snap.y - p0.y
        ctx.beginPath()
        ctx.moveTo(p0.x, p0.y)
        ctx.lineTo(snap.x, snap.y)
        ctx.stroke()
        ctx.setLineDash([3, 2])
        ctx.beginPath()
        ctx.moveTo(p0.x, p0.y - dy)
        ctx.lineTo(snap.x, snap.y - dy)
        ctx.stroke()
      }
      break
      
    case 'fib':
      {
        const p1 = pixelPoints[1] || (snappedPoint.value || { x: mouseX.value, y: mouseY.value })
        const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        const labels = ['0', '23.6%', '38.2%', '50%', '61.8%', '78.6%', '100%']
        const canvasWidth = canvasRef.value?.width || 1000
        
        levels.forEach((level, i) => {
          const y = p0.y + (p1.y - p0.y) * level
          ctx.strokeStyle = (i === 2 || i === 4) ? shape.color : shape.color + '66'
          ctx.setLineDash(i === 0 || i === 6 ? [] : [3, 2])
          ctx.lineWidth = (i === 2 || i === 4) ? 1.5 : 1
          
          ctx.beginPath()
          ctx.moveTo(0, y)
          ctx.lineTo(canvasWidth, y)
          ctx.stroke()
          
          ctx.fillStyle = shape.color
          ctx.font = '10px monospace'
          ctx.fillText(labels[i], 4, y - 2)
        })
        
        ctx.strokeStyle = shape.color
        ctx.setLineDash(dash)
        ctx.lineWidth = shape.lineWidth || 1
        ctx.beginPath()
        ctx.moveTo(p0.x, p0.y)
        ctx.lineTo(p1.x, p1.y)
        ctx.stroke()
      }
      break
      
    case 'rect':
      if (pixelPoints.length >= 2) {
        const p1 = pixelPoints[1]
        ctx.beginPath()
        ctx.rect(p0.x, p0.y, p1.x - p0.x, p1.y - p0.y)
        ctx.stroke()
        ctx.fillStyle = (shape.color || '#fbbf24') + '10'
        ctx.fill()
      } else if (drawing.value?.id === shape.id) {
        const snap = snappedPoint.value || { x: mouseX.value, y: mouseY.value }
        ctx.beginPath()
        ctx.rect(p0.x, p0.y, snap.x - p0.x, snap.y - p0.y)
        ctx.stroke()
      }
      break
      
    case 'circle':
      if (pixelPoints.length >= 2) {
        const p1 = pixelPoints[1]
        const r = Math.hypot(p1.x - p0.x, p1.y - p0.y)
        ctx.beginPath()
        ctx.arc(p0.x, p0.y, r, 0, Math.PI * 2)
        ctx.stroke()
      } else if (drawing.value?.id === shape.id) {
        const snap = snappedPoint.value || { x: mouseX.value, y: mouseY.value }
        const r = Math.hypot(snap.x - p0.x, snap.y - p0.y)
        ctx.beginPath()
        ctx.arc(p0.x, p0.y, r, 0, Math.PI * 2)
        ctx.stroke()
      }
      break
      
    case 'text':
      if (shape.text) {
        ctx.font = `bold ${shape.fontSize || 12}px sans-serif`
        const metrics = ctx.measureText(shape.text)
        
        ctx.fillStyle = '#0a0e17cc'
        ctx.fillRect(p0.x - 2, p0.y - (shape.fontSize || 12), metrics.width + 4, (shape.fontSize || 12) + 4)
        
        ctx.fillStyle = shape.color
        ctx.fillText(shape.text, p0.x, p0.y)
      }
      break
  }
  
  if (isSelected) {
    ctx.fillStyle = '#ffffff'
    ctx.strokeStyle = shape.color || '#fbbf24'
    ctx.lineWidth = 1.5
    ctx.setLineDash([])
    
    pixelPoints.forEach((p) => {
      ctx.beginPath()
      ctx.arc(p.x, p.y, 5, 0, Math.PI * 2)
      ctx.fill()
      ctx.stroke()
    })
  }
  
  ctx.restore()
}

function drawArrow(ctx, x1, y1, x2, y2) {
  const angle = Math.atan2(y2 - y1, x2 - x1)
  const arrowLen = 10
  const arrowAngle = Math.PI / 6
  
  ctx.beginPath()
  ctx.moveTo(x2, y2)
  ctx.lineTo(x2 - arrowLen * Math.cos(angle - arrowAngle), y2 - arrowLen * Math.sin(angle - arrowAngle))
  ctx.moveTo(x2, y2)
  ctx.lineTo(x2 - arrowLen * Math.cos(angle + arrowAngle), y2 - arrowLen * Math.sin(angle + arrowAngle))
  ctx.stroke()
}

function redraw() {
  if (!ctx || !canvasRef.value) return
  cancelAnimationFrame(animationFrame)
  animationFrame = requestAnimationFrame(() => {
    const canvas = canvasRef.value
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    
    shapes.value.forEach(shape => {
      drawShape(ctx, shape, shape.id === hoveredId.value, shape.id === selectedId.value)
    })
    
    if (drawing.value) {
      drawShape(ctx, drawing.value)
    }
  })
}

// 鼠标事件
function getCanvasPos(e) {
  const rect = canvasRef.value.getBoundingClientRect()
  return { x: e.clientX - rect.left, y: e.clientY - rect.top }
}

function onMouseDown(e) {
  // EDITING 状态：内联输入激活，拦截所有鼠标事件
  if (currentState.value === DrawState.EDITING) return
  if (e.button !== 0) return
  if (props.locked) return
  
  const { x, y } = getCanvasPos(e)
  
  // 选择/移动模式
  if (props.activeTool === 'select') {
    const hit = hitTest(x, y)
    if (hit) {
      selectedId.value = hit.id
      if (hit.pointIdx >= 0) {
        dragging.value = { id: hit.id, pointIdx: hit.pointIdx }
        dragStartPos.value = { x, y }
      } else {
        const shape = shapes.value.find(s => s.id === hit.id)
        if (shape && shape.type !== 'hray' && shape.type !== 'vline') {
          dragging.value = { id: hit.id, pointIdx: -1, startX: x, startY: y }
          dragStartPos.value = { x, y, points: JSON.parse(JSON.stringify(shape.points)) }
        }
      }
      redraw()
    } else {
      // 点击空白处取消选择
      selectedId.value = null
      redraw()
    }
    return
  }
  
  // 文本工具 — 创建新文字标注
  if (props.activeTool === 'text') {
    const data = toData(x, y)
    if (!data) return
    saveHistory()
    const shape = {
      id: genId(),
      type: 'text',
      points: [{ price: data.price, timestamp: data.timestamp }],
      color: props.activeColor,
      text: '',          // 先创建空文本，触发内联编辑
      fontSize: 12,
      lineWidth: 1.5,
      createdAt: Date.now(),
    }
    shapes.value.push(shape)
    const rect = canvasRef.value?.getBoundingClientRect()
    const pixel = toPixel(data.price, data.timestamp)
    // 立即弹出内联编辑
    startInlineEdit(shape, (pixel?.x ?? x) + (rect?.left ?? 0), (pixel?.y ?? y) + (rect?.top ?? 0) - 24)
    emit('drawn', shape)
    saveToStorage()
    return
  }
  
  const hit = hitTest(x, y)
  if (hit) {
    selectedId.value = hit.id
    if (hit.pointIdx >= 0) {
      dragging.value = { id: hit.id, pointIdx: hit.pointIdx }
      dragStartPos.value = { x, y }
    } else {
      const shape = shapes.value.find(s => s.id === hit.id)
      if (shape && shape.type !== 'hray' && shape.type !== 'vline') {
        dragging.value = { id: hit.id, pointIdx: -1, startX: x, startY: y }
        dragStartPos.value = { x, y, points: JSON.parse(JSON.stringify(shape.points)) }
      }
    }
    redraw()
    return
  }
  
  if (!props.activeTool) return
  
  const data = toData(x, y)
  if (!data) return
  
  const snapped = snapToKLine(x, y)
  selectedId.value = null
  drawing.value = {
    id: 'drawing-' + Date.now(),
    type: props.activeTool,
    points: [{
      price: snapped.price ?? data.price,
      timestamp: snapped.timestamp ?? data.timestamp
    }],
    color: props.activeColor,
    lineWidth: 1.5,
    createdAt: Date.now()
  }
}

function onMouseMove(e) {
  // EDITING 状态：不处理绘制/拖拽逻辑
  if (currentState.value === DrawState.EDITING) return
  const { x, y } = getCanvasPos(e)
  mouseX.value = x
  mouseY.value = y
  
  if (props.locked) {
    cursorStyle.value = 'not-allowed'
  } else if (currentState.value === DrawState.EDITING) {
    cursorStyle.value = 'text'
  } else if (props.activeTool === 'select') {
    cursorStyle.value = 'default'
  } else if (props.activeTool) {
    cursorStyle.value = 'crosshair'
  } else if (dragging.value) {
    cursorStyle.value = dragging.value.pointIdx >= 0 ? 'grabbing' : 'move'
  } else if (hoveredId.value) {
    const hit = hitTest(x, y)
    cursorStyle.value = hit?.pointIdx >= 0 ? 'grab' : 'pointer'
  } else {
    cursorStyle.value = 'default'
  }
  
  if (dragging.value) {
    const shape = shapes.value.find(s => s.id === dragging.value.id)
    if (!shape) return
    
    if (dragging.value.pointIdx >= 0) {
      const data = toData(x, y)
      if (data) {
        const snapped = snapToKLine(x, y)
        shape.points[dragging.value.pointIdx] = {
          price: snapped.price ?? data.price,
          timestamp: snapped.timestamp ?? data.timestamp
        }
        redraw()
      }
    } else {
      const dx = x - dragStartPos.value.x
      const dy = y - dragStartPos.value.y
      
      shape.points = dragStartPos.value.points.map((p) => {
        const pixel = toPixel(p.price, p.timestamp)
        if (!pixel) return p
        const newPixel = { x: pixel.x + dx, y: pixel.y + dy }
        const data = toData(newPixel.x, newPixel.y)
        return data ? { price: data.price, timestamp: data.timestamp } : p
      })
      redraw()
    }
    return
  }
  
  if (props.activeTool) {
    snappedPoint.value = snapToKLine(x, y)
    if (drawing.value) redraw()
  }
  
  const hit = hitTest(x, y)
  if (hit?.id !== hoveredId.value) {
    hoveredId.value = hit?.id ?? null
    
    if (hit) {
      const shape = shapes.value.find(s => s.id === hit.id)
      if (shape) {
        hoverInfo.value = {
          show: true,
          x: x + 12,
          y: y - 24,
          text: `${getToolLabel(shape.type)} - ${shape.points[0]?.price?.toFixed(2) ?? ''}`
        }
      }
    } else {
      hoverInfo.value.show = false
    }
    redraw()
  }
}

function onMouseUp(e) {
  if (dragging.value) {
    if (dragStartPos.value && (Math.abs(e.clientX - dragStartPos.value.x) > 2 || Math.abs(e.clientY - dragStartPos.value.y) > 2)) {
      saveHistory()
      saveToStorage()
    }
    dragging.value = null
    dragStartPos.value = null
    return
  }
  
  if (!drawing.value || !props.activeTool) return
  
  const { x, y } = getCanvasPos(e)
  const data = toData(x, y)
  if (!data) return
  
  const snapped = snapToKLine(x, y)
  drawing.value.points.push({
    price: snapped.price ?? data.price,
    timestamp: snapped.timestamp ?? data.timestamp
  })
  
  const minPoints = { 
    trend: 2, line: 2, ray: 2, segment: 2, 
    hray: 1, vline: 1, channel: 2, fib: 2, 
    rect: 2, circle: 2 
  }
  
  if ((minPoints[drawing.value.type] || 2) <= drawing.value.points.length) {
    saveHistory()
    const shape = { ...drawing.value, id: genId() }
    shapes.value.push(shape)
    emit('drawn', shape)
    saveToStorage()
    drawing.value = null
  }
  redraw()
}

function onDblClick(e) {
  if (currentState.value === DrawState.EDITING) return
  const { x, y } = getCanvasPos(e)
  const hit = hitTest(x, y)
  if (hit) {
    selectedId.value = hit.id
    const shape = shapes.value.find(s => s.id === hit.id)
    if (shape?.type === 'text') {
      // 双击文本 → 进入内联编辑
      const pixel = shape.points?.[0] ? toPixel(shape.points[0].price, shape.points[0].timestamp) : null
      const rect = canvasRef.value?.getBoundingClientRect()
      startInlineEdit(shape, (pixel?.x ?? x) + (rect?.left ?? 0), (pixel?.y ?? y) + (rect?.top ?? 0) - 24)
    } else {
      editSelected()
      redraw()
    }
  }
}

function onContextMenu(e) {
  const { x, y } = getCanvasPos(e)
  const hit = hitTest(x, y)
  if (hit) {
    selectedId.value = hit.id
    ctxMenu.value = { show: true, x: e.clientX, y: e.clientY, targetId: hit.id }
  }
}

function onMouseLeave() {
  hoverInfo.value.show = false
}

// 菜单操作
function startEditText() {
  const shape = shapes.value.find(s => s.id === selectedId.value)
  if (!shape || shape.type !== 'text') return
  ctxMenu.value.show = false
  const pixel = shape.points?.[0] ? toPixel(shape.points[0].price, shape.points[0].timestamp) : null
  const rect = canvasRef.value?.getBoundingClientRect()
  startInlineEdit(shape, (pixel?.x ?? 100) + (rect?.left ?? 0), (pixel?.y ?? 100) + (rect?.top ?? 0) - 24)
}

function editSelected() {
  const shape = shapes.value.find(s => s.id === selectedId.value)
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
  
  saveHistory()
  shape.color = styleEditor.value.color
  shape.lineWidth = styleEditor.value.lineWidth
  shape.lineDash = styleEditor.value.lineDash
  if (shape.type === 'text') {
    const sanitized = sanitizeText(styleEditor.value.text)
    shape.text = sanitized
    styleEditor.value.text = sanitized
  }
  
  saveToStorage()
  redraw()
}

function duplicateSelected() {
  const shape = shapes.value.find(s => s.id === selectedId.value)
  if (!shape) return
  
  saveHistory()
  const newShape = {
    ...JSON.parse(JSON.stringify(shape)),
    id: genId(),
    points: shape.points.map(p => ({
      ...p,
      timestamp: p.timestamp + 86400000
    })),
    createdAt: Date.now()
  }
  shapes.value.push(newShape)
  selectedId.value = newShape.id
  
  saveToStorage()
  redraw()
  ctxMenu.value.show = false
}

function ctxDeleteShape() {
  const id = ctxMenu.value.targetId || selectedId.value
  if (!id) return
  
  saveHistory()
  shapes.value = shapes.value.filter(s => s.id !== id)
  selectedId.value = null
  emit('deleted', id)
  saveToStorage()
  redraw()
  ctxMenu.value.show = false
}

function hitTest(x, y) {
  const R = 8
  
  for (let i = shapes.value.length - 1; i >= 0; i--) {
    const shape = shapes.value[i]
    const pixelPoints = shape.points.map(p => toPixel(p.price, p.timestamp)).filter(Boolean)
    if (pixelPoints.length === 0) continue
    
    for (let j = 0; j < pixelPoints.length; j++) {
      const p = pixelPoints[j]
      if (Math.hypot(p.x - x, p.y - y) < R) {
        return { id: shape.id, pointIdx: j }
      }
    }
    
    if (pixelPoints.length >= 2) {
      const p0 = pixelPoints[0]
      const p1 = pixelPoints[1]
      const dist = distToSegment(x, y, p0.x, p0.y, p1.x, p1.y)
      if (dist < R + 4) {
        return { id: shape.id, pointIdx: -1 }
      }
    }
    
    if (shape.type === 'hray' && pixelPoints.length >= 1) {
      if (Math.abs(pixelPoints[0].y - y) < R + 4) {
        return { id: shape.id, pointIdx: -1 }
      }
    }
    
    if (shape.type === 'vline' && pixelPoints.length >= 1) {
      if (Math.abs(pixelPoints[0].x - x) < R + 4) {
        return { id: shape.id, pointIdx: -1 }
      }
    }
    
    if (shape.type === 'rect' && pixelPoints.length >= 2) {
      const p0 = pixelPoints[0]
      const p1 = pixelPoints[1]
      const minX = Math.min(p0.x, p1.x), maxX = Math.max(p0.x, p1.x)
      const minY = Math.min(p0.y, p1.y), maxY = Math.max(p0.y, p1.y)
      
      if (x >= minX - R && x <= maxX + R && y >= minY - R && y <= maxY + R) {
        const onBorder = x <= minX + R || x >= maxX - R || y <= minY + R || y >= maxY - R
        if (onBorder) return { id: shape.id, pointIdx: -1 }
      }
    }
    
    if (shape.type === 'circle' && pixelPoints.length >= 2) {
      const p0 = pixelPoints[0]
      const p1 = pixelPoints[1]
      const r = Math.hypot(p1.x - p0.x, p1.y - p0.y)
      const dist = Math.abs(Math.hypot(x - p0.x, y - p0.y) - r)
      if (dist < R + 4) return { id: shape.id, pointIdx: -1 }
    }
  }
  
  return null
}

function distToSegment(px, py, x0, y0, x1, y1) {
  const dx = x1 - x0, dy = y1 - y0
  if (dx === 0 && dy === 0) return Math.hypot(px - x0, py - y0)
  const t = Math.max(0, Math.min(1, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)))
  return Math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))
}

function getToolLabel(type) {
  const labels = {
    trend: '趋势线', line: '直线', ray: '射线', segment: '线段',
    hray: '水平线', vline: '垂直线', channel: '平行通道', fib: '斐波那契',
    rect: '矩形', circle: '圆形', text: '文本'
  }
  return labels[type] || type
}

function genId() {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4)
}

function clearAll() {
  saveHistory()
  shapes.value = []
  selectedId.value = null
  drawing.value = null
  emit('cleared')
  saveToStorage()
  redraw()
}

function deleteSelected() {
  if (selectedId.value) {
    saveHistory()
    shapes.value = shapes.value.filter(s => s.id !== selectedId.value)
    emit('deleted', selectedId.value)
    selectedId.value = null
    saveToStorage()
    redraw()
  }
}

function getShapes() {
  return shapes.value
}

async function saveToStorage() {
  try {
    const key = `${props.symbol}_${props.period}`
    await storage.setItem(key, JSON.stringify(shapes.value))
  } catch (e) { logger.error('保存画线失败:', e) }
}

async function loadFromStorage() {
  try {
    const key = `${props.symbol}_${props.period}`
    const raw = await storage.getItem(key)
    if (raw) {
      shapes.value = JSON.parse(raw)
    } else {
      await loadFromOtherPeriods()
    }
  } catch (e) {
    shapes.value = []
  }
  undoStack.value = []
  redoStack.value = []
  redraw()
}

async function loadFromOtherPeriods() {
  try {
    const allKeys = await storage.keys()
    const symbolKeys = allKeys.filter(k => k.startsWith(`${props.symbol}_`))
    
    if (symbolKeys.length === 0) return
    
    const allShapes = []
    for (const key of symbolKeys) {
      const raw = await storage.getItem(key)
      if (raw) allShapes.push(...JSON.parse(raw))
    }
    
    const seen = new Set()
    shapes.value = allShapes.filter(s => {
      if (seen.has(s.id)) return false
      seen.add(s.id)
      return true
    })
  } catch (e) {
    logger.error('[DrawingCanvas] filter error:', e.message)
  }
}

function resizeCanvas() {
  if (!canvasRef.value) return
  const parent = canvasRef.value.parentElement
  if (!parent) return
  canvasRef.value.width = parent.clientWidth
  canvasRef.value.height = parent.clientHeight
  redraw()
}

onMounted(() => {
  ctx = canvasRef.value.getContext('2d')
  resizeCanvas()
  loadFromStorage()
  
  window.addEventListener('resize', resizeCanvas)
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.context-menu') && !e.target.closest('.style-editor')) {
      ctxMenu.value.show = false
    }
  })
  
  if (canvasRef.value?.parentElement) {
    const ro = new ResizeObserver(() => resizeCanvas())
    ro.observe(canvasRef.value.parentElement)
  }
})

onUnmounted(() => {
  cancelAnimationFrame(animationFrame)
  window.removeEventListener('resize', resizeCanvas)
})

watch(() => [props.symbol, props.period], () => loadFromStorage(), { immediate: true })

// activeTool 变化 → 同步状态机
watch(() => props.activeTool, (tool) => {
  if (tool && tool !== 'select') {
    setState(DrawState.DRAWING)
  } else {
    setState(DrawState.IDLE)
  }
  redraw()
})

watch([() => props.activeTool, () => props.activeColor, () => props.magnetMode], () => redraw())
watch(shapes, () => redraw(), { deep: true })

defineExpose({ 
  clearAll, deleteSelected, getShapes, undo, redo,
  canUndo: () => undoStack.value.length > 0,
  canRedo: () => redoStack.value.length > 0
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

/* 内联文本编辑覆盖层 */
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
