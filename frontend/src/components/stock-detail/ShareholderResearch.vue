<template>
  <div class="space-y-4">
    <h2 class="text-lg font-bold text-terminal-accent">股东研究</h2>
    
    <div v-if="loading" class="text-center py-8 text-terminal-dim">
      加载中...
    </div>
    
    <div v-else-if="error" class="text-center py-8 text-red-400">
      {{ error }}
    </div>
    
    <div v-else-if="!data" class="text-center py-8 text-terminal-dim">
      请先查询股票代码
    </div>
    
    <div v-else class="space-y-4">
      <!-- Top 10 流通股东 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <h3 class="text-sm font-bold text-terminal-primary mb-3">
          Top 10 流通股东
          <span v-if="data.circulateHolders?.date" class="text-xs text-terminal-dim ml-2">
            ({{ data.circulateHolders.date }})
          </span>
        </h3>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-theme-secondary text-terminal-dim">
                <th class="py-2 px-3 text-left">排名</th>
                <th class="py-2 px-3 text-left">股东名称</th>
                <th class="py-2 px-3 text-right">持股数量</th>
                <th class="py-2 px-3 text-right">占流通股比例</th>
                <th class="py-2 px-3 text-left">股本性质</th>
              </tr>
            </thead>
            <tbody>
              <tr 
                v-for="(holder, idx) in data.circulateHolders?.holders" 
                :key="idx"
                class="border-b border-theme-secondary/50 hover:bg-theme-hover"
              >
                <td class="py-2 px-3 text-terminal-dim">{{ idx + 1 }}</td>
                <td class="py-2 px-3 text-terminal-primary">{{ holder['股东名称'] }}</td>
                <td class="py-2 px-3 text-right text-terminal-secondary">{{ formatNumber(holder['持股数量']) }}</td>
                <td class="py-2 px-3 text-right text-terminal-accent">{{ holder['占流通股比例'] }}%</td>
                <td class="py-2 px-3 text-terminal-dim">{{ holder['股本性质'] }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- 股本变动记录 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <h3 class="text-sm font-bold text-terminal-primary mb-3">股本变动记录（最近365天）</h3>
        <div v-if="!data.shareChanges?.length" class="text-center py-4 text-terminal-dim">
          暂无股本变动记录
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-theme-secondary text-terminal-dim">
                <th class="py-2 px-3 text-left">变动日期</th>
                <th class="py-2 px-3 text-left">变动原因</th>
                <th class="py-2 px-3 text-right">总股本</th>
                <th class="py-2 px-3 text-right">已流通股份</th>
                <th class="py-2 px-3 text-right">流通受限股份</th>
              </tr>
            </thead>
            <tbody>
              <tr 
                v-for="(change, idx) in data.shareChanges" 
                :key="idx"
                class="border-b border-theme-secondary/50 hover:bg-theme-hover"
              >
                <td class="py-2 px-3 text-terminal-primary">{{ change.date }}</td>
                <td class="py-2 px-3 text-terminal-secondary">{{ change.reason }}</td>
                <td class="py-2 px-3 text-right text-terminal-dim">{{ formatNumber(change.totalShares) }}</td>
                <td class="py-2 px-3 text-right text-terminal-dim">{{ formatNumber(change.circulateShares) }}</td>
                <td class="py-2 px-3 text-right text-terminal-dim">{{ formatNumber(change.restrictedShares) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- 股东增减持记录 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <h3 class="text-sm font-bold text-terminal-primary mb-3">重要股东增减持</h3>
        <div v-if="!data.holderChanges?.length" class="text-center py-4 text-terminal-dim">
          暂无增减持记录
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-theme-secondary text-terminal-dim">
                <th class="py-2 px-3 text-left">公告日期</th>
                <th class="py-2 px-3 text-left">变动股东</th>
                <th class="py-2 px-3 text-right">变动数量</th>
                <th class="py-2 px-3 text-right">交易均价</th>
                <th class="py-2 px-3 text-right">剩余股份</th>
                <th class="py-2 px-3 text-left">变动途径</th>
              </tr>
            </thead>
            <tbody>
              <tr 
                v-for="(change, idx) in data.holderChanges" 
                :key="idx"
                class="border-b border-theme-secondary/50 hover:bg-theme-hover"
                :class="{
                  'bg-red-500/10': change.changeAmount && change.changeAmount.includes('减持'),
                  'bg-green-500/10': change.changeAmount && change.changeAmount.includes('增持')
                }"
              >
                <td class="py-2 px-3 text-terminal-primary">{{ change.date }}</td>
                <td class="py-2 px-3 text-terminal-secondary">{{ change.holder }}</td>
                <td 
                  class="py-2 px-3 text-right font-medium"
                  :class="{
                    'text-red-400': change.changeAmount && change.changeAmount.includes('减持'),
                    'text-green-400': change.changeAmount && change.changeAmount.includes('增持')
                  }"
                >
                  {{ change.changeAmount }}
                </td>
                <td class="py-2 px-3 text-right text-terminal-dim">{{ change.avgPrice }}</td>
                <td class="py-2 px-3 text-right text-terminal-dim">{{ change.remainingShares }}</td>
                <td class="py-2 px-3 text-terminal-dim">{{ change.channel }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useStockDetail } from '../../composables/useStockDetail'

defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' }
})

const { formatNumber } = useStockDetail()
</script>
