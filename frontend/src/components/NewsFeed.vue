<template>
  <div class="flex flex-col min-h-0 h-full">

    <!-- ── Header ─────────────────────────────────────────────── -->
    <div class="flex items-center justify-between mb-2 shrink-0">
      <span class="text-theme-primary font-bold text-sm">📰 快讯</span>
      <div class="flex items-center gap-2">
        <!-- 刷新成功提示 -->
        <span v-if="showRefreshed && refreshMsg" class="text-bearish text-xs">
          {{ refreshMsg }}
        </span>
        <span v-else-if="lastRefreshLabel" class="text-terminal-dim text-xs">
          {{ lastRefreshLabel }}
        </span>
        <span class="text-terminal-dim text-xs">{{ filteredTotal }} 条</span>
        <!-- 手动刷新按钮 -->
        <button
          class="w-8 h-8 flex items-center justify-center rounded-sm border transition shrink-0"
          :class="isRefreshing
            ? 'border-[var(--color-warning-border)] text-[var(--color-warning)] bg-[var(--color-warning-bg)] cursor-not-allowed'
            : 'border-theme-secondary text-terminal-dim hover:border-theme-secondary hover:text-theme-primary bg-terminal-bg'"
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
        <span class="w-1.5 h-1.5 rounded-sm shrink-0"
              :class="isRefreshing ? 'bg-[var(--color-warning)]' : 'bg-[var(--color-success-light)]'"></span>
      </div>
    </div>

    <!-- ── 舆情情绪摘要栏（增强版）─────────────────────────── -->
    <div v-if="sentiment.total_count > 0" class="mb-2 shrink-0 space-y-2"
    >
      <!-- 情绪概览：移动端紧凑布局 -->
      <div class="flex items-center gap-1.5 md:gap-3 px-2 py-1.5 rounded-sm border transition flex-wrap"
           :class="sentiment.score > 0.1
             ? 'border-bullish/30 bg-theme-secondary/30'
             : sentiment.score < -0.1
               ? 'border-bearish/30 bg-theme-secondary/30'
               : 'border-theme-secondary bg-theme-tertiary/5'"
      >
        <span class="text-xs font-bold px-2 py-1 rounded-sm shrink-0"
              :class="sentiment.score > 0.1
                ? 'bg-bullish/20 text-bullish'
                : sentiment.score < -0.1
                  ? 'bg-bearish/20 text-bearish'
                  : 'bg-theme-tertiary/20 text-theme-secondary'"
        >
          {{ sentiment.label }}
        </span>
        <span class="text-xs text-terminal-dim shrink-0">
          {{ sentiment.bullish_count }}🔴:{{ sentiment.bearish_count }}🟢
        </span>
        <div class="flex-1 flex gap-1 overflow-x-auto ml-1 md:ml-2 scrollbar-hide min-w-0">
          <span v-for="kw in sentiment.keywords.slice(0, 3)" :key="kw"
                class="shrink-0 text-xs px-1 py-0.5 rounded-sm bg-theme-tertiary/15 text-theme-tertiary whitespace-nowrap"
          >
            {{ kw }}
          </span>
        </div>
        <span class="text-xs text-terminal-dim/50 shrink-0 hidden sm:inline">{{ sentimentTime }}</span>
      </div>

      <!-- 情绪分布条形图：移动端隐藏，节省空间 -->
      <div class="hidden sm:block px-2 py-1.5 rounded-sm border border-theme-secondary bg-terminal-panel/50"
      >
        <div class="flex items-center justify-between mb-1"
        >
          <span class="text-xs text-terminal-dim"
          >情绪分布</span>
          <span class="text-xs text-terminal-dim"
          >共 {{ sentiment.total_count }} 条</span>
        </div>
        <div class="h-2 rounded-sm overflow-hidden flex"
        >
          <div class="h-full bg-bullish/60 transition-all"
               :style="{ width: bullishRatio + '%' }"
               title="看涨"
          />
          <div class="h-full bg-theme-tertiary/30 transition-all"
               :style="{ width: neutralRatio + '%' }"
               title="中性"
          />
          <div class="h-full bg-bearish/60 transition-all"
               :style="{ width: bearishRatio + '%' }"
               title="看跌"
          />
        </div>
        <div class="flex justify-between mt-1"
        >
          <span class="text-xs text-bullish"
          >{{ sentiment.bullish_count }} 看涨</span>
          <span class="text-xs text-theme-tertiary"
          >{{ sentiment.neutral_count || 0 }} 中性</span>
          <span class="text-xs text-bearish"
          >{{ sentiment.bearish_count }} 看跌</span>
        </div>
      </div>

      <!-- 热门资讯排行 -->
      <div v-if="hotNews.length > 0" class="px-2 py-1.5 rounded-sm border border-theme-secondary bg-terminal-panel/50"
      >
        <div class="flex items-center justify-between mb-1"
        >
          <span class="text-xs text-terminal-dim font-bold"
          >🔥 热门资讯</span
          >
          <span class="text-xs text-terminal-dim"
          >{{ hotNews.length }} 条</span
          >
        </div
        >
        <div class="flex gap-1 overflow-x-auto scrollbar-hide"
        >
          <button
            v-for="(item, idx) in hotNews.slice(0, 5)"
            :key="item.id || item.title"
            class="shrink-0 text-xs px-2 py-1 rounded-sm border transition text-left max-w-[140px] truncate"
            :class="modalItem?.id === item.id
              ? 'bg-theme-hover border-theme-secondary text-theme-primary'
              : 'bg-terminal-bg border-theme-secondary text-theme-primary hover:border-theme-secondary'"
            @click="openModal(item)"
            :title="item.title"
          >
            <span class="text-theme-primary font-bold"
            >{{ idx + 1 }}.</span
            > {{ item.title }}
          </button
          >
        </div
        >
      </div
      >

      <!-- 分类筛选标签 -->
      <div class="flex gap-1 px-2 flex-wrap mb-1"
      >
        <button
          v-for="cat in categories"
          :key="cat.value"
          class="text-xs px-1.5 md:px-3 py-1.5 rounded-sm border transition flex items-center gap-0.5"
          :class="activeCategory === cat.value
            ? 'bg-theme-hover border-theme-secondary text-theme-primary'
            : 'bg-terminal-bg border-theme-secondary text-theme-tertiary hover:text-theme-primary'"
          @click="activeCategory = cat.value"
        >
          <span>{{ cat.icon }}</span>
          <span>{{ cat.label }}</span>
          <span v-if="cat.value !== 'all'" class="text-xs opacity-60">({{ categoryCount(cat.value) }})</span>
        </button>
      </div>

      <!-- 情绪筛选标签：移动端紧凑 -->
      <div class="flex gap-1 px-2 flex-wrap"
      >
        <button
          v-for="filter in sentimentFilters"
          :key="filter.value"
          class="text-xs px-1.5 md:px-3 py-1.5 rounded-sm border transition"
          :class="activeSentimentFilter === filter.value
            ? 'bg-theme-hover border-theme-secondary text-theme-primary'
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
      <div class="space-y-2">
        <div
          v-for="item in pagedItems"
          :key="item.id || item.title"
          class="bg-terminal-bg rounded-sm border border-theme p-3 hover:border-theme-secondary transition-colors cursor-pointer"
          @click="openModal(item)"
        >
          <div class="flex items-start gap-2">
            <span class="shrink-0 text-xs px-2 py-1 rounded-sm"
                  :class="tagClass(item.tag)">
              {{ item.tag }}
            </span>
            <!-- 热门标记 -->
            <span v-if="hotNews.slice(0, 5).some(h => h.id === item.id)" class="shrink-0 text-xs px-1 py-0.5 rounded-sm bg-theme-tertiary/20 text-theme-tertiary font-bold"
            >HOT
            </span>
            <!-- 时间 -->
            <span class="shrink-0 text-xs text-theme-tertiary w-12 text-right">{{ formatTime(item.time) }}</span>
            <!-- 标题 + 来源 -->
            <div class="flex-1 min-w-0">
              <p class="text-xs text-theme-primary leading-snug line-clamp-2">{{ item.title }}</p>
              <span class="text-terminal-dim/50 text-xs">{{ item.source }}</span>
            </div>
            <!-- 情绪徽章 -->
            <span v-if="getItemSentiment(item)" class="shrink-0 text-xs px-2 py-1 rounded-sm font-medium"
                  :class="sentimentBadgeClass(getItemSentiment(item))">
              {{ getItemSentiment(item) }}
            </span>
          </div>
        </div>
        <!-- 骨架屏 -->
        <div v-if="isRefreshing && !pagedItems.length" class="space-y-2">
          <div v-for="i in 5" :key="i" class="flex items-start gap-2">
            <div class="w-8 h-4 rounded-sm bg-terminal-panel"></div>
            <div class="flex-1 space-y-1">
              <div class="h-4 rounded-sm bg-terminal-panel w-3/4"></div>
              <div class="h-3 rounded-sm bg-terminal-panel w-1/2"></div>
            </div>
          </div>
        </div>
        <div v-else-if="!pagedItems.length" class="text-center py-8 text-terminal-dim text-xs">
          {{ activeCategory === 'all' && activeSentimentFilter === 'all' ? '暂无快讯数据' : '暂无符合筛选条件的快讯' }}
        </div>
      </div>
    </div>

    <!-- ── 分页控制器 ─────────────────────────────────────────── -->
    <div v-if="totalPages > 1" class="flex items-center justify-center gap-3 mt-2 shrink-0">
      <button
        class="px-3 py-1.5 text-xs rounded-sm border transition"
        :class="currentPage === 1
          ? 'bg-theme-tertiary border-theme-secondary text-theme-tertiary cursor-not-allowed'
          : 'bg-terminal-bg border-theme-secondary text-theme-primary hover:border-theme-secondary'"
        :disabled="currentPage === 1"
        @click="prevPage">
        ‹
      </button>
      <button
        v-for="p in visiblePages"
        :key="p"
        class="px-3 py-1.5 text-xs rounded-sm border transition"
        :class="p === currentPage
          ? 'bg-theme-hover border-theme-secondary text-theme-primary'
          : 'bg-terminal-bg border-theme-secondary text-theme-primary hover:border-theme-secondary'"
        @click="goToPage(p)">
        {{ p }}
      </button>
      <button
        class="px-3 py-1.5 text-xs rounded-sm border transition"
        :class="currentPage === totalPages
          ? 'bg-theme-tertiary border-theme-secondary text-theme-tertiary cursor-not-allowed'
          : 'bg-terminal-bg border-theme-secondary text-theme-primary hover:border-theme-secondary'"
        :disabled="currentPage === totalPages"
        @click="nextPage">
        ›
      </button>
      <span class="text-terminal-dim text-xs ml-1">{{ currentPage }}/{{ totalPages }}</span>
    </div>

    <!-- ── 详情 Modal ─────────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="modalItem"
           class="fixed inset-0 z-50 flex items-center justify-center p-4"
           @click.self="closeModal">
        <div class="absolute inset-0 bg-black/60"></div>
        <div class="relative z-10 w-full max-w-2xl max-h-[80vh] flex flex-col
                    bg-[var(--bg-primary)] border border-theme-secondary rounded-sm shadow-sm overflow-hidden">
          <div class="flex items-start justify-between p-4 border-b border-theme shrink-0">
            <div class="flex-1 pr-4">
              <div class="flex items-center gap-3 mb-2 flex-wrap">
                <span class="text-xs px-3 py-1.5 rounded-sm" :class="tagClass(modalItem.tag)">
                  {{ modalItem.tag }}
                </span>
                <span class="text-terminal-dim text-xs">{{ modalItem.time }}</span>
                <span class="text-terminal-dim/50 text-xs">{{ modalItem.source }}</span>
              </div>
              <h2 class="text-sm font-medium text-theme-primary leading-snug">{{ modalItem.title }}</h2>
            </div>
            <button
              class="shrink-0 w-8 h-8 flex items-center justify-center rounded-sm
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
               class="text-xs text-[var(--color-info)] hover:text-[var(--color-info-light)] underline hover:no-underline transition">
              🔗 {{ modalItem.url }}
            </a>
            <span v-else class="text-xs text-theme-tertiary italic">（无原文链接）</span>
            <button
              class="ml-4 px-3 py-1 text-xs rounded-sm bg-[var(--color-info)] hover:bg-[var(--color-info-hover)] text-theme-primary transition shrink-0"
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
  if (s === '利好' || s === '偏多') return 'bg-[var(--color-danger-bg)] text-bullish border border-[var(--color-danger-border)]'
  if (s === '利空' || s === '偏空') return 'bg-[var(--color-success-bg)] text-bearish border border-[var(--color-success-border)]'
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

