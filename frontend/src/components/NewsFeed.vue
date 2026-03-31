<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center justify-between mb-2 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">📰 快讯</span>
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
        @click="openModal(item)"
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

    <!-- ── 详情 Modal ─────────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="modalItem"
           class="fixed inset-0 z-50 flex items-center justify-center p-4"
           @click.self="closeModal">
        <!-- 遮罩 -->
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
        <!-- 弹窗 -->
        <div class="relative z-10 w-full max-w-2xl max-h-[80vh] flex flex-col
                    bg-[#0d1117] border border-gray-600 rounded-xl shadow-2xl overflow-hidden">
          <!-- Header -->
          <div class="flex items-start justify-between p-4 border-b border-gray-700 shrink-0">
            <div class="flex-1 pr-4">
              <div class="flex items-center gap-2 mb-2">
                <span class="text-[11px] px-2 py-0.5 rounded" :class="tagClass(modalItem.tag)">
                  {{ modalItem.tag }}
                </span>
                <span class="text-terminal-dim text-[11px]">{{ modalItem.time }}</span>
                <span class="text-terminal-dim/50 text-[11px]">{{ modalItem.source }}</span>
              </div>
              <h2 class="text-sm font-medium text-gray-100 leading-snug">{{ modalItem.title }}</h2>
            </div>
            <button
              class="shrink-0 w-8 h-8 flex items-center justify-center rounded-full
                     bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-gray-200 transition"
              @click="closeModal">
              ✕
            </button>
          </div>
          <!-- Body -->
          <div class="flex-1 overflow-y-auto p-4">
            <p v-if="modalItem.content" class="text-xs text-gray-300 leading-relaxed whitespace-pre-wrap">
              {{ modalItem.content }}
            </p>
            <p v-else class="text-xs text-gray-500 leading-relaxed italic">
              （暂无正文内容，请点击来源链接查看原文）
            </p>
            <a v-if="modalItem.url && modalItem.url !== '#'"
               :href="modalItem.url" target="_blank" rel="noopener"
               class="mt-3 inline-flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 transition">
              🔗 查看原文
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
              </svg>
            </a>
          </div>
        </div>
      </div>
    </Teleport>
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
const modalItem = ref(null)
let refreshTimer = null

function tagClass(tag) {
  if (!tag) return 'bg-gray-600/30 text-gray-400'
  if (tag.includes('🔴') || tag.includes('突发') || tag.includes('暴跌')) return 'bg-red-500/20 text-red-400'
  if (tag.includes('📈') || tag.includes('上涨') || tag.includes('大涨')) return 'bg-orange-500/20 text-orange-400'
  if (tag.includes('📉')) return 'bg-green-500/20 text-green-400'
  if (tag.includes('🌏') || tag.includes('港股') || tag.includes('宏观')) return 'bg-blue-500/20 text-blue-400'
  if (tag.includes('💎') || tag.includes('黄金') || tag.includes('央行') || tag.includes('美联储')) return 'bg-yellow-500/20 text-yellow-400'
  if (tag.includes('🖥') || tag.includes('AI') || tag.includes('特朗普')) return 'bg-purple-500/20 text-purple-400'
  if (tag.includes('🛢') || tag.includes('原油') || tag.includes('商品')) return 'bg-amber-500/20 text-amber-400'
  return 'bg-gray-600/30 text-gray-400'
}

function onItemClick(item) { emit('item-click', item) }

function openModal(item) { modalItem.value = item }
function closeModal() { modalItem.value = null }

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
    const newItems = incoming.filter(it => {
      const id = it.id || it.title
      return !existingIds.has(id)
    })

    if (newItems.length) {
      items.value = [...newItems, ...items.value].slice(0, 100)
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
  fetchNews(false)
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
