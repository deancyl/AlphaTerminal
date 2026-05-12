<template>
  <div class="space-y-6">
    <!-- 字体大小设置 -->
    <div class="terminal-panel p-4">
      <h3 class="text-lg font-bold text-terminal-accent mb-4">🔤 字体大小设置</h3>
      
      <div class="space-y-4">
        <div class="bg-[var(--color-info-bg)]/30 border border-[var(--color-info-border)] rounded p-3">
          <div class="text-sm text-[var(--color-info)] mb-1">💡 字体大小调节</div>
          <div class="text-xs text-theme-muted">
            调整全局字体大小，让界面更易阅读。设置会自动保存到浏览器。
          </div>
        </div>

        <div class="grid grid-cols-5 gap-2">
          <button
            v-for="option in fontSizeOptions"
            :key="option.value"
            class="flex flex-col items-center justify-center p-3 rounded border transition-all"
            :class="currentFontSize === option.value
              ? 'bg-[var(--color-accent-bg)] border-[var(--color-accent-border)] text-[var(--color-accent)]'
              : 'bg-terminal-bg border-theme-secondary text-theme-secondary hover:border-[var(--color-accent-border)] hover:text-[var(--color-accent-light)]'"
            @click="setFontSize(option.value)"
          >
            <span class="text-lg font-bold">{{ option.label }}</span>
            <span class="text-[10px] text-theme-muted mt-1">{{ option.size }}</span>
          </button>
        </div>

        <div class="bg-terminal-bg rounded p-3 border border-theme">
          <div class="text-sm text-theme-secondary mb-2">当前设置</div>
          <div class="flex items-center gap-2">
            <span class="text-base font-medium text-theme-primary">{{ fontSizeInfo.label }}</span>
            <span class="text-xs text-theme-muted">({{ fontSizeInfo.size }})</span>
            <span class="text-xs text-theme-tertiary">- {{ fontSizeInfo.desc }}</span>
          </div>
        </div>

        <div class="text-xs text-theme-muted">
          提示：字体大小会影响所有界面元素的显示比例。
        </div>
      </div>
    </div>

    <!-- 布局设置 -->
    <div class="terminal-panel p-4">
      <h3 class="text-lg font-bold text-terminal-accent mb-4">📐 仪表盘布局设置</h3>

      <div class="space-y-4">
        <!-- 当前布局状态 -->
        <div class="bg-terminal-bg rounded p-3 border border-theme">
          <div class="text-sm text-theme-secondary mb-2">当前布局状态</div>
          <div class="flex items-center gap-2">
            <span
              class="px-2 py-1 rounded text-xs"
              :class="hasSavedLayout ? 'bg-[var(--color-success-bg)] text-[var(--color-success)]' : 'bg-gray-500/20 text-gray-400'"
            >
              {{ hasSavedLayout ? '✓ 已保存自定义布局' : '✕ 使用默认布局' }}
            </span>
            <span v-if="hasSavedLayout" class="text-xs text-theme-muted">
              (版本 {{ layoutVersion }})
            </span>
          </div>
        </div>

        <!-- 布局说明 -->
        <div class="bg-[var(--color-info-bg)]/30 border border-[var(--color-info-border)] rounded p-3">
          <div class="text-sm text-[var(--color-info)] mb-1">💡 布局自动保存</div>
          <div class="text-xs text-theme-muted">
            拖拽或调整仪表盘组件大小后，布局会自动保存到浏览器。<br>
            刷新页面或重新打开时会自动恢复上次的位置。
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="flex gap-3 pt-2">
          <button
            class="px-4 py-2 rounded text-sm bg-[var(--color-danger-bg)] text-[var(--color-danger)] border border-[var(--color-danger-border)] hover:bg-[var(--color-danger)]/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="!hasSavedLayout"
            @click="handleClearLayout"
          >
            🗑️ 清除保存的布局
          </button>
        </div>

        <!-- 警告信息 -->
        <div v-if="!hasSavedLayout" class="text-xs text-theme-muted">
          当前没有保存的布局，无需清除。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { toast } from '../../composables/useToast.js'
import { useFontSize } from '../../composables/useFontSize.js'

const emit = defineEmits(['clear-layout'])

const { currentFontSize, fontSizeOptions, setFontSize: setFontSizeValue, getFontSizeInfo } = useFontSize()

const fontSizeInfo = computed(() => getFontSizeInfo())

const hasSavedLayout = ref(false)
const layoutVersion = ref(0)

const LAYOUT_STORAGE_KEY = 'alphaterminal_grid_layout'

onMounted(() => {
  checkSavedLayout()
})

function setFontSize(value) {
  setFontSizeValue(value)
  const info = getFontSizeInfo()
  toast.success('字体大小已更改', `已设置为 ${info.label} (${info.size})`)
}

function checkSavedLayout() {
  try {
    const stored = localStorage.getItem(LAYOUT_STORAGE_KEY)
    if (stored) {
      const data = JSON.parse(stored)
      hasSavedLayout.value = true
      layoutVersion.value = data.version || 1
    } else {
      hasSavedLayout.value = false
    }
  } catch (e) {
    hasSavedLayout.value = false
  }
}

function handleClearLayout() {
  emit('clear-layout')
  // Clear localStorage
  try {
    localStorage.removeItem(LAYOUT_STORAGE_KEY)
    hasSavedLayout.value = false
    toast.success('布局已清除', '下次加载时将使用默认布局')
  } catch (e) {
    toast.error('操作失败', '无法清除布局设置')
  }
}
</script>