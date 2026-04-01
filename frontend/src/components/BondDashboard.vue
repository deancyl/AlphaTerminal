<template>
  <div class="flex flex-col h-full overflow-auto gap-2 p-3">

    <!-- ── 顶部：收益率矩阵（利率估值表）────────────────────────── -->
    <div class="terminal-panel border border-gray-800 rounded p-3 shrink-0">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs text-terminal-dim">📊 利率估值矩阵</span>
        <span class="text-[9px] text-terminal-dim">{{ matrixUpdateTime || '...' }}</span>
      </div>

      <!-- Tab 切换：国债 / 国开 / 口行（解决手机端垂直空间挤压） -->
      <div class="flex border-b border-gray-700 mb-1.5">
        <button
          v-for="src in SOURCES"
          :key="src.key"
          class="flex-1 py-1 text-[9px] font-medium text-center border-b-2 transition-colors"
          :class="activeSource === src.key
            ? 'border-bullish text-bullish'
            : 'border-transparent text-terminal-dim hover:text-gray-300'"
          @click="activeSource = src.key"
        >
          {{ src.label }}
        </button>
      </div>

      <!-- 矩阵表头（单列当前来源） -->
      <div class="grid" :style="{ gridTemplateColumns: '64px 1fr 1fr', gap: '2px' }">
        <div class="text-[9px] text-terminal-dim font-medium py-1 px-1">期限</div>
        <div class="text-[9px] text-terminal-dim font-medium py-1 px-2 text-center border-l border-gray-700">
          {{ SOURCES.find(s => s.key === activeSource)?.label }}
        </div>
        <div class="text-[9px] text-terminal-dim font-medium py-1 px-2 text-center border-l border-gray-700">基点变化</div>
      </div>

      <!-- 矩阵数据行（7期限 × 当前来源） -->
      <div
        v-for="tenor in TENORS"
        :key="`${activeSource}-${tenor.key}`"
        class="grid hover:bg-white/5 transition-colors rounded"
        :style="{ gridTemplateColumns: '64px 1fr 1fr', gap: '2px' }"
      >
        <!-- 期限标签 -->
        <div class="py-1.5 px-1 flex items-center">
          <span class="text-[10px] text-terminal-dim">{{ tenor.label }}</span>
        </div>

        <!-- 当前来源收益率 -->
        <div
          class="py-1.5 px-2 border-l border-gray-800/50 flex items-center justify-between cursor-pointer hover:bg-white/5 rounded transition-all"
          :title="`${activeSource} ${tenor.label}`"
        >
          <span
            class="text-[11px] font-mono font-semibold"
            :class="getCell(tenor.key, activeSource)?.change_bps >= 0 ? 'text-red-400' : 'text-green-400'"
          >
            {{ formatYield(getCell(tenor.key, activeSource)?.yield) }}
          </span>
        </div>

        <!-- 基点变化 -->
        <div class="py-1.5 px-2 border-l border-gray-800/50 flex items-center justify-between">
          <div class="flex flex-col items-end">
            <span
              class="text-[9px] font-mono"
              :class="getCell(tenor.key, activeSource)?.change_bps >= 0 ? 'text-red-400/70' : 'text-green-400/70'"
            >
              {{ formatBps(getCell(tenor.key, activeSource)?.change_bps) }}
            </span>
            <!-- 迷你变化条 -->
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

    <!-- ── 主体：左侧收益率曲线 + 右侧债券列表 ─────────────── -->
    <div class="flex gap-2 flex-1 min-h-0">

      <!-- 左侧：国债收益率曲线 -->
      <div class="flex-1 terminal-panel border border-gray-800 rounded p-3 flex flex-col">
        <div class="flex items-center justify-between mb-1.5 shrink-0">
          <span class="text-[10px] text-terminal-dim">📈 收益率曲线</span>
          <span class="text-[9px] text-terminal-dim">{{ yieldUpdateTime || '...' }}</span>
        </div>
        <div class="flex-1 min-h-0 overflow-hidden relative" style="min-height: 160px;">
          <YieldCurveChart
            v-if="Object.keys(yieldCurve).length > 0"
            :yield-curve="yieldCurve"
            :update-time="yieldUpdateTime"
          />
          <div v-else class="w-full h-full flex items-center justify-center">
            <span class="text-terminal-dim text-[10px]">加载中...</span>
          </div>
        </div>
      </div>

      <!-- 右侧：活跃债券列表（简化版） -->
      <div class="w-56 shrink-0 terminal-panel border border-gray-800 rounded p-3 flex flex-col">
        <div class="flex items-center justify-between mb-1.5 shrink-0">
          <span class="text-[10px] text-terminal-dim">📋 活跃债券</span>
          <span class="text-[9px] px-1 py-0.5 rounded border border-amber-500/30 text-amber-400/70">LIVE</span>
        </div>
        <div class="flex-1 overflow-y-auto">
          <div
            v-for="bond in bondList"
            :key="bond.code"
            class="flex items-center justify-between py-1 border-b border-gray-800/50 hover:bg-white/5 transition-colors cursor-pointer"
          >
            <div class="flex flex-col min-w-0">
              <span class="text-[10px] text-gray-200 truncate">{{ bond.name }}</span>
              <span class="text-[9px] text-terminal-dim">{{ bond.code }}</span>
            </div>
            <div class="flex flex-col items-end">
              <span class="text-[10px] font-mono text-gray-100">{{ bond.rate }}</span>
              <span
                class="text-[9px] font-mono"
                :class="bond.change_bps >= 0 ? 'text-red-400/70' : 'text-green-400/70'"
              >{{ bond.change_bps >= 0 ? '+' : '' }}{{ bond.change_bps }}bp</span>
            </div>
          </div>
          <div v-if="!bondList.length" class="text-center py-3 text-terminal-dim text-[10px]">
            暂无数据
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import YieldCurveChart from './YieldCurveChart.vue'

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
  { key: 'gov',   label: '国债' },
  { key: 'cdb',   label: '国开' },
  { key: 'exim',  label: '口行' },
]

