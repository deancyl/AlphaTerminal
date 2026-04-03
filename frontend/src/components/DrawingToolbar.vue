<template>
  <!-- 画线工具栏（垂直方向，左侧固定） -->
  <div class="flex flex-col gap-0.5 shrink-0" style="width: 36px;">

    <!-- 绘制工具 -->
    <div v-for="tool in tools" :key="tool.key"
      class="group relative">
      <button
        class="w-full h-7 flex items-center justify-center rounded transition-colors text-[13px]"
        :class="activeTool === tool.key
          ? 'bg-terminal-accent/20 text-terminal-accent border border-terminal-accent/40'
          : 'text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 border border-transparent'"
        :title="tool.label"
        @click="selectTool(tool.key)"
      >{{ tool.icon }}</button>

      <!-- Tooltip -->
      <div class="absolute left-8 top-1/2 -translate-y-1/2 hidden group-hover:block z-50 pointer-events-none">
        <div class="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-[10px] text-gray-300 whitespace-nowrap shadow-lg">
          {{ tool.label }}
          <span v-if="tool.shortcut" class="ml-2 text-gray-500">{{ tool.shortcut }}</span>
        </div>
      </div>
    </div>

    <!-- 分隔线 -->
    <div class="my-1 border-t border-gray-700/50"></div>

    <!-- 颜色选择 -->
    <div class="relative">
      <button
        class="w-full h-7 flex items-center justify-center rounded border transition-colors"
        :style="{ color: activeColor, borderColor: activeColor + '60' }"
        title="画线颜色"
        @click="showColorPicker = !showColorPicker"
      >🎨</button>

      <!-- 颜色面板 -->
      <div v-if="showColorPicker" class="absolute left-8 top-0 bg-terminal-panel border border-gray-600 rounded p-2 shadow-xl z-50">
        <div class="grid grid-cols-5 gap-1 mb-2">
          <button
            v-for="c in presetColors" :key="c"
            class="w-5 h-5 rounded border-2 transition-transform hover:scale-110"
            :style="{ backgroundColor: c, borderColor: activeColor === c ? '#fff' : 'transparent' }"
            @click="emit('color-change', c); showColorPicker = false"
          ></button>
        </div>
        <div class="flex items-center gap-1">
          <input type="color" :value="activeColor" @change="e => emit('color-change', e.target.value)"
            class="w-8 h-5 rounded cursor-pointer border-0 bg-transparent" />
          <span class="text-[9px] text-gray-500">自定义</span>
        </div>
      </div>
    </div>

    <!-- 磁吸模式 -->
    <button
      class="w-full h-7 flex items-center justify-center rounded transition-colors"
      :class="magnetMode
        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40'
        : 'text-gray-600 hover:text-gray-400 border border-transparent'"
      title="磁吸模式（自动吸附K线价格）"
      @click="emit('magnet-toggle')"
    >🧲</button>

    <!-- 分隔线 -->
    <div class="my-1 border-t border-gray-700/50"></div>

    <!-- 清除全部 -->
    <div class="group relative">
      <button
        class="w-full h-7 flex items-center justify-center rounded text-gray-600 hover:text-red-400 hover:bg-red-500/10 border border-transparent transition-colors"
        title="清除全部画线"
        @click="confirmClear"
      >🗑️</button>
    </div>

    <!-- 显示/隐藏 -->
    <button
      class="w-full h-7 flex items-center justify-center rounded transition-colors"
      :class="visible
        ? 'text-gray-400 hover:text-gray-300 border border-transparent'
        : 'text-gray-700 hover:text-gray-500 border border-transparent'"
      :title="visible ? '隐藏画线' : '显示画线'"
      @click="emit('visibility-toggle')"
    >{{ visible ? '👁️' : '👁️‍🗨️' }}</button>

    <!-- 锁定 -->
    <button
      class="w-full h-7 flex items-center justify-center rounded transition-colors"
      :class="locked
        ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
        : 'text-gray-600 hover:text-gray-400 border border-transparent'"
      title="锁定画线（禁止修改）"
      @click="emit('lock-toggle')"
    >{{ locked ? '🔒' : '🔓' }}</button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  activeTool:   { type: String,  default: '' },
  activeColor:  { type: String,  default: '#fbbf24' },
  magnetMode:   { type: Boolean, default: true },
  visible:      { type: Boolean, default: true },
  locked:       { type: Boolean, default: false },
})

const emit = defineEmits([
  'tool-change', 'color-change', 'magnet-toggle',
  'visibility-toggle', 'lock-toggle', 'clear',
])

const showColorPicker = ref(false)

const tools = [
  { key: '',        label: '选择工具',      icon: '↖️',  shortcut: '' },
  { key: 'line',    label: '直线',          icon: '📏',  shortcut: 'L' },
  { key: 'ray',     label: '射线',          icon: '�️',  shortcut: 'R' },
  { key: 'segment', label: '线段',          icon: '—',   shortcut: 'S' },
  { key: 'hray',    label: '水平射线',      icon: '━━',  shortcut: 'H' },
  { key: 'channel', label: '平行通道',      icon: '╱╲',  shortcut: 'C' },
  { key: 'fib',     label: '黄金分割',      icon: '🔱',  shortcut: 'F' },
  { key: 'rect',    label: '矩形（筹码区）', icon: '▢',   shortcut: 'Q' },
  { key: 'text',    label: '文本标注',      icon: 'T',    shortcut: 'T' },
]

const presetColors = [
  '#fbbf24', '#f87171', '#34d399', '#60a5fa',
  '#c084fc', '#fb923c', '#e879f9', '#94a3b8',
  '#ffffff', '#ef4444',
]

function selectTool(key) {
  emit('tool-change', key === props.activeTool ? '' : key)
}

function confirmClear() {
  if (confirm('确定清除全部画线？')) {
    emit('clear')
  }
}
</script>
