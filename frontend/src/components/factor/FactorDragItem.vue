<template>
  <div
    ref="itemRef"
    class="factor-drag-item"
    :class="{
      'factor-drag-item--selected': selected,
      'factor-drag-item--dragging': isDragging,
      'factor-drag-item--touch-dragging': isTouchDragging,
      'ring-2 ring-primary': selected,
    }"
    :title="factor.description || factor.name"
    :tabindex="0"
    role="option"
    :aria-selected="selected ? 'true' : 'false'"
    :aria-label="`${factor.name}${factor.description ? ': ' + factor.description : ''}${selected ? ' (已选中)' : ''}`"
    draggable="true"
    @dragstart="handleDragStart"
    @dragend="handleDragEnd"
    @click="handleClick"
    @keydown.enter="handleKeyToggle"
    @keydown.space.prevent="handleKeyToggle"
    @touchstart="handleTouchStart"
    @touchmove="handleTouchMove"
    @touchend="handleTouchEnd"
  >
    <div class="factor-drag-item__icon">
      {{ categoryIcon }}
    </div>
    <div class="factor-drag-item__content">
      <div class="factor-drag-item__name">{{ factor.name }}</div>
      <div v-if="factor.description" class="factor-drag-item__desc">
        {{ factor.description }}
      </div>
    </div>
    <div v-if="factor.unit" class="factor-drag-item__unit">
      {{ factor.unit }}
    </div>
    <div v-if="selected" class="factor-drag-item__check">✓</div>
    
    <Teleport to="body">
      <div
        v-if="isTouchDragging && touchDragElement"
        class="factor-drag-item__touch-ghost"
        :style="touchGhostStyle"
      >
        <div class="factor-drag-item__icon">{{ categoryIcon }}</div>
        <div class="factor-drag-item__name">{{ factor.name }}</div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'

const props = defineProps({
  factor: {
    type: Object,
    required: true,
  },
  selected: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['click', 'dragstart', 'dragend', 'touchdrop'])

const itemRef = ref(null)
const isDragging = ref(false)
const isTouchDragging = ref(false)
const touchDragElement = ref(null)
const touchGhostStyle = ref({})

const LONG_PRESS_DURATION = 300
let longPressTimer = null
let touchStartPos = { x: 0, y: 0 }

const categoryIcon = computed(() => {
  const icons = {
    value: '💰',
    growth: '📈',
    quality: '⭐',
    momentum: '🚀',
    technical: '📊',
    sentiment: '🧠',
    fund_flow: '💵',
    volatility: '📉',
  }
  return icons[props.factor.category] || '📌'
})

function handleDragStart(event) {
  isDragging.value = true
  event.dataTransfer.setData('application/json', JSON.stringify(props.factor))
  event.dataTransfer.effectAllowed = 'copy'
  emit('dragstart', props.factor)
}

function handleDragEnd() {
  isDragging.value = false
  emit('dragend')
}

function handleClick(event) {
  if (!isTouchDragging.value) {
    emit('click', props.factor)
  }
}

function handleKeyToggle() {
  emit('click', props.factor)
}

function handleTouchStart(event) {
  if (event.touches.length !== 1) return
  
  const touch = event.touches[0]
  touchStartPos = { x: touch.clientX, y: touch.clientY }
  
  longPressTimer = setTimeout(() => {
    isTouchDragging.value = true
    touchDragElement.value = props.factor
    
    if (navigator.vibrate) {
      navigator.vibrate(50)
    }
    
    updateTouchGhostPosition(touch.clientX, touch.clientY)
  }, LONG_PRESS_DURATION)
}

function handleTouchMove(event) {
  if (!isTouchDragging.value) {
    if (longPressTimer) {
      const touch = event.touches[0]
      const dx = Math.abs(touch.clientX - touchStartPos.x)
      const dy = Math.abs(touch.clientY - touchStartPos.y)
      if (dx > 10 || dy > 10) {
        clearTimeout(longPressTimer)
        longPressTimer = null
      }
    }
    return
  }
  
  event.preventDefault()
  const touch = event.touches[0]
  updateTouchGhostPosition(touch.clientX, touch.clientY)
  
  const dropTarget = document.elementFromPoint(touch.clientX, touch.clientY)
  if (dropTarget) {
    const funnel = dropTarget.closest('.factor-funnel')
    if (funnel) {
      funnel.classList.add('factor-funnel--drop-target')
    } else {
      document.querySelectorAll('.factor-funnel--drop-target').forEach(el => {
        el.classList.remove('factor-funnel--drop-target')
      })
    }
  }
}

function handleTouchEnd(event) {
  if (longPressTimer) {
    clearTimeout(longPressTimer)
    longPressTimer = null
  }
  
  if (isTouchDragging.value) {
    const touch = event.changedTouches[0]
    const dropTarget = document.elementFromPoint(touch.clientX, touch.clientY)
    
    if (dropTarget) {
      const funnel = dropTarget.closest('.factor-funnel')
      if (funnel) {
        emit('touchdrop', props.factor)
      }
    }
    
    document.querySelectorAll('.factor-funnel--drop-target').forEach(el => {
      el.classList.remove('factor-funnel--drop-target')
    })
  }
  
  setTimeout(() => {
    isTouchDragging.value = false
    touchDragElement.value = null
  }, 100)
}

function updateTouchGhostPosition(x, y) {
  touchGhostStyle.value = {
    position: 'fixed',
    left: `${x - 60}px`,
    top: `${y - 20}px`,
    zIndex: 9999,
    pointerEvents: 'none',
  }
}

onBeforeUnmount(() => {
  if (longPressTimer) {
    clearTimeout(longPressTimer)
  }
})
</script>

<style scoped>
.factor-drag-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  background-color: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  cursor: grab;
  transition: all var(--duration-fast) var(--easing-default);
  user-select: none;
  -webkit-user-select: none;
  touch-action: none;
}

.factor-drag-item:hover {
  background-color: var(--bg-surface-hover);
  border-color: var(--border-hover);
}

.factor-drag-item:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
  background-color: var(--color-primary-bg);
}

.factor-drag-item--selected {
  background-color: var(--color-primary-bg);
  border-color: var(--color-primary-border);
}

.factor-drag-item--dragging {
  opacity: 0.5;
  cursor: grabbing;
}

.factor-drag-item--touch-dragging {
  opacity: 0.3;
}

.factor-drag-item__icon {
  font-size: 14px;
  line-height: 1;
}

.factor-drag-item__content {
  flex: 1;
  min-width: 0;
}

.factor-drag-item__name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.factor-drag-item__desc {
  font-size: 10px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}

.factor-drag-item__unit {
  font-size: 10px;
  color: var(--text-muted);
  padding: 2px 6px;
  background-color: var(--bg-surface-hover);
  border-radius: var(--radius-sm);
}

.factor-drag-item__check {
  font-size: 12px;
  color: var(--color-primary);
  font-weight: bold;
}

.factor-drag-item__touch-ghost {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  background-color: var(--color-primary-bg);
  border: 2px solid var(--color-primary);
  border-radius: var(--radius-sm);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  opacity: 0.9;
}

.factor-drag-item__touch-ghost .factor-drag-item__icon {
  font-size: 16px;
}

.factor-drag-item__touch-ghost .factor-drag-item__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-primary);
}
</style>
