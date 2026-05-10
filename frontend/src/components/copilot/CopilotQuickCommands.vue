<template>
  <div class="px-4 py-2 border-b border-theme-secondary">
    <div class="text-[10px] text-terminal-dim mb-2">💡 快捷命令</div>
    <div class="flex flex-wrap gap-1.5">
      <button
        v-for="cmd in commands" :key="cmd.cmd"
        class="px-2 py-1 text-[10px] rounded-sm bg-terminal-bg border border-theme text-terminal-dim
               hover:border-terminal-accent/50 hover:text-terminal-accent transition-colors whitespace-nowrap"
        :disabled="isLoading" @click="$emit('execute', cmd)">
        {{ cmd.icon }} {{ cmd.label }}
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  commands: { type: Array, required: true },
  isLoading: { type: Boolean, default: false }
})

defineEmits(['execute'])
</script>