// ── 新闻分类 ─────────────────────────────────────────────────────────
const activeCategory = ref('all')
const categories = [
  { label: '全部', value: 'all', icon: '📰' },
  { label: '宏观', value: 'macro', icon: '🌍' },
  { label: '股市', value: 'stock', icon: '📈' },
  { label: '行业', value: 'industry', icon: '🏭' },
  { label: '债券', value: 'bond', icon: '📉' },
]

const categoryKeywords = {
  macro: ['GDP', 'CPI', 'PPI', 'PMI', '央行', '美联储', '货币政策', '财政政策', '降准', '降息', '利率', '通胀', '通缩', '经济', '宏观'],
  stock: ['A股', '沪深', '涨停', '跌停', '板块', '个股', '指数', '上证', '深证', '创业板', '科创板', '北交所', '成交量', '市值'],
  industry: ['新能源', '半导体', '芯片', '医药', '医疗', '消费', '汽车', '房地产', '基建', '光伏', '锂电', 'AI', '人工智能', '机器人', '5G', '通信'],
  bond: ['国债', '利率债', '信用债', '城投', '可转债', '债券', '收益率', '利差', '久期', '凸性', '回购', 'SHIBOR'],
}

function classifyNews(item) {
  const title = (item.title || '').toLowerCase()
  const tag = (item.tag || '').toLowerCase()
  const text = title + ' ' + tag
  
  for (const [category, keywords] of Object.entries(categoryKeywords)) {
    if (keywords.some(kw => text.includes(kw.toLowerCase()))) {
      return category
    }
  }
  return 'other'
}

