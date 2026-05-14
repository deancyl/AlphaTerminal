<template>
  <div class="space-y-6">
    <h2 class="text-lg font-bold text-theme-primary">🛡️ 速率限制</h2>
    <p class="text-xs text-theme-muted">API 请求频率控制，防止滥用和 DoS 攻击</p>

    <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 这个功能是做什么的？</h3>
      <p class="text-xs text-theme-secondary leading-relaxed">
        <strong class="text-terminal-accent">速率限制</strong>防止单个IP过度请求API，保护服务器资源。超过限制的请求会返回 <code class="bg-theme-secondary/30 px-1 rounded">429 Too Many Requests</code>。
      </p>
    </div>

    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">追踪IP数</div>
        <div class="text-xl font-bold text-terminal-accent">{{ stats.total_tracked_ips || 0 }}</div>
        <div class="text-[10px] text-theme-muted">个活跃IP</div>
      </div>
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">被限制请求数</div>
        <div class="text-xl font-bold text-[var(--color-danger)]">{{ stats.blocked_requests?.length || 0 }}</div>
        <div class="text-[10px] text-theme-muted">个被限制</div>
      </div>
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">全局限制</div>
        <div class="text-xl font-bold text-terminal-accent">{{ stats.endpoint_limits?.default?.requests || 200 }}</div>
        <div class="text-[10px] text-theme-muted">请求/分钟</div>
      </div>
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">状态</div>
        <div class="text-xl font-bold" :class="stats.enabled ? 'text-terminal-success' : 'text-[var(--color-danger)]'">
          {{ stats.enabled ? '✓ 启用' : '✗ 禁用' }}
        </div>
        <div class="text-[10px] text-theme-muted">速率限制</div>
      </div>
    </div>

    <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <h3 class="text-sm font-bold text-theme-primary mb-4">端点限制配置</h3>
      <div class="overflow-x-auto">
        <table class="w-full text-xs">
          <thead>
            <tr class="border-b border-theme">
              <th class="text-left py-2 text-theme-muted">端点类型</th>
              <th class="text-right py-2 text-theme-muted">请求数</th>
              <th class="text-right py-2 text-theme-muted">周期(秒)</th>
              <th class="text-right py-2 text-theme-muted">速率</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(limit, name) in stats.endpoint_limits" :key="name" class="border-b border-theme/50">
              <td class="py-2 text-theme-primary font-medium">{{ getEndpointLabel(name) }}</td>
              <td class="py-2 text-right text-theme-secondary">{{ limit.requests }}</td>
              <td class="py-2 text-right text-theme-secondary">{{ limit.period }}</td>
              <td class="py-2 text-right text-terminal-accent">{{ (limit.requests / limit.period * 60).toFixed(1) }}/min</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="stats.blocked_requests?.length > 0" class="p-4 bg-[var(--color-danger-bg)] border border-[var(--color-danger-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-danger)] mb-4">⚠️ 被限制的请求</h3>
      <div class="overflow-x-auto max-h-48 overflow-y-auto">
        <table class="w-full text-xs">
          <thead class="sticky top-0 bg-[var(--color-danger-bg)]">
            <tr class="border-b border-[var(--color-danger-border)]">
              <th class="text-left py-2 text-theme-muted">IP地址</th>
              <th class="text-left py-2 text-theme-muted">路径</th>
              <th class="text-right py-2 text-theme-muted">请求数</th>
              <th class="text-right py-2 text-theme-muted">剩余秒数</th>
              <th class="text-right py-2 text-theme-muted">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(req, idx) in stats.blocked_requests" :key="idx" class="border-b border-[var(--color-danger-border)]/50">
              <td class="py-2 text-theme-primary font-mono">{{ req.ip }}</td>
              <td class="py-2 text-theme-secondary truncate max-w-[200px]">{{ req.path }}</td>
              <td class="py-2 text-right text-[var(--color-danger)]">{{ req.count }}</td>
              <td class="py-2 text-right text-theme-secondary">{{ req.remaining_seconds }}s</td>
              <td class="py-2 text-right">
                <button 
                  class="px-2 py-1 bg-[var(--color-warning-bg)] text-[var(--color-warning)] rounded text-[10px]"
                  @click="$emit('confirm-action', '重置IP限制', `确定要重置 ${req.ip} 的速率限制吗？`, () => $emit('reset-ip', req.ip))"
                >
                  重置
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <h3 class="text-sm font-bold text-theme-primary mb-4">管理操作</h3>
      <div class="flex flex-wrap gap-3">
        <button 
          class="px-4 py-2 bg-[var(--color-info-bg)] text-[var(--color-info)] rounded-sm text-sm"
          @click="$emit('refresh')"
        >
          🔄 刷新统计
        </button>
        <button 
          class="px-4 py-2 bg-[var(--color-warning-bg)] text-[var(--color-warning)] rounded-sm text-sm"
          @click="$emit('confirm-action', '重置所有限制', '这将重置所有IP的速率限制计数器。确定？', () => $emit('reset-all'))"
        >
          🔓 重置所有限制
        </button>
      </div>
    </div>

    <div class="p-3 bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] rounded-sm text-xs text-theme-muted">
      <strong class="text-[var(--color-warning)]">安全说明：</strong>
      <ul class="mt-1 space-y-1 list-disc list-inside">
        <li><strong>速率限制</strong>：防止单个IP过度请求，保护服务器免受DoS攻击</li>
        <li><strong>429响应</strong>：超限请求返回429状态码，包含Retry-After头告知重试时间</li>
        <li><strong>端点限制</strong>：昂贵操作（回测、F9深度数据）有更严格的限制</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
defineProps({
  stats: { type: Object, default: () => ({}) }
})

defineEmits(['confirm-action', 'refresh', 'reset-ip', 'reset-all'])

function getEndpointLabel(name) {
  const labels = {
    'f9_deep': 'F9深度数据',
    'backtest': '回测引擎',
    'agent': 'Agent API',
    'market': '市场行情',
    'news': '新闻快讯',
    'default': '全局默认'
  }
  return labels[name] || name
}
</script>