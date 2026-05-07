<template>
  <div class="flex flex-col min-h-0 h-full overflow-hidden">

    <!-- ── Header ─────────────────────────────────────────────── -->
    <div class="flex items-center justify-between mb-2 shrink-0 flex-wrap gap-1">
      <div class="flex items-center gap-2">
        <span class="text-theme-primary font-semibold text-sm">快讯</span>
        <span class="text-[10px] text-terminal-dim/60 px-1.5 py-0.5 rounded-sm bg-theme-tertiary/10">
          {{ filteredTotal }} 条
        </span>
      </div>
      <div class="flex items-center gap-2">
        <!-- 刷新状态提示 -->
        <span v-if="showRefreshed && refreshMsg" 
              class="text-[10px] px-2 py-0.5 rounded-sm bg-bearish/10 text-bearish"
              :class="refreshMsg.includes('⚠️') ? 'bg-theme-accent/10 text-theme-accent' : ''"
        >
          {{ refreshMsg }}
        </span>
        <span v-else-if="lastRefreshLabel" class="text-[10px] text-terminal-dim/50">
          {{ lastRefreshLabel }}
        </span>
        <!-- 手动刷新按钮 -->
        <button
          class="w-7 h-7 flex items-center justify-center rounded-sm border transition shrink-0"
          :class="isRefreshing
            ? 'border-theme-accent/40 text-theme-accent bg-theme-accent/10 cursor-not-allowed'
            : 'border-theme-secondary text-terminal-dim hover:text-theme-primary hover:border-theme-secondary bg-terminal-bg'"
          :disabled="isRefreshing"
          @click="manualRefresh"
          title="刷新快讯"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"
               class="w-3.5 h-3.5 transition-all"
               :class="isRefreshing ? 'animate-spin' : ''">
            <path fill-rule="evenodd" d="M4.755 10.059a7.5 7.5 0 0110.138-5.133A7.501 7.501 0 1019.8 13.71a7 7 0 01-14.046 3.293l-1.207.855.002.001zm-.9 1.865l1.207-.856a7.501 7.501 0 0112.237-4.384A7.5 7.5 0 014.26 17.32l-1.15.67.001-.001zm3.163-3.018l.708 1.228a9 9 0 0010.725 3.658l.578-1.117-1.414.818a7.5 7.5 0 01-10.596-2.93zM12 2.25a.75.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0V3a.75.75 0 01.75-.75zM5.166 6.036a8.963 8.963 0 0111.668.156 8.964 8.964 0 01-11.668-.156z" clip-rule="evenodd" />
          </svg>
        </button>
        <span class="w-1.5 h-1.5 rounded-full shrink-0"
              :class="isRefreshing ? 'bg-theme-accent' : 'bg-bearish'"
              title="数据状态"
        ></span>
      </div>
    </div>

    
    <!-- ── 顶部控制 & 数据摘要栏 ─────────────────────────── -->
    <div class="mb-2 shrink-0 flex flex-col gap-1.5">
      
      <!-- 第一行：情绪概览 (移动端单行滚动) -->
      <div v-if="sentiment.total_count > 0" 
           class="flex items-center gap-2 px-2 py-1 rounded-sm border transition overflow-x-auto scrollbar-hide whitespace-nowrap"
           :class="sentiment.score > 0.1
             ? 'border-bearish/30 bg-bearish/5'
             : sentiment.score < -0.1
               ? 'border-bullish/30 bg-bullish/5'
               : 'border-theme-secondary bg-theme-tertiary/5'"
      >
        <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-sm shrink-0"
              :class="sentiment.score > 0.1
                ? 'bg-bearish/15 text-bearish'
                : sentiment.score < -0.1
                  ? 'bg-bullish/15 text-bullish'
                  : 'bg-theme-tertiary/20 text-theme-secondary'"
        >
          {{ sentiment.label }}
        </span>
        <div class="flex items-center gap-1 shrink-0">
          <span class="text-[10px] text-bearish font-medium">{{ sentiment.bullish_count }}</span>
          <span class="text-[10px] text-theme-tertiary">:</span>
          <span class="text-[10px] text-bullish font-medium">{{ sentiment.bearish_count }}</span>
        </div>
        <div class="flex items-center gap-1 shrink-0 ml-1">
          <span v-for="kw in sentiment.keywords.slice(0, 3)" :key="kw"
                class="text-[10px] px-1 py-0.5 rounded-sm bg-theme-tertiary/10 text-theme-tertiary"
          >
            {{ kw }}
          </span>
        </div>
      </div>

      <!-- 第二行：热门资讯 (单行滚动) -->
      <div v-if="hotNews.length > 0" class="flex items-center gap-1.5 overflow-x-auto scrollbar-hide whitespace-nowrap">
        <span class="text-[10px] text-terminal-dim/70 font-medium shrink-0 bg-theme-tertiary/10 px-1.5 py-1 rounded-sm">HOT</span>
        <button
          v-for="(item, idx) in hotNews.slice(0, 5)"
          :key="item.id || item.title"
          class="shrink-0 text-[10px] px-2 py-1 rounded-sm border transition text-left max-w-[140px] truncate"
          :class="modalItem?.id === item.id
            ? 'bg-theme-hover border-theme-secondary text-theme-primary'
            : 'bg-terminal-bg border-theme-secondary text-theme-primary hover:border-theme-secondary'"
          @click="openModal(item)"
          :title="item.title"
        >
          <span class="text-theme-primary/60 mr-0.5">{{ idx + 1 }}.</span>{{ item.title }}
        </button>
      </div>

      <!-- 第三行：分类与情绪筛选 (单行横向滚动，不换行) -->
      <div class="flex items-center gap-1 overflow-x-auto scrollbar-hide whitespace-nowrap pb-0.5">
        <button
          v-for="cat in categories"
          :key="cat.value"
          class="text-[10px] px-2 py-1 rounded-sm border transition shrink-0 flex items-center gap-0.5"
          :class="activeCategory === cat.value
            ? 'bg-theme-hover border-theme-secondary text-theme-primary'
            : 'bg-terminal-bg border-theme-secondary text-theme-tertiary hover:text-theme-primary'"
          @click="activeCategory = cat.value"
        >
          <span>{{ cat.label }}</span>
          <span v-if="cat.value !== 'all'" class="opacity-50 text-[9px]">({{ categoryCount(cat.value) }})</span>
        </button>
        <div class="w-px h-3 bg-theme-secondary mx-0.5 shrink-0"></div>
        <button
          v-for="filter in sentimentFilters"
          :key="filter.value"
          class="text-[10px] px-2 py-1 rounded-sm border transition shrink-0"
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
      class="flex-1 overflow-y-auto mt-2 min-h-[200px] md:min-h-[300px]"
    >
      <div class="flex flex-col">
        <div
          v-for="item in pagedItems"
          :key="item.id || item.title"
          class="group flex flex-col gap-1 py-1.5 px-2 -mx-2 border-b border-theme-secondary hover:bg-theme-hover/30 transition-colors cursor-pointer"
          @click="openModal(item)"
        >
          <!-- 第一行：时间 + 标签 + 情绪 + 来源 -->
          <div class="flex items-center gap-1.5">
            <span class="text-[11px] text-theme-tertiary font-mono w-10 shrink-0">{{ formatTime(item.time) }}</span>
            <span v-if="item.tag" class="text-[10px] px-1 py-0.5 rounded-sm font-medium shrink-0" :class="tagClass(item.tag)">
              {{ item.tag }}
            </span>
            <span v-if="getItemSentiment(item)" class="text-[10px] px-1 py-0.5 rounded-sm font-medium shrink-0"
                  :class="sentimentBadgeClass(getItemSentiment(item))">
              {{ getItemSentiment(item) }}
            </span>
            <div class="flex-1"></div>
            <span class="text-[11px] text-terminal-dim/60 shrink-0">{{ item.source }}</span>
          </div>
          <!-- 第二行：标题 -->
          <p class="text-[13px] text-theme-primary leading-snug group-hover:text-theme-accent transition-colors line-clamp-2">
            {{ item.title }}
          </p>
        </div>
        <!-- 骨架屏 -->
        <div v-if="isRefreshing && !pagedItems.length" class="flex flex-col">
          <div v-for="i in 5" :key="i" class="py-3 px-2 -mx-2 border-b border-theme-secondary">
            <div class="flex items-center gap-2 mb-2">
              <div class="w-10 h-3.5 rounded-sm bg-terminal-panel"></div>
              <div class="w-12 h-3 rounded-sm bg-terminal-panel"></div>
            </div>
            <div class="h-4 rounded-sm bg-terminal-panel w-full mb-1.5"></div>
            <div class="h-4 rounded-sm bg-terminal-panel w-2/3"></div>
          </div>
        </div>
        <div v-else-if="!pagedItems.length" class="text-center py-12 text-theme-tertiary text-sm">
          暂无符合条件的快讯
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
        <div class="absolute inset-0 bg-black/70"></div>
        <div class="relative z-10 w-full max-w-2xl max-h-[85vh] flex flex-col
                    bg-[var(--bg-primary)] border border-theme-secondary rounded-sm shadow-lg overflow-hidden">
          <!-- Modal Header -->
          <div class="flex items-start justify-between p-4 border-b border-theme shrink-0 bg-theme-hover/20">
            <div class="flex-1 pr-4 min-w-0">
              <div class="flex items-center gap-2 mb-2 flex-wrap">
                <span class="text-[10px] px-2 py-0.5 rounded-sm font-medium" :class="tagClass(modalItem.tag)">
                  {{ modalItem.tag }}
                </span>
                <span class="text-[10px] text-theme-tertiary font-mono">{{ modalItem.time }}</span>
                <span class="text-[10px] text-terminal-dim/60">{{ modalItem.source }}</span>
                <span v-if="getItemSentiment(modalItem)" 
                      class="text-[10px] px-1.5 py-0.5 rounded-sm font-medium"
                      :class="sentimentBadgeClass(getItemSentiment(modalItem))">
                  {{ getItemSentiment(modalItem) }}
                </span>
              </div>
              <h2 class="text-sm font-semibold text-theme-primary leading-snug">{{ modalItem.title }}</h2>
            </div>
            <button
              class="shrink-0 w-7 h-7 flex items-center justify-center rounded-sm
                     bg-theme-tertiary/30 hover:bg-theme-tertiary/50 text-theme-tertiary hover:text-theme-primary transition"
              @click="closeModal">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-4 h-4">
                <path fill-rule="evenodd" d="M5.47 5.47a.75.75 0 011.06 0L12 10.94l5.47-5.47a.75.75 0 111.06 1.06L13.06 12l5.47 5.47a.75.75 0 11-1.06 1.06L12 13.06l-5.47 5.47a.75.75 0 01-1.06-1.06L10.94 12 5.47 6.53a.75.75 0 010-1.06z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>
          <!-- Modal Body -->
          <div class="flex-1 overflow-y-auto p-4">
            <div v-if="modalLoading" class="flex items-center gap-2 text-xs text-terminal-dim italic">
              <svg class="animate-spin w-3.5 h-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              正文加载中...
            </div>
            <p v-else-if="modalContent" class="text-xs text-theme-primary leading-relaxed whitespace-pre-wrap">
              {{ modalContent }}
            </p>
            <div v-else class="text-xs text-theme-tertiary italic text-center py-8">
              <div class="mb-2 text-2xl opacity-20">📄</div>
              暂无正文内容
            </div>
          </div>
          <!-- Modal Footer -->
          <div class="p-3 border-t border-theme shrink-0 flex justify-between items-center bg-theme-hover/10">
            <a v-if="modalItem.url"
               :href="modalItem.url" target="_blank" rel="noopener"
               class="text-[11px] text-theme-accent hover:text-theme-primary underline hover:no-underline transition truncate max-w-[60%]">
              {{ modalItem.url }}
            </a>
            <span v-else class="text-[11px] text-theme-tertiary italic">无原文链接</span>
            <a
              v-if="modalItem.url"
              :href="modalItem.url"
              target="_blank"
              rel="noopener noreferrer"
              class="ml-4 px-3 py-1.5 text-[11px] rounded-sm bg-theme-accent/10 hover:bg-theme-accent/20 
                     text-theme-accent border border-theme-accent/20 transition shrink-0 inline-block no-underline"
            >
              浏览器打开
            </a>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useBreakpoints, breakpointsTailwind } from '@vueuse/core'
