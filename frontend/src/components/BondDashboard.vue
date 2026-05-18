<template>
  <div class="flex flex-col h-full overflow-auto gap-2 p-3">

    <!-- ── 顶部：收益率矩阵（利率估值表）────────────────────────── -->
    <div class="terminal-panel border border-theme-secondary rounded-sm p-3 shrink-0">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs text-terminal-dim">📊 利率估值矩阵</span>
        <div class="flex items-center gap-2">
          <!-- 隐含税率图例 -->
          <span class="text-[10px] text-[var(--color-primary)]/80 flex items-center gap-1">
            <span class="w-2 h-2 rounded-full bg-[var(--color-primary)]/60"></span>
            隐含税率
          </span>
          <span class="text-[10px] text-terminal-dim">{{ matrixUpdateTime || '...' }}</span>
          <!-- 数据源警告（Mock 数据） -->
          <span
            v-if="bondDataSource === 'mock'"
            class="text-[10px] px-1.5 py-0.5 rounded-sm bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] text-[var(--color-warning)]"
            title="数据加载失败，当前显示模拟数据"
          >
            ⚠️ 模拟数据
          </span>
        </div>
      </div>

      <!-- Tab 切换：国债 / 国开 / 商A-AAA -->
      <div class="flex border-b border-theme mb-1.5">
        <button
          v-for="src in SOURCES"
          :key="src.key"
          class="flex-1 py-1 text-[10px] font-medium text-center border-b-2 transition-colors"
          :class="activeSource === src.key
            ? 'border-bullish text-bullish'
            : 'border-transparent text-terminal-dim hover:text-theme-primary'"
          @click="activeSource = src.key"
        >
          {{ src.label }}
        </button>
      </div>

      <!-- 矩阵表头：桌面端 -->
      <div class="hidden sm:grid" :style="{ gridTemplateColumns: '56px 1fr 1fr', gap: '2px' }">
        <div class="text-[10px] text-terminal-dim font-medium py-1 px-1">期限</div>
        <div class="text-[10px] text-terminal-dim font-medium py-1 px-2 text-center border-l border-theme">
          {{ SOURCES.find(s => s.key === activeSource)?.label }}
        </div>
        <div class="text-[10px] text-terminal-dim font-medium py-1 px-2 text-center border-l border-theme">基点变化</div>
      </div>
      <!-- 移动端简化表头 -->
      <div class="grid sm:hidden" :style="{ gridTemplateColumns: '48px 1fr 1fr', gap: '2px' }">
        <div class="text-[10px] text-terminal-dim font-medium py-1 px-1">期限</div>
        <div class="text-[10px] text-terminal-dim font-medium py-1 px-1 text-center border-l border-theme">收益率</div>
        <div class="text-[10px] text-terminal-dim font-medium py-1 px-1 text-center border-l border-theme">变化</div>
      </div>

      <!-- 矩阵数据行：桌面端 -->
      <div
        v-for="tenor in TENORS"
        :key="`${activeSource}-${tenor.key}`"
        class="hidden sm:grid hover:bg-theme-hover transition-colors rounded-sm cursor-pointer focus:bg-theme-hover focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
        :style="{ gridTemplateColumns: '56px 1fr 1fr', gap: '2px' }"
        tabindex="0"
        role="button"
        :aria-label="`${tenor.label}国债收益率，点击查看历史走势`"
        @click="openHistory(tenor)"
        @keydown.enter="openHistory(tenor)"
        @keydown.space.prevent="openHistory(tenor)"
      >
        <!-- 期限标签 -->
        <div class="py-1.5 px-1 flex items-center">
          <span class="text-[10px] text-terminal-dim">{{ tenor.label }}</span>
        </div>

        <!-- 当前来源收益率 + 利差/隐含税率 -->
        <div class="py-1.5 px-2 border-l border-theme flex flex-col justify-center gap-0.5">
          <div class="flex items-center gap-1.5">
            <span
              class="text-[11px] font-mono font-semibold leading-none"
              :class="getCell(tenor.key, activeSource)?.change_bps >= 0 ? 'text-bullish' : 'text-bearish'"
            >
              {{ formatYield(getCell(tenor.key, activeSource)?.yield) }}
            </span>
            <!-- 隐含税率（仅国开列） -->
            <span
              v-if="activeSource === 'cdb' && getCell(tenor.key, 'gov')?.yield && getCell(tenor.key, 'cdb')?.yield"
              class="text-[10px] px-1 py-0.5 rounded-sm bg-[var(--color-primary-bg)] border border-[var(--color-primary-border)] text-[var(--color-primary)]/90 leading-none"
              :title="`隐含税率 = (国开-国债)/国开`"
            >
              税{{ impliedTaxRate(getCell(tenor.key, 'gov')?.yield, getCell(tenor.key, 'cdb')?.yield) }}
            </span>
          </div>
          <!-- 利差标注：国开/商A-AAA 显示相对国债的利差 -->
          <span
            v-if="getCell(tenor.key, activeSource)?.spread_bps != null"
            class="text-[10px] text-terminal-dim leading-none"
          >
            {{ getCell(tenor.key, activeSource)?.spread_bps >= 0 ? '+' : '' }}{{ getCell(tenor.key, activeSource)?.spread_bps.toFixed(1) }}bp
          </span>
        </div>

        <!-- 基点变化 -->
        <div class="py-1.5 px-2 border-l border-theme flex items-center justify-between">
          <div class="flex flex-col items-end">
            <span
              class="text-[10px] font-mono"
              :class="getCell(tenor.key, activeSource)?.change_bps >= 0 ? 'text-bullish/70' : 'text-bearish/70'"
            >
              {{ formatBps(getCell(tenor.key, activeSource)?.change_bps) }}
            </span>
            <div
              class="h-0.5 rounded-full mt-0.5"
              :class="getCell(tenor.key, activeSource)?.change_bps >= 0 ? 'bg-bullish' : 'bg-bearish'"
              :style="{ width: Math.min(Math.abs(getCell(tenor.key, activeSource)?.change_bps || 0), 20) + 'px' }"
            />
          </div>
        </div>
      </div>

      <!-- 矩阵数据行：移动端简化 -->
      <div
        v-for="tenor in TENORS"
        :key="`mobile-${activeSource}-${tenor.key}`"
        class="sm:hidden grid hover:bg-theme-hover transition-colors rounded-sm cursor-pointer focus:bg-theme-hover focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
        :style="{ gridTemplateColumns: '48px 1fr 1fr', gap: '2px' }"
        tabindex="0"
        role="button"
        :aria-label="`${tenor.label}国债收益率，点击查看历史走势`"
        @click="openHistory(tenor)"
        @keydown.enter="openHistory(tenor)"
        @keydown.space.prevent="openHistory(tenor)"
      >
        <!-- 期限标签 -->
        <div class="py-1 px-1 flex items-center">
          <span class="text-[10px] text-terminal-dim">{{ tenor.label }}</span>
        </div>

        <!-- 收益率 -->
        <div class="py-1 px-1 border-l border-theme flex items-center justify-center">
          <span
            class="text-[10px] font-mono font-semibold"
            :class="getCell(tenor.key, activeSource)?.change_bps >= 0 ? 'text-bullish' : 'text-bearish'"
          >
            {{ formatYield(getCell(tenor.key, activeSource)?.yield) }}
          </span>
        </div>

        <!-- 基点变化 -->
        <div class="py-1 px-1 border-l border-theme flex items-center justify-end">
          <div class="flex flex-col items-end">
             <span
              class="text-[10px] font-mono"
              :class="getCell(tenor.key, activeSource)?.change_bps >= 0 ? 'text-bullish/70' : 'text-bearish/70'"
            >
              {{ formatBps(getCell(tenor.key, activeSource)?.change_bps) }}
            </span>
            <div
              class="h-0.5 rounded-full mt-0.5"
              :class="getCell(tenor.key, activeSource)?.change_bps >= 0 ? 'bg-bullish/40' : 'bg-bearish/40'"
              :style="{ width: Math.min(40, Math.abs(getCell(tenor.key, activeSource)?.change_bps || 0) * 4) + 'px' }"
             ></div>
          </div>
        </div>
      </div>

      <!-- 无数据骨架屏 -->
      <div v-if="!hasData" class="py-3 space-y-2">
        <div class="flex gap-2" v-for="n in 4" :key="n">
          <div class="skeleton h-6 flex-1 rounded-sm"></div>
          <div class="skeleton h-6 w-12 rounded-sm"></div>
          <div class="skeleton h-6 w-12 rounded-sm"></div>
          <div class="skeleton h-6 w-12 rounded-sm"></div>
        </div>
      </div>
    </div>

    <!-- ── 主体：左侧曲线组 + 右侧债券列表 ─────────────── -->
    <!-- 移动端：垂直堆叠，桌面端：左右布局 -->
    <div class="flex flex-col lg:flex-row gap-2 flex-1 min-h-0">

      <!-- 左侧：国债收益率曲线 + 期限利差图 -->
      <div class="flex-1 flex flex-col gap-2 min-w-0 order-2 lg:order-1">

        <!-- 收益率曲线 -->
        <div class="terminal-panel border border-theme-secondary rounded-sm p-2 md:p-3 flex flex-col" style="flex: 2;">
          <div class="flex items-center justify-between mb-1.5 shrink-0">
            <span class="text-[10px] text-terminal-dim">📈 收益率曲线</span>
            <span class="text-[10px] text-terminal-dim hidden sm:inline">{{ yieldUpdateTime || '...' }}</span>
          </div>
          <div class="flex-1 min-h-0 overflow-hidden relative" style="min-height: 120px;">
            <YieldCurveChart
              v-if="Object.keys(yieldCurve).length > 0"
              :yield-curve="yieldCurve"
              :curve1m="yieldCurve1m"
              :curve1y="yieldCurve1y"
              :update-time="yieldUpdateTime"
            />
            <div v-else class="w-full h-full flex flex-col p-3 gap-2">
              <div class="skeleton h-3 w-24 rounded-sm"></div>
              <div class="flex-1 skeleton rounded-sm"></div>
              <div class="flex gap-2">
                <div class="skeleton h-2 w-12 rounded-sm"></div>
                <div class="skeleton h-2 w-12 rounded-sm"></div>
                <div class="skeleton h-2 w-12 rounded-sm"></div>
              </div>
            </div>
          </div>
        </div>

        <!-- 10Y-2Y 期限利差走势 -->
        <div class="terminal-panel border border-theme-secondary rounded-sm p-2 md:p-3 flex flex-col" style="flex: 1; min-height: 100px;">
          <YieldSpreadChart
            :tenors10y="spreadHistory10y"
            :tenors3y="spreadHistory3y"
            :update-time="spreadUpdateTime"
            :isLoading="spreadLoading"
            :hasError="!!spreadError"
            :errorMsg="spreadError"
          />
        </div>
      </div>

      <!-- 右侧：活跃债券列表 -->
      <!-- 移动端：水平滚动卡片，桌面端：固定宽度列表 -->
      <div class="lg:w-56 shrink-0 terminal-panel border border-theme-secondary rounded-sm p-2 md:p-3 flex flex-col order-1 lg:order-2">
        <div class="flex items-center justify-between mb-1.5 shrink-0">
          <span class="text-[10px] text-terminal-dim">📋 活跃债券</span>
          <span class="text-[10px] px-1 py-0.5 rounded-sm border border-[var(--color-warning-border)] text-[var(--color-warning)]/70">LIVE</span>
        </div>
        <!-- 移动端：水平滚动，桌面端：垂直滚动 -->
        <div class="flex-1 overflow-x-auto lg:overflow-y-auto lg:overflow-x-hidden">
          <div class="flex lg:flex-col gap-2 lg:gap-0 min-w-min">
            <div
              v-for="bond in bondList"
              :key="bond.code"
              class="flex lg:flex-row flex-col items-center lg:items-stretch justify-between py-1 px-2 lg:px-0 border-b border-theme hover:bg-theme-hover transition-colors cursor-pointer shrink-0 lg:w-full w-24"
            >
              <div class="flex flex-col min-w-0 lg:flex-1">
                <span class="text-[10px] text-theme-primary truncate">{{ bond.name }}</span>
                <span class="text-[10px] text-terminal-dim hidden lg:inline">{{ bond.code }}</span>
              </div>
              <div class="flex flex-col lg:items-end items-center">
                <span class="text-[10px] font-mono text-theme-primary">{{ bond.rate }}</span>
                <span
                  class="text-[10px] font-mono"
                  :class="bond.change_bps >= 0 ? 'text-bullish/70' : 'text-bearish/70'"
                >{{ bond.change_bps >= 0 ? '+' : '' }}{{ bond.change_bps }}bp</span>
              </div>
            </div>
          </div>
          <div v-if="!bondList.length" class="text-center py-3 text-terminal-dim text-[10px]">
            暂无数据
          </div>
        </div>
      </div>

    </div>

    <!-- ── 历史分位弹窗 ───────────────────────────────── -->
    <BondHistoryModal
      :visible="historyModalVisible"
      :tenor="historyModalTenor"
      period="1Y"
      @close="historyModalVisible = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { logger } from '../utils/logger.js'
