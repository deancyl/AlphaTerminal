<template>
  <div class="flex flex-col h-full overflow-auto gap-3 p-4">

    <!-- 顶部核心卡片：国债收益率 -->
    <div class="flex gap-3 shrink-0">
      <div
        v-for="card in bondCards"
        :key="card.name"
        class="flex-1 terminal-panel border border-gray-800 rounded px-4 py-3 flex flex-col gap-1"
      >
        <span class="text-[10px] text-terminal-dim uppercase tracking-wider">{{ card.name }}</span>
        <div class="flex items-end gap-2">
          <span class="text-lg font-mono text-gray-100">{{ card.rate }}</span>
          <span
            class="text-xs font-mono"
            :class="card.change >= 0 ? 'text-red-400' : 'text-green-400'"
          >{{ card.change >= 0 ? '+' : '' }}{{ card.change }}bps</span>
        </div>
        <span class="text-[9px] text-terminal-dim">{{ card.note }}</span>
      </div>
    </div>

    <!-- 主体：左侧收益率曲线 + 右侧债券列表 -->
    <div class="flex gap-3 flex-1 min-h-0">

      <!-- 左侧：国债收益率曲线（真实图表） -->
      <div class="flex-1 terminal-panel border border-gray-800 rounded p-4 flex flex-col">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-terminal-dim">📈 国债收益率曲线</span>
          <span class="text-[9px] text-terminal-dim">{{ yieldUpdateTime || '...' }}</span>
        </div>
        <div class="flex-1 min-h-0 overflow-hidden relative" style="min-height: 180px;">
          <YieldCurveChart
            v-if="Object.keys(yieldCurve).length > 0"
            :yield-curve="yieldCurve"
            :update-time="yieldUpdateTime"
          />
          <div v-else class="w-full h-full flex items-center justify-center">
            <span class="text-terminal-dim text-xs">加载中...</span>
          </div>
        </div>
      </div>

      <!-- 右侧：债券列表 -->
      <div class="w-72 shrink-0 terminal-panel border border-gray-800 rounded p-4 flex flex-col">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-terminal-dim">📋 活跃债券</span>
          <span class="text-[9px] px-1.5 py-0.5 rounded border border-amber-500/30 text-amber-400">Mock</span>
        </div>
        <div class="flex-1 overflow-y-auto">
          <table class="w-full text-[11px]">
            <thead>
              <tr class="text-terminal-dim text-[9px] border-b border-gray-800">
                <th class="text-left pb-1">名称</th>
                <th class="text-right pb-1">收益率</th>
                <th class="text-right pb-1">涨跌</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="bond in bondList" :key="bond.code"
                  class="border-b border-gray-800/50 hover:bg-white/5 transition-colors">
                <td class="py-1.5 text-gray-300" :title="bond.type">{{ bond.name }}</td>
                <td class="py-1.5 text-right font-mono text-gray-100">{{ bond.rate }}</td>
                <td class="py-1.5 text-right font-mono"
                    :class="bond.change_bps >= 0 ? 'text-red-400' : 'text-green-400'">
                  {{ bond.change_bps >= 0 ? '+' : '' }}{{ bond.change_bps }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import YieldCurveChart from './YieldCurveChart.vue'

const yieldCurve    = ref({})
const yieldUpdateTime = ref('')

const bondCards = ref([
  { name: '10年期国债', rate: '--',   change: 0, note: 'CN10Y · 银行间' },
  { name: '2年期国债',  rate: '--',   change: 0, note: 'CN2Y · 银行间' },
  { name: '中美利差',   rate: '--',   change: 0, note: 'CN10Y - US10Y' },
])

const bondList = ref([])

async function fetchBondData() {
  try {
    const [yc, ba] = await Promise.all([
      fetch('/api/v1/bond/yield_curve').then(r => r.ok ? r.json() : null),
      fetch('/api/v1/bond/active').then(r => r.ok ? r.json() : null),
    ])

    if (yc) {
      yieldCurve.value    = yc.yield_curve || {}
      yieldUpdateTime.value = yc.update_time || ''

      // 更新卡片
      const y = yc.yield_curve
      if (y['10年'] != null && y['1年'] != null) {
        const cn10 = y['10年']
        const cn2  = y['2年'] || y['1年']
        bondCards.value = [
          { name: '10年期国债', rate: (cn10 / 100).toFixed(3) + '%', change: 0, note: 'CN10Y · 银行间' },
          { name: '2年期国债',  rate: (cn2  / 100).toFixed(3) + '%', change: 0, note: 'CN2Y · 银行间' },
          { name: '中美利差',   rate: ((cn10 - cn2) / 100).toFixed(3) + '%', change: 0, note: 'CN10Y - CN2Y' },
        ]
      }
    }

    if (ba) {
      bondList.value = ba.bonds || []
    }
  } catch (e) {
    console.warn('[BondDashboard] fetch failed:', e)
  }
}

onMounted(() => {
  fetchBondData()
  setInterval(fetchBondData, 300_000)  // 每5分钟刷新
})
</script>
