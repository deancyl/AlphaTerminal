<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-bold text-theme-primary">🔑 API密钥管理</h2>
        <p class="text-xs text-theme-muted mt-1">管理Agent和第三方服务的API密钥</p>
      </div>
      <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="$emit('refresh')">🔄 刷新</button>
    </div>

    <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 这个功能是做什么的？</h3>
      <p class="text-xs text-theme-secondary leading-relaxed">
        管理用于<strong class="text-terminal-accent">AI Agent</strong>和<strong class="text-terminal-accent">第三方服务</strong>的API密钥。
        密钥将被安全存储，用于自动化交易、数据获取等功能。
      </p>
    </div>

    <div class="bg-terminal-panel border border-theme rounded-sm p-5">
      <div class="text-center py-12 text-theme-muted">
        <div class="text-4xl mb-3">🔑</div>
        <div class="text-sm">API密钥管理功能</div>
        <div class="text-xs mt-2 text-theme-tertiary">请切换到主界面的API密钥管理模块进行操作</div>
        <button @click="$emit('navigate', 'agent_tokens')" class="mt-4 px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm hover:bg-terminal-accent/25 transition-colors">
          前往API密钥管理 →
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineEmits(['refresh', 'navigate'])
</script>