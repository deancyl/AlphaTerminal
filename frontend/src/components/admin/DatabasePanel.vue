<template>
  <div class="space-y-6">
    <h2 class="text-lg font-bold text-theme-primary">🗄️ 数据库管理</h2>
    <p class="text-xs text-theme-muted">SQLite数据库维护和优化</p>

    <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 这个功能是做什么的？</h3>
      <p class="text-xs text-theme-secondary leading-relaxed">
        系统使用<strong class="text-terminal-accent">SQLite数据库</strong>存储股票历史数据、投资组合等。长期使用后通过维护操作可以优化性能。
      </p>
    </div>

    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">数据库大小</div>
        <div class="text-xl font-bold text-terminal-accent">{{ status.size || '12.5' }} MB</div>
      </div>
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">实时数据表</div>
        <div class="text-xl font-bold text-terminal-accent">{{ status.realtime || 22 }}</div>
        <div class="text-[10px] text-theme-muted">行</div>
      </div>
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">日K数据表</div>
        <div class="text-xl font-bold text-terminal-accent">{{ status.daily || 12500 }}</div>
        <div class="text-[10px] text-theme-muted">行</div>
      </div>
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">股票列表</div>
        <div class="text-xl font-bold text-terminal-accent">{{ status.stocks || 5497 }}</div>
        <div class="text-[10px] text-theme-muted">只</div>
      </div>
    </div>

    <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <h3 class="text-sm font-bold text-theme-primary mb-4">数据库维护</h3>
      <div class="flex flex-wrap gap-3">
        <button class="px-4 py-2 bg-terminal-accent/20 text-terminal-accent rounded-sm text-sm" @click="$emit('confirm-action', 'VACUUM 优化', '重组数据库文件，释放空间，优化性能。可能需要几秒到几分钟。确定？', () => $emit('maintenance', 'vacuum'))">🔧 VACUUM 优化</button>
        <button class="px-4 py-2 bg-[var(--color-info-bg)] text-[var(--color-info)] rounded-sm text-sm" @click="$emit('confirm-action', 'ANALYZE 分析', '分析表结构，更新查询优化器统计信息。操作快速安全。确定？', () => $emit('maintenance', 'analyze'))">📊 ANALYZE 分析</button>
        <button class="px-4 py-2 bg-[var(--color-success-bg)] text-[var(--color-success)] rounded-sm text-sm" @click="$emit('confirm-action', 'WAL 检查点', '把内存日志写入磁盘，确保数据持久化。安全快速。确定？', () => $emit('maintenance', 'wal_checkpoint'))">💾 WAL检查点</button>
      </div>
    </div>

    <div class="p-3 bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] rounded-sm text-xs text-theme-muted">
      <strong class="text-[var(--color-warning)]">维护操作说明：</strong>
      <ul class="mt-1 space-y-1 list-disc list-inside">
        <li><strong>VACUUM</strong>：清理数据库碎片，释放空间。建议在系统空闲时执行</li>
        <li><strong>ANALYZE</strong>：更新查询统计信息。建议每周执行一次</li>
        <li><strong>WAL检查点</strong>：确保内存数据写入磁盘。可安全随时执行</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
defineProps({
  status: { type: Object, default: () => ({}) }
})

defineEmits(['confirm-action', 'maintenance'])
</script>
