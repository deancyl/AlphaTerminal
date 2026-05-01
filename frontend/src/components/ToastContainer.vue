<template>
  <Teleport to="body">
    <div
      class="fixed z-[var(--z-toast)] flex flex-col gap-2 pointer-events-none"
      :class="isMobile ? 'top-2 left-2 right-2 items-center' : 'top-4 right-4 items-end'"
    >
      <TransitionGroup
        enter-active-class="transition-all duration-300 ease-out"
        enter-from-class="opacity-0 translate-x-4"
        enter-to-class="opacity-100 translate-x-0"
        leave-active-class="transition-all duration-200 ease-in"
        leave-from-class="opacity-100 translate-x-0 scale-100"
        leave-to-class="opacity-0 translate-x-4 scale-95"
      >
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="pointer-events-auto w-full max-w-[360px] rounded-sm border shadow-sm backdrop-blur-sm overflow-hidden"
          :class="getToastClass(toast.type)"
          @mouseenter="pauseToast(toast.id)"
          @mouseleave="resumeToast(toast.id)"
        >
          <div class="flex items-start gap-2 p-3">
            <span class="text-base shrink-0 mt-0.5">{{ toast.icon }}</span>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium leading-tight">{{ toast.title }}</div>
              <div v-if="toast.message" class="text-xs mt-0.5 opacity-80 leading-relaxed">{{ toast.message }}</div>
            </div>
            <button
              class="shrink-0 w-5 h-5 flex items-center justify-center rounded-sm opacity-50 hover:opacity-100 transition-opacity text-xs"
              @click="remove(toast.id)"
            >
              ✕
            </button>
          </div>
          <!-- 进度条 -->
          <div class="h-0.5 bg-current opacity-20">
            <div
              class="h-full bg-current opacity-60 transition-all linear"
              :style="{ width: getProgress(toast) + '%', transitionDuration: toast.duration + 'ms' }"
            ></div>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
import { useBreakpoints, breakpointsTailwind } from '@vueuse/core'
import { useToast } from '../composables/useToast.js'

const { toasts, remove } = useToast()

const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('md')

// 暂停的 toast 计时器
const pausedTimers = new Map()

function getToastClass(type) {
  const map = {
    success: 'bg-[var(--color-success-bg)]/90 border-[var(--color-success-border)] text-[var(--color-success)]',
    error:   'bg-[var(--color-danger-bg)]/90 border-[var(--color-danger-border)] text-[var(--color-danger)]',
    warning: 'bg-[var(--color-warning-bg)]/90 border-[var(--color-warning-border)] text-[var(--color-warning)]',
    info:    'bg-[var(--color-info-bg)]/90 border-[var(--color-info-border)] text-[var(--color-info)]',
  }
  return map[type] || map.info
}

function getProgress(toast) {
  if (pausedTimers.has(toast.id)) return 100
  const elapsed = Date.now() - toast.createdAt
  const remaining = Math.max(0, toast.duration - elapsed)
  return (remaining / toast.duration) * 100
}

function pauseToast(id) {
  // 简单实现：暂停时重置为100%，移除时恢复
  pausedTimers.set(id, true)
}

function resumeToast(id) {
  pausedTimers.delete(id)
  // 重新计时
  const toast = toasts.value.find(t => t.id === id)
  if (toast) {
    setTimeout(() => remove(id), toast.duration)
  }
}
</script>