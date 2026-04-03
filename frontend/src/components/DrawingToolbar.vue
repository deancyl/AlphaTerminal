<template>
  <!-- 紧凑型垂直画线工具栏：SVG图标 + tooltip -->
  <div class="flex flex-col shrink-0 rounded border border-gray-700/50 bg-terminal-panel/90 overflow-hidden" style="width:28px;">

    <!-- 绘制工具组 -->
    <div v-for="tool in drawTools" :key="tool.key" class="group relative">
      <button
        class="w-full h-6 flex items-center justify-center transition-colors"
        :class="activeTool === tool.key
          ? 'bg-terminal-accent/20 text-terminal-accent'
          : 'text-gray-600 hover:text-gray-300 hover:bg-gray-700/60'"
        :title="tool.label"
        @click="emit('tool-change', activeTool === tool.key ? '' : tool.key)"
      >
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none" v-html="tool.svg"></svg>
      </button>
      <!-- Tooltip right -->
      <div class="absolute left-full top-1/2 -translate-y-1/2 ml-1 hidden group-hover:flex z-50 pointer-events-none">
        <div class="flex items-center gap-1.5 bg-gray-900 border border-gray-600 rounded px-2 py-1 shadow-xl whitespace-nowrap">
          <span class="text-[10px] text-gray-200">{{ tool.label }}</span>
          <span v-if="tool.shortcut" class="text-[9px] text-gray-500 bg-gray-800 px-1 rounded">{{ tool.shortcut }}</span>
        </div>
      </div>
    </div>

    <!-- 分隔线 -->
    <div class="border-t border-gray-700/50"></div>

    <!-- 颜色按钮 -->
    <div class="group relative">
      <button
        class="w-full h-6 flex items-center justify-center transition-colors"
        :class="showColorPicker ? 'text-white bg-gray-700/60' : 'text-gray-600 hover:text-gray-300 hover:bg-gray-700/60'"
        title="画线颜色"
        @click="showColorPicker = !showColorPicker"
      >
        <span class="w-3 h-3 rounded-full border border-gray-600" :style="{ backgroundColor: activeColor }"></span>
      </button>
      <!-- 颜色面板 -->
      <div v-if="showColorPicker"
        class="absolute left-full top-0 ml-1 bg-terminal-panel border border-gray-600 rounded p-1.5 shadow-xl z-50"
        style="width: 120px;">
        <div class="grid grid-cols-5 gap-1 mb-2">
          <button
            v-for="c in presetColors" :key="c"
            class="w-4 h-4 rounded-full border-2 transition-transform hover:scale-110"
            :style="{ backgroundColor: c, borderColor: activeColor === c ? '#fff' : 'transparent' }"
            @click="emit('color-change', c); showColorPicker = false"
          ></button>
        </div>
        <div class="flex items-center gap-1">
          <input type="color" :value="activeColor"
            @change="e => { emit('color-change', e.target.value); showColorPicker = false }"
            class="w-7 h-4 rounded cursor-pointer border-0 bg-transparent" />
          <span class="text-[9px] text-gray-500">自定义</span>
        </div>
      </div>
    </div>

    <!-- 磁吸 -->
    <button
      class="w-full h-6 flex items-center justify-center transition-colors"
      :class="magnetMode
        ? 'text-blue-400 bg-blue-500/10'
        : 'text-gray-700 hover:text-gray-500'"
      title="磁吸模式"
      @click="emit('magnet-toggle')"
    >
      <!-- Magnet SVG -->
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <path d="M3 2v3a3 3 0 0 0 6 0V2M1 2h10M3 2h1M8 2h1" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
      </svg>
    </button>

    <!-- 分隔线 -->
    <div class="border-t border-gray-700/50"></div>

    <!-- 显示/隐藏 -->
    <button
      class="w-full h-6 flex items-center justify-center transition-colors"
      :class="visible ? 'text-gray-500 hover:text-gray-300' : 'text-gray-800 hover:text-gray-600'"
      :title="visible ? '隐藏画线' : '显示画线'"
      @click="emit('visibility-toggle')"
    >
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <ellipse cx="6" cy="6" rx="5" ry="3" stroke="currentColor" stroke-width="1.2"/>
        <circle cx="6" cy="6" r="1.5" fill="currentColor"/>
      </svg>
    </button>

    <!-- 锁定 -->
    <button
      class="w-full h-6 flex items-center justify-center transition-colors"
      :class="locked ? 'text-amber-400' : 'text-gray-700 hover:text-gray-500'"
      title="锁定画线"
      @click="emit('lock-toggle')"
    >
      <svg v-if="locked" width="12" height="12" viewBox="0 0 12 12" fill="none">
        <rect x="2" y="5" width="8" height="6" rx="1" stroke="currentColor" stroke-width="1.2"/>
        <path d="M4 5V3.5a2 2 0 0 1 4 0V5" stroke="currentColor" stroke-width="1.2"/>
      </svg>
      <svg v-else width="12" height="12" viewBox="0 0 12 12" fill="none">
        <rect x="2" y="5" width="8" height="6" rx="1" stroke="currentColor" stroke-width="1.2"/>
        <path d="M4 5V3.5a2 2 0 0 1 3.9-.6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
      </svg>
    </button>

    <!-- 分隔线 -->
    <div class="border-t border-gray-700/50"></div>

    <!-- 清除 -->
    <button
      class="w-full h-6 flex items-center justify-center text-gray-700 hover:text-red-400 transition-colors"
      title="清除全部"
      @click="confirmClear"
    >
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <path d="M2 3h8M5 3V2h2v1M4 3v7h4V3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  activeTool:  { type: String,  default: '' },
  activeColor: { type: String,  default: '#fbbf24' },
  magnetMode:  { type: Boolean, default: true },
  visible:     { type: Boolean, default: true },
  locked:      { type: Boolean, default: false },
})

