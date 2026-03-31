<template>
  <div class="flex flex-col h-full overflow-auto gap-3 p-4">

    <!-- 顶部核心卡片：股指期货主力 -->
    <div class="flex gap-3 shrink-0">
      <div
        v-for="card in futuresCards" :key="card.symbol"
        class="flex-1 terminal-panel border border-gray-800 rounded px-4 py-3 flex flex-col gap-1"
      >
        <div class="flex items-center justify-between">
          <span class="text-[10px] text-terminal-dim uppercase tracking-wider">{{ card.name }}</span>
          <span
            class="text-[9px] px-1 py-0.5 rounded border"
            :class="card.change >= 0
              ? 'border-red-500/30 text-red-400'
              : 'border-green-500/30 text-green-400'"
          >{{ card.change >= 0 ? '多' : '空' }}</span>
        </div>
        <div class="flex items-end gap-2">
          <span class="text-lg font-mono text-gray-100">{{ card.price }}</span>
          <span
            class="text-xs font-mono"
            :class="card.change >= 0 ? 'text-red-400' : 'text-green-400'"
          >{{ card.change >= 0 ? '+' : '' }}{{ card.change }}%</span>
        </div>
        <div class="text-[9px] text-terminal-dim flex justify-between">
          <span>持仓: {{ card.position }}</span>
          <span>{{ card.note }}</span>
        </div>
      </div>
    </div>

    <!-- 主体：上方大宗商品热力图 + 下方主力合约图表占位 -->
    <div class="flex flex-col gap-3 flex-1 min-h-0">

      <!-- 大宗商品涨跌方块阵列（热力图风格） -->
      <div class="terminal-panel border border-gray-800 rounded p-4">
        <div class="text-xs text-terminal-dim mb-3">🛢️ 国内大宗商品主力合约</div>
        <div class="grid grid-cols-6 gap-2">
          <div
            v-for="item in commodityBlocks" :key="item.name"
            class="rounded border flex flex-col items-center justify-center py-2 px-1 cursor-default transition-all hover:brightness-125"
            :style="{
              borderColor: item.change >= 0
                ? 'rgba(239,68,68,0.35)'
                : 'rgba(34,197,94,0.35)',
              background: item.change >= 0
                ? 'rgba(239,68,68,0.08)'
                : 'rgba(34,197,94,0.08)',
            }"
          >
            <span class="text-[10px] text-gray-300 truncate w-full text-center">{{ item.name }}</span>
            <span
              class="text-xs font-mono mt-0.5"
              :class="item.change >= 0 ? 'text-red-400' : 'text-green-400'"
            >{{ item.change >= 0 ? '+' : '' }}{{ item.change }}%</span>
          </div>
        </div>
      </div>

      <!-- 下方：主力合约图表占位 -->
      <div class="flex-1 terminal-panel border border-gray-800 rounded p-4 flex flex-col">
        <div class="text-xs text-terminal-dim mb-3">📈 期货主力合约走势</div>
        <div class="flex-1 flex items-center justify-center bg-black/20 rounded border border-gray-800">
          <div class="text-center">
            <div class="text-3xl mb-2">📊</div>
            <div class="text-terminal-dim text-xs">期货实时走势图表</div>
            <div class="text-terminal-dim/40 text-[10px] mt-1">待接入期货数据源</div>
            <!-- Mock K线示意 -->
            <div class="mt-4 flex items-end gap-px justify-center h-12">
              <div v-for="(bar, i) in mockBars" :key="i"
                class="w-1.5 rounded-t"
                :style="{
                  height: bar.h + '%',
                  background: bar.up
                    ? 'rgba(239,68,68,0.7)'
                    : 'rgba(34,197,94,0.7)',
                }"
              ></div>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
const futuresCards = [
  { symbol: 'IF', name: 'IF 沪深300',   price: '4448.2', change: -0.93, position: '8.2万手', note: 'IMIF' },
  { symbol: 'IC', name: 'IC 中证500',   price: '6102.4', change: +0.31, position: '6.5万手', note: 'IMIC' },
  { symbol: 'IM', name: 'IM 中证1000', price: '6438.8', change: +0.72, position: '5.1万手', note: 'IMIM' },
]

const commodityBlocks = [
  { name: '螺纹钢',  change: +1.28 },
  { name: '热卷',    change: -0.54 },
  { name: '纯碱',    change: +3.21 },
  { name: '碳酸锂',  change: -2.17 },
  { name: '铁矿石',  change: +0.83 },
  { name: '焦煤',    change: +1.45 },
  { name: '原油',    change: -1.32 },
  { name: '燃油',    change: -0.78 },
  { name: 'PTA',    change: +0.29 },
  { name: '甲醇',    change: +1.08 },
  { name: 'PVC',    change: -0.21 },
  { name: '尿素',    change: +2.44 },
]

// Mock K线数据（22根）
const mockBars = Array.from({ length: 22 }, (_, i) => {
  const base = 50 + Math.sin(i * 0.5) * 15
  const h = Math.max(20, Math.min(90, base + Math.random() * 20))
  return { h, up: Math.random() > 0.4 }
})
</script>
