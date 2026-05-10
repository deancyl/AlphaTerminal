<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-bold text-theme-primary">🔌 AI工具配置</h2>
        <p class="text-xs text-theme-muted mt-1">配置MCP工具和外部AI服务集成</p>
      </div>
      <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="$emit('refresh')">🔄 刷新</button>
    </div>

    <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 这个功能是做什么的？</h3>
      <p class="text-xs text-theme-secondary leading-relaxed">
        配置<strong class="text-terminal-accent">MCP (Model Context Protocol)</strong>工具和外部AI服务。
        通过MCP协议，可以让AI助手访问更多数据源和工具，如实时行情、数据库查询等。
      </p>
    </div>

    <div class="bg-terminal-panel border border-theme rounded-sm p-5">
      <div class="text-center py-12 text-theme-muted">
        <div class="text-4xl mb-3">🔌</div>
        <div class="text-sm">AI工具配置功能</div>
        <div class="text-xs mt-2 text-theme-tertiary">请切换到主界面的AI工具配置模块进行操作</div>
        <button @click="$emit('navigate', 'mcp')" class="mt-4 px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm hover:bg-terminal-accent/25 transition-colors">
          前往AI工具配置 →
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineEmits(['refresh', 'navigate'])
</script>