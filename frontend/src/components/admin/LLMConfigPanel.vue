<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-bold text-theme-primary">🤖 模型服务配置</h2>
        <p class="text-xs text-theme-muted mt-1">配置 LLM API Key 和 Base URL，数据库配置优先于 .env</p>
      </div>
      <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="$emit('refresh')">🔄 刷新</button>
    </div>

    <div v-for="(cfg, provider) in providers" :key="provider"
         class="bg-terminal-panel border border-theme rounded-sm p-5">
      <div class="flex items-center gap-3 mb-4">
        <div class="text-lg">{{ cfg.icon }}</div>
        <div>
          <div class="font-bold text-theme-primary">{{ cfg.label }}</div>
          <div class="text-[11px] text-theme-muted">{{ cfg.desc }}</div>
        </div>
        <span v-if="cfg.has_db_config"
              class="ml-auto px-2 py-0.5 rounded-sm text-[10px] bg-[var(--color-info-bg)] text-[var(--color-info)] border border-[var(--color-info-border)]">
          数据库已配置
        </span>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="text-[11px] text-theme-muted mb-1.5 block">API Key</label>
          <div class="relative">
            <input
              v-model="cfg.input_key"
              :type="cfg.show_key ? 'text' : 'password'"
              class="w-full bg-terminal-bg border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary
                     focus:outline-none focus:border-terminal-accent/60 pr-10"
              placeholder="sk-...">
            <button class="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-theme-muted hover:text-terminal-accent"
                    @click="cfg.show_key = !cfg.show_key">
              {{ cfg.show_key ? '🙈' : '👁' }}
            </button>
          </div>
        </div>
        <div>
          <label class="text-[11px] text-theme-muted mb-1.5 block">Base URL</label>
          <input
            v-model="cfg.input_base"
            class="w-full bg-terminal-bg border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary
                   focus:outline-none focus:border-terminal-accent/60"
            :placeholder="cfg.default_base">
        </div>
        <div class="col-span-2">
          <label class="text-[11px] text-theme-muted mb-1.5 block">模型名称</label>
          <div class="flex gap-3">
            <select
              v-model="cfg.input_model"
              class="flex-1 bg-terminal-bg border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary
                     focus:outline-none focus:border-terminal-accent/60 cursor-pointer">
              <option value="">-- 选择模型 --</option>
              <optgroup :label="group.label" v-for="group in cfg.modelGroups" :key="group.label">
                <option v-for="m in group.models" :key="m.id" :value="m.id">
                  {{ m.name }}
                </option>
              </optgroup>
            </select>
            <button class="text-[11px] text-theme-muted hover:text-terminal-accent px-2" @click="cfg.show_model_info = !cfg.show_model_info">
              {{ cfg.show_model_info ? '🔼 收起详情' : '🔽 查看详情' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 模型详情展开 -->
      <div v-if="cfg.show_model_info" class="mt-4 p-3 bg-terminal-bg/50 rounded-sm border border-theme/50">
        <div class="text-[11px] text-theme-muted mb-2">价格特点 & 金融适配性</div>
        <div class="grid grid-cols-3 gap-2 text-[10px]">
          <template v-for="group in cfg.modelGroups" :key="group.label">
            <template v-for="m in group.models" :key="m.id">
              <div v-if="m.id === cfg.input_model || !cfg.input_model" class="col-span-1 p-2 rounded-sm bg-terminal-panel/50">
                <div class="font-medium text-theme-primary">{{ m.name }}</div>
                <div class="text-terminal-accent mt-1">{{ m.pricing }}</div>
                <div class="text-theme-secondary mt-1">{{ m.finance }}</div>
                <div class="text-[var(--color-success)]/70 mt-1" v-if="m.best_for">{{ m.best_for }}</div>
              </div>
            </template>
          </template>
        </div>
      </div>

      <div class="flex gap-3 mt-4">
        <button
          class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm hover:bg-terminal-accent/25 transition-colors"
          :disabled="cfg.testing"
          @click="$emit('test', provider)">
          {{ cfg.testing ? '⏳ 测试中...' : '🔗 测试连接' }}
        </button>
        <button
          class="px-4 py-2 bg-terminal-accent rounded-sm text-sm text-theme-primary hover:bg-terminal-accent/80 transition-colors"
          :disabled="cfg.saving"
          @click="$emit('save', provider)">
          {{ cfg.saving ? '💾 保存中...' : '💾 保存全局配置' }}
        </button>
        <span v-if="cfg.message" class="flex items-center text-[11px]" :class="cfg.message_ok ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'">
          {{ cfg.message }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  providers: { type: Object, default: () => ({}) }
})

defineEmits(['refresh', 'test', 'save'])
</script>