function getCategoryLabel(category) {
  const cat = categories.find(c => c.value === category)
  return cat ? cat.label : '其他'
}

function getCategoryIcon(category) {
  const cat = categories.find(c => c.value === category)
  return cat ? cat.icon : '📄'
}

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

/** 根据分类和情绪筛选过滤新闻 */
const filteredItems = computed(() => {
  let result = items.value
  
  // 分类筛选
  if (activeCategory.value !== 'all') {
    result = result.filter(item => classifyNews(item) === activeCategory.value)
  }
  
  // 情绪筛选
  if (activeSentimentFilter.value !== 'all') {
    result = result.filter(item => {
      const s = getItemSentiment(item)
      if (activeSentimentFilter.value === 'bullish') {
        return s === '利好' || s === '偏多'
      }
      if (activeSentimentFilter.value === 'bearish') {
        return s === '利空' || s === '偏空'
      }
      return s === ''
    })
  }
  
  return result
})

watch(activeSentimentFilter, () => {
  currentPage.value = 1
  if (listEl.value) listEl.value.scrollTop = 0
})

watch(activeCategory, () => {
  currentPage.value = 1
  if (listEl.value) listEl.value.scrollTop = 0
})

function categoryCount(category) {
  return items.value.filter(item => classifyNews(item) === category).length
}

