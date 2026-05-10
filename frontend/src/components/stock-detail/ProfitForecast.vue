<template>
  <div class="space-y-4">
    <h2 class="text-lg font-bold text-terminal-accent">盈利预测</h2>
    
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
      <!-- EPS预测表 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <h3 class="text-sm font-bold text-terminal-primary mb-3">EPS预测（每股收益）</h3>
        <div v-if="data.eps_forecast && data.eps_forecast.length > 0" class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-theme-secondary">
                <th class="text-left py-2 px-3 text-terminal-dim font-normal">年份</th>
                <th class="text-right py-2 px-3 text-terminal-dim font-normal">最小值</th>
                <th class="text-right py-2 px-3 text-terminal-dim font-normal">平均值</th>
                <th class="text-right py-2 px-3 text-terminal-dim font-normal">最大值</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, idx) in data.eps_forecast" :key="idx" class="border-b border-theme-secondary/50 hover:bg-theme-hover">
                <td class="py-2 px-3 text-terminal-primary">{{ item['年度'] || item['年份'] || '--' }}</td>
                <td class="py-2 px-3 text-right text-terminal-secondary">{{ item['最小值'] || item['预测最小值'] || '--' }}</td>
                <td class="py-2 px-3 text-right text-terminal-accent font-medium">{{ item['均值'] || item['预测均值'] || '--' }}</td>
                <td class="py-2 px-3 text-right text-terminal-secondary">{{ item['最大值'] || item['预测最大值'] || '--' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="text-center py-4 text-terminal-dim">暂无EPS预测数据</div>
      </div>
      
      <!-- 机构预测详表 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <h3 class="text-sm font-bold text-terminal-primary mb-3">机构预测详表</h3>
        <div v-if="data.institutions && data.institutions.length > 0" class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-theme-secondary">
                <th class="text-left py-2 px-3 text-terminal-dim font-normal">机构名称</th>
                <th class="text-left py-2 px-3 text-terminal-dim font-normal">研究员</th>
                <th class="text-right py-2 px-3 text-terminal-dim font-normal">报告日期</th>
                <th class="text-right py-2 px-3 text-terminal-dim font-normal">2026EPS</th>
                <th class="text-right py-2 px-3 text-terminal-dim font-normal">2027EPS</th>
                <th class="text-right py-2 px-3 text-terminal-dim font-normal">2028EPS</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, idx) in data.institutions.slice(0, 20)" :key="idx" class="border-b border-theme-secondary/50 hover:bg-theme-hover">
                <td class="py-2 px-3 text-terminal-primary">{{ item['机构名称'] || '--' }}</td>
                <td class="py-2 px-3 text-terminal-secondary">{{ item['研究员'] || '--' }}</td>
                <td class="py-2 px-3 text-right text-terminal-secondary">{{ item['报告日期'] || '--' }}</td>
                <td class="py-2 px-3 text-right text-terminal-accent font-medium">{{ item['预测年报每股收益2026预测'] || '--' }}</td>
                <td class="py-2 px-3 text-right text-terminal-secondary">{{ item['预测年报每股收益2027预测'] || '--' }}</td>
                <td class="py-2 px-3 text-right text-terminal-secondary">{{ item['预测年报每股收益2028预测'] || '--' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="data.institutions.length > 20" class="text-center py-2 text-terminal-dim text-xs">
            显示前20条，共 {{ data.institutions.length }} 条记录
          </div>
        </div>
        <div v-else class="text-center py-4 text-terminal-dim">暂无机构预测数据</div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' }
})
</script>
