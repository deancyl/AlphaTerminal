<template>
  <Teleport to="body">
    <div 
      v-if="visible" 
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" 
      role="dialog"
      aria-modal="true"
      :aria-labelledby="titleId"
      :aria-describedby="descriptionId"
      @click.self="cancel"
      @keydown.esc="cancel"
      @keydown.enter="handleEnter"
    >
      <div 
        ref="modalRef"
        class="bg-terminal-panel border border-theme rounded-lg p-6 max-w-md shadow-xl focus:outline-none"
        tabindex="-1"
      >
        <!-- Title -->
        <h2 
          :id="titleId" 
          class="text-theme-primary font-semibold text-sm mb-2"
        >
          {{ title }}
        </h2>
        
        <!-- Message -->
        <p 
          :id="descriptionId" 
          class="text-theme-secondary mb-4 text-sm"
        >
          {{ message }}
        </p>
        
        <!-- Action buttons -->
        <div class="flex gap-3 justify-end">
          <button 
            ref="cancelBtnRef"
            @click="cancel" 
            class="px-4 py-2 bg-terminal-bg border border-theme-secondary rounded text-theme-tertiary hover:border-theme-primary hover:text-theme-primary text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] focus:ring-offset-2 focus:ring-offset-terminal-panel"
            :aria-label="cancelText"
            type="button"
          >
            {{ cancelText }}
          </button>
          <button 
            ref="confirmBtnRef"
            @click="confirm" 
            class="px-4 py-2 bg-terminal-accent/20 border border-terminal-accent/50 rounded text-terminal-accent hover:bg-terminal-accent/30 text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] focus:ring-offset-2 focus:ring-offset-terminal-panel"
            :aria-label="confirmText"
            :autofocus="true"
            type="button"
          >
            {{ confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick, onUnmounted, computed } from 'vue'

const props = defineProps({
  title: { type: String, default: '确认操作' },
  message: { type: String, required: true },
  confirmText: { type: String, default: '确定' },
  cancelText: { type: String, default: '取消' },
})

const emit = defineEmits(['confirmed', 'cancelled'])

// State
const visible = ref(false)
const modalRef = ref(null)
const confirmBtnRef = ref(null)
const cancelBtnRef = ref(null)

// Generate unique IDs for ARIA
const titleId = computed(() => `confirm-modal-title-${Math.random().toString(36).slice(2, 9)}`)
const descriptionId = computed(() => `confirm-modal-desc-${Math.random().toString(36).slice(2, 9)}`)

// Track previously focused element
let previouslyFocused = null

// Focus trap implementation
function trapFocus() {
  if (!modalRef.value) return
  
  const focusableElements = modalRef.value.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  )
  
  if (focusableElements.length === 0) return
  
  const firstElement = focusableElements[0]
  const lastElement = focusableElements[focusableElements.length - 1]
  
  function handleTabKey(e) {
    if (e.key !== 'Tab') return
    
    if (e.shiftKey) {
      // Shift + Tab
      if (document.activeElement === firstElement) {
        e.preventDefault()
        lastElement.focus()
      }
    } else {
      // Tab
      if (document.activeElement === lastElement) {
        e.preventDefault()
        firstElement.focus()
      }
    }
  }
  
  modalRef.value.addEventListener('keydown', handleTabKey)
  
  return () => {
    modalRef.value?.removeEventListener('keydown', handleTabKey)
  }
}

// Show modal
function show() {
  // Store the currently focused element
  previouslyFocused = document.activeElement
  
  visible.value = true
  
  // Focus the confirm button after the modal is rendered
  nextTick(() => {
    confirmBtnRef.value?.focus()
    trapFocus()
  })
}

// Hide modal
function hide() {
  visible.value = false
  
  // Restore focus to the previously focused element
  if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
    nextTick(() => {
      previouslyFocused.focus()
    })
  }
}

// Confirm action
function confirm() {
  hide()
  emit('confirmed')
}

// Cancel action
function cancel() {
  hide()
  emit('cancelled')
}

// Handle Enter key
function handleEnter(e) {
  // Only handle Enter if it's not on a button (buttons handle their own Enter)
  if (e.target.tagName !== 'BUTTON') {
    confirm()
  }
}

// Watch for visibility changes to manage body scroll
watch(visible, (isVisible) => {
  if (isVisible) {
    document.body.style.overflow = 'hidden'
  } else {
    document.body.style.overflow = ''
  }
})

// Cleanup on unmount
onUnmounted(() => {
  document.body.style.overflow = ''
})

// Expose show method for parent components
defineExpose({ show, hide })
</script>

<style scoped>
/* Ensure focus ring is visible on dark background */
button:focus-visible {
  outline: 2px solid var(--accent-primary, #3b82f6);
  outline-offset: 2px;
}
</style>
