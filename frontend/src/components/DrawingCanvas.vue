<template>
  <!-- Canvas 覆盖层：透明背景，捕获图表上所有鼠标事件 -->
  <canvas
    ref="canvasRef"
    class="absolute inset-0 w-full h-full"
    :style="{ cursor: cursorStyle }"
    @mousedown="onMouseDown"
    @mousemove="onMouseMove"
    @mouseup="onMouseUp"
    @dblclick="onDblClick"
    @contextmenu.prevent="onContextMenu"
  />
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import localforage from 'localforage'
import { UP, DOWN } from '../utils/indicators.js'

const props = defineProps({
  // 绑定到哪个 ECharts 实例（通过 convertFromPixel 转换坐标）
  chartInstance:  { type: Object,  default: null },
  activeTool:     { type: String,  default: '' },   // '' | 'line' | 'ray' | 'segment' | 'hray' | 'channel' | 'fib' | 'rect' | 'text'
  activeColor:    { type: String,  default: '#fbbf24' },
  magnetMode:     { type: Boolean, default: true },
  symbol:        { type: String,  default: '' },
})

const emit = defineEmits([
  'drawn',        // (shape) 新绘制了图形
  'deleted',      // (id) 删除了图形
  'cleared',      // ()  清除了全部
])

// ── 状态 ────────────────────────────────────────────────────
const canvasRef = ref(null)
let ctx = null
let animationFrame = null

// 坐标映射：像素坐标 → 数据索引 + 像素偏移
const coordConverter = ref(null)   // { gridIndex, xAxisIndex } 传给 chartInstance.convertFromPixel

// 所有已保存的图形
const shapes = ref([])             // [{ id, type, points:[{x,y,price,idx}], color, locked, text? }]

// 正在绘制的图形
const drawing = ref(null)          // { type, points:[], color }
const selectedId = ref(null)       // 选中图形 id
const hoveredId  = ref(null)        // 悬停图形 id

// 拖拽状态
const dragging = ref(null)          // { id, pointIdx, startX, startY }
const resizing = ref(null)          // { id, pointIdx, startX, startY }

// 鼠标位置
const mouseX = ref(0)
const mouseY = ref(0)
const snappedPoint = ref(null)      // 磁吸后的 { x, y, price, idx }

// ── 磁吸 ────────────────────────────────────────────────────
function snapToKLine(x, y) {
  if (!props.chartInstance || !props.magnetMode || !props.symbol) return { x, y }
  const opt = props.chartInstance.getOption()
  const grid = opt.grid?.[0]
  if (!grid) return { x, y }

  // 从像素坐标转换为数据索引
  try {
    const converted = props.chartInstance.convertFromPixel({ gridIndex: 0 }, [x, y])
    if (!converted) return { x, y }
    const idx = Math.round(converted[0])
    const price = converted[1]
    if (idx < 0) return { x, y }

    // 获取该索引对应的 K 线数据
    const seriesData = props.chartInstance.getOption().series
    const candlestickData = seriesData?.[0]?.data
    if (!candlestickData || !candlestickData[idx]) return { x, y }

    if (idx < 0 || idx >= candlestickData.length) return { x, y }
    const [open, close, low, high] = candlestickData[idx] || []
    if (high == null || low == null) return { x, y }
    const SNAP_THRESHOLD = 15  // 像素

    // 吸附到最近的 OHLC 价格
    const candidates = [open, close, low, high]
    let closest = null, minDist = Infinity
    for (const c of candidates) {
      if (c == null) continue
      const py = props.chartInstance.convertToPixel({ gridIndex: 0 }, [0, c])?.[1]
      if (py == null) continue
      const dist = Math.abs(py - y)
      if (dist < minDist) { minDist = dist; closest = c }
    }

    if (closest !== null && minDist < SNAP_THRESHOLD) {
      const snappedY = props.chartInstance.convertToPixel({ gridIndex: 0 }, [0, closest])?.[1]
      if (snappedY != null) {
        return { x, y: snappedY, price: closest, idx }
      }
    }
  } catch (e) { /* ignore */ }

  return { x, y }
}

