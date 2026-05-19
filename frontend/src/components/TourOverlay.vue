<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="isActive" class="fixed inset-0 z-[9999]">
        <div class="absolute inset-0 bg-black/60" @click="handleBackdropClick"></div>
        
        <div
          v-if="currentStepData"
          class="absolute transition-all duration-300"
          :style="tooltipStyle"
        >
          <div class="bg-terminal-panel border border-theme-secondary rounded-lg shadow-xl max-w-sm">
            <div class="px-4 py-3 border-b border-theme-secondary">
              <h3 class="text-sm font-medium text-terminal-primary">{{ currentStepData.title }}</h3>
            </div>
            <div class="px-4 py-3">
              <p class="text-xs text-terminal-dim leading-relaxed">{{ currentStepData.content }}</p>
            </div>
            <div class="px-4 py-3 border-t border-theme-secondary flex items-center justify-between">
              <span class="text-xs text-terminal-dim">{{ currentStep + 1 }} / {{ steps.length }}</span>
              <div class="flex items-center gap-2">
                <button
                  v-if="currentStep > 0"
                  @click="prevStep"
                  class="px-3 py-1.5 text-xs border border-theme-secondary rounded-sm text-terminal-dim hover:bg-terminal-hover transition"
                >
                  上一步
                </button>
                <button
                  @click="handleNext"
                  class="px-3 py-1.5 text-xs bg-terminal-accent/20 text-terminal-accent rounded-sm hover:bg-terminal-accent/30 transition"
                >
                  {{ currentStep === steps.length - 1 ? '完成' : '下一步' }}
                </button>
              </div>
            </div>
          </div>
          
          <div
            v-if="targetElement"
            class="absolute w-3 h-3 bg-terminal-panel border-l border-t border-theme-secondary transform rotate-45"
            :style="arrowStyle"
          ></div>
        </div>
        
        <button
          @click="skipTour"
          class="absolute top-4 right-4 px-3 py-1.5 text-xs text-terminal-dim hover:text-terminal-primary transition"
        >
          跳过引导
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  isActive: {
    type: Boolean,
    default: false,
  },
  currentStep: {
    type: Number,
    default: 0,
  },
  steps: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['next', 'prev', 'skip', 'complete'])

const targetElement = ref(null)
const tooltipPosition = ref({ top: 0, left: 0 })
const arrowPosition = ref({ top: 0, left: 0 })

const currentStepData = computed(() => {
  return props.steps[props.currentStep] || null
})

const tooltipStyle = computed(() => {
  const placement = currentStepData.value?.placement || 'bottom'
  const offset = 16
  
  let style = {
    top: `${tooltipPosition.value.top}px`,
    left: `${tooltipPosition.value.left}px`,
  }
  
  return style
})

const arrowStyle = computed(() => {
  const placement = currentStepData.value?.placement || 'bottom'
  
  if (placement === 'bottom') {
    return {
      top: '-6px',
      left: '50%',
      transform: 'translateX(-50%) rotate(45deg)',
    }
  } else if (placement === 'top') {
    return {
      bottom: '-6px',
      left: '50%',
      transform: 'translateX(-50%) rotate(225deg)',
    }
  } else if (placement === 'left') {
    return {
      right: '-6px',
      top: '50%',
      transform: 'translateY(-50%) rotate(-45deg)',
    }
  } else if (placement === 'right') {
    return {
      left: '-6px',
      top: '50%',
      transform: 'translateY(-50%) rotate(135deg)',
    }
  }
  
  return {}
})

function updatePosition() {
  if (!currentStepData.value || !props.isActive) return
  
  const target = document.querySelector(currentStepData.value.target)
  if (!target) {
    targetElement.value = null
    return
  }
  
  targetElement.value = target
  const rect = target.getBoundingClientRect()
  const placement = currentStepData.value.placement || 'bottom'
  const offset = 16
  const tooltipWidth = 320
  const tooltipHeight = 200
  
  let top = 0
  let left = 0
  
  if (placement === 'bottom') {
    top = rect.bottom + offset
    left = rect.left + rect.width / 2 - tooltipWidth / 2
  } else if (placement === 'top') {
    top = rect.top - tooltipHeight - offset
    left = rect.left + rect.width / 2 - tooltipWidth / 2
  } else if (placement === 'left') {
    top = rect.top + rect.height / 2 - tooltipHeight / 2
    left = rect.left - tooltipWidth - offset
  } else if (placement === 'right') {
    top = rect.top + rect.height / 2 - tooltipHeight / 2
    left = rect.right + offset
  }
  
  top = Math.max(16, Math.min(top, window.innerHeight - tooltipHeight - 16))
  left = Math.max(16, Math.min(left, window.innerWidth - tooltipWidth - 16))
  
  tooltipPosition.value = { top, left }
}

function handleNext() {
  if (props.currentStep === props.steps.length - 1) {
    emit('complete')
  } else {
    emit('next')
  }
}

function handleBackdropClick() {
}

function skipTour() {
  emit('skip')
}

watch([() => props.currentStep, () => props.isActive], () => {
  setTimeout(updatePosition, 50)
})

onMounted(() => {
  window.addEventListener('resize', updatePosition)
  window.addEventListener('scroll', updatePosition, true)
})

onUnmounted(() => {
  window.removeEventListener('resize', updatePosition)
  window.removeEventListener('scroll', updatePosition, true)
})
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.bg-terminal-panel {
  background: var(--bg-secondary, #1a1f2e);
}

.border-theme-secondary {
  border-color: var(--border-color, #2d3748);
}

.text-terminal-primary {
  color: var(--text-primary, #E5E7EB);
}

.text-terminal-dim {
  color: var(--text-secondary, #8B949E);
}

.text-terminal-accent {
  color: var(--color-primary, #0F52BA);
}

.bg-terminal-accent\/20 {
  background: rgba(15, 82, 186, 0.2);
}

.hover\:bg-terminal-accent\/30:hover {
  background: rgba(15, 82, 186, 0.3);
}

.hover\:bg-terminal-hover:hover {
  background: var(--bg-hover, #262d3d);
}
</style>
