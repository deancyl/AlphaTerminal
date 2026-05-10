<template>
  <div class="drawing-toolbar">
    <!-- 绘制工具组 -->
    <div class="toolbar-section">
      <div v-for="tool in sanitizedDrawTools" :key="tool.key" class="tool-item">
        <button
          class="tool-btn"
          :class="{ active: activeTool === tool.key }"
          :title="tool.label + ' (' + tool.shortcut + ')'"
          @click="emit('tool-change', activeTool === tool.key ? '' : tool.key)"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" v-html="tool.sanitizedSvg"></svg>
        </button>
        <div class="tooltip">
          <div class="tooltip-inner">
            <span>{{ tool.label }}</span>
            <span class="shortcut">{{ tool.shortcut }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="divider"></div>

    <!-- 颜色选择 -->
    <div class="toolbar-section">
      <div class="tool-item">
        <button
          class="tool-btn color-btn"
          :class="{ active: showColorPicker }"
          title="画线颜色"
          @click="showColorPicker = !showColorPicker"
        >
          <span class="color-dot" :style="{ backgroundColor: activeColor }"></span>
        </button>
        <div v-if="showColorPicker" class="color-picker" @click.stop>
          <div class="color-grid">
            <button
              v-for="c in presetColors" :key="c"
              class="color-option"
              :class="{ active: activeColor === c }"
              :style="{ backgroundColor: c }"
              @click="selectColor(c)"
            ></button>
          </div>
          <div class="custom-color">
            <input type="color" :value="activeColor" @change="e => selectColor(e.target.value)">
            <span>自定义</span>
          </div>
        </div>
      </div>
    </div>

    <div class="divider"></div>

    <!-- 功能按钮 -->
    <div class="toolbar-section">
      <!-- 磁吸 -->
      <div class="tool-item">
        <button
          class="tool-btn"
          :class="{ active: magnetMode }"
          title="磁吸模式 (M)"
          @click="emit('magnet-toggle')"
        >
          <svg width="13" height="13" viewBox="0 0 12 12" fill="none">
            <path d="M3 2v3a3 3 0 0 0 6 0V2M1 2h10M3 2h1M8 2h1" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
        </button>
        <div class="tooltip"><div class="tooltip-inner"><span>磁吸模式</span><span class="shortcut">M</span></div></div>
      </div>

      <!-- 显示/隐藏 -->
      <div class="tool-item">
        <button
          class="tool-btn"
          :class="{ inactive: !visible }"
          title="显示/隐藏 (V)"
          @click="emit('visibility-toggle')"
        >
          <svg v-if="visible" width="13" height="13" viewBox="0 0 12 12" fill="none">
            <ellipse cx="6" cy="6" rx="5" ry="3" stroke="currentColor" stroke-width="1.2"/>
            <circle cx="6" cy="6" r="1.5" fill="currentColor"/>
          </svg>
          <svg v-else width="13" height="13" viewBox="0 0 12 12" fill="none">
            <path d="M2 6c1-2 3-3 4-3s3 1 4 3M2 6c1 2 3 3 4 3s3-1 4-3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
            <path d="M3 3l6 6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
        </button>
        <div class="tooltip"><div class="tooltip-inner"><span>{{ visible ? '隐藏画线' : '显示画线' }}</span><span class="shortcut">V</span></div></div>
      </div>

      <!-- 锁定 -->
      <div class="tool-item">
        <button
          class="tool-btn"
          :class="{ active: locked }"
          title="锁定画线"
          @click="emit('lock-toggle')"
        >
          <svg v-if="locked" width="13" height="13" viewBox="0 0 12 12" fill="none">
            <rect x="2" y="5" width="8" height="6" rx="1" stroke="currentColor" stroke-width="1.2"/>
            <path d="M4 5V3.5a2 2 0 0 1 4 0V5" stroke="currentColor" stroke-width="1.2"/>
          </svg>
          <svg v-else width="13" height="13" viewBox="0 0 12 12" fill="none">
            <rect x="2" y="5" width="8" height="6" rx="1" stroke="currentColor" stroke-width="1.2"/>
            <path d="M4 5V3.5a2 2 0 0 1 3.9-.6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
        </button>
        <div class="tooltip"><div class="tooltip-inner"><span>{{ locked ? '解锁' : '锁定' }}</span></div></div>
      </div>
    </div>

    <div class="divider"></div>

    <!-- 清除 -->
    <div class="toolbar-section">
      <div class="tool-item">
        <button
          class="tool-btn delete-btn"
          title="清除全部"
          @click="confirmClear"
        >
          <svg width="13" height="13" viewBox="0 0 12 12" fill="none">
            <path d="M2 3h8M5 3V2h2v1M4 3v7h4V3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
        <div class="tooltip"><div class="tooltip-inner delete-text"><span>清除全部</span></div></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import DOMPurify from 'dompurify'

const props = defineProps({
  activeTool:  { type: String,  default: '' },
  activeColor: { type: String,  default: '#fbbf24' },
  magnetMode:  { type: Boolean, default: true },
  visible:     { type: Boolean, default: true },
  locked:      { type: Boolean, default: false },
})

const emit = defineEmits([
  'tool-change', 'color-change', 'magnet-toggle',
  'visibility-toggle', 'lock-toggle', 'clear'
])

const showColorPicker = ref(false)

const presetColors = [
  '#fbbf24', '#ef4444', '#22c55e', '#3b82f6', '#a855f7',
  '#f97316', '#ec4899', '#14b8a6', '#94a3b8', '#ffffff',
]

const drawTools = [
  {
    key: 'select',
    label: '选择/移动',
    shortcut: 'V',
    svg: '<path d="M2 2l3 8 2-5 2 3 3-6 3 4" stroke="currentColor" stroke-width="1.3" fill="none" stroke-linecap="round"/><path d="M9 9l3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'
  },
  {
    key: 'trend',
    label: '趋势线',
    shortcut: 'T',
    svg: '<line x1="1" y1="12" x2="12" y2="2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="1" cy="12" r="1.5" fill="currentColor"/><circle cx="12" cy="2" r="1.5" fill="currentColor"/>'
  },
  {
    key: 'line',
    label: '直线',
    shortcut: 'L',
    svg: '<line x1="1" y1="12" x2="12" y2="1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="2 1"/>'
  },
  {
    key: 'ray',
    label: '射线',
    shortcut: 'R',
    svg: '<line x1="1" y1="12" x2="12" y2="1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="1" cy="12" r="1.5" fill="currentColor"/>'
  },
  {
    key: 'segment',
    label: '线段',
    shortcut: 'S',
    svg: '<line x1="2" y1="11" x2="11" y2="2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="2" cy="11" r="1.2" fill="currentColor"/><circle cx="11" cy="2" r="1.2" fill="currentColor"/>'
  },
  {
    key: 'hray',
    label: '水平线',
    shortcut: 'H',
    svg: '<line x1="1" y1="7" x2="12" y2="7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="3 2"/>'
  },
  {
    key: 'vline',
    label: '垂直线',
    shortcut: 'V',
    svg: '<line x1="7" y1="1" x2="7" y2="12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="3 2"/>'
  },
  {
    key: 'channel',
    label: '平行通道',
    shortcut: 'C',
    svg: '<line x1="1" y1="10" x2="12" y2="3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><line x1="1" y1="7" x2="12" y2="0" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-dasharray="2 2"/>'
  },
  {
    key: 'fib',
    label: '斐波那契',
    shortcut: 'F',
    svg: '<line x1="1" y1="12" x2="12" y2="1" stroke="currentColor" stroke-width="1.2"/><line x1="1" y1="9" x2="12" y2="9" stroke="currentColor" stroke-width="1" stroke-dasharray="2 1" opacity="0.7"/><line x1="1" y1="6" x2="12" y2="6" stroke="currentColor" stroke-width="1" stroke-dasharray="2 1" opacity="0.7"/><line x1="1" y1="3" x2="12" y2="3" stroke="currentColor" stroke-width="1" stroke-dasharray="2 1" opacity="0.7"/>'
  },
  {
    key: 'rect',
    label: '矩形',
    shortcut: 'Q',
    svg: '<rect x="2" y="3" width="9" height="8" stroke="currentColor" stroke-width="1.3" rx="0.5" fill="none"/>'
  },
  {
    key: 'circle',
    label: '圆形',
    shortcut: 'O',
    svg: '<circle cx="7" cy="7" r="5" stroke="currentColor" stroke-width="1.3" fill="none"/>'
  },
  {
    key: 'text',
    label: '文本',
    shortcut: 'A',
    svg: '<path d="M3 11V4l4-2.5 4 2.5v7M7 6v4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>'
  },
]

// P0-007 Fix: Sanitize SVG to prevent XSS attacks
const sanitizedDrawTools = computed(() => 
  drawTools.map(tool => ({
    ...tool,
    sanitizedSvg: DOMPurify.sanitize(tool.svg, { 
      USE_PROFILES: { svg: true, svgFilters: true },
      ADD_TAGS: ['path', 'line', 'circle', 'rect', 'ellipse'],
      ADD_ATTR: ['d', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'x', 'y', 'width', 'height', 'rx', 'ry', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'stroke-dasharray', 'fill', 'opacity']
    })
  }))
)

function selectColor(color) {
  emit('color-change', color)
  showColorPicker.value = false
}

function confirmClear() {
  if (confirm('确定要清除所有画线吗？此操作不可恢复。')) {
    emit('clear')
  }
}
</script>

<style scoped>
.drawing-toolbar {
  position: absolute;
  top: 56px;
  left: 12px;
  z-index: 10;
  display: flex;
  flex-direction: column;
  width: 34px;
  background: rgba(17, 24, 39, 0.95);
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-radius: 8px;
  padding: 4px 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(8px);
}

.toolbar-section {
  padding: 2px 0;
}

.tool-item {
  position: relative;
}

.tool-btn {
  width: 100%;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.15s;
}

.tool-btn:hover {
  color: #e5e7eb;
  background: rgba(75, 85, 99, 0.3);
}

.tool-btn.active {
  color: #fbbf24;
  background: rgba(251, 191, 36, 0.15);
}

.tool-btn.inactive {
  color: #374151;
}

.tool-btn.delete-btn:hover {
  color: #f87171;
  background: rgba(248, 113, 113, 0.15);
}

.color-btn .color-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid rgba(75, 85, 99, 0.5);
}