// ── 像素/数据坐标互转 ───────────────────────────────────────
function toPixel(price, idx) {
  if (!props.chartInstance) return { x: 0, y: 0 }
  try {
    return {
      x: props.chartInstance.convertToPixel({ gridIndex: 0 }, [idx, price])?.[0] ?? 0,
      y: props.chartInstance.convertToPixel({ gridIndex: 0 }, [idx, price])?.[1] ?? 0,
    }
  } catch { return { x: 0, y: 0 } }
}

function toData(x, y) {
  if (!props.chartInstance) return { idx: 0, price: 0 }
  try {
    const [idx, price] = props.chartInstance.convertFromPixel({ gridIndex: 0 }, [x, y]) ?? [0, 0]
    return { idx: Math.round(idx), price }
  } catch { return { idx: 0, price: 0 } }
}

// ── 绘图 ────────────────────────────────────────────────────
function drawShape(ctx, shape, isHovered = false, isSelected = false) {
  if (!shape.points || shape.points.length < 1) return
  ctx.save()
  ctx.strokeStyle = shape.color || '#fbbf24'
  ctx.lineWidth = isSelected ? 2 : (isHovered ? 1.8 : 1.2)
  ctx.setLineDash(shape.type === 'hray' || shape.type === 'ray' ? [6, 4] : [])
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'

  const p0 = toPixel(shape.points[0].price, shape.points[0].idx)

  if (shape.type === 'line' || shape.type === 'segment' || shape.type === 'trend') {
    // 直线/线段/趋势线
    if (shape.points.length < 2) {
      // 绘制到鼠标位置
      const snap = snappedPoint.value || { x: mouseX.value, y: mouseY.value }
      ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(snap.x, snap.y); ctx.stroke()
    } else {
      const p1 = toPixel(shape.points[1].price, shape.points[1].idx)
      ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(p1.x, p1.y); ctx.stroke()
      if (shape.type === 'segment') {
        // 画端点
        ctx.fillStyle = shape.color
        ;[p0, p1].forEach(p => { ctx.beginPath(); ctx.arc(p.x, p.y, 4, 0, Math.PI * 2); ctx.fill() })
      }
    }
  } else if (shape.type === 'ray') {
    // 射线（向右延伸）
    if (shape.points.length < 2) {
      const snap = snappedPoint.value || { x: mouseX.value, y: mouseY.value }
      ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(snap.x, snap.y); ctx.stroke()
    } else {
      const p1 = toPixel(shape.points[1].price, shape.points[1].idx)
      const dx = p1.x - p0.x, dy = p1.y - p0.y
      const scale = 5000
      ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(p0.x + dx * scale, p0.y + dy * scale); ctx.stroke()
    }
  } else if (shape.type === 'hray') {
    // 水平射线
    if (shape.points.length < 2) {
      const snap = snappedPoint.value || { x: mouseX.value, y: mouseY.value }
      ctx.beginPath(); ctx.moveTo(0, p0.y); ctx.lineTo(canvasRef.value?.width || 1000, p0.y); ctx.stroke()
    } else {
      const py = p0.y
      ctx.beginPath(); ctx.moveTo(0, py); ctx.lineTo(canvasRef.value?.width || 1000, py); ctx.stroke()
    }
  } else if (shape.type === 'channel') {
    // 平行通道
    if (shape.points.length < 2) {
      const snap = snappedPoint.value || { x: mouseX.value, y: mouseY.value }
      const dy = snap.y - p0.y
      ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(snap.x, snap.y); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(p0.x, p0.y + dy); ctx.lineTo(snap.x, snap.y + dy); ctx.stroke()
    } else {
      const p1 = toPixel(shape.points[1].price, shape.points[1].idx)
      const dy = p1.y - p0.y
      ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(p1.x, p1.y); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(p0.x, p0.y - dy); ctx.lineTo(p1.x, p1.y - dy); ctx.stroke()
    }
  } else if (shape.type === 'fib') {
    // 黄金分割（从 p0 到鼠标位）
    const snap = snappedPoint.value || { x: mouseX.value, y: mouseY.value }
    const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    const labels = ['0', '23.6', '38.2', '50', '61.8', '78.6', '100']
    ctx.setLineDash([])
    levels.forEach((level, i) => {
      const y = p0.y + (snap.y - p0.y) * level
      ctx.strokeStyle = i === 2 || i === 4 ? shape.color : shape.color + '88'
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvasRef.value?.width || 1000, y); ctx.stroke()
      ctx.fillStyle = shape.color
      ctx.font = '10px monospace'
      ctx.fillText(labels[i] + '%', 4, y - 2)
    })
    // 绘制主趋势线
    ctx.strokeStyle = shape.color
    ctx.setLineDash([])
    ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(snap.x, snap.y); ctx.stroke()
  } else if (shape.type === 'rect') {
    // 矩形
    if (shape.points.length < 2) {
      const snap = snappedPoint.value || { x: mouseX.value, y: mouseY.value }
      ctx.beginPath(); ctx.rect(p0.x, p0.y, snap.x - p0.x, snap.y - p0.y); ctx.stroke()
    } else {
      const p1 = toPixel(shape.points[1].price, shape.points[1].idx)
      ctx.beginPath(); ctx.rect(p0.x, p0.y, p1.x - p0.x, p1.y - p0.y); ctx.stroke()
      ctx.fillStyle = (shape.color || '#fbbf24') + '15'
      ctx.fillRect(p0.x, p0.y, p1.x - p0.x, p1.y - p0.y)
    }
  } else if (shape.type === 'text') {
    // 文本标注
    if (shape.text) {
      ctx.fillStyle = shape.color || '#fbbf24'
      ctx.font = '12px sans-serif'
      ctx.fillText(shape.text, p0.x, p0.y)
    }
  }

  // 选中状态：画控制点
  if (isSelected) {
    ctx.fillStyle = '#ffffff'
    ctx.strokeStyle = shape.color || '#fbbf24'
    ctx.lineWidth = 1.5
    ctx.setLineDash([])
    shape.points.forEach(pt => {
      const p = toPixel(pt.price, pt.idx)
      ctx.beginPath(); ctx.arc(p.x, p.y, 5, 0, Math.PI * 2)
      ctx.fill(); ctx.stroke()
    })
  }

  ctx.restore()
}

