<template>
  <div class="crosshair-overlay" :class="{ 'active': isActive, 'locked': locked }">
    <!-- 十字线 Canvas -->
    <canvas
      ref="crosshairCanvas"
      class="crosshair-canvas"
      @mousemove="onMouseMove"
      @mouseleave="onMouseLeave"
      @click="onClick"
    />

    <!-- 价格标签（Y轴） -->
    <div v-if="showLabels && crosshair.visible" class="price-label" :style="{ top: crosshair.y + 'px' }">
      <span class="price-value" :class="priceColor">{{ formatPrice(crosshair.price) }}</span>
    </div>

    <!-- 时间标签（X轴） -->
    <div v-if="showLabels && crosshair.visible" class="time-label" :style="{ left: crosshair.x + 'px' }">
      <span class="time-value">{{ formatTime(crosshair.timestamp) }}</span>
    </div>

    <!-- 信息浮窗 -->
    <div v-if="showTooltip && crosshair.visible && hoverData" class="data-tooltip" 
         :style="{ left: tooltipPos.x + 'px', top: tooltipPos.y + 'px' }"
    >
      <div class="tooltip-header">
        <span class="tooltip-date">{{ hoverData.date }}</span>
      </div>
      <div class="tooltip-row">
        <span class="label">开</span>
        <span class="value" :class="getPriceColor(hoverData.open, hoverData.close)">{{ formatPrice(hoverData.open) }}</span>
      </div>
      <div class="tooltip-row">
        <span class="label">高</span>
        <span class="value up">{{ formatPrice(hoverData.high) }}</span>
      </div>
      <div class="tooltip-row">
        <span class="label">低</span>
        <span class="value down">{{ formatPrice(hoverData.low) }}</span>
      </div>
      <div class="tooltip-row">
        <span class="label">收</span>
        <span class="value" :class="getPriceColor(hoverData.close, hoverData.open)">{{ formatPrice(hoverData.close) }}</span>
      </div>
      <div class="tooltip-row volume">
        <span class="label">量</span>
        <span class="value">{{ formatVolume(hoverData.volume) }}</span>
      </div>
      <div v-if="hoverData.changePct !== undefined" class="tooltip-row change">
        <span class="label">涨跌</span>
        <span class="value" :class="hoverData.changePct >= 0 ? 'up' : 'down'">
          {{ hoverData.changePct >= 0 ? '+' : '' }}{{ hoverData.changePct.toFixed(2) }}%
        </span>
      </div>
    </div>

    <!-- 坐标轴高亮线 -->
    <div v-if="crosshair.visible && showAxisHighlight" class="axis-highlight">
      <div class="x-highlight" :style="{ left: crosshair.x + 'px' }"></div>
      <div class="y-highlight" :style="{ top: crosshair.y + 'px' }"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { logger } from '../utils/logger.js'

const props = defineProps({
  chartInstance: { type: Object, default: null },
  data: { type: Array, default: () => [] },
  visible: { type: Boolean, default: true },
  locked: { type: Boolean, default: false },
  showLabels: { type: Boolean, default: true },
  showTooltip: { type: Boolean, default: true },
  showAxisHighlight: { type: Boolean, default: true },
  snapToCandle: { type: Boolean, default: true },
  followMouse: { type: Boolean, default: true },
})

const emit = defineEmits(['crosshair-move', 'candle-hover', 'click'])

// 状态
const crosshairCanvas = ref(null)
let ctx = null
let animationFrame = null

const isActive = ref(false)
const crosshair = ref({ visible: false, x: 0, y: 0, price: 0, timestamp: 0, index: -1 })
const hoverData = ref(null)
const tooltipPos = ref({ x: 0, y: 0 })

// 计算属性
const priceColor = computed(() => {
  if (!hoverData.value) return ''
  return hoverData.value.close >= hoverData.value.open ? 'up' : 'down'
})

// 初始化
onMounted(() => {
  ctx = crosshairCanvas.value.getContext('2d')
  resizeCanvas()
  window.addEventListener('resize', resizeCanvas)
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeCanvas)
  cancelAnimationFrame(animationFrame)
})

// 监听数据变化
watch(() => props.data, () => {
  if (crosshair.value.visible) {
    updateCrosshair(crosshair.value.x, crosshair.value.y)
  }
})

