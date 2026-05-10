<template>
  <div class="space-y-6">
    <h2 class="text-lg font-bold text-theme-primary">💾 缓存管理</h2>
    <p class="text-xs text-theme-muted">清理和预热系统缓存，优化数据加载速度</p>

    <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 这个功能是做什么的？</h3>
      <p class="text-xs text-theme-secondary leading-relaxed">
        系统使用<strong class="text-terminal-accent">缓存</strong>加速数据加载。<strong class="text-terminal-accent">预热</strong>是提前加载常用数据，提升首次访问速度。
      </p>
    </div>

    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">行情数据缓存</div>
        <div class="text-xl font-bold text-terminal-accent">{{ status.market || 5497 }}</div>
        <div class="text-[10px] text-theme-muted">只股票</div>
      </div>
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">板块数据缓存</div>
        <div class="text-xl font-bold text-terminal-accent">{{ status.sectors || 20 }}</div>
        <div class="text-[10px] text-theme-muted">个板块</div>
      </div>
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">新闻缓存</div>
        <div class="text-xl font-bold text-terminal-accent">{{ status.news || 150 }}</div>
        <div class="text-[10px] text-theme-muted">条快讯</div>
      </div>
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">数据库缓存</div>
        <div class="text-xl font-bold text-terminal-accent">{{ status.db || 22 }}</div>
        <div class="text-[10px] text-theme-muted">条实时数据</div>
      </div>
    </div>

    <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <h3 class="text-sm font-bold text-theme-primary mb-4">缓存操作</h3>
      <div class="flex flex-wrap gap-3">
        <button class="px-4 py-2 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded-sm text-sm" @click="$emit('confirm-action', '清空行情缓存', '清空后系统会重新从数据源获取，可能有短暂延迟。确定？', () => $emit('invalidate', 'market'))">🗑️ 清空行情缓存</button>
        <button class="px-4 py-2 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded-sm text-sm" @click="$emit('confirm-action', '清空板块缓存', '板块列表可能需要几秒重新加载。确定？', () => $emit('invalidate', 'sectors'))">🗑️ 清空板块缓存</button>
        <button class="px-4 py-2 bg-[var(--color-info-bg)] text-[var(--color-info)] rounded-sm text-sm" @click="$emit('confirm-action', '预热板块缓存', '提前加载板块数据，提升访问速度。确定？', () => $emit('warmup', 'sectors'))">🔥 预热板块缓存</button>
      </div>
    </div>

    <div class="p-3 bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] rounded-sm text-xs text-theme-muted">
      <strong class="text-[var(--color-warning)]">操作后果说明：</strong>
      <ul class="mt-1 space-y-1 list-disc list-inside">
        <li><strong>清空缓存</strong>：删除已缓存的数据，下次访问时重新获取，可能有短暂延迟</li>
        <li><strong>预热缓存</strong>：提前加载数据到缓存中，适合在开盘前执行</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
defineProps({
  status: { type: Object, default: () => ({}) }
})

defineEmits(['confirm-action', 'invalidate', 'warmup'])
</script>