function redraw() {
  if (!ctx || !canvasRef.value) return
  cancelAnimationFrame(animationFrame)
  animationFrame = requestAnimationFrame(() => {
    const canvas = canvasRef.value
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // 绘制已保存的图形
    shapes.value.forEach(shape => {
      drawShape(ctx, shape, shape.id === hoveredId.value, shape.id === selectedId.value)
    })

    // 绘制正在绘制的图形
    if (drawing.value) {
      drawShape(ctx, drawing.value)
    }
  })
}

// ── 鼠标事件 ─────────────────────────────────────────────────
function getCanvasPos(e) {
  const rect = canvasRef.value.getBoundingClientRect()
  return { x: e.clientX - rect.left, y: e.clientY - rect.top }
}

function onMouseDown(e) {
  if (e.button !== 0) return
  const { x, y } = getCanvasPos(e)

  if (props.activeTool === 'text') {
    // 文本：直接输入
    const text = prompt('输入标注文字：')
    if (text) {
      const { idx, price } = toData(x, y)
      const id = genId()
      const shape = { id, type: 'text', points: [{ x, y, price, idx }], color: props.activeColor, text }
      shapes.value.push(shape)
      emit('drawn', shape)
      saveToStorage()
    }
    return
  }

  // 检查是否点击了已有图形的控制点
  const hit = hitTest(x, y)
  if (hit) {
    selectedId.value = hit.id
    dragging.value = { ...hit, startX: x, startY: y }
    redraw()
    return
  }

  // 开始绘制新图形
  selectedId.value = null
  const { idx, price } = toData(x, y)
  const snapped = snapToKLine(x, y)
  drawing.value = {
    type: props.activeTool,
    points: [{ x: snapped.x, y: snapped.y, price: snapped.price ?? price, idx }],
    color: props.activeColor,
  }
}

function onMouseMove(e) {
  const { x, y } = getCanvasPos(e)
  mouseX.value = x
  mouseY.value = y

  if (dragging.value) {
    // 拖拽已有图形的控制点
    const snap = snapToKLine(x, y)
    const { idx, price } = toData(x, y)
    const shape = shapes.value.find(s => s.id === dragging.value.id)
    if (shape && shape.points[dragging.value.pointIdx]) {
      shape.points[dragging.value.pointIdx] = { x: snap.x, y: snap.y, price: snap.price ?? price, idx }
      redraw()
    }
    return
  }

  // 更新磁吸
  if (props.activeTool) {
    snappedPoint.value = snapToKLine(x, y)
    if (drawing.value) {
      redraw()
    }
  }

  // 检测悬停
  const hit = hitTest(x, y)
  hoveredId.value = hit?.id ?? null
  redraw()
}

