<template>
  <Teleport to="body">
    <Transition name="bottom-sheet">
      <div
        v-if="modelValue"
        class="fixed inset-0 z-modal flex items-end justify-center"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
        @click.self="handleBackdropClick"
        @keydown.esc="close"
      >
        <!-- Backdrop -->
        <div
          class="absolute inset-0 bg-overlay"
          aria-hidden="true"
        />

        <!-- Sheet Container -->
        <div
          ref="sheetRef"
          class="relative w-full max-h-[80vh] bg-surface rounded-t-2xl shadow-2xl overflow-hidden"
          :style="{ height: height }"
          tabindex="-1"
        >
          <!-- Drag Handle -->
          <div
            class="flex justify-center pt-3 pb-2 cursor-grab active:cursor-grabbing"
            @mousedown="startDrag"
            @touchstart="startDrag"
          >
            <div class="w-10 h-1 bg-gray-500 rounded-full" />
          </div>

          <!-- Header -->
          <div
            v-if="title || $slots.header"
            class="px-4 pb-2 border-b border-border-base"
          >
            <slot name="header">
              <h3
                :id="titleId"
                class="text-lg font-semibold text-primary"
              >
                {{ title }}
              </h3>
            </slot>
          </div>

          <!-- Content -->
          <div
            class="overflow-y-auto"
            :style="{ maxHeight: contentMaxHeight }"
          >
            <slot />
          </div>

          <!-- Footer (optional) -->
          <div
            v-if="$slots.footer"
            class="px-4 py-3 border-t border-border-base bg-surface-hover"
          >
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { useFocusTrap } from '@/composables/useFocusTrap.js'
import { useHaptic } from '@/composables/useHaptic.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  height: { type: String, default: 'auto' },
  closeOnBackdrop: { type: Boolean, default: true },
  minHeight: { type: Number, default: 100 },
})

const emit = defineEmits(['update:modelValue', 'close'])

// Haptic feedback
const { light } = useHaptic()

// Refs
const sheetRef = ref(null)

// Generate unique ID for ARIA
const titleId = computed(() =>
  `bottom-sheet-title-${Math.random().toString(36).slice(2, 9)}`
)

// Content max height calculation
const contentMaxHeight = computed(() => {
  return 'calc(80vh - 80px)'
})

// Focus trap
const isActive = computed(() => props.modelValue)
useFocusTrap({
  isActive,
  containerRef: sheetRef,
  onClose: close
})

// Drag-to-close functionality
let isDragging = false
let startY = 0
let startHeight = 0

function startDrag(e) {
  if (!sheetRef.value) return

  isDragging = true
  startY = e.type === 'touchstart' ? e.touches[0].clientY : e.clientY

  const rect = sheetRef.value.getBoundingClientRect()
  startHeight = rect.height

  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', endDrag)
  document.addEventListener('touchmove', onDrag)
  document.addEventListener('touchend', endDrag)
}

function onDrag(e) {
  if (!isDragging || !sheetRef.value) return

  const currentY = e.type === 'touchmove' ? e.touches[0].clientY : e.clientY
  const deltaY = currentY - startY
  const newHeight = Math.max(props.minHeight, startHeight - deltaY)

  sheetRef.value.style.height = `${newHeight}px`

  // If dragged more than 100px down, close
  if (deltaY > 100) {
    endDrag()
    close()
  }
}

function endDrag() {
  isDragging = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', endDrag)
  document.removeEventListener('touchmove', onDrag)
  document.removeEventListener('touchend', endDrag)
}

// Close handlers
function close() {
  light() // Haptic feedback on close
  emit('update:modelValue', false)
  emit('close')
}

function handleBackdropClick() {
  if (props.closeOnBackdrop) {
    close()
  }
}

// Manage body scroll
watch(() => props.modelValue, (visible) => {
  if (visible) {
    document.body.style.overflow = 'hidden'
    nextTick(() => {
      sheetRef.value?.focus()
    })
  } else {
    document.body.style.overflow = ''
  }
})

// Cleanup on unmount
onUnmounted(() => {
  document.body.style.overflow = ''
  endDrag()
})

// Expose methods
defineExpose({ close })
</script>

<style scoped>
.bottom-sheet-enter-active,
.bottom-sheet-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.bottom-sheet-enter-from,
.bottom-sheet-leave-to {
  opacity: 0;
}

.bottom-sheet-enter-from .relative,
.bottom-sheet-leave-to .relative {
  transform: translateY(100%);
}

/* Smooth transition for the sheet content */
.relative {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
</style>
