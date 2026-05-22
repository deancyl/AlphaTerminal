<template>
  <div class="educational-tooltip-wrapper inline-flex items-center">
    <button
      class="help-icon text-xs text-secondary hover:text-primary transition cursor-help"
      @click="toggleTooltip"
      @mouseenter="showTooltipOnHover"
      @mouseleave="hideTooltipOnHover"
      type="button"
      :aria-label="`了解 ${term} 的含义`"
    >
      ⓘ
    </button>
    
    <Teleport to="body">
      <Transition name="tooltip-fade">
        <div
          v-if="isVisible"
          class="tooltip-content fixed z-50 p-3 rounded-lg shadow-lg max-w-[280px]"
          :style="tooltipPosition"
          role="tooltip"
          :aria-hidden="!isVisible"
        >
          <div class="text-sm font-bold text-primary mb-1">{{ glossaryData?.term }}</div>
          <div class="text-xs text-secondary mb-2">{{ glossaryData?.shortExplanation }}</div>
          
          <div v-if="showDetailed" class="detailed-section border-t border-theme-secondary pt-2 mt-2">
            <div class="text-xs text-secondary">{{ glossaryData?.detailedExplanation }}</div>
            <div class="text-xs mt-2 p-2 rounded bg-primary/10">
              <span class="text-primary font-bold">💡 提示：</span>
              <span class="text-secondary">{{ glossaryData?.practicalTip }}</span>
            </div>
          </div>
          
          <button
            v-if="!showDetailed"
            class="expand-btn text-xs text-primary hover:underline mt-2"
            @click="showDetailed = true"
            type="button"
          >
            查看详情 →
          </button>
          
          <button
            class="close-btn absolute top-1 right-1 text-xs text-secondary hover:text-primary"
            @click="hideTooltip"
            type="button"
            aria-label="关闭"
          >
            ✕
          </button>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { optionsGlossary } from '../../data/optionsGlossary.js'

const props = defineProps({
  term: { type: String, required: true },
  showDetailed: { type: Boolean, default: false }
})

const isVisible = ref(false)
const showDetailed = ref(props.showDetailed)
const tooltipPosition = ref({ top: '0px', left: '0px' })

const glossaryData = computed(() => optionsGlossary[props.term])

function toggleTooltip() {
  isVisible.value = !isVisible.value
  if (isVisible.value) {
    updatePosition()
  }
}

function showTooltipOnHover() {
  isVisible.value = true
  updatePosition()
}

function hideTooltipOnHover() {
  setTimeout(() => {
    if (!isVisible.value) return
    isVisible.value = false
  }, 300)
}

function hideTooltip() {
  isVisible.value = false
}

function updatePosition() {
  const button = document.activeElement
  if (!button) return
  
  const rect = button.getBoundingClientRect()
  tooltipPosition.value = {
    top: `${rect.bottom + 8}px`,
    left: `${Math.min(rect.left, window.innerWidth - 300)}px`
  }
}

onMounted(() => {
  document.addEventListener('click', handleOutsideClick)
})

onUnmounted(() => {
  document.removeEventListener('click', handleOutsideClick)
})

function handleOutsideClick(e) {
  if (!isVisible.value) return
  const tooltip = document.querySelector('.tooltip-content')
  const wrapper = document.querySelector('.educational-tooltip-wrapper')
  if (tooltip && !tooltip.contains(e.target) && wrapper && !wrapper.contains(e.target)) {
    isVisible.value = false
  }
}
</script>

<style scoped>
.tooltip-content {
  background: var(--bg-surface, #1e1e1e);
  border: 1px solid var(--border-base, #30363d);
}

.text-primary { color: var(--text-primary, #f0f6fc); }
.text-secondary { color: var(--text-secondary, #9ca3af); }
.bg-primary\/10 { background: rgba(15, 82, 186, 0.1); }
.border-theme-secondary { border-color: var(--border-base, #30363d); }

.tooltip-fade-enter-active,
.tooltip-fade-leave-active {
  transition: opacity 0.2s ease;
}

.tooltip-fade-enter-from,
.tooltip-fade-leave-to {
  opacity: 0;
}
</style>