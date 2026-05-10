<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-all duration-150 ease-out"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition-all duration-100 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="visible"
        class="fixed z-[var(--z-popover)] bg-terminal-panel border border-theme-secondary rounded-sm shadow-sm py-1 min-w-[160px]"
        :style="{ left: x + 'px', top: y + 'px' }"
        @click.stop
        role="menu"
        aria-label="上下文菜单"
      >
        <div
          v-for="item in items"
          :key="item.id"
          class="px-3 py-2 text-[12px] text-theme-primary hover:bg-theme-hover cursor-pointer flex items-center gap-2 transition-colors"
          @click="handleClick(item)"
          role="menuitem"
          :aria-label="item.label"
          tabindex="0"
        >
          <span class="text-base" aria-hidden="true">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
          <span v-if="item.shortcut" class="ml-auto text-[10px] text-theme-muted" aria-hidden="true">{{ item.shortcut }}</span>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
const props = defineProps({
  visible: { type: Boolean, default: false },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
  items: { type: Array, default: () => [] }
})

const emit = defineEmits(['select', 'close'])

function handleClick(item) {
  emit('select', item)
  emit('close')
}
</script>