// Canvas 大小调整
function resizeCanvas() {
  if (!crosshairCanvas.value) return
  const parent = crosshairCanvas.value.parentElement
  if (!parent) return
  crosshairCanvas.value.width = parent.clientWidth
  crosshairCanvas.value.height = parent.clientHeight
  drawCrosshair()
}

// 鼠标移动
function onMouseMove(e) {
  if (!props.visible || props.locked) return
  
  const rect = crosshairCanvas.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top
  
  isActive.value = true
  updateCrosshair(x, y)
  
  // 计算 tooltip 位置
  const tooltipWidth = 140
  const tooltipHeight = 180
  let tooltipX = x + 15
  let tooltipY = y + 15
  
  // 边界检测
  if (tooltipX + tooltipWidth > rect.width) {
    tooltipX = x - tooltipWidth - 15
  }
  if (tooltipY + tooltipHeight > rect.height) {
    tooltipY = y - tooltipHeight - 15
  }
  
  tooltipPos.value = { x: tooltipX, y: tooltipY }
}

// 更新十字线位置
function updateCrosshair(x, y) {
  if (!props.chartInstance) return
  
  try {
    // 转换为数据坐标
    const [dataIndex, price] = props.chartInstance.convertFromPixel({ gridIndex: 0 }, [x, y])
    
    let finalX = x
    let finalY = y
    let finalIndex = Math.round(dataIndex)
    let finalPrice = price
    let finalTimestamp = 0
    
    // 磁吸到K线
    if (props.snapToCandle && props.data.length > 0) {
      finalIndex = Math.max(0, Math.min(finalIndex, props.data.length - 1))
      const candle = props.data[finalIndex]
      
      if (candle) {
        finalTimestamp = new Date(candle.date).getTime()
        
        // 计算最近的价格（开高低收）
        const prices = [candle.open, candle.high, candle.low, candle.close]
        let minDist = Infinity
        
        for (const p of prices) {
          const pixelY = props.chartInstance.convertToPixel({ gridIndex: 0 }, [0, p])?.[1]
          if (pixelY != null) {
            const dist = Math.abs(pixelY - y)
            if (dist < minDist && dist < 30) {
              minDist = dist
              finalPrice = p
            }
          }
        }
        
        // 获取X坐标
        const pixelX = props.chartInstance.convertToPixel({ gridIndex: 0 }, [finalIndex, 0])?.[0]
        if (pixelX != null) finalX = pixelX
        
        // 获取Y坐标
        const pixelY = props.chartInstance.convertToPixel({ gridIndex: 0 }, [0, finalPrice])?.[1]
        if (pixelY != null) finalY = pixelY
        
        // 更新悬浮数据
        hoverData.value = {
          date: candle.date,
          open: candle.open,
          high: candle.high,
          low: candle.low,
          close: candle.close,
          volume: candle.volume,
          changePct: candle.change_pct
        }
      }
    }
    
    crosshair.value = {
      visible: true,
      x: finalX,
      y: finalY,
      price: finalPrice,
      timestamp: finalTimestamp,
      index: finalIndex
    }
    
    emit('crosshair-move', crosshair.value)
    emit('candle-hover', hoverData.value)
    
    drawCrosshair()
  } catch (e) {
    logger.error('Crosshair update error:', e)
  }
}

// 绘制十字线
function drawCrosshair() {
  if (!ctx || !crosshairCanvas.value) return
  
  cancelAnimationFrame(animationFrame)
  animationFrame = requestAnimationFrame(() => {
    const canvas = crosshairCanvas.value
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    
    if (!crosshair.value.visible) return
    
    const { x, y } = crosshair.value
    
    ctx.save()
    
    // 设置线条样式
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.6)'
    ctx.lineWidth = 1
    ctx.setLineDash([4, 4])
    
    // 水平线
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(canvas.width, y)
    ctx.stroke()
    
    // 垂直线
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, canvas.height)
    ctx.stroke()
    
    // 中心点
    ctx.fillStyle = '#fbbf24'
    ctx.beginPath()
    ctx.arc(x, y, 3, 0, Math.PI * 2)
    ctx.fill()
    
    // 中心点外圈
    ctx.strokeStyle = '#fbbf24'
    ctx.lineWidth = 1
    ctx.setLineDash([])
    ctx.beginPath()
    ctx.arc(x, y, 6, 0, Math.PI * 2)
    ctx.stroke()
    
    ctx.restore()
  })
}

