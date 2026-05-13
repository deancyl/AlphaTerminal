<template>
  <button
    class="swap-button flex items-center justify-center rounded-lg bg-terminal-panel border border-theme-secondary hover:bg-terminal-hover hover:border-terminal-accent/50 transition-all"
    :style="{ width: '44px', height: '44px', minWidth: '44px', minHeight: '44px' }"
    @click="handleClick"
    :disabled="disabled"
    :aria-label="ariaLabel || '交换'"
    title="交换"
  >
    <span 
      class="swap-icon text-lg text-terminal-dim transition-transform duration-200"
      :class="{ 'rotate-180': isRotated }"
    >
      ⇄
    </span>
  </button>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  disabled: {
    type: Boolean,
    default: false
  },
  ariaLabel: {
    type: String,
    default: '交换'
  }
})

const emit = defineEmits(['swap'])

const isRotated = ref(false)

function handleClick() {
  if (props.disabled) return
  
  isRotated.value = true
  emit('swap')
  
  setTimeout(() => {
    isRotated.value = false
  }, 200)
}
</script>

<style scoped>
.swap-button {
  touch-action: manipulation;
  cursor: pointer;
}

.swap-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.bg-terminal-panel {
  background: var(--bg-secondary, #1a1f2e);
}

.bg-terminal-hover {
  background: var(--bg-hover, #262d3d);
}

.text-terminal-dim {
  color: var(--text-secondary, #8B949E);
}

.border-theme-secondary {
  border-color: var(--border-color, #2d3748);
}

.swap-icon {
  display: inline-block;
}
</style>
