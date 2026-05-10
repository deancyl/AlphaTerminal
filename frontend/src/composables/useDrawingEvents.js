/**
 * useDrawingEvents.js — DrawingCanvas 事件处理
 * 
 * 负责：
 * - 鼠标事件（down/move/up/dblclick）
 * - 右键菜单
 * - 命中测试
 * - 拖拽逻辑
 */
import { } from 'vue'

/**
 * 事件处理 composable
 */
export function useDrawingEvents() {
  // ═══════════════════════════════════════════════════════════════
  // 命中测试
  // ═══════════════════════════════════════════════════════════════
  function hitTest(x, y, shapes, toPixel) {
    const R = 8
    
    for (let i = shapes.length - 1; i >= 0; i--) {
      const shape = shapes[i]
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

  // ═══════════════════════════════════════════════════════════════
  // 事件处理
  // ═══════════════════════════════════════════════════════════════
  function getCanvasPos(e, canvasRef) {
    const rect = canvasRef.getBoundingClientRect()
    return { x: e.clientX - rect.left, y: e.clientY - rect.top }
  }

  function createMouseHandlers(options) {
    const {
      canvasRef,
      chartInstance,
      state,
      renderer,
      storage,
      props,
      emit,
      startInlineEdit,
    } = options

    const onMouseDown = (e) => {
      if (state.currentState.value === 'EDITING') return
      if (e.button !== 0) return
      if (props.locked) return
      
      const { x, y } = getCanvasPos(e, canvasRef)
      
      if (props.activeTool === 'select') {
        const hit = hitTest(x, y, state.shapes.value, (p, t) => renderer.toPixel(chartInstance, p, t))
        if (hit) {
          state.select(hit.id)
          if (hit.pointIdx >= 0) {
            state.startDrag(hit.id, hit.pointIdx, x, y)
          } else {
            const shape = state.getShape(hit.id)
            if (shape && shape.type !== 'hray' && shape.type !== 'vline') {
              state.startDrag(hit.id, -1, x, y, shape.points)
            }
          }
          return { needRedraw: true }
        } else {
          state.deselect()
          return { needRedraw: true }
        }
      }
      
      if (props.activeTool === 'text') {
        const data = renderer.toData(chartInstance, x, y)
        if (!data) return { needRedraw: false }
        state.saveHistory()
        const shape = {
          id: state.genId(),
          type: 'text',
          points: [{ price: data.price, timestamp: data.timestamp }],
          color: props.activeColor,
          text: '',
          fontSize: 12,
          lineWidth: 1.5,
          createdAt: Date.now(),
        }
        state.addShape(shape)
        const rect = canvasRef?.getBoundingClientRect()
        const pixel = renderer.toPixel(chartInstance, data.price, data.timestamp)
        startInlineEdit(shape, (pixel?.x ?? x) + (rect?.left ?? 0), (pixel?.y ?? y) + (rect?.top ?? 0) - 24)
        emit('drawn', shape)
        storage.saveToStorage()
        return { needRedraw: true }
      }
      
      const hit = hitTest(x, y, state.shapes.value, (p, t) => renderer.toPixel(chartInstance, p, t))
      if (hit) {
        state.select(hit.id)
        if (hit.pointIdx >= 0) {
          state.startDrag(hit.id, hit.pointIdx, x, y)
        } else {
          const shape = state.getShape(hit.id)
          if (shape && shape.type !== 'hray' && shape.type !== 'vline') {
            state.startDrag(hit.id, -1, x, y, shape.points)
          }
        }
        return { needRedraw: true }
      }
      
      if (!props.activeTool) return { needRedraw: false }
      
      const data = renderer.toData(chartInstance, x, y)
      if (!data) return { needRedraw: false }
      
      const snapped = renderer.snapToKLine(chartInstance, x, y, props.magnetMode)
      state.deselect()
      state.startDrawing({
        id: 'drawing-' + Date.now(),
        type: props.activeTool,
        points: [{
          price: snapped.price ?? data.price,
          timestamp: snapped.timestamp ?? data.timestamp
        }],
        color: props.activeColor,
        lineWidth: 1.5,
        createdAt: Date.now()
      })
      return { needRedraw: true }
    }

    const onMouseMove = (e) => {
      if (state.currentState.value === 'EDITING') return { needRedraw: false }
      
      const { x, y } = getCanvasPos(e, canvasRef)
      state.mouseX.value = x
      state.mouseY.value = y
      
      if (props.locked) {
        state.cursorStyle.value = 'not-allowed'
        return { needRedraw: false }
      } else if (state.currentState.value === 'EDITING') {
        state.cursorStyle.value = 'text'
      } else if (props.activeTool === 'select') {
        state.cursorStyle.value = 'default'
      } else if (props.activeTool) {
        state.cursorStyle.value = 'crosshair'
      } else if (state.dragging.value) {
        state.cursorStyle.value = state.dragging.value.pointIdx >= 0 ? 'grabbing' : 'move'
      } else if (state.hoveredId.value) {
        const hit = hitTest(x, y, state.shapes.value, (p, t) => renderer.toPixel(chartInstance, p, t))
        state.cursorStyle.value = hit?.pointIdx >= 0 ? 'grab' : 'pointer'
      } else {
        state.cursorStyle.value = 'default'
      }
      
      if (state.dragging.value) {
        const shape = state.getShape(state.dragging.value.id)
        if (!shape) return { needRedraw: false }
        
        if (state.dragging.value.pointIdx >= 0) {
          const data = renderer.toData(chartInstance, x, y)
          if (data) {
            const snapped = renderer.snapToKLine(chartInstance, x, y, props.magnetMode)
            shape.points[state.dragging.value.pointIdx] = {
              price: snapped.price ?? data.price,
              timestamp: snapped.timestamp ?? data.timestamp
            }
            return { needRedraw: true }
          }
        } else {
          const dx = x - state.dragStartPos.value.x
          const dy = y - state.dragStartPos.value.y
          
          shape.points = state.dragStartPos.value.points.map((p) => {
            const pixel = renderer.toPixel(chartInstance, p.price, p.timestamp)
            if (!pixel) return p
            const newPixel = { x: pixel.x + dx, y: pixel.y + dy }
            const data = renderer.toData(chartInstance, newPixel.x, newPixel.y)
            return data ? { price: data.price, timestamp: data.timestamp } : p
          })
          return { needRedraw: true }
        }
        return { needRedraw: false }
      }
      
      if (props.activeTool) {
        state.snappedPoint.value = renderer.snapToKLine(chartInstance, x, y, props.magnetMode)
        if (state.drawing.value) return { needRedraw: true }
      }
      
      const hit = hitTest(x, y, state.shapes.value, (p, t) => renderer.toPixel(chartInstance, p, t))
      const hoverInfo = { show: false, x: 0, y: 0, text: '' }
      
      if (hit?.id !== state.hoveredId.value) {
        state.hover(hit?.id ?? null)
        
        if (hit) {
          const shape = state.getShape(hit.id)
          if (shape) {
            hoverInfo.show = true
            hoverInfo.x = x + 12
            hoverInfo.y = y - 24
            hoverInfo.text = `${state.getToolLabel(shape.type)} - ${shape.points[0]?.price?.toFixed(2) ?? ''}`
          }
        }
        return { needRedraw: true, hoverInfo }
      }
      
      return { needRedraw: false }
    }

    const onMouseUp = (e) => {
      if (state.dragging.value) {
        if (state.dragStartPos.value && (Math.abs(e.clientX - state.dragStartPos.value.x) > 2 || Math.abs(e.clientY - state.dragStartPos.value.y) > 2)) {
          state.saveHistory()
          storage.saveToStorage()
        }
        state.endDrag()
        return { needRedraw: false }
      }
      
      if (!state.drawing.value || !props.activeTool) return { needRedraw: false }
      
      const { x, y } = getCanvasPos(e, canvasRef)
      const data = renderer.toData(chartInstance, x, y)
      if (!data) return { needRedraw: false }
      
      const snapped = renderer.snapToKLine(chartInstance, x, y, props.magnetMode)
      state.drawing.value.points.push({
        price: snapped.price ?? data.price,
        timestamp: snapped.timestamp ?? data.timestamp
      })
      
      const minPoints = { 
        trend: 2, line: 2, ray: 2, segment: 2, 
        hray: 1, vline: 1, channel: 2, fib: 2, 
        rect: 2, circle: 2 
      }
      
      if ((minPoints[state.drawing.value.type] || 2) <= state.drawing.value.points.length) {
        state.saveHistory()
        const shape = { ...state.drawing.value, id: state.genId() }
        state.addShape(shape)
        emit('drawn', shape)
        storage.saveToStorage()
        state.finishDrawing()
      }
      return { needRedraw: true }
    }

    const onDblClick = (e) => {
      if (state.currentState.value === 'EDITING') return { needRedraw: false }
      const { x, y } = getCanvasPos(e, canvasRef)
      const hit = hitTest(x, y, state.shapes.value, (p, t) => renderer.toPixel(chartInstance, p, t))
      if (hit) {
        state.select(hit.id)
        const shape = state.getShape(hit.id)
        if (shape?.type === 'text') {
          const pixel = shape.points?.[0] ? renderer.toPixel(chartInstance, shape.points[0].price, shape.points[0].timestamp) : null
          const rect = canvasRef?.getBoundingClientRect()
          startInlineEdit(shape, (pixel?.x ?? x) + (rect?.left ?? 0), (pixel?.y ?? y) + (rect?.top ?? 0) - 24)
          return { needRedraw: false, startEdit: true }
        } else {
          return { needRedraw: true, openStyleEditor: true }
        }
      }
      return { needRedraw: false }
    }

    const onContextMenu = (e) => {
      const { x, y } = getCanvasPos(e, canvasRef)
      const hit = hitTest(x, y, state.shapes.value, (p, t) => renderer.toPixel(chartInstance, p, t))
      if (hit) {
        state.select(hit.id)
        return { showMenu: true, x: e.clientX, y: e.clientY, targetId: hit.id }
      }
      return { showMenu: false }
    }

    const onMouseLeave = () => {
      return { hoverInfo: { show: false } }
    }

    return {
      getCanvasPos,
      hitTest,
      distToSegment,
      onMouseDown,
      onMouseMove,
      onMouseUp,
      onDblClick,
      onContextMenu,
      onMouseLeave,
    }
  }

  return {
    hitTest,
    distToSegment,
    getCanvasPos,
    createMouseHandlers,
  }
}
