<template>
  <div class="bg-terminal-panel/95 border border-theme/60 rounded px-3 py-1.5 text-[10px] font-mono">
    <!-- 日期时间 -->
    <div class="text-theme-tertiary mb-0.5">{{ data.date || data.time || '--' }} {{ data.time ? data.time.slice(11, 16) : '' }}</div>
    <!-- OHLCV -->
    <div class="flex gap-3">
      <span class="text-theme-secondary">开 <span class="text-theme-primary">{{ data.open?.toFixed(2) ?? '--' }}</span></span>
      <span class="text-theme-secondary">高 <span class="text-red-300">{{ data.high?.toFixed(2) ?? '--' }}</span></span>
      <span class="text-theme-secondary">低 <span class="text-green-300">{{ data.low?.toFixed(2) ?? '--' }}</span></span>
      <span class="text-theme-secondary">收 <span class="text-theme-primary">{{ data.close?.toFixed(2) ?? '--' }}</span></span>
      <span class="text-theme-secondary">量 <span class="text-theme-primary">{{ data.volume != null ? (data.volume / 1e8).toFixed(2) + '亿股' : '--' }}</span></span>
    </div>
  </div>
</template>

<script setup>
defineProps({ data: { type: Object, default: () => ({}) } })
</script>