import { safeDivide } from '../utils/safeMath.js'
import YieldCurveChart from './YieldCurveChart.vue'
import YieldSpreadChart from './YieldSpreadChart.vue'
import BondHistoryModal from './BondHistoryModal.vue'
import { apiFetch } from '../utils/api.js'

// ── 常量 ──────────────────────────────────────────────────────────
const TENORS = [
  { key: '1Y',  label: '1年' },
  { key: '3Y',  label: '3年' },
  { key: '5Y',  label: '5年' },
  { key: '7Y',  label: '7年' },
  { key: '10Y', label: '10年' },
  { key: '30Y', label: '30年' },
]

const SOURCES = [
  { key: 'gov', label: '国债' },
  { key: 'cdb', label: '国开' },
  { key: 'aaa', label: '商A-AAA' },
]

// ── 状态 ──────────────────────────────────────────────────────────
const yieldMatrix     = ref({})
const matrixUpdateTime = ref('')
const bondDataSource  = ref('')  // 'akshare' | 'mock'
const yieldCurve    = ref({})
const yieldCurve1m  = ref({})
const yieldCurve1y  = ref({})
const yieldUpdateTime = ref('')
const bondList      = ref([])
const activeSource  = ref('gov')

// 历史分位弹窗
const historyModalVisible = ref(false)
const historyModalTenor  = ref('10年')  // 中文期限

