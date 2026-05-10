<template>
  <div class="space-y-4">
    <h2 class="text-lg font-bold text-terminal-accent">公司概况</h2>
    
    <div v-if="loading" class="text-center py-8 text-terminal-dim">
      加载中...
    </div>
    
    <div v-else-if="!stockInfo" class="text-center py-8 text-terminal-dim">
      请输入股票代码查询
    </div>
    
    <div v-else class="space-y-4">
      <!-- 基本信息卡片 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <h3 class="text-sm font-bold text-terminal-primary mb-3">基本信息</h3>
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <div class="text-xs text-terminal-dim">股票名称</div>
            <div class="text-sm text-terminal-primary">{{ stockInfo.name || '--' }}</div>
          </div>
          <div>
            <div class="text-xs text-terminal-dim">股票代码</div>
            <div class="text-sm text-terminal-primary">{{ stockInfo.symbol || '--' }}</div>
          </div>
          <div>
            <div class="text-xs text-terminal-dim">所属行业</div>
            <div class="text-sm text-terminal-primary">{{ stockInfo.industry || '--' }}</div>
          </div>
          <div>
            <div class="text-xs text-terminal-dim">上市时间</div>
            <div class="text-sm text-terminal-primary">{{ stockInfo.listDate || '--' }}</div>
          </div>
          <div>
            <div class="text-xs text-terminal-dim">总股本</div>
            <div class="text-sm text-terminal-primary">{{ formatNumber(stockInfo.totalShares) }}</div>
          </div>
          <div>
            <div class="text-xs text-terminal-dim">流通股本</div>
            <div class="text-sm text-terminal-primary">{{ formatNumber(stockInfo.floatShares) }}</div>
          </div>
          <div>
            <div class="text-xs text-terminal-dim">总市值</div>
            <div class="text-sm text-terminal-primary">{{ formatMoney(stockInfo.totalMarketCap) }}</div>
          </div>
          <div>
            <div class="text-xs text-terminal-dim">流通市值</div>
            <div class="text-sm text-terminal-primary">{{ formatMoney(stockInfo.floatMarketCap) }}</div>
          </div>
        </div>
      </div>
      
      <!-- 主营业务 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <h3 class="text-sm font-bold text-terminal-primary mb-3">主营业务</h3>
        <p class="text-sm text-terminal-secondary leading-relaxed">
          {{ stockInfo.business || '暂无数据' }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useStockDetail } from '../../composables/useStockDetail'

const props = defineProps({
  stockInfo: { type: Object, default: null },
  loading: { type: Boolean, default: false }
})

const { formatNumber, formatMoney } = useStockDetail()
</script>
