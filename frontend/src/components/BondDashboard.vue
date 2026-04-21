<template>
  <div class="flex flex-col h-full overflow-auto gap-2 p-3">

    <!-- ── 顶部：收益率矩阵（利率估值表）────────────────────────── -->
    <div class="terminal-panel border border-theme-secondary rounded p-3 shrink-0">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs text-terminal-dim">📊 利率估值矩阵</span>
        <div class="flex items-center gap-2">
          <!-- 隐含税率图例 -->
          <span class="text-[9px] text-purple-400/80 flex items-center gap-1">
            <span class="w-2 h-2 rounded-full bg-purple-500/60"></span>
            隐含税率
          </span>
          <span class="text-[9px] text-terminal-dim">{{ matrixUpdateTime || '...' }}</span>
          <!-- 数据源警告（Mock 数据） -->
          <span
            v-if="bondDataSource === 'mock'"
            class="text-[9px] px-1.5 py-0.5 rounded bg-yellow-500/20 border border-yellow-500/40 text-yellow-400"
            title="AkShare 债券数据已停更，数据截至 2021-01-22"
          >
            ⚠️ 数据截至 2021
          </span>
        </div>
      </div>

      <!-- Tab 切换：国债 / 国开 / 商A-AAA -->
      <div class="flex border-b border-theme mb-1.5">
        <button
          v-for="src in SOURCES"
          :key="src.key"
          class="flex-1 py-1 text-[9px] font-medium text-center border-b-2 transition-colors"
          :class="activeSource === src.key
            ? 'border-bullish text-bullish'
            : 'border-transparent text-terminal-dim hover:text-theme-primary'"
          @click="activeSource = src.key"
        >
          {{ src.label }}
        </button>
      </div>

      <!-- 矩阵表头 -->
      <div class="grid" :style="{ gridTemplateColumns: '64px 1fr 1fr', gap: '2px' }">
        <div class="text-[9px] text-terminal-dim font-medium py-1 px-1">期限</div>
        <div class="text-[9px] text-terminal-dim font-medium py-1 px-2 text-center border-l border-theme">
          {{ SOURCES.find(s => s.key === activeSource)?.label }}
        </div>
        <div class="text-[9px] text-terminal-dim font-medium py-1 px-2 text-center border-l border-theme">基点变化</div>
      </div>

      <!-- 矩阵数据行 -->
      <div
        v-for="tenor in TENORS"
        :key="`${activeSource}-${tenor.key}`"
        class="grid hover:bg-white/5 transition-colors rounded cursor-pointer"
        :style="{ gridTemplateColumns: '64px 1fr 1fr', gap: '2px' }"
        @click="openHistory(tenor)"
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
              class="text-[9px] px-1 py-0.5 rounded bg-purple-500/15 border border-purple-500/30 text-purple-400/90 leading-none"
              :title="`隐含税率 = (国开-国债)/国开`"
            >
              税{{ impliedTaxRate(getCell(tenor.key, 'gov')?.yield, getCell(tenor.key, 'cdb')?.yield) }}
            </span>
          </div>
          <!-- 利差标注：国开/商A-AAA 显示相对国债的利差 -->
          <span
            v-if="getCell(tenor.key, activeSource)?.spread_bps != null"
            class="text-[9px] text-terminal-dim leading-none"
          >
            {{ getCell(tenor.key, activeSource)?.spread_bps >= 0 ? '+' : '' }}{{ getCell(tenor.key, activeSource)?.spread_bps.toFixed(1) }}bp
          </span>
        </div>

        <!-- 基点变化 -->
        <div class="py-1.5 px-2 border-l border-theme flex items-center justify-between">
          <div class="flex flex-col items-end">
            <span
              class="text-[9px] font-mono"
              :class="getCell(tenor.key, activeSource)?.change_bps >= 0 ? 'text-bullish/70' : 'text-bearish/70'"
            >
              {{ formatBps(getCell(tenor.key, activeSource)?.change_bps) }}
            </span>
            <div
              class="h-0.5 rounded-full mt-0.5"
              :class="getCell(tenor.key, activeSource)?.change_bps >= 0 ? 'bg-red-400/40' : 'bg-green-400/40'"
              :style="{ width: Math.min(40, Math.abs(getCell(tenor.key, activeSource)?.change_bps || 0) * 4) + 'px' }"
            ></div>
          </div>
        </div>
      </div>

      <!-- 无数据提示 -->
      <div v-if="!hasData" class="text-center py-3 text-terminal-dim text-[10px]">
        利率矩阵数据加载中...
      </div>
    </div>

    <!-- ── 主体：左侧曲线组 + 右侧债券列表 ─────────────── -->
    <div class="flex gap-2 flex-1 min-h-0">

      <!-- 左侧：国债收益率曲线 + 期限利差图 -->
      <div class="flex-1 flex flex-col gap-2">

        <!-- 收益率曲线 -->
        <div class="terminal-panel border border-theme-secondary rounded p-3 flex flex-col" style="flex: 2;">
          <div class="flex items-center justify-between mb-1.5 shrink-0">
            <span class="text-[10px] text-terminal-dim">📈 收益率曲线</span>
            <span class="text-[9px] text-terminal-dim">{{ yieldUpdateTime || '...' }}</span>
          </div>
          <div class="flex-1 min-h-0 overflow-hidden relative" style="min-height: 160px;">
            <YieldCurveChart
              v-if="Object.keys(yieldCurve).length > 0"
              :yield-curve="yieldCurve"
              :curve-1m="yieldCurve1m"
              :curve-1y="yieldCurve1y"
              :update-time="yieldUpdateTime"
            />
            <div v-else class="w-full h-full flex items-center justify-center">
              <span class="text-terminal-dim text-[10px]">加载中...</span>
            </div>
          </div>
        </div>

        <!-- 10Y-2Y 期限利差走势 -->
        <div class="terminal-panel border border-theme-secondary rounded p-3 flex flex-col" style="flex: 1; min-height: 130px;">
          <YieldSpreadChart
            :tenors10y="spreadHistory10y"
            :tenors2y="spreadHistory2y"
            :update-time="spreadUpdateTime"
            :isLoading="spreadLoading"
            :hasError="!!spreadError"
            :errorMsg="spreadError"
          />
        </div>
      </div>

      <!-- 右侧：活跃债券列表 -->
      <div class="w-56 shrink-0 terminal-panel border border-theme-secondary rounded p-3 flex flex-col">
        <div class="flex items-center justify-between mb-1.5 shrink-0">
          <span class="text-[10px] text-terminal-dim">📋 活跃债券</span>
          <span class="text-[9px] px-1 py-0.5 rounded border border-amber-500/30 text-amber-400/70">LIVE</span>
        </div>
        <div class="flex-1 overflow-y-auto">
          <div
            v-for="bond in bondList"
            :key="bond.code"
            class="flex items-center justify-between py-1 border-b border-theme hover:bg-white/5 transition-colors cursor-pointer"
          >
            <div class="flex flex-col min-w-0">
              <span class="text-[10px] text-theme-primary truncate">{{ bond.name }}</span>
              <span class="text-[9px] text-terminal-dim">{{ bond.code }}</span>
            </div>
            <div class="flex flex-col items-end">
              <span class="text-[10px] font-mono text-theme-primary">{{ bond.rate }}</span>
              <span
                class="text-[9px] font-mono"
                :class="bond.change_bps >= 0 ? 'text-bullish/70' : 'text-bearish/70'"
              >{{ bond.change_bps >= 0 ? '+' : '' }}{{ bond.change_bps }}bp</span>
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
import YieldCurveChart from './YieldCurveChart.vue'
import YieldSpreadChart from './YieldSpreadChart.vue'
import BondHistoryModal from './BondHistoryModal.vue'
import { apiFetch } from '../utils/api.js'