// 10Y-2Y 期限利差
const spreadHistory10y   = ref([])
const spreadHistory3y    = ref([])
const spreadUpdateTime  = ref('')
const spreadLoading     = ref(false)
const spreadError       = ref('')

// ── 计算属性 ──────────────────────────────────────────────────────
const hasData = computed(() => Object.keys(yieldMatrix.value).length > 0)

function getCell(tenor, source) {
  return yieldMatrix.value[tenor]?.[source] || null
}

// 隐含税率：(国开 - 国债) / 国开 * 100%
function impliedTaxRate(govRate, cdbRate) {
  if (govRate == null || cdbRate == null) return '--'
  const tax = safeDivide(cdbRate - govRate, cdbRate, null) * 100
  if (tax == null || isNaN(tax)) return '--'
  return Number(tax.toFixed(1)) + '%'
}

function formatYield(v) {
  if (v == null || isNaN(v)) return '--'
  return Number(v).toFixed(4) + '%'
}

function formatBps(bps) {
  if (bps == null || isNaN(bps)) return '--'
  const sign = bps >= 0 ? '+' : ''
  return `${sign}${bps.toFixed(1)}bp`
}

// ── 数据抓取 ──────────────────────────────────────────────────────
const TENOR_LABEL_MAP = {
  '1年': '1Y', '2年': '2Y', '3年': '3Y',
  '5年': '5Y', '7年': '7Y', '10年': '10Y', '30年': '30Y',
}

