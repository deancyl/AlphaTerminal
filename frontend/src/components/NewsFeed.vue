<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center justify-between mb-2 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">📰 快讯瀑布流</span>
      <span class="text-terminal-dim text-[10px]">{{ items.length }} 条</span>
    </div>
    <div class="flex-1 overflow-y-auto space-y-1.5 min-h-0">
      <div
        v-for="item in items"
        :key="item.id"
        class="bg-terminal-bg rounded border border-gray-700 p-2 hover:border-terminal-accent/40 transition-colors cursor-pointer"
        @click="onItemClick(item)"
      >
        <div class="flex items-start gap-2">
          <span class="shrink-0 text-[10px] px-1.5 py-0.5 rounded"
                :class="tagClass(item.tag)">
            {{ item.tag }}
          </span>
          <div class="flex-1 min-w-0">
            <p class="text-xs text-gray-200 leading-snug line-clamp-2">{{ item.title }}</p>
            <div class="flex items-center gap-2 mt-1">
              <span class="text-terminal-dim text-[9px]">{{ item.time }}</span>
              <span class="text-terminal-dim/50 text-[9px]">{{ item.source }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({
  initialItems: { type: Array, default: () => [] }
})

const emit = defineEmits(['item-click'])
const items = ref(props.initialItems)

function tagClass(tag) {
  if (tag?.includes('🔴')) return 'bg-red-500/20 text-red-400'
  if (tag?.includes('📈')) return 'bg-orange-500/20 text-orange-400'
  if (tag?.includes('📉')) return 'bg-green-500/20 text-green-400'
  if (tag?.includes('🌏')) return 'bg-blue-500/20 text-blue-400'
  if (tag?.includes('💎')) return 'bg-yellow-500/20 text-yellow-400'
  if (tag?.includes('🖥') || tag?.includes('AI')) return 'bg-purple-500/20 text-purple-400'
  return 'bg-gray-600/30 text-gray-400'
}

function onItemClick(item) {
  emit('item-click', item)
}

async function fetchNews() {
  try {
    const res = await fetch('http://localhost:8002/api/v1/news/flash')
    if (res.ok) {
      const data = await res.json()
      items.value = data.news || []
    }
  } catch {}
}

onMounted(fetchNews)
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