function onMouseUp(e) {
  if (dragging.value) {
    saveToStorage()
    dragging.value = null
    return
  }

  if (!drawing.value || !props.activeTool) return

  const { x, y } = getCanvasPos(e)
  const snapped = snapToKLine(x, y)
  const { idx, price } = toData(x, y)

  drawing.value.points.push({ x: snapped.x, y: snapped.y, price: snapped.price ?? price, idx: idx })

  // 完成绘制的条件
  const minPoints = { line: 2, ray: 2, segment: 2, hray: 2, channel: 2, fib: 2, rect: 2 }
  if ((minPoints[drawing.value.type] || 2) <= drawing.value.points.length) {
    const shape = { ...drawing.value, id: genId() }
    shapes.value.push(shape)
    emit('drawn', shape)
    saveToStorage()
    drawing.value = null
  }
  redraw()
}

function onDblClick(e) {
  // 双击已有图形 → 选中（弹出操作菜单）
  const { x, y } = getCanvasPos(e)
  const hit = hitTest(x, y)
  if (hit) {
    selectedId.value = hit.id
    redraw()
  }
}

function onContextMenu(e) {
  const { x, y } = getCanvasPos(e)
  const hit = hitTest(x, y)
  if (hit) {
    selectedId.value = hit.id
    const action = confirm('删除此画线？')
    if (action) {
      shapes.value = shapes.value.filter(s => s.id !== hit.id)
      selectedId.value = null
      emit('deleted', hit.id)
      saveToStorage()
      redraw()
    }
  } else {
    // 无图形处右键：区间统计触发
    const { idx, price } = toData(x, y)
    emit('range-select', { idx, price })
  }
}

// ── 命中测试 ─────────────────────────────────────────────────
function hitTest(x, y) {
  const R = 8
  for (const shape of shapes.value) {
    for (let i = 0; i < shape.points.length; i++) {
      const pt = toPixel(shape.points[i].price, shape.points[i].idx)
      if (Math.hypot(pt.x - x, pt.y - y) < R) {
        return { id: shape.id, pointIdx: i }
      }
    }
  }
  return null
}

// ── 工具函数 ─────────────────────────────────────────────────
function genId() {
  return Math.random().toString(36).slice(2, 10)
}

function clearAll() {
  shapes.value = []
  selectedId.value = null
  drawing.value = null
  emit('cleared')
  saveToStorage()
  redraw()
}

function deleteSelected() {
  if (selectedId.value) {
    shapes.value = shapes.value.filter(s => s.id !== selectedId.value)
    emit('deleted', selectedId.value)
    selectedId.value = null
    saveToStorage()
    redraw()
  }
}

// ── 持久化 ───────────────────────────────────────────────────
const storage = localforage.createInstance({ name: 'AlphaTerminal', storeName: 'drawings' })

async function saveToStorage() {
  try {
    await storage.setItem(props.symbol || 'default', JSON.stringify(shapes.value))
  } catch (e) { /* ignore */ }
}

async function loadFromStorage() {
  try {
    const raw = await storage.getItem(props.symbol || 'default')
    if (raw) shapes.value = JSON.parse(raw)
    else shapes.value = []
  } catch {
    shapes.value = []
  }
  redraw()
}

// ── 生命周期 ───────────────────────────────────────────────
function resizeCanvas() {
  if (!canvasRef.value) return
  const parent = canvasRef.value.parentElement
  if (!parent) return
  canvasRef.value.width  = parent.clientWidth
  canvasRef.value.height = parent.clientHeight
  redraw()
}

onMounted(() => {
  ctx = canvasRef.value.getContext('2d')
  resizeCanvas()
  loadFromStorage()
  window.addEventListener('resize', resizeCanvas)
})

onUnmounted(() => {
  cancelAnimationFrame(animationFrame)
  window.removeEventListener('resize', resizeCanvas)
})

// symbol 变化时加载对应画线数据
watch(() => props.symbol, () => { loadFromStorage() })
watch([() => props.activeTool, () => props.activeColor, () => props.magnetMode], () => redraw())
watch(shapes, () => redraw(), { deep: true })

// ── 暴露方法 ────────────────────────────────────────────────
defineExpose({ clearAll, deleteSelected, shapes })
</script>
