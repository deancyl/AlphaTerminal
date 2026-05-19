<template>
  <div class="w-72 bg-surface rounded-xl border border-border-base flex flex-col overflow-hidden">
    <!-- Collapsible Guidance Panel -->
    <div class="p-4 border-b border-border-base bg-surface-hover/50">
      <button 
        @click="showGuidance = !showGuidance"
        class="flex items-center gap-2 text-sm text-secondary w-full"
      >
        <span>💡</span>
        <span>模拟交易说明</span>
        <svg class="w-4 h-4 ml-auto transition-transform" :class="{ 'rotate-180': showGuidance }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 9l6 6 6-6" />
        </svg>
      </button>
      
      <div v-if="showGuidance" class="mt-2 text-xs text-muted space-y-1">
        <p>• 这是模拟交易，不涉及真实资金</p>
        <p>• 买入时检查可用现金是否充足</p>
        <p>• 卖出时检查持仓数量是否足够</p>
        <p>• 建议每次交易不超过总资金的20%</p>
      </div>
    </div>
    
    <!-- Portfolio Summary -->
    <div class="p-4 border-b border-border-base">
      <h4 class="text-sm font-semibold text-primary mb-3">模拟账户</h4>
      <div class="space-y-2 text-sm">
        <div class="flex justify-between items-center">
          <span class="text-secondary">现金</span>
          <span class="font-data text-primary">{{ formatMoney(portfolio.cash) }}</span>
        </div>
        <div class="flex justify-between items-center">
          <span class="text-secondary">持仓市值</span>
          <span class="font-data text-primary">{{ formatMoney(portfolio.position_value) }}</span>
        </div>
        <div class="flex justify-between items-center">
          <span class="text-secondary">总资产</span>
          <span class="font-data text-primary font-semibold">{{ formatMoney(portfolio.total_value) }}</span>
        </div>
        <div class="flex justify-between items-center pt-2 border-t border-border-base">
          <span class="text-secondary">收益率</span>
          <span
            :class="portfolio.pnl_pct >= 0 ? 'text-bull' : 'text-bear'"
            class="font-data font-semibold"
          >
            {{ portfolio.pnl_pct >= 0 ? '+' : '' }}{{ portfolio.pnl_pct.toFixed(2) }}%
          </span>
        </div>
        <div v-if="portfolio.shares > 0" class="flex justify-between items-center text-xs text-muted">
          <span>持仓 {{ portfolio.shares }} 股</span>
          <span>成本 {{ portfolio.avg_cost.toFixed(2) }}</span>
        </div>
      </div>
    </div>
    
    <!-- Trade Form -->
    <div class="p-4 border-b border-border-base">
      <h4 class="text-sm font-semibold text-primary mb-3">下单</h4>
      
      <!-- Direction Toggle -->
      <div class="flex gap-2 mb-3">
        <button
          @click="tradeDirection = 'buy'"
          :class="[
            'flex-1 py-2 rounded-lg text-sm font-medium transition-all',
            tradeDirection === 'buy'
              ? 'bg-bull text-white shadow-sm'
              : 'bg-base text-secondary hover:bg-surface-hover'
          ]"
        >
          买入
        </button>
        <button
          @click="tradeDirection = 'sell'"
          :class="[
            'flex-1 py-2 rounded-lg text-sm font-medium transition-all',
            tradeDirection === 'sell'
              ? 'bg-bear text-white shadow-sm'
              : 'bg-base text-secondary hover:bg-surface-hover'
          ]"
        >
          卖出
        </button>
      </div>
      
      <!-- Quantity Input -->
      <div class="mb-3">
        <input
          v-model.number="tradeQuantity"
          type="number"
          min="1"
          step="100"
          placeholder="数量（股）"
          class="w-full px-3 py-2 bg-base rounded-lg border border-border-base text-primary
                 focus:border-primary focus:outline-none text-sm font-data"
        />
        <div class="flex gap-2 mt-2">
          <button
            @click="tradeQuantity = 100"
            class="px-2 py-1 text-xs bg-base rounded border border-border-base text-secondary hover:bg-surface-hover"
          >
            100股
          </button>
          <button
            @click="tradeQuantity = 500"
            class="px-2 py-1 text-xs bg-base rounded border border-border-base text-secondary hover:bg-surface-hover"
          >
            500股
          </button>
          <button
            @click="tradeQuantity = 1000"
            class="px-2 py-1 text-xs bg-base rounded border border-border-base text-secondary hover:bg-surface-hover"
          >
            1000股
          </button>
        </div>
      </div>
      
      <!-- Estimated Value -->
      <div v-if="tradeQuantity > 0" class="mb-3 p-2 bg-base/50 rounded-lg text-sm">
        <div class="flex justify-between">
          <span class="text-secondary">预估金额</span>
          <span class="font-data text-primary">{{ formatMoney(currentPrice * tradeQuantity) }}</span>
        </div>
        <div v-if="tradeDirection === 'sell' && portfolio.shares > 0" class="flex justify-between text-xs text-muted mt-1">
          <span>可卖 {{ portfolio.shares }} 股</span>
          <span v-if="tradeQuantity > portfolio.shares" class="text-danger">超出持仓</span>
        </div>
        <div v-if="tradeDirection === 'buy'" class="flex justify-between text-xs text-muted mt-1">
          <span>可用现金 {{ formatMoney(portfolio.cash) }}</span>
          <span v-if="currentPrice * tradeQuantity > portfolio.cash" class="text-danger">资金不足</span>
        </div>
      </div>
      
      <!-- Execute Button -->
      <button
        @click="handleTrade"
        :disabled="!canTrade"
        :class="[
          'w-full py-2 rounded-lg text-sm font-medium transition-all',
          canTrade
            ? tradeDirection === 'buy'
              ? 'bg-bull text-white hover:bg-bull/90'
              : 'bg-bear text-white hover:bg-bear/90'
            : 'bg-base text-disabled cursor-not-allowed'
        ]"
      >
        {{ tradeDirection === 'buy' ? '确认买入' : '确认卖出' }}
      </button>
    </div>
    
    <!-- Trade History -->
    <div class="flex-1 overflow-y-auto p-4">
      <h4 class="text-sm font-semibold text-primary mb-3">交易记录</h4>
      
      <div v-if="trades.length === 0" class="text-center text-muted text-sm py-4">
        暂无交易记录
      </div>
      
      <div v-else class="space-y-2">
        <div
          v-for="(trade, idx) in trades.slice().reverse()"
          :key="idx"
          class="p-2 bg-base rounded-lg text-sm"
        >
          <div class="flex items-center justify-between mb-1">
            <span
              :class="trade.action === 'buy' ? 'text-bull' : 'text-bear'"
              class="font-medium"
            >
              {{ trade.action === 'buy' ? '买入' : '卖出' }}
            </span>
            <span class="text-muted text-xs">{{ trade.date }}</span>
          </div>
          <div class="flex justify-between text-xs">
            <span class="text-secondary">{{ trade.quantity }} 股 × {{ trade.price.toFixed(2) }}</span>
            <span class="font-data text-primary">{{ formatMoney(trade.value) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  portfolio: {
    type: Object,
    required: true
  },
  trades: {
    type: Array,
    default: () => []
  },
  currentPrice: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['trade'])

const tradeDirection = ref('buy')
const tradeQuantity = ref(100)
const showGuidance = ref(true) // Expanded by default for user guidance

const canTrade = computed(() => {
  if (!props.currentPrice || tradeQuantity.value <= 0) return false
  
  if (tradeDirection.value === 'buy') {
    return props.currentPrice * tradeQuantity.value <= props.portfolio.cash
  } else {
    return tradeQuantity.value <= props.portfolio.shares
  }
})

function handleTrade() {
  if (!canTrade.value) return
  emit('trade', {
    action: tradeDirection.value,
    quantity: tradeQuantity.value
  })
}

function formatMoney(value) {
  if (value === null || value === undefined) return '¥0.00'
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value)
}
</script>