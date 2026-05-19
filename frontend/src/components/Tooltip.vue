<template>
  <div class="tooltip-container" relative>
    <slot />
    <div v-if="show" class="tooltip-inner absolute z-50 px-2 py-1 text-xs rounded bg-surface border border-border-base text-primary shadow-lg">
      {{ content }}
    </div>
  </div>
</template>

<script setup>
defineProps({
  content: { type: String, default: '' },
  show: { type: Boolean, default: false }
})
</script>

<style scoped>
.tooltip-container { position: relative; }
.tooltip-inner {
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  white-space: nowrap;
}
</style>
