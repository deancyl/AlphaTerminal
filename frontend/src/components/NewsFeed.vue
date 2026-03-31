<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center justify-between mb-2 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">📰 快讯瀑布流</span>
      <div class="flex items-center gap-2">
        <span class="text-terminal-dim text-[10px]">{{ items.length }} 条</span>
        <span class="w-1.5 h-1.5 rounded-full"
              :class="loading ? 'bg-yellow-400 animate-pulse' : 'bg-green-400'"></span>
      </div>
    </div>
    <div class="flex-1 overflow-y-auto space-y-1.5 min-h-0" ref="listEl">
      <div
        v-for="item in items"
        :key="item.id || item.title"
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
      <div v-if="!items.length" class="text-center mt-8 text-terminal-dim text-xs">
        暂无快讯数据
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  initialItems: { type: Array, default: () => [] }
})

const emit  = defineEmits(['item-click'])
const items   = ref(props.initialItems)
const loading = ref(false)
const listEl  = ref(null)
let refreshTimer = null

function tagClass(tag) {
  if (!tag) return 'bg-gray-600/30 text-gray-400'
  if (tag.includes('🔴') || tag.includes('下跌')) return 'bg-red-500/20 text-red-400'
  if (tag.includes('📈') || tag.includes('上涨')) return 'bg-orange-500/20 text-orange-400'
  if (tag.includes('📉')) return 'bg-green-500/20 text-green-400'
  if (tag.includes('🌏') || tag.includes('宏观')) return 'bg-blue-500/20 text-blue-400'
  if (tag.includes('💎') || tag.includes('黄金')) return 'bg-yellow-500/20 text-yellow-400'
  if (tag.includes('🖥') || tag.includes('AI') || tag.includes('特朗普')) return 'bg-purple-500/20 text-purple-400'
  return 'bg-gray-600/30 text-gray-400'
}

function onItemClick(item) { emit('item-click', item) }

async function fetchNews(quiet = false) {
  if (!quiet) loading.value = true
  try {
    const res = await fetch('/api/v1/news/flash')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data    = await res.json()
    const incoming = data.news || []

    if (!incoming.length) {
      if (!quiet) loading.value = false
      return
    }

    // ── 去重：基于 id 或 title 排重 ──────────────────────────────
    const existingIds = new Set(items.value.map(it => it.id || it.title))
    const existingTitles = new Set(items.value.map(it => it.title))
    const newItems = incoming.filter(it => {
      const id    = it.id || it.title
      return !existingIds.has(id) && !existingTitles.has(it.title)
    })

    if (newItems.length) {
      // 新数据追加到顶部
      items.value = [...newItems, ...items.value]
      // 最多保留 100 条，防止内存膨胀
      if (items.value.length > 100) {
        items.value = items.value.slice(0, 100)
      }
      // 滚动到顶部看新消息
      if (listEl.value) listEl.value.scrollTop = 0
    }
  } catch (e) {
    console.warn('[NewsFeed] fetch failed:', e.message)
  } finally {
    if (!quiet) loading.value = false
  }
}

// 每 5 分钟自动刷新一次
function startAutoRefresh() {
  // 立即拉一次
  fetchNews(false)
  // 之后每 5 分钟
  refreshTimer = setInterval(() => fetchNews(true), 5 * 60 * 1000)
}

onMounted(startAutoRefresh)
onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
