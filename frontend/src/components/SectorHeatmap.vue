<template>
  <MarketRadar @stock-click="onStockClick" />
</template>

<script setup>
import MarketRadar from './MarketRadar.vue'

const emit = defineEmits(['stock-click'])

function onStockClick(stock) {
  emit('stock-click', stock)
}
</script>