import { logger } from '../utils/logger.js'
import { emit as busEmit } from '../composables/useEventBus.js'

// 响应式断点检测
const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('md')  // < 768px 为手机端

const props = defineProps({
  initialItems: { type: Array, default: () => [] }
})

const items        = ref(props.initialItems)
const total        = ref(0)
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
  { label: '全部', value: 'all' },
  { label: '宏观', value: 'macro' },
  { label: '股市', value: 'stock' },
  { label: '行业', value: 'industry' },
  { label: '债券', value: 'bond' },
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
      if (tag.includes('突发') || tag.includes('重要') || tag.includes('紧急')) score += 5
      if (tag.includes('公告') || tag.includes('通知')) score += 3
      
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
// 手机端每页10条，桌面端每页50条
const PAGE_SIZE = computed(() => isMobile.value ? 10 : 50)
const currentPage = ref(1)

const totalPages = computed(() => Math.max(1, Math.ceil(filteredItems.value.length / PAGE_SIZE.value)))

const pagedItems = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE.value
  return filteredItems.value.slice(start, start + PAGE_SIZE.value)
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
  if (!tag) return 'bg-theme-tertiary/20 text-theme-tertiary'
  const t = tag.toLowerCase()
  
  if (t.includes('突发') || t.includes('重要') || t.includes('紧急') || t.includes('公告')) {
    return 'bg-bullish/15 text-bullish'
  }
  if (t.includes('上涨') || t.includes('大涨') || t.includes('涨停') || t.includes('利好') || t.includes('突破')) {
    return 'bg-bullish/15 text-bullish'
  }
  if (t.includes('下跌') || t.includes('大跌') || t.includes('跌停') || t.includes('利空') || t.includes('跳水')) {
    return 'bg-bearish/15 text-bearish'
  }
  if (t.includes('宏观') || t.includes('政策') || t.includes('央行') || t.includes('美联储') || t.includes('降准') || t.includes('降息')) {
    return 'bg-theme-tertiary/20 text-theme-secondary'
  }
  if (t.includes('行业') || t.includes('板块') || t.includes('概念') || t.includes('题材')) {
    return 'bg-theme-tertiary/20 text-theme-secondary'
  }
  if (t.includes('港股') || t.includes('美股') || t.includes('外围') || t.includes('全球')) {
    return 'bg-theme-tertiary/20 text-theme-secondary'
  }
  if (t.includes('原油') || t.includes('黄金') || t.includes('商品') || t.includes('期货')) {
    return 'bg-theme-tertiary/20 text-theme-secondary'
  }
  return 'bg-theme-tertiary/20 text-theme-tertiary'
}

