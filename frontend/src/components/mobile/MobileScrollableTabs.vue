<template>
  <div class="mobile-tabs-container">
    <div 
      ref="tabsRef"
      class="mobile-tabs-scroll flex overflow-x-auto scrollbar-hide gap-1 px-2 py-1"
      @scroll="handleScroll"
    >
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="[
          'mobile-tab flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all',
          modelValue === tab.key 
            ? 'bg-terminal-accent text-white shadow-sm' 
            : 'bg-terminal-panel text-terminal-dim hover:bg-terminal-hover hover:text-terminal-primary'
        ]"
        :style="{ minWidth: '44px', minHeight: '44px' }"
        @click="$emit('update:modelValue', tab.key)"
        :aria-selected="modelValue === tab.key"
        :aria-label="tab.label"
        role="tab"
      >
        <span v-if="tab.icon" class="text-base">{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
      </button>
    </div>
    <div 
      v-if="showScrollIndicator && !isAtEnd" 
      class="scroll-indicator-right absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-terminal-bg to-transparent pointer-events-none"
    ></div>
    <div 
      v-if="showScrollIndicator && !isAtStart" 
      class="scroll-indicator-left absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-terminal-bg to-transparent pointer-events-none"
    ></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  tabs: {
    type: Array,
    required: true,
    default: () => []
  },
  modelValue: {
    type: String,
    required: true
  },
  showScrollIndicator: {
    type: Boolean,
    default: true
  }
})

defineEmits(['update:modelValue'])

const tabsRef = ref(null)
const isAtStart = ref(true)
const isAtEnd = ref(false)

function handleScroll() {
  if (!tabsRef.value) return
  const { scrollLeft, scrollWidth, clientWidth } = tabsRef.value
  isAtStart.value = scrollLeft <= 10
  isAtEnd.value = scrollLeft + clientWidth >= scrollWidth - 10
}

function checkScrollPosition() {
  handleScroll()
}

onMounted(() => {
  checkScrollPosition()
  window.addEventListener('resize', checkScrollPosition)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkScrollPosition)
})
</script>

<style scoped>
.mobile-tabs-container {
  position: relative;
}

.mobile-tabs-scroll {
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
}

.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

.mobile-tab {
  touch-action: manipulation;
}
</style>
