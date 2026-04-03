<template>
  <div class="bg-terminal-panel/95 border border-gray-600 rounded-lg shadow-2xl p-4 min-w-64">
    <!-- 标题栏 -->
    <div class="flex items-center justify-between mb-3">
      <span class="text-[12px] font-bold text-terminal-accent">📊 区间统计</span>
      <button class="text-gray-500 hover:text-gray-300 text-[11px]" @click="emit('close')">✕</button>
    </div>

    <!-- 区间范围 -->
    <div class="text-[10px] text-gray-500 mb-3 border-b border-gray-700/50 pb-2">
      <span>{{ stats.startDate }}</span>
      <span class="mx-2">→</span>
      <span>{{ stats.endDate }}</span>
      <span class="ml-2 text-gray-600">({{ stats.tradeDays }}个交易日)</span>
    </div>

    <!-- 涨跌统计 -->
    <div class="grid grid-cols-2 gap-x-4 gap-y-1.5 mb-3">
      <div class="flex justify-between text-[11px]">
        <span class="text-gray-500">区间涨跌幅</span>
        <span class="font-mono" :class="stats.changePct >= 0 ? 'text-red-400' : 'text-green-400'">
          {{ stats.changePct >= 0 ? '+' : '' }}{{ stats.changePct?.toFixed(2) ?? '--' }}%
        </span>
      </div>
      <div class="flex justify-between text-[11px]">
        <span class="text-gray-500">最大振幅</span>
        <span class="font-mono text-gray-200">{{ stats.maxAmplitude?.toFixed(2) ?? '--' }}%</span>
      </div>
      <div class="flex justify-between text-[11px]">
        <span class="text-gray-500">最高价</span>
        <span class="font-mono text-red-300">{{ stats.highest?.toFixed(2) ?? '--' }}</span>
      </div>
      <div class="flex justify-between text-[11px]">
        <span class="text-gray-500">最低价</span>
        <span class="font-mono text-green-300">{{ stats.lowest?.toFixed(2) ?? '--' }}</span>
      </div>
      <div class="flex justify-between text-[11px]">
        <span class="text-gray-500">累计成交量</span>
        <span class="font-mono text-gray-200">{{ stats.totalVolume != null ? (stats.totalVolume / 1e8).toFixed(2) + '亿' : '--' }}</span>
      </div>
      <div class="flex justify-between text-[11px]">
        <span class="text-gray-500">累计成交额</span>
        <span class="font-mono text-gray-200">{{ stats.totalAmount != null ? (stats.totalAmount / 1e8).toFixed(2) + '亿' : '--' }}</span>
      </div>
      <div class="flex justify-between text-[11px]">
        <span class="text-gray-500">累计换手率</span>
        <span class="font-mono text-gray-200">{{ stats.totalTurnoverRate != null ? stats.totalTurnoverRate.toFixed(2) + '%' : '--' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({ stats: { type: Object, default: () => ({}) } })
const emit = defineEmits(['close'])
</script>