async function fetchBondData() {
  try {
    const [bc, ba] = await Promise.all([
      apiFetch('/api/v1/bond/curve'),
      apiFetch('/api/v1/bond/active'),
    ])

    if (bc) {
      // 后端返回格式: { code: 0, data: {...}, message: 'success' }
      const data = bc.data || bc
      const govCurve   = data.yield_curve  || {}
      const commCurve = data.comm_yield   || {}
      const spreadsBps = data.spreads_bps || {}
      const updateTime = data.update_time  || ''
      bondDataSource.value   = data.source   || ''

      yieldCurve.value       = govCurve
      yieldCurve1m.value    = data.yield_curve_1m || {}
      yieldCurve1y.value    = data.yield_curve_1y || {}
      yieldUpdateTime.value = updateTime

      const matrix = {}
      for (const [label, rate] of Object.entries(govCurve)) {
        const tenorKey = TENOR_LABEL_MAP[label]
        if (!tenorKey) continue
        const govRate  = rate
        const commRate = commCurve[label]
        const spread   = spreadsBps[label]

        matrix[tenorKey] = {
          gov: { yield: govRate, change_bps: 0 },
          cdb: {
            yield:      govRate + 0.0025,
            change_bps: 0,
            spread_bps: 25,
          },
          aaa: {
            yield:      commRate ?? govRate + (spread / 10000),
            change_bps: 0,
            spread_bps: spread ?? 0,
          },
        }
      }
      yieldMatrix.value      = matrix
      matrixUpdateTime.value = updateTime
    }

    if (ba) {
      // 兼容新旧格式
      const bonds = (ba.data && ba.data.bonds) || ba.bonds || []
      bondList.value = bonds.slice(0, 12)
    }
  } catch (e) {
    logger.warn('[BondDashboard] fetch failed:', e)
  }
}

