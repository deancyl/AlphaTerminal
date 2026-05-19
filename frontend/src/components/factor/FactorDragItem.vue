<template>
  <div
    class="factor-drag-item"
    :class="{
      'factor-drag-item--selected': selected,
      'factor-drag-item--dragging': isDragging,
    }"
    draggable="true"
    @dragstart="handleDragStart"
    @dragend="handleDragEnd"
    @click="$emit('click', factor)"
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
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

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

const emit = defineEmits(['click', 'dragstart', 'dragend'])

const isDragging = ref(false)

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
}

.factor-drag-item:hover {
  background-color: var(--bg-surface-hover);
  border-color: var(--border-hover);
}

.factor-drag-item--selected {
  background-color: var(--color-primary-bg);
  border-color: var(--color-primary-border);
}

.factor-drag-item--dragging {
  opacity: 0.5;
  cursor: grabbing;
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
</style>
