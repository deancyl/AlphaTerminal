<template>
  <div
    class="factor-funnel"
    role="list"
    aria-label="筛选漏斗"
    @dragover.prevent
    @drop="handleDrop"
  >
    <div class="factor-funnel__header">
      <span class="factor-funnel__title">筛选漏斗</span>
      <span class="factor-funnel__count" aria-live="polite">{{ factors.length }} 个因子</span>
    </div>
    
    <div v-if="factors.length === 0" class="factor-funnel__empty">
      <div class="factor-funnel__empty-icon">📥</div>
      <div class="factor-funnel__empty-text">拖拽因子到此处</div>
    </div>
    
    <div v-else class="factor-funnel__list">
      <div
        v-for="(factor, index) in factors"
        :key="factor.id"
        class="factor-funnel__item"
        :style="{ '--item-index': index }"
        role="listitem"
        :tabindex="0"
        :aria-label="`第${index + 1}个因子: ${factor.name}`"
        draggable="true"
        @dragstart="handleItemDragStart($event, index)"
        @dragover.prevent="handleItemDragOver($event, index)"
        @drop="handleItemDrop($event, index)"
        @dragend="handleItemDragEnd"
        @keydown.delete="handleKeyRemove(factor.id)"
        @keydown.backspace.prevent="handleKeyRemove(factor.id)"
      >
        <div class="factor-funnel__item-connector" v-if="index > 0">
          <svg width="20" height="24" viewBox="0 0 20 24">
            <path
              d="M10 0 L10 24"
              stroke="var(--border-light)"
              stroke-width="2"
              stroke-dasharray="4 2"
            />
          </svg>
        </div>
        
        <div class="factor-funnel__item-content">
          <div class="factor-funnel__item-order">{{ index + 1 }}</div>
          <div class="factor-funnel__item-name">{{ factor.name }}</div>
          <div class="factor-funnel__item-actions">
            <button
              v-if="hasConfigurableParams(factor)"
              class="factor-funnel__item-config"
              @click.stop="$emit('configure', factor)"
              title="配置参数"
            >
              ⚙️
            </button>
<button
            class="factor-funnel__item-remove"
            @click.stop="$emit('remove', factor.id)"
            :aria-label="`移除因子 ${factor.name}`"
            title="移除因子"
          >
              ✕
            </button>
          </div>
        </div>
        
        <div class="factor-funnel__item-funnel">
          <svg width="100%" height="8" viewBox="0 0 100 8" preserveAspectRatio="none">
            <polygon
              :points="getFunnelPoints(index)"
              fill="var(--color-primary-bg)"
              stroke="var(--color-primary-border)"
              stroke-width="0.5"
            />
          </svg>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  factors: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['remove', 'reorder', 'add', 'configure'])

const draggedIndex = ref(null)
const dropTargetIndex = ref(null)

function handleDrop(event) {
  const data = event.dataTransfer.getData('application/json')
  if (data) {
    try {
      const factor = JSON.parse(data)
      if (!props.factors.find(f => f.id === factor.id)) {
        emit('add', factor)
      }
    } catch (e) {
      console.error('[FactorFunnel] Drop parse error:', e)
    }
  }
}

function handleItemDragStart(event, index) {
  draggedIndex.value = index
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', String(index))
}

function handleItemDragOver(event, index) {
  if (draggedIndex.value !== null && draggedIndex.value !== index) {
    dropTargetIndex.value = index
  }
}

function handleItemDrop(event, targetIndex) {
  if (draggedIndex.value !== null && draggedIndex.value !== targetIndex) {
    emit('reorder', draggedIndex.value, targetIndex)
  }
  draggedIndex.value = null
  dropTargetIndex.value = null
}

function handleItemDragEnd() {
  draggedIndex.value = null
  dropTargetIndex.value = null
}

function handleKeyRemove(factorId) {
  emit('remove', factorId)
}

function getFunnelPoints(index) {
  const total = props.factors.length
  if (total <= 1) return '0,0 100,0 100,8 0,8'
  
  const topWidth = 100 - (index / total) * 30
  const bottomWidth = 100 - ((index + 1) / total) * 30
  
  const topLeft = (100 - topWidth) / 2
  const topRight = topLeft + topWidth
  const bottomLeft = (100 - bottomWidth) / 2
  const bottomRight = bottomLeft + bottomWidth
  
  return `${topLeft},0 ${topRight},0 ${bottomRight},8 ${bottomLeft},8`
}

// Factor parameter definitions
const FACTOR_PARAMS = {
  rsi_oversold: ['period', 'threshold'],
  breakout_ma: ['period'],
  volume_surge: ['multiplier', 'period'],
  macd_golden_cross: ['fast', 'slow', 'signal'],
}

function hasConfigurableParams(factor) {
  return factor.id in FACTOR_PARAMS
}
</script>

<style scoped>
.factor-funnel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.factor-funnel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-sm) var(--space-md);
  background-color: var(--bg-surface-hover);
  border-bottom: 1px solid var(--border-base);
}

.factor-funnel__title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.factor-funnel__count {
  font-size: 10px;
  color: var(--text-muted);
  padding: 2px 8px;
  background-color: var(--color-primary-bg);
  border-radius: var(--radius-full);
}

.factor-funnel__empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
}

.factor-funnel__empty-icon {
  font-size: 32px;
  margin-bottom: var(--space-sm);
  opacity: 0.5;
}

.factor-funnel__empty-text {
  font-size: 12px;
}

.factor-funnel__list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-sm);
}

.factor-funnel__item {
  position: relative;
  margin-bottom: var(--space-xs);
  animation: fadeSlideIn 0.2s ease-out;
  animation-delay: calc(var(--item-index) * 50ms);
}

@keyframes fadeSlideIn {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.factor-funnel__item-connector {
  position: absolute;
  top: -20px;
  left: 16px;
  width: 20px;
  height: 24px;
}

.factor-funnel__item-content {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  background-color: var(--bg-surface-hover);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  cursor: grab;
  transition: all var(--duration-fast) var(--easing-default);
}

.factor-funnel__item-content:hover {
  border-color: var(--color-primary-border);
  background-color: var(--color-primary-bg);
}

.factor-funnel__item:focus-visible .factor-funnel__item-content {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
  border-color: var(--color-primary-border);
  background-color: var(--color-primary-bg);
}

.factor-funnel__item-order {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  font-size: 10px;
  font-weight: 600;
  color: var(--color-primary);
  background-color: var(--color-primary-bg);
  border: 1px solid var(--color-primary-border);
  border-radius: var(--radius-full);
}

.factor-funnel__item-name {
  flex: 1;
  font-size: 12px;
  color: var(--text-primary);
}

.factor-funnel__item-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.factor-funnel__item-config {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  font-size: 10px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--easing-default);
}

.factor-funnel__item-config:hover {
  color: var(--color-primary);
  background-color: var(--color-primary-bg);
}

.factor-funnel__item-remove {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  font-size: 10px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--easing-default);
}

.factor-funnel__item-remove:hover {
  color: var(--color-danger);
  background-color: var(--color-danger-bg);
}

.factor-funnel__item-remove:focus-visible {
  outline: 2px solid var(--color-danger);
  outline-offset: 2px;
}

.factor-funnel__item-funnel {
  margin-top: 2px;
  opacity: 0.7;
}
</style>