.divider {
  height: 1px;
  background: rgba(75, 85, 99, 0.3);
  margin: 4px 6px;
}

.tooltip {
  position: absolute;
  left: 100%;
  top: 50%;
  transform: translateY(-50%);
  margin-left: 6px;
  display: none;
  z-index: 50;
  pointer-events: none;
}

.tool-item:hover .tooltip {
  display: block;
}

.tooltip-inner {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(17, 24, 39, 0.98);
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 11px;
  color: #e5e7eb;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.tooltip-inner .shortcut {
  font-size: 10px;
  color: #6b7280;
  background: rgba(31, 41, 55, 0.8);
  padding: 1px 5px;
  border-radius: 3px;
}

.tooltip-inner.delete-text {
  color: #f87171;
}

.color-picker {
  position: absolute;
  left: 100%;
  top: 0;
  margin-left: 8px;
  background: rgba(17, 24, 39, 0.98);
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-radius: 8px;
  padding: 10px;
  width: 140px;
  z-index: 100;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

.color-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 6px;
  margin-bottom: 10px;
}

.color-option {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  transition: transform 0.15s;
}

.color-option:hover {
  transform: scale(1.1);
}

.color-option.active {
  border-color: #fff;
}

.custom-color {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(75, 85, 99, 0.3);
}

.custom-color input[type="color"] {
  width: 28px;
  height: 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  padding: 0;
}

.custom-color span {
  font-size: 11px;
  color: #9ca3af;
}
</style>