// 鼠标离开
function onMouseLeave() {
  isActive.value = false
  crosshair.value.visible = false
  hoverData.value = null
  drawCrosshair()
}

// 点击
function onClick(e) {
  if (!crosshair.value.visible) return
  emit('click', {
    x: crosshair.value.x,
    y: crosshair.value.y,
    price: crosshair.value.price,
    timestamp: crosshair.value.timestamp,
    index: crosshair.value.index,
    data: hoverData.value
  })
}

// 格式化
function formatPrice(price) {
  if (price == null) return '--'
  return price.toFixed(2)
}

function formatTime(timestamp) {
  if (!timestamp) return '--'
  const date = new Date(timestamp)
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function formatVolume(vol) {
  if (vol == null) return '--'
  if (vol >= 1e8) return (vol / 1e8).toFixed(2) + '亿股'
  if (vol >= 1e4) return (vol / 1e4).toFixed(2) + '万股'
  return vol.toFixed(0) + '股'
}

function getPriceColor(price, ref) {
  if (price > ref) return 'up'
  if (price < ref) return 'down'
  return ''
}

// 暴露方法
defineExpose({
  getCrosshair: () => crosshair.value,
  setCrosshair: (x, y) => updateCrosshair(x, y),
  hide: () => { crosshair.value.visible = false; drawCrosshair() }
})
</script>

<style scoped>
.crosshair-overlay {
  position: absolute;
  top: 48px;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 4;
}

.crosshair-overlay.active {
  pointer-events: auto;
}

.crosshair-overlay.locked {
  pointer-events: none !important;
}

.crosshair-canvas {
  width: 100%;
  height: 100%;
  cursor: crosshair;
}

/* 价格标签 */
.price-label {
  position: absolute;
  right: 0;
  transform: translateY(-50%);
  z-index: 10;
}

.price-value {
  display: block;
  background: rgba(17, 24, 39, 0.95);
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-right: none;
  padding: 2px 8px;
  font-size: 11px;
  font-family: monospace;
  font-weight: 600;
  color: #e5e7eb;
  min-width: 50px;
  text-align: right;
}

.price-value.up {
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.5);
}

.price-value.down {
  color: #22c55e;
  border-color: rgba(34, 197, 94, 0.5);
}

/* 时间标签 */
.time-label {
  position: absolute;
  bottom: 0;
  transform: translateX(-50%);
  z-index: 10;
}

.time-value {
  display: block;
  background: rgba(17, 24, 39, 0.95);
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-bottom: none;
  padding: 2px 8px;
  font-size: 10px;
  font-family: monospace;
  color: #9ca3af;
  white-space: nowrap;
}

/* 数据浮窗 */
.data-tooltip {
  position: absolute;
  background: rgba(17, 24, 39, 0.98);
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-radius: 6px;
  padding: 8px 12px;
  min-width: 120px;
  z-index: 20;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(8px);
}

.tooltip-header {
  margin-bottom: 6px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(75, 85, 99, 0.3);
}

.tooltip-date {
  font-size: 11px;
  color: #9ca3af;
  font-weight: 500;
}

.tooltip-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 3px 0;
  font-size: 11px;
}

.tooltip-row .label {
  color: #6b7280;
  min-width: 24px;
}

.tooltip-row .value {
  font-family: monospace;
  font-weight: 600;
  color: #e5e7eb;
}

.tooltip-row .value.up {
  color: #ef4444;
}

.tooltip-row .value.down {
  color: #22c55e;
}

.tooltip-row.volume {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid rgba(75, 85, 99, 0.2);
}

.tooltip-row.change {
  font-size: 12px;
}

/* 坐标轴高亮 */
.axis-highlight {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.x-highlight {
  position: absolute;
  top: 0;
  bottom: 24px;
  width: 1px;
  background: rgba(251, 191, 36, 0.3);
  transform: translateX(-50%);
}

.y-highlight {
  position: absolute;
  left: 60px;
  right: 0;
  height: 1px;
  background: rgba(251, 191, 36, 0.3);
  transform: translateY(-50%);
}
</style>