// 10Y-3Y 利差历史（取最近 252 个交易日，即 1 年）
async function fetchSpreadHistory() {
  spreadLoading.value = true
  spreadError.value   = ''
  try {
    const [data10y, data3y] = await Promise.all([
      apiFetch(`/api/v1/bond/history?tenor=${encodeURIComponent('10年')}&period=1Y`, { timeoutMs: 25000, retries: 0 }).catch(e => {
        logger.warn('[BondDashboard] 10Y history fetch failed:', e)
        return null
      }),
      apiFetch(`/api/v1/bond/history?tenor=${encodeURIComponent('3年')}&period=1Y`, { timeoutMs: 25000, retries: 0 }).catch(e => {
        logger.warn('[BondDashboard] 3Y history fetch failed:', e)
        return null
      }),
    ])
    
    // Check for timeout/network errors
    if (data10y === null && data3y === null) {
      spreadError.value = '请求超时，请检查网络连接'
    } else if (data10y === null || data3y === null) {
      spreadError.value = '部分数据加载失败，利差图可能不完整'
    }
    
    spreadHistory10y.value  = (data10y?.data?.history || data10y?.history || []).filter(d => d.yield > 0).map(d => ({ date: d.date, yield: d.yield }))
    spreadHistory3y.value   = (data3y?.data?.history || data3y?.history || []).filter(d => d.yield > 0).map(d => ({ date: d.date, yield: d.yield }))
    spreadUpdateTime.value   = data10y ? new Date().toLocaleTimeString() : ''
  } catch (e) {
    spreadError.value = e.message || '加载利差数据失败'
    logger.error('[BondDashboard] fetchSpreadHistory error:', e)
  } finally {
    spreadLoading.value = false
  }
}

// ── 交互 ──────────────────────────────────────────────────────────
function openHistory(tenor) {
  historyModalTenor.value  = tenor.label  // 如 "10年"
  historyModalVisible.value = true
}

// ── 生命周期 ──────────────────────────────────────────────────────
let timer = null

onMounted(() => {
  fetchBondData()
  fetchSpreadHistory()
  timer = setInterval(fetchBondData, 5 * 60 * 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
