<template>
  <div class="flex flex-col h-full overflow-auto gap-3 p-4">

    <!-- 顶部核心卡片：国债收益率 -->
    <div class="flex gap-3 shrink-0">
      <div
        v-for="card in bondCards" :key="card.name"
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

    <!-- 主体：左侧收益率曲线占位 + 右侧债券列表 -->
    <div class="flex gap-3 flex-1 min-h-0">

      <!-- 左侧：国债收益率曲线占位 -->
      <div class="flex-1 terminal-panel border border-gray-800 rounded p-4 flex flex-col">
        <div class="text-xs text-terminal-dim mb-3">📈 国债收益率曲线</div>
        <div class="flex-1 flex items-center justify-center bg-black/20 rounded border border-gray-800">
          <div class="text-center">
            <div class="text-3xl mb-2">📊</div>
            <div class="text-terminal-dim text-xs">收益率曲线图表</div>
            <div class="text-terminal-dim/40 text-[10px] mt-1">待接入宏观数据源</div>
            <!-- Mock 简单曲线示意 -->
            <div class="mt-4 flex items-end gap-0.5 justify-center h-12">
              <div v-for="(h, i) in curveBars" :key="i"
                class="w-2 rounded-t"
                :style="{ height: h + '%', background: 'var(--terminal-accent, #60a5fa)', opacity: 0.4 + i * 0.04 }"
              ></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：债券列表 -->
      <div class="w-72 shrink-0 terminal-panel border border-gray-800 rounded p-4 flex flex-col">
        <div class="text-xs text-terminal-dim mb-3">📋 活跃债券</div>
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
              <tr v-for="bond in bondList" :key="bond.name"
                  class="border-b border-gray-800/50 hover:bg-white/5 transition-colors">
                <td class="py-1.5 text-gray-300">{{ bond.name }}</td>
                <td class="py-1.5 text-right font-mono text-gray-100">{{ bond.rate }}</td>
                <td class="py-1.5 text-right font-mono"
                    :class="bond.change >= 0 ? 'text-red-400' : 'text-green-400'">
                  {{ bond.change >= 0 ? '+' : '' }}{{ bond.change }}
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
const curveBars = [30, 35, 42, 50, 58, 65, 72, 68, 63, 70, 75, 80]

const bondCards = [
  { name: '10年期国债', rate: '1.652%', change: -3.2, note: 'CN10Y · 银行间' },
  { name: '2年期国债',  rate: '1.412%', change: -1.8, note: 'CN2Y · 银行间' },
  { name: '中美利差',   rate: '-0.238%', change: +5.4, note: 'CN10Y - US10Y' },
]

const bondList = [
  { name: '22附息国债15', rate: '1.638%', change: -2.1 },
  { name: '23附息国债05', rate: '1.721%', change: +1.3 },
  { name: '22农发09',     rate: '2.104%', change: -0.8 },
  { name: '23进出01',     rate: '1.953%', change: +0.5 },
  { name: '22国开02',     rate: '1.892%', change: -1.2 },
  { name: '23重庆债07',   rate: '2.341%', change: +2.1 },
  { name: '22河北债22',  rate: '2.218%', change: -0.4 },
  { name: 'AAA企业债(3Y)', rate: '2.89%',  change: +3.7 },
  { name: 'AA+企业债(3Y)', rate: '3.24%',  change: -1.5 },
  { name: '城投债(5Y)AA+', rate: '3.01%',  change: +0.9 },
]
</script>
