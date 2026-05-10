/**
 * useDrawingRenderer.js — DrawingCanvas 渲染逻辑
 * 
 * 负责：
 * - Canvas 绑定和上下文管理
 * - 图形绘制（各类工具）
 * - 重绘调度
 * - 坐标转换
 */
import { ref } from 'vue'
import { logger } from '../utils/logger.js'

/**
 * 渲染 composable
 */
export function useDrawingRenderer() {
  const canvasRef = ref(null)
  let ctx = null
  let animationFrame = null

  // ═══════════════════════════════════════════════════════════════
  // Canvas 初始化
  // ═══════════════════════════════════════════════════════════════
  function initCanvas(canvas) {
    canvasRef.value = canvas
    ctx = canvas?.getContext('2d')
    return ctx
  }

  function resizeCanvas() {
    if (!canvasRef.value) return
    const parent = canvasRef.value.parentElement
    if (!parent) return
    canvasRef.value.width = parent.clientWidth
    canvasRef.value.height = parent.clientHeight
  }

  function getCanvas() {
    return canvasRef.value
  }

  function getContext() {
    return ctx
  }

  // ═══════════════════════════════════════════════════════════════
  // 坐标转换
  // ═══════════════════════════════════════════════════════════════
  function getTimestampByIndex(chartInstance, idx) {
    try {
      const option = chartInstance.getOption()
      const times = option.xAxis?.[0]?.data
      if (times && times[idx]) return new Date(times[idx]).getTime()
    } catch (e) {
      // ignore parsing errors
    }
    return null
  }

  function getIndexByTimestamp(chartInstance, timestamp) {
    if (!timestamp) return null
    try {
      const option = chartInstance.getOption()
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

  function toPixel(chartInstance, price, timestamp) {
    if (!chartInstance) return null
    try {
      const idx = getIndexByTimestamp(chartInstance, timestamp)
      if (idx == null) return null
      const pixel = chartInstance.convertToPixel({ gridIndex: 0 }, [idx, price])
      return pixel ? { x: pixel[0], y: pixel[1] } : null
    } catch { return null }
  }

  function toData(chartInstance, x, y) {
    if (!chartInstance) return null
    try {
      const [idx, price] = chartInstance.convertFromPixel({ gridIndex: 0 }, [x, y])
      return { idx: Math.round(idx), price, timestamp: getTimestampByIndex(chartInstance, Math.round(idx)) }
    } catch (e) {
      logger.warn('[DrawingCanvas] toData convertFromPixel failed:', e)
      return null
    }
  }

  // ═══════════════════════════════════════════════════════════════
  // 磁吸
  // ═══════════════════════════════════════════════════════════════
  function snapToKLine(chartInstance, x, y, magnetMode) {
    if (!chartInstance || !magnetMode) return { x, y }
    
    try {
      const converted = chartInstance.convertFromPixel({ gridIndex: 0 }, [x, y])
      if (!converted) return { x, y }
      
      const [idx] = converted
      const roundedIdx = Math.round(idx)
      
      const option = chartInstance.getOption()
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
        const pixelY = chartInstance.convertToPixel({ gridIndex: 0 }, [0, c.price])?.[1]
        if (pixelY == null) continue
        const dist = Math.abs(pixelY - y)
        if (dist < minDist && dist < SNAP_THRESHOLD) {
          minDist = dist
          closest = c
        }
      }
      
      if (closest) {
        const snappedY = chartInstance.convertToPixel({ gridIndex: 0 }, [0, closest.price])?.[1]
        return { 
          x, y: snappedY ?? y, price: closest.price, 
          timestamp: getTimestampByIndex(chartInstance, roundedIdx),
          idx: roundedIdx, magnetTo: closest.label
        }
      }
    } catch (e) {
      logger.warn('[DrawingCanvas] snapToKLine convertFromPixel failed:', e)
    }
    
    return { x, y }
  }

  // ═══════════════════════════════════════════════════════════════
  // 绘制图形
  // ═══════════════════════════════════════════════════════════════
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

  function drawShape(chartInstance, shape, options = {}) {
    const { isHovered = false, isSelected = false, drawing: drawingState, mouseX, mouseY, snappedPoint } = options
    
    if (!shape.points || shape.points.length < 1) return
    if (!ctx) return
    
    const pixelPoints = shape.points.map(p => toPixel(chartInstance, p.price, p.timestamp)).filter(Boolean)
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
        } else if (drawingState?.id === shape.id && snappedPoint) {
          const snap = snappedPoint || { x: mouseX, y: mouseY }
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
        } else if (drawingState?.id === shape.id && snappedPoint) {
          const snap = snappedPoint || { x: mouseX, y: mouseY }
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
        } else if (drawingState?.id === shape.id && snappedPoint) {
          const snap = snappedPoint || { x: mouseX, y: mouseY }
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
        } else if (drawingState?.id === shape.id && snappedPoint) {
          const snap = snappedPoint || { x: mouseX, y: mouseY }
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
          const p1 = pixelPoints[1] || (snappedPoint || { x: mouseX, y: mouseY })
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
        } else if (drawingState?.id === shape.id && snappedPoint) {
          const snap = snappedPoint || { x: mouseX, y: mouseY }
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
        } else if (drawingState?.id === shape.id && snappedPoint) {
          const snap = snappedPoint || { x: mouseX, y: mouseY }
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

  function redraw(chartInstance, shapes, options = {}) {
    if (!ctx || !canvasRef.value) return
    cancelAnimationFrame(animationFrame)
    animationFrame = requestAnimationFrame(() => {
      const canvas = canvasRef.value
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      
      const { hoveredId, selectedId, drawing: drawingState, mouseX, mouseY, snappedPoint } = options
      
      shapes.forEach(shape => {
        drawShape(chartInstance, shape, {
          isHovered: shape.id === hoveredId,
          isSelected: shape.id === selectedId,
          drawing: drawingState,
          mouseX,
          mouseY,
          snappedPoint
        })
      })
      
      if (drawingState) {
        drawShape(chartInstance, drawingState, { mouseX, mouseY, snappedPoint })
      }
    })
  }

  function cancelAnimation() {
    if (animationFrame) {
      cancelAnimationFrame(animationFrame)
    }
  }

  return {
    canvasRef,
    initCanvas,
    resizeCanvas,
    getCanvas,
    getContext,
    getTimestampByIndex,
    getIndexByTimestamp,
    toPixel,
    toData,
    snapToKLine,
    drawShape,
    drawArrow,
    redraw,
    cancelAnimation,
  }
}
