<template>
  <div class="flex flex-col min-h-0 h-full">

    <!-- ── Header ─────────────────────────────────────────────── -->
    <div class="flex items-center justify-between mb-2 shrink-0">
      <span class="text-terminal-accent font-bold text-sm">📰 快讯</span>
      <div class="flex items-center gap-2">
        <!-- 刷新成功提示 -->
        <span v-if="showRefreshed && refreshMsg" class="text-bearish text-[10px] animate-pulse">
          {{ refreshMsg }}
        </span>
        <span v-else-if="lastRefreshLabel" class="text-terminal-dim text-[10px]">
          {{ lastRefreshLabel }}
        </span>
        <span class="text-terminal-dim text-[10px]">{{ filteredTotal }} 条</span>
        <!-- 手动刷新按钮 -->
        <button
          class="w-8 h-8 flex items-center justify-center rounded border transition shrink-0"
          :class="isRefreshing
            ? 'border-yellow-500/30 text-yellow-400 bg-yellow-500/10 cursor-not-allowed'
            : 'border-theme-secondary text-terminal-dim hover:border-terminal-accent/50 hover:text-terminal-accent bg-terminal-bg'"
          :disabled="isRefreshing"
          @click="manualRefresh"
          title="刷新快讯"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"
               class="w-4 h-4 transition-all"
               :class="isRefreshing ? 'animate-spin' : ''">
            <path fill-rule="evenodd" d="M4.755 10.059a7.5 7.5 0 0110.138-5.133A7.501 7.501 0 1019.8 13.71a7 7 0 01-14.046 3.293l-1.207.855.002.001zm-.9 1.865l1.207-.856a7.501 7.501 0 0112.237-4.384A7.5 7.5 0 014.26 17.32l-1.15.67.001-.001zm3.163-3.018l.708 1.228a9 9 0 0010.725 3.658l.578-1.117-1.414.818a7.5 7.5 0 01-10.596-2.93zM12 2.25a.75.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0V3a.75.75 0 01.75-.75zM5.166 6.036a8.963 8.963 0 0111.668.156 8.964 8.964 0 01-11.668-.156z" clip-rule="evenodd" />
          </svg>
        </button>
        <span class="w-1.5 h-1.5 rounded-full shrink-0"
              :class="isRefreshing ? 'bg-yellow-400 animate-pulse' : 'bg-green-400'"></span>
      </div>
    </div>

    <!-- ── 舆情情绪摘要栏（增强版）─────────────────────────── -->
    <div v-if="sentiment.total_count > 0" class="mb-2 shrink-0 space-y-2"
    >
      <!-- 情绪概览 -->
      <div class="flex items-center gap-2 px-2 py-1.5 rounded-lg border transition"
           :class="sentiment.score > 0.1
             ? 'border-red-500/30 bg-red-500/5'
             : sentiment.score < -0.1
               ? 'border-green-500/30 bg-green-500/5'
               : 'border-theme-secondary bg-theme-tertiary/5'"
      >
        <span class="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0"
              :class="sentiment.score > 0.1
                ? 'bg-red-500/20 text-bullish'
                : sentiment.score < -0.1
                  ? 'bg-green-500/20 text-bearish'
                  : 'bg-theme-tertiary/20 text-theme-secondary'"
        >
          {{ sentiment.label }}
        </span>
        <span class="text-[10px] text-terminal-dim shrink-0">
          {{ sentiment.bullish_count }}🔴:{{ sentiment.bearish_count }}🟢
        </span>
        <div class="flex-1 flex gap-1 overflow-x-auto ml-2 scrollbar-hide">
          <span v-for="kw in sentiment.keywords.slice(0, 5)" :key="kw"
                class="shrink-0 text-[9px] px-1 py-0.5 rounded bg-theme-tertiary/15 text-theme-tertiary whitespace-nowrap"
          >
            {{ kw }}
          </span>
        </div>
        <span class="text-[9px] text-terminal-dim/50 shrink-0">{{ sentimentTime }}</span>
      </div>

      <!-- 情绪分布条形图 -->
      <div class="px-2 py-1.5 rounded-lg border border-theme-secondary bg-terminal-panel/50"
      >
        <div class="flex items-center justify-between mb-1"
        >
          <span class="text-[10px] text-terminal-dim"
          >情绪分布</span>
          <span class="text-[9px] text-terminal-dim"
          >共 {{ sentiment.total_count }} 条</span>
        </div>
        <div class="h-2 rounded-full overflow-hidden flex"
        >
          <div class="h-full bg-red-500/60 transition-all"
               :style="{ width: bullishRatio + '%' }"
               title="看涨"
          />
          <div class="h-full bg-theme-tertiary/30 transition-all"
               :style="{ width: neutralRatio + '%' }"
               title="中性"
          />
          <div class="h-full bg-green-500/60 transition-all"
               :style="{ width: bearishRatio + '%' }"
               title="看跌"
          />
        </div>
        <div class="flex justify-between mt-1"
        >
          <span class="text-[9px] text-red-400"
          >{{ sentiment.bullish_count }} 看涨</span>
          <span class="text-[9px] text-theme-tertiary"
          >{{ sentiment.neutral_count || 0 }} 中性</span>
          <span class="text-[9px] text-green-400"
          >{{ sentiment.bearish_count }} 看跌</span>
        </div>
      </div>

      <!-- 筛选标签 -->
      <div class="flex gap-1 px-2"
      >
        <button
          v-for="filter in sentimentFilters"
          :key="filter.value"
          class="text-[9px] px-2 py-0.5 rounded border transition"
          :class="activeSentimentFilter === filter.value
            ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent'
            : 'bg-terminal-bg border-theme-secondary text-theme-tertiary hover:text-theme-primary'"
          @click="activeSentimentFilter = filter.value"
        >
          {{ filter.label }}
        </button>
      </div>
    </div>

    <!-- ── 新闻列表（自适应高度） ───────────────────────── -->
    <div
      ref="listEl"
      class="flex-1 overflow-y-auto"
      style="height: 0; min-height: 200px;"
    >
      <div class="space-y-1.5">
        <div
          v-for="item in pagedItems"
          :key="item.id || item.title"
          class="bg-terminal-bg rounded border border-theme p-2 hover:border-terminal-accent/40 transition-colors cursor-pointer"
          @click="openModal(item)"
        >
          <div class="flex items-start gap-2">
            <span class="shrink-0 text-[10px] px-1.5 py-0.5 rounded"
                  :class="tagClass(item.tag)">
              {{ item.tag }}
            </span>
            <!-- 时间 -->
            <span class="shrink-0 text-[9px] text-theme-tertiary w-12 text-right">{{ formatTime(item.time) }}</span>
            <!-- 标题 + 来源 -->
            <div class="flex-1 min-w-0">
              <p class="text-xs text-theme-primary leading-snug line-clamp-2">{{ item.title }}</p>
              <span class="text-terminal-dim/50 text-[9px]">{{ item.source }}</span>
            </div>
            <!-- 情绪徽章 -->
            <span v-if="getItemSentiment(item)" class="shrink-0 text-[9px] px-1.5 py-0.5 rounded font-medium"
                  :class="sentimentBadgeClass(getItemSentiment(item))">
              {{ getItemSentiment(item) }}
            </span>
          </div>
        </div>
        <!-- 骨架屏 -->
        <div v-if="isRefreshing && !pagedItems.length" class="space-y-2 animate-pulse">
          <div v-for="i in 5" :key="i" class="flex items-start gap-2">
            <div class="w-8 h-4 rounded bg-terminal-panel"></div>
            <div class="flex-1 space-y-1">
              <div class="h-4 rounded bg-terminal-panel w-3/4"></div>
              <div class="h-3 rounded bg-terminal-panel w-1/2"></div>
            </div>
          </div>
        </div>
        <div v-else-if="!pagedItems.length" class="text-center py-8 text-terminal-dim text-xs">
          {{ activeSentimentFilter === 'all' ? '暂无快讯数据' : '暂无符合筛选条件的快讯' }}
        </div>
      </div>
    </div>

    <!-- ── 分页控制器 ─────────────────────────────────────────── -->
    <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 mt-2 shrink-0">
      <button
        class="px-2 py-0.5 text-[10px] rounded border transition"
        :class="currentPage === 1
          ? 'bg-theme-tertiary border-theme-secondary text-theme-tertiary cursor-not-allowed'
          : 'bg-terminal-bg border-theme-secondary text-theme-primary hover:border-terminal-accent/50'"
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
          : 'bg-terminal-bg border-theme-secondary text-theme-primary hover:border-terminal-accent/50'"
        @click="goToPage(p)">
        {{ p }}
      </button>
      <button
        class="px-2 py-0.5 text-[10px] rounded border transition"
        :class="currentPage === totalPages
          ? 'bg-theme-tertiary border-theme-secondary text-theme-tertiary cursor-not-allowed'
          : 'bg-terminal-bg border-theme-secondary text-theme-primary hover:border-terminal-accent/50'"
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
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
        <div class="relative z-10 w-full max-w-2xl max-h-[80vh] flex flex-col
                    bg-[#0d1117] border border-theme-secondary rounded-xl shadow-2xl overflow-hidden">
          <div class="flex items-start justify-between p-4 border-b border-theme shrink-0">
            <div class="flex-1 pr-4">
              <div class="flex items-center gap-2 mb-2 flex-wrap">
                <span class="text-[11px] px-2 py-0.5 rounded" :class="tagClass(modalItem.tag)">
                  {{ modalItem.tag }}
                </span>
                <span class="text-terminal-dim text-[11px]">{{ modalItem.time }}</span>
                <span class="text-terminal-dim/50 text-[11px]">{{ modalItem.source }}</span>
              </div>
              <h2 class="text-sm font-medium text-theme-primary leading-snug">{{ modalItem.title }}</h2>
            </div>
            <button
              class="shrink-0 w-8 h-8 flex items-center justify-center rounded-full
                     bg-theme-tertiary hover:bg-theme-tertiary text-theme-secondary hover:text-theme-primary transition"
              @click="closeModal">
              ✕
            </button>
          </div>
          <div class="flex-1 overflow-y-auto p-4">
            <p v-if="modalLoading" class="text-xs text-terminal-dim italic leading-relaxed">
              正文努力提取中...
            </p>
            <p v-else-if="modalContent" class="text-xs text-theme-primary leading-relaxed whitespace-pre-wrap">
              {{ modalContent }}
            </p>
            <p v-else class="text-xs text-theme-tertiary leading-relaxed italic">
              （暂无正文内容，请点击来源链接查看原文）
            </p>
          </div>
          <div class="p-3 border-t border-theme shrink-0 flex justify-between items-center">
            <a v-if="modalItem.url"
               :href="modalItem.url" target="_blank" rel="noopener"
               class="text-xs text-blue-400 hover:text-blue-300 underline hover:no-underline transition">
              🔗 {{ modalItem.url }}
            </a>
            <span v-else class="text-xs text-theme-tertiary italic">（无原文链接）</span>
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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { logger } from '../utils/logger.js'
import { emit as busEmit } from '../composables/useEventBus.js'

const props = defineProps({
  initialItems: { type: Array, default: () => [] }
})

const items        = ref(props.initialItems)
const total        = ref(0)
const loading      = ref(false)
const isRefreshing = ref(false)
const showRefreshed = ref(false)
const refreshMsg   = ref('')
const listEl       = ref(null)
const refreshTimer  = ref(null)
const forceRefreshCounter = ref(0)
const lastRefreshTime = ref(null)

// ── 舆情情感数据 ──────────────────────────────────────────────
const sentiment = ref({
  score: 0,
  label: '中性',
  bullish_count: 0,
  bearish_count: 0,
  total_count: 0,
  keywords: [],
  timestamp: '',
})
const sentimentTimer = ref(null)

const filteredTotal = computed(() => filteredItems.value.length)

const sentimentTime = computed(() => {
  if (!sentiment.value.timestamp) return ''
  const parts = sentiment.value.timestamp.split(' ')
  return parts.length >= 2 ? parts[1].slice(0, 5) : ''
})

/** 基于关键词匹配判断单条新闻情绪 */
function getItemSentiment(item) {
  const title = (item.title || '').toLowerCase()
  const bullKw = sentiment.value.keywords.filter(k =>
    ['买入', '增持', '资金流入', '业绩', '增长', '利好', '新高', '涨停'].some(b => k.includes(b)))
  const bearKw = sentiment.value.keywords.filter(k =>
    ['风险', '资金出逃', '利空', '下跌', '亏损', '减持'].some(b => k.includes(b)))

  const bullHit = bullKw.some(k => title.includes(k.toLowerCase()) || (item.tag || '').includes(k))
  const bearHit = bearKw.some(k => title.includes(k.toLowerCase()) || (item.tag || '').includes(k))

  if (bullHit && !bearHit) return '利好'
  if (bearHit && !bullHit) return '利空'
  if (sentiment.value.score > 0.2 && bullKw.length > bearKw.length) return '偏多'
  if (sentiment.value.score < -0.2 && bearKw.length > bullKw.length) return '偏空'
  return ''
}

function sentimentBadgeClass(s) {
  if (s === '利好' || s === '偏多') return 'bg-red-500/20 text-bullish border border-red-500/30'
  if (s === '利空' || s === '偏空') return 'bg-green-500/20 text-bearish border border-green-500/30'
  return ''
}

async function fetchSentiment() {
  try {
    const res = await fetch(`/api/v1/market/sentiment/news?_t=${Date.now()}`)
    if (!res.ok) return
    const json = await res.json()
    const data = (json && json.code === 0) ? json.data : json
    if (data && data.total_count > 0) {
      sentiment.value = { ...data }
    }
  } catch (e) {
    logger.debug('[NewsFeed] sentiment fetch failed:', e.message)
  }
}

const lastRefreshLabel = computed(() => {
  if (!lastRefreshTime.value) return ''
  const diff = Date.now() - lastRefreshTime.value
  if (diff < 30000) return '刚刚更新'
  if (diff < 60000) return `${Math.floor(diff / 1000)}秒前`
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  return lastRefreshTime.value.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
})

// ── 情绪筛选 ─────────────────────────────────────────────────────────
const activeSentimentFilter = ref('all')
const sentimentFilters = [
  { label: '全部', value: 'all' },
  { label: '利好', value: 'bullish' },
  { label: '中性', value: 'neutral' },
  { label: '利空', value: 'bearish' },
]

const bullishRatio = computed(() => {
  const total = sentiment.value.total_count || 1
  return ((sentiment.value.bullish_count || 0) / total * 100).toFixed(1)
})

const bearishRatio = computed(() => {
  const total = sentiment.value.total_count || 1
  return ((sentiment.value.bearish_count || 0) / total * 100).toFixed(1)
})

const neutralRatio = computed(() => {
  const total = sentiment.value.total_count || 1
  const neutral = sentiment.value.neutral_count ||
    (total - (sentiment.value.bullish_count || 0) - (sentiment.value.bearish_count || 0))
  return ((neutral / total) * 100).toFixed(1)
})

/** 根据情绪筛选过滤新闻 */
const filteredItems = computed(() => {
  if (activeSentimentFilter.value === 'all') return items.value
  return items.value.filter(item => {
    const s = getItemSentiment(item)
    if (activeSentimentFilter.value === 'bullish') {
      return s === '利好' || s === '偏多'
    }
    if (activeSentimentFilter.value === 'bearish') {
      return s === '利空' || s === '偏空'
    }
    return s === ''
  })
})

watch(activeSentimentFilter, () => {
  currentPage.value = 1
  if (listEl.value) listEl.value.scrollTop = 0
})

// ── 分页状态 ─────────────────────────────────────────────────────────
const PAGE_SIZE  = 50
const currentPage = ref(1)

const totalPages = computed(() => Math.max(1, Math.ceil(filteredItems.value.length / PAGE_SIZE)))

const pagedItems = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return filteredItems.value.slice(start, start + PAGE_SIZE)
})

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
function formatTime(timeStr) {
  if (!timeStr) return '--:--'
  const parts = timeStr.split(' ')
  return parts.length >= 2 ? parts[1].slice(0, 5) : (timeStr.slice(0, 5))
}
function tagClass(tag) {
  if (!tag) return 'bg-theme-tertiary/30 text-theme-secondary'
  if (tag.includes('🔴') || tag.includes('突发') || tag.includes('暴跌')) return 'bg-red-500/20 text-bullish'
  if (tag.includes('📈') || tag.includes('上涨') || tag.includes('大涨')) return 'bg-orange-500/20 text-orange-400'
  if (tag.includes('📉')) return 'bg-green-500/20 text-bearish'
  if (tag.includes('🌏') || tag.includes('港股') || tag.includes('宏观')) return 'bg-blue-500/20 text-blue-400'
  if (tag.includes('💎') || tag.includes('黄金') || tag.includes('央行') || tag.includes('美联储')) return 'bg-yellow-500/20 text-yellow-400'
  if (tag.includes('🖥') || tag.includes('AI') || tag.includes('特朗普')) return 'bg-purple-500/20 text-purple-400'
  if (tag.includes('🛢') || tag.includes('原油') || tag.includes('商品')) return 'bg-amber-500/20 text-amber-400'
  return 'bg-theme-tertiary/30 text-theme-secondary'
}