function sentimentBadgeClass(s) {
  if (s === '利好' || s === '偏多') return 'bg-bullish/10 text-bullish border border-bullish/20'
  if (s === '利空' || s === '偏空') return 'bg-bearish/10 text-bearish border border-bearish/20'
  return 'bg-theme-tertiary/10 text-theme-tertiary border border-theme-tertiary/20'
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
            refreshMsg.value = `${errMsg}（显示 ${detail.stale_count} 条旧数据）`
          } else {
            refreshMsg.value = `${errMsg}`
          }
        }
      } catch (e) {
        logger.error('[NewsFeed] parse error:', e.message)
      }
      if (!useForce || !refreshMsg.value) {
        refreshMsg.value = `${errMsg}`
      }
      if (!quiet) { showRefreshed.value = true; setTimeout(() => { showRefreshed.value = false; refreshMsg.value = '' }, 6000) }
      return
    }
    const d = await res.json()
    const payload = d.data || d
    const incoming = payload.news || []

    if (!quiet && payload.items_stale && !incoming.length) {
      refreshMsg.value = `网络异常，显示 ${payload.stale_count || 0} 条旧数据`
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
        refreshMsg.value = `获取到 ${newItems.length} 条新资讯（来源: ${sources}）`
      } else {
        refreshMsg.value = `当前已是最新数据`
      }
      showRefreshed.value = true
      setTimeout(() => { showRefreshed.value = false; refreshMsg.value = '' }, 4000)

      if (!quiet) busEmit('news-refreshed', { count: newItems.length, sources: [...new Set(newItems.map(it => it.source))] })
    }
  } catch (e) {
    logger.warn('[NewsFeed] fetch failed:', e.message)
    if (!quiet) refreshMsg.value = `抓取失败: ${e.message}`
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