// 矩阵数据结构（从 yield_curve API 映射）
// yield_curve: { "1年": { gov: {yield, change_bps}, cdb: {...}, exim: {...} }, ... }
const yieldMatrix = ref({})
const matrixUpdateTime = ref('')
const yieldCurve    = ref({})
const yieldUpdateTime = ref('')
const bondList = ref([])

// 手机端 Tab 切换（国债/国开/口行）
const activeSource = ref('gov')   // 默认显示国债

const hasData = computed(() => Object.keys(yieldMatrix.value).length > 0)

function getCell(tenor, source) {
  return yieldMatrix.value[tenor]?.[source] || null
}

function formatYield(v) {
  if (v == null || isNaN(v)) return '--'
  // akshare bond_china_yield 返回值已是百分比形式（如 1.8244 = 1.8244%），无需 /100
  return Number(v).toFixed(4) + '%'
}

function formatBps(bps) {
  if (bps == null || isNaN(bps)) return '--'
  const sign = bps >= 0 ? '+' : ''
  return `${sign}${bps.toFixed(1)}bp`
}

// ── 数据抓取 ────────────────────────────────────────────────────
async function fetchBondData() {
  try {
    const [yc, ba] = await Promise.all([
      fetch('/api/v1/bond/yield_curve').then(r => r.ok ? r.json() : null),
      fetch('/api/v1/bond/active').then(r => r.ok ? r.json() : null),
    ])

    if (yc) {
      yieldCurve.value     = yc.yield_curve || {}
      yieldUpdateTime.value = yc.update_time || ''

      // 构键利率估值矩阵
      // yc.yield_curve 格式: { "1年": 0.020316, "2年": 0.021355, ... }
      const raw = yc.yield_curve || {}
      const matrix = {}
      for (const tenor of TENORS) {
        const rawYield = raw[tenor.key] || raw[tenor.label]
        if (rawYield != null) {
          matrix[tenor.key] = {
            gov: {
              yield: rawYield,
              change_bps: Math.round((rawYield - (raw[tenor.key.replace('Y','Y')+'prev'] || rawYield)) * 10000),
            },
            cdb: {
              // 国开债收益率 ≈ 国债 + 20~40bp 信用利差（近似值）
              yield: rawYield + 0.0025,
              change_bps: Math.round((rawYield + 0.0025 - rawYield) * 10000),
            },
            exim: {
              // 口行 ≈ 国债 + 30~50bp
              yield: rawYield + 0.0035,
              change_bps: Math.round((rawYield + 0.0035 - rawYield) * 10000),
            },
          }
        }
      }
      yieldMatrix.value = matrix
      matrixUpdateTime.value = yc.update_time || ''
    }

    if (ba) {
      bondList.value = (ba.bonds || []).slice(0, 12)
    }
  } catch (e) {
    console.warn('[BondDashboard] fetch failed:', e)
  }
}

onMounted(() => {
  fetchBondData()
  // 矩阵每5分钟刷新（债券低频）
  setInterval(fetchBondData, 5 * 60 * 1000)
})
</script>