// ── 热门资讯排行 ──────────────────────────────────────────────────────
const hotNews = computed(() => {
  // 根据情绪强度和重要性排序
  return [...items.value]
    .map(item => {
      const sentiment = getItemSentiment(item)
      const category = classifyNews(item)
      let score = 0
      
      // 情绪强度加分
      if (sentiment === '利好' || sentiment === '利空') score += 3
      else if (sentiment === '偏多' || sentiment === '偏空') score += 2
      
      // 重要标签加分
      const tag = (item.tag || '').toLowerCase()
      if (tag.includes('突发') || tag.includes('🔴')) score += 5
      if (tag.includes('📈') || tag.includes('📉')) score += 2
      
      // 宏观新闻加分
      if (category === 'macro') score += 1
      
      // 时间越近越重要
      const timeStr = item.time || ''
      if (timeStr.includes(':')) {
        const parts = timeStr.split(' ')
        if (parts.length >= 2) {
          const time = parts[1]
          const hour = parseInt(time.split(':')[0])
          if (hour >= 9 && hour <= 15) score += 1  // 交易时间
        }
      }
      
      return { ...item, hotScore: score }
    })
    .sort((a, b) => b.hotScore - a.hotScore)
    .filter(item => item.hotScore > 0)
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
  if (tag.includes('🔴') || tag.includes('突发') || tag.includes('暴跌')) return 'bg-[var(--color-danger-bg)] text-bullish'
  if (tag.includes('📈') || tag.includes('上涨') || tag.includes('大涨')) return 'bg-[var(--color-warning-bg)] text-[var(--color-warning)]'
  if (tag.includes('📉')) return 'bg-[var(--color-success-bg)] text-bearish'
  if (tag.includes('🌏') || tag.includes('港股') || tag.includes('宏观')) return 'bg-[var(--color-info-bg)] text-[var(--color-info)]'
  if (tag.includes('💎') || tag.includes('黄金') || tag.includes('央行') || tag.includes('美联储')) return 'bg-[var(--color-warning-bg)] text-[var(--color-warning)]'
  if (tag.includes('🖥') || tag.includes('AI') || tag.includes('特朗普')) return 'bg-[var(--color-primary-bg)] text-[var(--color-primary)]'
  if (tag.includes('🛢') || tag.includes('原油') || tag.includes('商品')) return 'bg-[var(--color-warning-bg)] text-[var(--color-warning)]'
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
.line-clamp-3 {
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
