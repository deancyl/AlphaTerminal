<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" @click.self="cancel" @keydown.esc="cancel">
      <div class="bg-terminal-panel border border-theme rounded-lg p-6 max-w-md shadow-xl">
        <div class="text-theme-primary mb-4 text-sm">{{ message }}</div>
        <div class="flex gap-3 justify-end">
          <button @click="cancel" class="px-4 py-2 bg-terminal-bg border border-theme-secondary rounded text-theme-tertiary hover:border-theme-primary text-xs">
            取消
          </button>
          <button @click="confirm" class="px-4 py-2 bg-terminal-accent/20 border border-terminal-accent/50 rounded text-terminal-accent hover:bg-terminal-accent/30 text-xs">
            确定
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'
const props = defineProps({ message: String })
const visible = ref(false)
const emit = defineEmits(['confirmed', 'cancelled'])

function show() { visible.value = true }
function confirm() { visible.value = false; emit('confirmed') }
function cancel() { visible.value = false; emit('cancelled') }

defineExpose({ show })
</script>