<template>
  <div class="absolute bottom-4 left-1/2 -translate-x-1/2 z-20">
    <div class="flex items-center gap-3 bg-glass backdrop-blur-md px-4 py-2 rounded-xl border border-border-base shadow-theme-lg">
      <!-- Play/Pause Button -->
      <button
        @click="handlePlayPause"
        class="p-2 rounded-lg hover:bg-surface-hover transition-colors"
        :aria-label="status === 'playing' ? '暂停' : '播放'"
      >
        <svg v-if="status !== 'playing'" class="w-5 h-5 text-primary" fill="currentColor" viewBox="0 0 24 24">
          <path d="M8 5v14l11-7z" />
        </svg>
        <svg v-else class="w-5 h-5 text-primary" fill="currentColor" viewBox="0 0 24 24">
          <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
        </svg>
      </button>
      
      <!-- Step Forward Button -->
      <button
        @click="$emit('step', 1)"
        :disabled="currentBar >= totalBars - 1"
        class="p-2 rounded-lg hover:bg-surface-hover transition-colors disabled:opacity-40"
        aria-label="前进一根K线"
      >
        <svg class="w-5 h-5 text-primary" fill="currentColor" viewBox="0 0 24 24">
          <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" />
        </svg>
      </button>
      
      <!-- Fast Forward Button -->
      <button
        @click="$emit('step', 10)"
        :disabled="currentBar + 10 >= totalBars"
        class="p-2 rounded-lg hover:bg-surface-hover transition-colors disabled:opacity-40"
        aria-label="前进10根K线"
      >
        <svg class="w-5 h-5 text-primary" fill="currentColor" viewBox="0 0 24 24">
          <path d="M4 18l8.5-6L4 6v12zm9-12v12l8.5-6L13 6z" />
        </svg>
      </button>
      
      <!-- Divider -->
      <div class="w-px h-6 bg-border-base"></div>
      
      <!-- Speed Control -->
      <div class="flex items-center gap-2">
        <span class="text-xs text-secondary">速度</span>
        <select
          :value="speed"
          @change="$emit('speed-change', Number($event.target.value))"
          class="bg-base text-primary text-sm px-2 py-1 rounded border border-border-base focus:border-primary focus:outline-none"
        >
          <option :value="0.5">0.5x</option>
          <option :value="1">1x</option>
          <option :value="2">2x</option>
          <option :value="5">5x</option>
          <option :value="10">10x</option>
        </select>
      </div>
      
      <!-- Divider -->
      <div class="w-px h-6 bg-border-base"></div>
      
      <!-- Progress Display -->
      <div class="flex items-center gap-2 text-sm">
        <span class="text-secondary">进度</span>
        <span class="font-data text-primary">{{ currentBar + 1 }}</span>
        <span class="text-muted">/</span>
        <span class="font-data text-secondary">{{ totalBars }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: {
    type: String,
    default: 'idle',
    validator: (v) => ['idle', 'playing', 'paused'].includes(v)
  },
  currentBar: {
    type: Number,
    default: 0
  },
  totalBars: {
    type: Number,
    default: 0
  },
  speed: {
    type: Number,
    default: 1
  }
})

const emit = defineEmits(['play', 'pause', 'step', 'speed-change'])

function handlePlayPause() {
  if (props.status === 'playing') {
    emit('pause')
  } else {
    emit('play')
  }
}
</script>
