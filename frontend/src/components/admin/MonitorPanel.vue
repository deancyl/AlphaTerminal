<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-bold text-theme-primary">📊 系统监控</h2>
      <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="$emit('refresh')">🔄 刷新</button>
    </div>

    <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 这个功能是做什么的？</h3>
      <p class="text-xs text-theme-secondary leading-relaxed">
        显示运行系统的服务器的<strong class="text-terminal-accent">实时资源使用情况</strong>。当系统变慢时，可以查看这些指标判断原因。
      </p>
    </div>

    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">CPU 使用率</div>
        <div class="text-2xl font-bold" :class="getCpuColor(metrics.cpu_percent)">{{ metrics.cpu_percent?.toFixed(1) || 0 }}%</div>
        <div class="text-[10px] text-theme-muted mt-1">{{ getCpuStatus(metrics.cpu_percent) }}</div>
      </div>
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">内存使用</div>
        <div class="text-2xl font-bold" :class="getMemoryColor(metrics.memory?.percent)">{{ metrics.memory?.percent?.toFixed(1) || 0 }}%</div>
        <div class="text-[10px] text-theme-muted mt-1">{{ metrics.memory?.used_gb?.toFixed(1) || 0 }} / {{ metrics.memory?.total_gb?.toFixed(1) || 0 }} GB</div>
      </div>
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">磁盘使用</div>
        <div class="text-2xl font-bold" :class="getDiskColor(metrics.disk?.percent)">{{ metrics.disk?.percent?.toFixed(1) || 0 }}%</div>
        <div class="text-[10px] text-theme-muted mt-1">{{ metrics.disk?.used_gb?.toFixed(1) || 0 }} / {{ metrics.disk?.total_gb?.toFixed(1) || 0 }} GB</div>
      </div>
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">后端进程内存</div>
        <div class="text-2xl font-bold text-terminal-accent">{{ metrics.process?.memory_mb?.toFixed(0) || 0 }} MB</div>
        <div class="text-[10px] text-theme-muted mt-1">{{ metrics.process?.threads || 0 }} 线程</div>
      </div>
    </div>

    <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <h3 class="text-sm font-bold text-theme-primary mb-3">🌐 网络状态</h3>
      <div class="grid grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
        <div><span class="text-theme-muted">活跃连接：</span><span class="text-terminal-accent font-bold">{{ metrics.network?.connections || 0 }}</span></div>
        <div><span class="text-theme-muted">发送数据：</span><span class="text-theme-secondary">{{ formatBytes(metrics.network?.io_counters?.bytes_sent) }}</span></div>
        <div><span class="text-theme-muted">接收数据：</span><span class="text-theme-secondary">{{ formatBytes(metrics.network?.io_counters?.bytes_recv) }}</span></div>
      </div>
    </div>

<div class="p-3 bg-[var(--color-success-bg)] border border-[var(--color-success)]/20 rounded-sm text-xs text-theme-muted">
      <strong class="text-[var(--color-success)]">指标说明：</strong>
      <ul class="mt-1 space-y-1 list-disc list-inside">
        <li><strong>CPU</strong>：处理器使用率，持续高于80%可能导致系统响应变慢</li>
        <li><strong>内存</strong>：RAM使用情况，接近100%时系统可能变慢</li>
        <li><strong>磁盘</strong>：硬盘使用率，接近100%时需要清理空间</li>
        <li><strong>网络连接</strong>：当前活跃的网络连接数</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
defineProps({
  metrics: { type: Object, default: () => ({}) }
})

defineEmits(['refresh'])

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024
    i++
  }
  return bytes.toFixed(2) + ' ' + units[i]
}

function getCpuColor(p) { return !p ? 'text-theme-muted' : p < 50 ? 'text-[var(--color-success)]' : p < 80 ? 'text-[var(--color-warning)]' : 'text-[var(--color-danger)]' }
function getCpuStatus(p) { return !p ? '未知' : p < 50 ? '正常' : p < 80 ? '较高' : '过高' }
function getMemoryColor(p) { return !p ? 'text-theme-muted' : p < 70 ? 'text-[var(--color-success)]' : p < 90 ? 'text-[var(--color-warning)]' : 'text-[var(--color-danger)]' }
function getDiskColor(p) { return !p ? 'text-theme-muted' : p < 70 ? 'text-[var(--color-success)]' : p < 90 ? 'text-[var(--color-warning)]' : 'text-[var(--color-danger)]' }
</script>
