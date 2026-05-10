<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-bold text-theme-primary">⏱️ 定时任务管理</h2>
        <p class="text-xs text-theme-muted mt-1">控制系统后台的自动数据更新任务</p>
      </div>
      <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="$emit('refresh')">🔄 刷新</button>
    </div>

    <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 这个功能是做什么的？</h3>
      <p class="text-xs text-theme-secondary leading-relaxed">
        系统通过<strong class="text-terminal-accent">定时任务</strong>自动更新股票行情、板块数据、新闻快讯等。
        你可以暂停某个任务，或手动触发立即执行。
      </p>
    </div>

    <div class="space-y-3">
      <div v-for="job in jobs" :key="job.id" class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-3">
            <span class="w-2 h-2 rounded-full" :class="job.state === 'running' ? 'bg-[var(--color-success-light)] animate-pulse' : 'bg-yellow-400'"></span>
            <div>
              <span class="font-medium text-theme-primary">{{ job.name }}</span>
              <div class="text-[10px] text-theme-muted">{{ job.id }}</div>
            </div>
          </div>
          <div class="flex gap-2">
            <button v-if="job.state === 'running'" class="px-3 py-1.5 bg-[var(--color-warning-bg)] text-[var(--color-warning)] rounded-sm text-xs" @click="$emit('confirm-action', `暂停 ${job.name}`, `该任务将停止自动执行，相关数据不再更新。确定？`, () => $emit('control-job', job.id, 'pause'))">⏸️ 暂停</button>
            <button v-else class="px-3 py-1.5 bg-[var(--color-success-bg)] text-[var(--color-success)] rounded-sm text-xs" @click="$emit('control-job', job.id, 'resume')">▶️ 恢复</button>
            <button class="px-3 py-1.5 bg-[var(--color-info-bg)] text-[var(--color-info)] rounded-sm text-xs" @click="$emit('confirm-action', `立即执行 ${job.name}`, `立即执行一次该任务，不影响定时计划。确定？`, () => $emit('control-job', job.id, 'run'))">⚡ 立即执行</button>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-4 text-xs text-theme-muted">
          <div><span class="text-theme-secondary">执行频率：</span><span>{{ job.trigger }}</span></div>
          <div><span class="text-theme-secondary">下次执行：</span><span>{{ formatTime(job.next_run) || '已暂停' }}</span></div>
        </div>
      </div>
    </div>

    <div class="p-3 bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] rounded-sm text-xs text-theme-muted">
      <strong class="text-[var(--color-warning)]">常用任务说明：</strong>
      <ul class="mt-1 space-y-1 list-disc list-inside">
        <li><strong>data_fetch</strong>：每30秒拉取股票实时行情，暂停后行情不再更新</li>
        <li><strong>sectors_update</strong>：每5分钟更新板块数据</li>
        <li><strong>news_refresh</strong>：每10分钟获取新闻快讯</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
defineProps({
  jobs: { type: Array, default: () => [] }
})

defineEmits(['refresh', 'confirm-action', 'control-job'])

function formatTime(isoTime) {
  if (!isoTime) return null
  const date = new Date(isoTime)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
</script>