const emit = defineEmits([
  'tool-change', 'color-change', 'magnet-toggle',
  'visibility-toggle', 'lock-toggle', 'clear',
])

const showColorPicker = ref(false)

const presetColors = [
  '#fbbf24', '#f87171', '#34d399', '#60a5fa', '#c084fc',
  '#fb923c', '#e879f9', '#94a3b8', '#ffffff', '#ef4444',
]

// SVG paths for each tool (viewBox 0 0 13 13)
const drawTools = [
  {
    key: 'line',
    label: '直线',
    shortcut: 'L',
    svg: '<line x1="1" y1="12" x2="12" y2="1" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>'
  },
  {
    key: 'ray',
    label: '射线',
    shortcut: 'R',
    svg: '<line x1="1" y1="12" x2="12" y2="1" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><circle cx="1" cy="12" r="1.5" fill="currentColor"/>'
  },
  {
    key: 'segment',
    label: '线段',
    shortcut: 'S',
    svg: '<line x1="2" y1="11" x2="11" y2="2" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><circle cx="2" cy="11" r="1.2" fill="currentColor"/><circle cx="11" cy="2" r="1.2" fill="currentColor"/>'
  },
  {
    key: 'hray',
    label: '水平线',
    shortcut: 'H',
    svg: '<line x1="1" y1="6.5" x2="12" y2="6.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-dasharray="2 1.5"/>'
  },
  {
    key: 'channel',
    label: '平行通道',
    shortcut: 'C',
    svg: '<line x1="1" y1="10" x2="12" y2="3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><line x1="1" y1="7" x2="12" y2="0" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-dasharray="2 1.5"/>'
  },
  {
    key: 'fib',
    label: '黄金分割',
    shortcut: 'F',
    svg: '<line x1="1" y1="11" x2="12" y2="2" stroke="currentColor" stroke-width="1.2"/><line x1="1" y1="8.5" x2="12" y2="8.5" stroke="currentColor" stroke-width="0.9" stroke-dasharray="1.5 1"/><line x1="1" y1="6" x2="12" y2="6" stroke="currentColor" stroke-width="0.9" stroke-dasharray="1.5 1"/><line x1="1" y1="3.5" x2="12" y2="3.5" stroke="currentColor" stroke-width="0.9" stroke-dasharray="1.5 1"/>'
  },
  {
    key: 'rect',
    label: '矩形',
    shortcut: 'Q',
    svg: '<rect x="2" y="3" width="9" height="7" stroke="currentColor" stroke-width="1.2" rx="0.5" fill="none"/>'
  },
  {
    key: 'text',
    label: '文本标注',
    shortcut: 'T',
    svg: '<path d="M2 11V3.5l3-2.5 3 2.5V11M5 7v3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>'
  },
]

function confirmClear() {
  if (confirm('清除全部画线？')) emit('clear')
}
</script>
