<template>
  <div class="flex flex-col h-full">

    <!-- ── Header ─────────────────────────────────────────────── -->
    <div class="flex items-center justify-between mb-2 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">📰 快讯</span>
      <div class="flex items-center gap-2">
        <span class="text-terminal-dim text-[10px]">{{ total }} 条</span>
        <span class="w-1.5 h-1.5 rounded-full"
              :class="loading ? 'bg-yellow-400 animate-pulse' : 'bg-green-400'"></span>
      </div>
    </div>

    <!-- ── 新闻列表（固定高度，显示 7 条） ───────────────────────── -->
    <div
      ref="listEl"
      class="flex-1 overflow-y-auto"
      style="height: 0; min-height: 380px;"
    >
      <div class="space-y-1.5">
        <div
          v-for="item in pagedItems"
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
        <div v-if="!pagedItems.length" class="text-center py-8 text-terminal-dim text-xs">
          暂无快讯数据
        </div>
      </div>
    </div>

    <!-- ── 分页控制器 ─────────────────────────────────────────── -->
    <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 mt-2 shrink-0">
      <button
        class="px-2 py-0.5 text-[10px] rounded border transition"
        :class="currentPage === 1
          ? 'bg-gray-700 border-gray-600 text-gray-500 cursor-not-allowed'
          : 'bg-terminal-bg border-gray-600 text-gray-300 hover:border-terminal-accent/50'"
        :disabled="currentPage === 1"
        @click="prevPage">
        ‹
      </button>

      <button
        v-for="p in visiblePages"
        :key="p"
        class="px-2 py-0.5 text-[10px] rounded border transition"
        :class="p === currentPage
          ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent'
          : 'bg-terminal-bg border-gray-600 text-gray-300 hover:border-terminal-accent/50'"
        @click="goToPage(p)">
        {{ p }}
      </button>

      <button
        class="px-2 py-0.5 text-[10px] rounded border transition"
        :class="currentPage === totalPages
          ? 'bg-gray-700 border-gray-600 text-gray-500 cursor-not-allowed'
          : 'bg-terminal-bg border-gray-600 text-gray-300 hover:border-terminal-accent/50'"
        :disabled="currentPage === totalPages"
        @click="nextPage">
        ›
      </button>

      <span class="text-terminal-dim text-[9px] ml-1">{{ currentPage }}/{{ totalPages }}</span>
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
              <div class="flex items-center gap-2 mb-2 flex-wrap">
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
            <!-- 加载态 -->
            <p v-if="modalLoading" class="text-xs text-terminal-dim italic leading-relaxed">
              正文努力提取中...
            </p>
            <!-- 正文内容 -->
            <p v-else-if="modalContent" class="text-xs text-gray-300 leading-relaxed whitespace-pre-wrap">
              {{ modalContent }}
            </p>
            <!-- 降级 -->
            <p v-else class="text-xs text-gray-500 leading-relaxed italic">
              （暂无正文内容，请点击来源链接查看原文）
            </p>
          </div>
          <!-- Footer -->
          <div class="p-3 border-t border-gray-700 shrink-0 flex justify-between items-center">
            <a v-if="modalItem.url"
               :href="modalItem.url" target="_blank" rel="noopener"
               class="text-xs text-blue-400 hover:text-blue-300 underline hover:no-underline transition">
              🔗 {{ modalItem.url }}
            </a>
            <span v-else class="text-xs text-gray-500 italic">（无原文链接）</span>
            <button
              class="ml-4 px-3 py-1 text-[11px] rounded bg-blue-600 hover:bg-blue-500 text-white transition shrink-0"
              @click="modalItem.url ? window.open(modalItem.url, '_blank') : null">
              浏览器打开
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  initialItems: { type: Array, default: () => [] }
})

const items       = ref(props.initialItems)
const total       = ref(0)
const loading     = ref(false)
const listEl      = ref(null)
const refreshTimer = ref(null)

// ── 分页状态 ─────────────────────────────────────────────────────────
const PAGE_SIZE  = 50
const currentPage = ref(1)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

// 当前页数据
const pagedItems = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return items.value.slice(start, start + PAGE_SIZE)
})

// 显示的页码按钮（最多 5 个）
const visiblePages = computed(() => {
  const tp = totalPages.value
  const cp = currentPage.value
  if (tp <= 5) return Array.from({ length: tp }, (_, i) => i + 1)
  const pages = []
  if (cp <= 3) {
    pages.push(1, 2, 3, 4, 5)
  } else if (cp >= tp - 2) {
    pages.push(tp - 4, tp - 3, tp - 2, tp - 1, tp)
  } else {
    pages.push(cp - 2, cp - 1, cp, cp + 1, cp + 2)
  }
  return pages
})

function goToPage(p) {
  if (p < 1 || p > totalPages.value || p === currentPage.value) return
  currentPage.value = p
  if (listEl.value) listEl.value.scrollTop = 0
}
function prevPage() { goToPage(currentPage.value - 1) }
function nextPage() { goToPage(currentPage.value + 1) }

// ── Modal 状态 ────────────────────────────────────────────────────────
const modalItem    = ref(null)
const modalContent = ref('')
const modalLoading = ref(false)

// ── 标签颜色映射 ──────────────────────────────────────────────────────
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

// ── Modal 异步加载正文 ────────────────────────────────────────────────
async function openModal(item) {
  modalItem.value    = item
  modalContent.value = ''
  modalLoading.value = true

  try {
    const res = await fetch(`/api/v1/news/detail?url=${encodeURIComponent(item.url)}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    modalContent.value = data.content || ''
  } catch (e) {
    console.warn('[NewsFeed] detail fetch failed:', e.message)
    modalContent.value = ''
  } finally {
    modalLoading.value = false
  }
}

function closeModal() {
  modalItem.value    = null
  modalContent.value = ''
  modalLoading.value = false
}

// ── 数据拉取 ──────────────────────────────────────────────────────────
async function fetchNews(quiet = false) {
  if (!quiet) loading.value = true
  try {
    const res = await fetch('/api/v1/news/flash')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    const incoming = data.news || []

    if (!incoming.length) return

    // 去重
    const existingIds = new Set(items.value.map(it => it.id || it.title))
    const newItems = incoming.filter(it => {
      const id = it.id || it.title
      return !existingIds.has(id)
    })

    if (newItems.length) {
      items.value = [...newItems, ...items.value].slice(0, 200)
    }
    total.value = incoming.length   // 使用 API 返回的 total 计数
    currentPage.value = 1
    if (listEl.value) listEl.value.scrollTop = 0
  } catch (e) {
    console.warn('[NewsFeed] fetch failed:', e.message)
  } finally {
    if (!quiet) loading.value = false
  }
}

function startAutoRefresh() {
  fetchNews(false)
  refreshTimer.value = setInterval(() => fetchNews(true), 20 * 60 * 1000)
}

onMounted(startAutoRefresh)
onUnmounted(() => {
  if (refreshTimer.value) clearInterval(refreshTimer.value)
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
