<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-bold text-theme-primary">🛡️ 进程保活监控</h2>
        <p class="text-xs text-theme-muted mt-1">监控后端进程健康状态，崩溃时自动重启</p>
      </div>
      <div class="flex items-center gap-2">
        <span v-if="loading" class="text-xs text-theme-muted">加载中...</span>
        <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="$emit('refresh')">🔄 刷新状态</button>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="p-3 bg-[var(--color-danger-bg)] border border-[var(--color-danger-border)] rounded-sm text-xs text-[var(--color-danger)]">
      <strong>加载失败:</strong> {{ error }}
    </div>

    <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 这个功能是做什么的？</h3>
      <p class="text-xs text-theme-secondary leading-relaxed">
        <strong class="text-terminal-accent">进程保活</strong>会每30秒检查一次后端服务是否正常运行。
        如果发现后端崩溃或无法响应，系统会<strong class="text-terminal-accent">自动重启</strong>服务，确保前端始终能获取数据。
        适合长期运行的场景（如24小时监控）。
      </p>
    </div>

    <!-- 状态卡片 -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div class="p-4 rounded-sm border" :class="status.enabled ? 'bg-[var(--color-success-bg)] border-[var(--color-success-border)]' : 'bg-[var(--color-neutral-bg)] border-[var(--border-secondary)]'">
        <div class="flex items-center justify-between mb-3">
          <span class="font-medium text-theme-primary">保活开关</span>
          <span class="w-3 h-3 rounded-full" :class="status.enabled ? 'bg-[var(--color-success-light)] animate-pulse' : 'bg-gray-400'"></span>
        </div>
        <div class="text-2xl font-bold" :class="status.enabled ? 'text-[var(--color-success)]' : 'text-[var(--text-secondary)]'">
          {{ status.enabled ? '已启用' : '已禁用' }}
        </div>
        <div class="text-[10px] text-theme-muted mt-1">
          {{ status.enabled ? '后端崩溃时将自动重启' : '后端崩溃后需手动重启' }}
        </div>
        <div class="flex gap-2 mt-4 pt-3 border-t border-theme/50">
          <button v-if="!status.enabled" class="flex-1 px-3 py-1.5 bg-[var(--color-success-bg)] text-[var(--color-success)] rounded-sm text-xs" @click="$emit('toggle', true)">✅ 启用保活</button>
          <button v-else class="flex-1 px-3 py-1.5 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded-sm text-xs" @click="$emit('toggle', false)">⏹️ 禁用保活</button>
        </div>
      </div>

      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">监控状态</div>
        <div class="text-xl font-bold" :class="status.running ? 'text-terminal-accent' : 'text-[var(--color-warning)]'">
          {{ status.running ? '运行中' : '未运行' }}
        </div>
        <div class="text-[10px] text-theme-muted mt-1">
          上次检查: {{ status.last_check ? formatTime(status.last_check) : '从未' }}
        </div>
      </div>

      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">重启统计</div>
        <div class="text-xl font-bold" :class="status.total_restarts > 0 ? 'text-[var(--color-warning)]' : 'text-[var(--color-success)]'">
          {{ status.total_restarts }} 次
        </div>
        <div class="text-[10px] text-theme-muted mt-1">
          连续失败: {{ status.restart_count }}/3
        </div>
      </div>
    </div>

    <!-- 手动操作 -->
    <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <h3 class="text-sm font-bold text-theme-primary mb-4">紧急操作</h3>
      <div class="flex flex-wrap gap-3">
        <button class="px-4 py-2 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded-sm text-sm" @click="$emit('confirm-action', '手动重启后端', '这将立即终止当前后端进程并启动新实例，所有连接将中断5-10秒。确定？', () => $emit('manual-restart'))">🔄 手动重启后端</button>
        <button class="px-4 py-2 bg-[var(--color-info-bg)] text-[var(--color-info)] rounded-sm text-sm" @click="$emit('refresh')">📊 刷新状态</button>
      </div>
    </div>

    <!-- 最近错误 -->
    <div v-if="status.recent_errors && status.recent_errors.length > 0" class="p-4 bg-[var(--color-danger-bg)] border border-[var(--color-danger-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-danger)] mb-3">最近错误记录</h3>
      <div class="space-y-2 text-xs">
        <div v-for="(err, i) in status.recent_errors" :key="i" class="flex gap-3">
          <span class="text-theme-muted whitespace-nowrap">{{ formatTime(err.time) }}</span>
          <span class="text-[var(--color-danger)]">{{ err.error }}</span>
        </div>
      </div>
    </div>

    <div class="p-3 bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] rounded-sm text-xs text-theme-muted">
      <strong class="text-[var(--color-warning)]">使用说明：</strong>
      <ul class="mt-1 space-y-1 list-disc list-inside">
        <li><strong>启用保活</strong>：后端崩溃后自动重启，适合长期运行场景</li>
        <li><strong>禁用保活</strong>：后端崩溃后保持停止，便于调试问题</li>
        <li><strong>手动重启</strong>：立即重启后端，用于紧急恢复或配置生效</li>
        <li>连续重启3次仍失败会进入5分钟冷却期，防止无限循环</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
defineProps({
  status: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  error: { type: String, default: null }
})

defineEmits(['refresh', 'toggle', 'manual-restart', 'confirm-action'])

function formatTime(isoTime) {
  if (!isoTime) return null
  const date = new Date(isoTime)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
</script>