// ── 常量 ──────────────────────────────────────────────────────────
const TENORS = [
  { key: '1Y',  label: '1年' },
  { key: '2Y',  label: '2年' },
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
const spreadHistory2y    = ref([])
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
  if (!govRate || !cdbRate || cdbRate === 0) return '--'
  const tax = ((cdbRate - govRate) / cdbRate) * 100
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
      const govCurve   = bc.yield_curve  || {}
      const commCurve = bc.comm_yield   || {}
      const spreadsBps = bc.spreads_bps || {}
      const updateTime = bc.update_time  || ''
      bondDataSource.value   = bc.source   || ''

      yieldCurve.value       = govCurve
      yieldCurve1m.value    = bc.yield_curve_1m || {}
      yieldCurve1y.value    = bc.yield_curve_1y || {}
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

// 10Y-2Y 利差历史（取最近 252 个交易日，即 1 年）
async function fetchSpreadHistory() {
  spreadLoading.value = true
  spreadError.value   = ''
  try {
    const [data10y, data2y] = await Promise.all([
      apiFetch(`/api/v1/bond/history?tenor=${encodeURIComponent('10年')}&period=1Y`, 10000).catch(() => null),
      apiFetch(`/api/v1/bond/history?tenor=${encodeURIComponent('2年')}&period=1Y`, 10000).catch(() => null),
    ])
    spreadHistory10y.value  = (data10y?.data?.history || data10y?.history || []).filter(d => d.yield > 0).map(d => ({ date: d.date, yield: d.yield }))
    spreadHistory2y.value   = (data2y?.data?.history || data2y?.history || []).filter(d => d.yield > 0).map(d => ({ date: d.date, yield: d.yield }))
    spreadUpdateTime.value   = data10y ? new Date().toLocaleTimeString() : ''
  } catch (e) {
    spreadError.value = e.message
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