// ── Modal 异步加载正文 ────────────────────────────────────────────────
async function openModal(item) {
  modalItem.value    = item
  modalContent.value = ''
  modalLoading.value = true

  try {
    const res = await fetch(`/api/v1/news/detail?url=${encodeURIComponent(item.url)}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const json = await res.json()
    const data = (json && json.code === 0) ? json.data : json
    modalContent.value = data?.content || ''
  } catch (e) {
    logger.warn('[NewsFeed] detail fetch failed:', e.message)
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
async function fetchNews(quiet = false, isTimer = false) {
  if (!quiet) isRefreshing.value = true
  try {
    if (isTimer) {
      forceRefreshCounter.value = (forceRefreshCounter.value || 0) + 1
    }
    const useForce = !quiet || (isTimer && forceRefreshCounter.value % 3 === 1)
    const url = useForce
      ? '/api/v1/news/force_refresh'
      : `/api/v1/news/flash?_t=${Date.now()}`
    const res = await fetch(url, useForce ? { method: 'POST' } : {})
    if (!res.ok) {
      let errMsg = `HTTP ${res.status}`
      try {
        const errBody = await res.json()
        const detail = errBody?.detail || {}
        if (detail.error) {
          errMsg = `抓取失败: ${detail.error}`
          if (detail.stale_count > 0) {
            refreshMsg.value = `⚠️ ${errMsg}（显示 ${detail.stale_count} 条旧数据）`
          } else {
            refreshMsg.value = `🔴 ${errMsg}`
          }
        }
      } catch (e) {
        logger.error('[NewsFeed] parse error:', e.message)
      }
      if (!useForce || !refreshMsg.value) {
        refreshMsg.value = `⚠️ ${errMsg}`
      }
      if (!quiet) { showRefreshed.value = true; setTimeout(() => { showRefreshed.value = false; refreshMsg.value = '' }, 6000) }
      return
    }
    const d = await res.json()
    const payload = d.data || d
    const incoming = payload.news || []

    if (!quiet && payload.items_stale && !incoming.length) {
      refreshMsg.value = `⚠️ 网络异常，显示 ${payload.stale_count || 0} 条旧数据`
      showRefreshed.value = true
      setTimeout(() => { showRefreshed.value = false; refreshMsg.value = '' }, 6000)
      return
    }

    if (!incoming.length) return

    const existingIds = new Set(items.value.map(it => it.id || it.title))
    const newItems = incoming.filter(it => {
      const id = it.id || it.title
      return !existingIds.has(id)
    })

    if (newItems.length) {
      const merged = [...newItems, ...items.value]
      items.value = merged
        .sort((a, b) => (b.time || '').localeCompare(a.time || ''))
        .slice(0, 200)
    }
    total.value = incoming.length
    lastRefreshTime.value = Date.now()
    currentPage.value = 1
    if (listEl.value) listEl.value.scrollTop = 0

    if (!quiet) {
      if (newItems.length > 0) {
        const sources = [...new Set(newItems.map(it => it.source))].join('、')
        refreshMsg.value = `✅ 获取到 ${newItems.length} 条新资讯（来源: ${sources}）`
      } else {
        refreshMsg.value = `✅ 当前已是最新数据`
      }
      showRefreshed.value = true
      setTimeout(() => { showRefreshed.value = false; refreshMsg.value = '' }, 4000)

      if (!quiet) busEmit('news-refreshed', { count: newItems.length, sources: [...new Set(newItems.map(it => it.source))] })
    }
  } catch (e) {
    logger.warn('[NewsFeed] fetch failed:', e.message)
    if (!quiet) refreshMsg.value = `⚠️ 抓取失败: ${e.message}`
  } finally {
    if (!quiet) isRefreshing.value = false
  }
}

async function manualRefresh() {
  logger.log('[NewsFeed] 点击刷新，发起 POST /api/v1/news/force_refresh ...')
  if (isRefreshing.value) return
  await Promise.all([fetchNews(false), fetchSentiment()])
}

function startAutoRefresh() {
  fetchNews(true)
  fetchSentiment()
  refreshTimer.value = setInterval(() => fetchNews(true, true), 2 * 60 * 1000)
  sentimentTimer.value = setInterval(() => fetchSentiment(), 60 * 1000)
}

onMounted(startAutoRefresh)
onUnmounted(() => {
  if (refreshTimer.value) clearInterval(refreshTimer.value)
  if (sentimentTimer.value) clearInterval(sentimentTimer.value)
})
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
