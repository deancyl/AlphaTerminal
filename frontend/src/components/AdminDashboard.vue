<template>
  <div class="flex h-full">
    <!-- 移动端遮罩 -->
    <div
      v-if="mobileNavOpen"
      class="fixed inset-0 bg-black/50 z-[9998] md:hidden"
      @click="mobileNavOpen = false"
    />
    <!-- 左侧导航 -->
    <aside
      class="border-r border-theme bg-terminal-panel flex-shrink-0 transition-all duration-300 z-[9999] md:relative fixed left-0 top-0 h-full"
      :class="mobileNavOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0 w-64'"
    >
      <div class="p-4 border-b border-theme flex items-center justify-between">
        <div>
          <span class="text-sm font-bold text-terminal-accent">⚙️ 系统管理</span>
          <div class="text-xs text-theme-muted mt-1">v{{ version }}</div>
        </div>
        <button class="md:hidden text-theme-secondary hover:text-theme-primary" @click="mobileNavOpen = false">✕</button>
      </div>
      <div class="px-4 py-2 text-xs text-[var(--color-warning)] bg-[var(--color-warning-bg)]/30">⚠️ 以下功能会影响系统运行，请谨慎操作</div>
      <nav class="py-2">
        <button
          v-for="item in navItems"
          :key="item.id"
          class="w-full flex items-center gap-3 px-4 py-3 text-sm transition-all text-left"
          :class="activeTab === item.id
            ? 'bg-terminal-accent/15 text-terminal-accent border-r-2 border-terminal-accent'
            : 'text-theme-secondary hover:bg-theme-hover hover:text-theme-primary'"
          @click="activeTab = item.id; mobileNavOpen = false"
        >
          <span class="text-base">{{ item.icon }}</span>
          <div class="flex-1">
            <div class="font-medium">{{ item.label }}</div>
            <div class="text-xs text-theme-muted leading-tight">{{ item.desc }}</div>
          </div>
          <span v-if="item.status" class="w-2 h-2 rounded-full flex-shrink-0" :class="item.statusClass"></span>
        </button>
      </nav>
    </aside>

    <!-- 右侧内容 -->
    <main class="flex-1 overflow-auto p-4 md:p-6">
      <!-- 移动端菜单按钮 -->
      <button
        class="md:hidden mb-4 flex items-center gap-2 px-3 py-2 rounded-sm bg-terminal-panel border border-theme-secondary text-theme-primary text-sm"
        @click="mobileNavOpen = true"
      >
        <span>☰</span> 菜单
      </button>

      <!-- 数据源控制 -->
      <div v-if="activeTab === 'sources'" class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-theme-primary">📡 数据源控制</h2>
            <p class="text-xs text-theme-muted mt-1">管理股票行情数据的来源，控制数据质量和系统稳定性</p>
          </div>
          <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="refreshSourceStatus">🔄 刷新状态</button>
        </div>

        <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
          <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 这个功能是做什么的？</h3>
          <p class="text-xs text-theme-secondary leading-relaxed">
            <strong class="text-terminal-accent">股票/基金/期货行情数据源</strong>：当获取实时行情时，后端自动选择最快的数据源。
            当前使用：<span class="text-[var(--color-warning)]">{{ probeData?.current_source || '-' }}</span>
            <br/>⭐ 主源 = 默认优先级 | ✓ 当前使用 = 实际被使用的
            <br/><strong class="text-[var(--color-warning)]">注意</strong>：此面板仅控制行情数据源，基金/宏观等模块使用独立数据源。
          </p>
        </div>

        <!-- 统一代理设置 -->
        <div class="p-4 bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] rounded-sm">
          <h3 class="text-sm font-bold text-[var(--color-warning)] mb-2">🌐 国外数据源代理设置</h3>
          <p class="text-xs text-theme-muted mb-3">AlphaVantage 等国外数据源需要代理才能访问。设置代理后重启服务生效。</p>
          <div class="flex gap-2">
            <input v-model="proxyUrl" type="text" placeholder="如: 192.168.1.50:7897" class="flex-1 bg-terminal-bg border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary" />
            <button @click="saveProxy" class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm">保存并重启</button>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div v-for="(source, key) in sourceStatus.sources" :key="key" class="p-4 rounded-sm border" :class="source.health === 'healthy' ? 'bg-[var(--color-success-bg)] border-[var(--color-success-border)]' : source.health === 'unknown' ? 'bg-[var(--color-info-bg)] border-[var(--color-info-border)]' : 'bg-[var(--color-danger-bg)] border-[var(--color-danger-border)]'">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-2">
                <span class="w-3 h-3 rounded-full" :class="source.state === 'closed' ? 'bg-[var(--color-success-light)]' : source.state === 'unknown' ? 'bg-[var(--color-info)]' : 'bg-[var(--color-danger-light)]'"></span>
                <span class="font-medium text-theme-primary">{{ key }}</span>
                <span v-if="source.is_primary" class="text-[10px] px-1.5 py-0.5 rounded-sm bg-[var(--color-warning)] text-black font-bold">⭐ 主源</span>
                <span v-if="probeData?.current_source === key" class="text-[10px] px-1.5 py-0.5 rounded-sm bg-[var(--color-success)] text-black font-bold">✓ 当前使用</span>
              </div>
              <span class="text-[10px] px-2 py-0.5 rounded-sm" :class="source.health === 'healthy' ? 'bg-[var(--color-success-bg)] text-[var(--color-success)]' : source.health === 'unknown' ? 'bg-[var(--color-info-bg)] text-[var(--color-info)]' : 'bg-[var(--color-danger-bg)] text-[var(--color-danger)]'">
                {{ source.health === 'healthy' ? '健康' : source.health === 'unknown' ? '未探测' : '异常' }}
              </span>
            </div>
            <div class="space-y-2 text-sm">
              <div class="flex justify-between"><span class="text-theme-muted">响应延迟</span><span :class="source.latency_ms === null ? 'text-theme-muted' : source.latency_ms < 100 ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]'">{{ source.latency_ms === null ? '-' : source.latency_ms + 'ms' }}</span></div>
              <div class="flex justify-between"><span class="text-theme-muted">连续失败</span><span :class="source.fail_count === 0 ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'">{{ source.fail_count }} 次</span></div>
            </div>
            <div class="flex gap-2 mt-4 pt-3 border-t border-theme/50">
              <button v-if="source.state !== 'open'" class="flex-1 px-3 py-1.5 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded-sm text-xs" @click="confirmAction(`熔断 ${key}`, `系统将停止从 ${key} 获取数据，转到其他数据源。确定？`, () => controlCircuit(key, 'open'))">⚠️ 熔断</button>
              <button v-if="source.state === 'open'" class="flex-1 px-3 py-1.5 bg-[var(--color-success-bg)] text-[var(--color-success)] rounded-sm text-xs" @click="confirmAction(`恢复 ${key}`, `系统将重新从 ${key} 获取数据。确定？`, () => controlCircuit(key, 'close'))">✅ 恢复</button>
            </div>
            <!-- 探测历史 -->
            <div class="mt-3 pt-3 border-t border-theme/50">
              <button @click="expandedHistory[key] = !expandedHistory[key]" class="text-[10px] text-theme-muted hover:text-theme-primary flex items-center gap-1">
                <span>{{ expandedHistory[key] ? '▼' : '▶' }}</span>
                <span>探测历史</span>
                <span v-if="source.history?.length">({{ source.history.length }})</span>
              </button>
              <div v-if="expandedHistory[key] && source.history?.length" class="mt-2 space-y-1">
                <div v-for="(h, i) in source.history.slice().reverse()" :key="i" class="flex items-center justify-between text-[10px]">
                  <span class="text-theme-muted">{{ formatHistoryTime(h.timestamp) }}</span>
                  <span :class="getHistoryStatusClass(h.status)">{{ h.status === 'ok' ? '✅' : h.status === 'fail' ? '❌' : h.status === 'timeout' ? '⏱️' : '⚠️' }}</span>
                  <span :class="getHistoryStatusClass(h.status)">{{ h.status === 'ok' ? h.latency + 'ms' : h.status }}</span>
                </div>
                <div v-if="!source.history?.length" class="text-[10px] text-theme-muted">暂无历史记录</div>
              </div>
            </div>
          </div>
        </div>

        <div class="p-3 bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] rounded-sm text-xs text-theme-muted">
          <strong class="text-[var(--color-warning)]">操作后果说明：</strong>
          <ul class="mt-1 space-y-1 list-disc list-inside">
            <li><strong>熔断</strong>：立即停止从该数据源获取数据，系统自动切换到其他可用源</li>
            <li><strong>恢复</strong>：重新启用该数据源，系统会尝试连接并检测其健康状态</li>
          </ul>
        </div>
      </div>

      <!-- 调度器控制 -->
      <div v-else-if="activeTab === 'scheduler'" class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-theme-primary">⏱️ 定时任务管理</h2>
            <p class="text-xs text-theme-muted mt-1">控制系统后台的自动数据更新任务</p>
          </div>
          <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="refreshScheduler">🔄 刷新</button>
        </div>

        <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
          <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 这个功能是做什么的？</h3>
          <p class="text-xs text-theme-secondary leading-relaxed">
            系统通过<strong class="text-terminal-accent">定时任务</strong>自动更新股票行情、板块数据、新闻快讯等。
            你可以暂停某个任务，或手动触发立即执行。
          </p>
        </div>

        <div class="space-y-3">
          <div v-for="job in schedulerJobs" :key="job.id" class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-3">
                <span class="w-2 h-2 rounded-full" :class="job.state === 'running' ? 'bg-[var(--color-success-light)] animate-pulse' : 'bg-yellow-400'"></span>
                <div>
                  <span class="font-medium text-theme-primary">{{ job.name }}</span>
                  <div class="text-[10px] text-theme-muted">{{ job.id }}</div>
                </div>
              </div>
              <div class="flex gap-2">
                <button v-if="job.state === 'running'" class="px-3 py-1.5 bg-[var(--color-warning-bg)] text-[var(--color-warning)] rounded-sm text-xs" @click="confirmAction(`暂停 ${job.name}`, `该任务将停止自动执行，相关数据不再更新。确定？`, () => controlJob(job.id, 'pause'))">⏸️ 暂停</button>
                <button v-else class="px-3 py-1.5 bg-[var(--color-success-bg)] text-[var(--color-success)] rounded-sm text-xs" @click="controlJob(job.id, 'resume')">▶️ 恢复</button>
                <button class="px-3 py-1.5 bg-[var(--color-info-bg)] text-[var(--color-info)] rounded-sm text-xs" @click="confirmAction(`立即执行 ${job.name}`, `立即执行一次该任务，不影响定时计划。确定？`, () => controlJob(job.id, 'trigger_now'))">⚡ 立即执行</button>
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

      <!-- 进程保活 -->
      <div v-else-if="activeTab === 'watchdog'" class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-theme-primary">🛡️ 进程保活监控</h2>
            <p class="text-xs text-theme-muted mt-1">监控后端进程健康状态，崩溃时自动重启</p>
          </div>
          <div class="flex items-center gap-2">
            <span v-if="watchdogLoading" class="text-xs text-theme-muted">加载中...</span>
            <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="refreshWatchdog">🔄 刷新状态</button>
          </div>
        </div>

        <!-- 错误提示 -->
        <div v-if="watchdogError" class="p-3 bg-[var(--color-danger-bg)] border border-[var(--color-danger-border)] rounded-sm text-xs text-[var(--color-danger)]">
          <strong>加载失败:</strong> {{ watchdogError }}
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
          <div class="p-4 rounded-sm border" :class="watchdogStatus.enabled ? 'bg-[var(--color-success-bg)] border-[var(--color-success-border)]' : 'bg-[var(--color-neutral-bg)] border-[var(--border-secondary)]'">
            <div class="flex items-center justify-between mb-3">
              <span class="font-medium text-theme-primary">保活开关</span>
              <span class="w-3 h-3 rounded-full" :class="watchdogStatus.enabled ? 'bg-[var(--color-success-light)] animate-pulse' : 'bg-gray-400'"></span>
            </div>
            <div class="text-2xl font-bold" :class="watchdogStatus.enabled ? 'text-[var(--color-success)]' : 'text-[var(--text-secondary)]'">
              {{ watchdogStatus.enabled ? '已启用' : '已禁用' }}
            </div>
            <div class="text-[10px] text-theme-muted mt-1">
              {{ watchdogStatus.enabled ? '后端崩溃时将自动重启' : '后端崩溃后需手动重启' }}
            </div>
            <div class="flex gap-2 mt-4 pt-3 border-t border-theme/50">
              <button v-if="!watchdogStatus.enabled" class="flex-1 px-3 py-1.5 bg-[var(--color-success-bg)] text-[var(--color-success)] rounded-sm text-xs" @click="toggleWatchdog(true)">✅ 启用保活</button>
              <button v-else class="flex-1 px-3 py-1.5 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded-sm text-xs" @click="toggleWatchdog(false)">⏹️ 禁用保活</button>
            </div>
          </div>

          <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">监控状态</div>
            <div class="text-xl font-bold" :class="watchdogStatus.running ? 'text-terminal-accent' : 'text-[var(--color-warning)]'">
              {{ watchdogStatus.running ? '运行中' : '未运行' }}
            </div>
            <div class="text-[10px] text-theme-muted mt-1">
              上次检查: {{ watchdogStatus.last_check ? formatTime(watchdogStatus.last_check) : '从未' }}
            </div>
          </div>

          <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">重启统计</div>
            <div class="text-xl font-bold" :class="watchdogStatus.total_restarts > 0 ? 'text-[var(--color-warning)]' : 'text-[var(--color-success)]'">
              {{ watchdogStatus.total_restarts }} 次
            </div>
            <div class="text-[10px] text-theme-muted mt-1">
              连续失败: {{ watchdogStatus.restart_count }}/3
            </div>
          </div>
        </div>

        <!-- 手动操作 -->
        <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
          <h3 class="text-sm font-bold text-theme-primary mb-4">紧急操作</h3>
          <div class="flex flex-wrap gap-3">
            <button class="px-4 py-2 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded-sm text-sm" @click="confirmAction('手动重启后端', '这将立即终止当前后端进程并启动新实例，所有连接将中断5-10秒。确定？', manualRestart)">🔄 手动重启后端</button>
            <button class="px-4 py-2 bg-[var(--color-info-bg)] text-[var(--color-info)] rounded-sm text-sm" @click="refreshWatchdog">📊 刷新状态</button>
          </div>
        </div>

        <!-- 最近错误 -->
        <div v-if="watchdogStatus.recent_errors && watchdogStatus.recent_errors.length > 0" class="p-4 bg-[var(--color-danger-bg)] border border-[var(--color-danger-border)] rounded-sm">
          <h3 class="text-sm font-bold text-[var(--color-danger)] mb-3">最近错误记录</h3>
          <div class="space-y-2 text-xs">
            <div v-for="(err, i) in watchdogStatus.recent_errors" :key="i" class="flex gap-3">
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

      <!-- 缓存管理 -->
      <div v-else-if="activeTab === 'cache'" class="space-y-6">
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
            <div class="text-xl font-bold text-terminal-accent">{{ cacheStatus.market || 5497 }}</div>
            <div class="text-[10px] text-theme-muted">只股票</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">板块数据缓存</div>
            <div class="text-xl font-bold text-terminal-accent">{{ cacheStatus.sectors || 20 }}</div>
            <div class="text-[10px] text-theme-muted">个板块</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">新闻缓存</div>
            <div class="text-xl font-bold text-terminal-accent">{{ cacheStatus.news || 150 }}</div>
            <div class="text-[10px] text-theme-muted">条快讯</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">数据库缓存</div>
            <div class="text-xl font-bold text-terminal-accent">{{ cacheStatus.db || 22 }}</div>
            <div class="text-[10px] text-theme-muted">条实时数据</div>
          </div>
        </div>

        <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
          <h3 class="text-sm font-bold text-theme-primary mb-4">缓存操作</h3>
          <div class="flex flex-wrap gap-3">
            <button class="px-4 py-2 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded-sm text-sm" @click="confirmAction('清空行情缓存', '清空后系统会重新从数据源获取，可能有短暂延迟。确定？', () => invalidateCache('market'))">🗑️ 清空行情缓存</button>
            <button class="px-4 py-2 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded-sm text-sm" @click="confirmAction('清空板块缓存', '板块列表可能需要几秒重新加载。确定？', () => invalidateCache('sectors'))">🗑️ 清空板块缓存</button>
            <button class="px-4 py-2 bg-[var(--color-info-bg)] text-[var(--color-info)] rounded-sm text-sm" @click="confirmAction('预热板块缓存', '提前加载板块数据，提升访问速度。确定？', () => warmupCache('sectors'))">🔥 预热板块缓存</button>
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

      <!-- 数据库管理 -->
      <div v-else-if="activeTab === 'database'" class="space-y-6">
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
            <div class="text-xl font-bold text-terminal-accent">{{ dbStatus.size || '12.5' }} MB</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">实时数据表</div>
            <div class="text-xl font-bold text-terminal-accent">{{ dbStatus.realtime || 22 }}</div>
            <div class="text-[10px] text-theme-muted">行</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">日K数据表</div>
            <div class="text-xl font-bold text-terminal-accent">{{ dbStatus.daily || 12500 }}</div>
            <div class="text-[10px] text-theme-muted">行</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">股票列表</div>
            <div class="text-xl font-bold text-terminal-accent">{{ dbStatus.stocks || 5497 }}</div>
            <div class="text-[10px] text-theme-muted">只</div>
          </div>
        </div>

        <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
          <h3 class="text-sm font-bold text-theme-primary mb-4">数据库维护</h3>
          <div class="flex flex-wrap gap-3">
            <button class="px-4 py-2 bg-terminal-accent/20 text-terminal-accent rounded-sm text-sm" @click="confirmAction('VACUUM 优化', '重组数据库文件，释放空间，优化性能。可能需要几秒到几分钟。确定？', () => dbMaintenance('vacuum'))">🔧 VACUUM 优化</button>
            <button class="px-4 py-2 bg-[var(--color-info-bg)] text-[var(--color-info)] rounded-sm text-sm" @click="confirmAction('ANALYZE 分析', '分析表结构，更新查询优化器统计信息。操作快速安全。确定？', () => dbMaintenance('analyze'))">📊 ANALYZE 分析</button>
            <button class="px-4 py-2 bg-[var(--color-success-bg)] text-[var(--color-success)] rounded-sm text-sm" @click="confirmAction('WAL 检查点', '把内存日志写入磁盘，确保数据持久化。安全快速。确定？', () => dbMaintenance('wal_checkpoint'))">💾 WAL检查点</button>
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

      <!-- 系统监控 -->
      <div v-else-if="activeTab === 'monitor'" class="space-y-6">
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-bold text-theme-primary">📊 系统监控</h2>
          <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="refreshSystemMetrics">🔄 刷新</button>
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
            <div class="text-2xl font-bold" :class="getCpuColor(systemMetrics.cpu_percent)">{{ systemMetrics.cpu_percent?.toFixed(1) || 0 }}%</div>
            <div class="text-[10px] text-theme-muted mt-1">{{ getCpuStatus(systemMetrics.cpu_percent) }}</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">内存使用</div>
            <div class="text-2xl font-bold" :class="getMemoryColor(systemMetrics.memory?.percent)">{{ systemMetrics.memory?.percent?.toFixed(1) || 0 }}%</div>
            <div class="text-[10px] text-theme-muted mt-1">{{ systemMetrics.memory?.used_gb?.toFixed(1) || 0 }} / {{ systemMetrics.memory?.total_gb?.toFixed(1) || 0 }} GB</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">磁盘使用</div>
            <div class="text-2xl font-bold" :class="getDiskColor(systemMetrics.disk?.percent)">{{ systemMetrics.disk?.percent?.toFixed(1) || 0 }}%</div>
            <div class="text-[10px] text-theme-muted mt-1">{{ systemMetrics.disk?.used_gb?.toFixed(1) || 0 }} / {{ systemMetrics.disk?.total_gb?.toFixed(1) || 0 }} GB</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">后端进程内存</div>
            <div class="text-2xl font-bold text-terminal-accent">{{ systemMetrics.process?.memory_mb?.toFixed(0) || 0 }} MB</div>
            <div class="text-[10px] text-theme-muted mt-1">{{ systemMetrics.process?.threads || 0 }} 线程</div>
          </div>
        </div>

        <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
          <h3 class="text-sm font-bold text-theme-primary mb-3">🌐 网络状态</h3>
          <div class="grid grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
            <div><span class="text-theme-muted">活跃连接：</span><span class="text-terminal-accent font-bold">{{ systemMetrics.network?.connections || 0 }}</span></div>
            <div><span class="text-theme-muted">发送数据：</span><span class="text-theme-secondary">{{ formatBytes(systemMetrics.network?.io_counters?.bytes_sent) }}</span></div>
            <div><span class="text-theme-muted">接收数据：</span><span class="text-theme-secondary">{{ formatBytes(systemMetrics.network?.io_counters?.bytes_recv) }}</span></div>
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

      <!-- 数据源健康度仪表盘 -->
      <div v-else-if="activeTab === 'source-health'" class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-theme-primary">📡 数据源健康度</h2>
            <p class="text-xs text-theme-muted mt-1">实时监测各数据源连通性与响应速度</p>
          </div>
          <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="refreshSourceHealth">🔄 刷新状态</button>
        </div>

        <!-- 代理配置 -->
        <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
          <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">🌐 代理配置</h3>
          <div v-if="proxyConfig" class="mt-2 flex items-center gap-4 text-xs">
            <div class="flex items-center gap-2">
              <span class="text-theme-muted">代理地址：</span>
              <span class="text-terminal-accent font-mono">{{ proxyConfig.proxy_url || '未配置' }}</span>
            </div>
            <span class="px-2 py-0.5 rounded-sm text-[10px]" :class="proxyConfig.enabled ? 'bg-[var(--color-success-bg)] text-[var(--color-success)]' : 'bg-[var(--color-neutral-bg)] text-[var(--text-secondary)]'">
              {{ proxyConfig.enabled ? '● 已启用' : '○ 已禁用' }}
            </span>
          </div>
        </div>

        <!-- 饼图 + 卡片 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- ECharts 饼图 -->
          <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="text-sm font-bold text-theme-primary mb-3">📊 数据源可用性</div>
            <div ref="sourceChartRef" style="width:100%;height:220px"></div>
          </div>
          <!-- 状态列表 -->
          <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
            <div class="text-sm font-bold text-theme-primary mb-3">🔍 各源详情</div>
            <div class="space-y-2">
              <div v-for="(info, key) in sourceHealthData" :key="key" class="flex items-center justify-between p-2 rounded-sm bg-terminal-panel/50">
                <div class="flex items-center gap-2">
                  <span class="w-2.5 h-2.5 rounded-full" :class="info.status === 'ok' ? 'bg-[var(--color-success-light)]' : info.status === 'slow' ? 'bg-yellow-400' : 'bg-[var(--color-danger-light)]'"></span>
                  <span class="text-sm text-theme-primary">{{ key }}</span>
                </div>
                <div class="flex items-center gap-3 text-xs">
                  <span class="text-theme-muted">{{ info.latency_ms || 0 }}ms</span>
                  <span class="px-1.5 py-0.5 rounded-sm text-[10px]" :class="info.status === 'ok' ? 'bg-[var(--color-success-bg)] text-[var(--color-success)]' : info.status === 'slow' ? 'bg-[var(--color-warning-bg)] text-[var(--color-warning)]' : 'bg-[var(--color-danger-bg)] text-[var(--color-danger)]'">
                    {{ info.status === 'ok' ? '正常' : info.status === 'slow' ? '缓慢' : '异常' }}
                  </span>
                </div>
              </div>
              <div v-if="!Object.keys(sourceHealthData).length" class="text-center text-theme-muted text-xs py-4">暂无数据</div>
            </div>
          </div>
        </div>
      </div>

      <!-- LLM 配置 -->
      <div v-else-if="activeTab === 'llm'" class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-theme-primary">🤖 模型服务配置</h2>
            <p class="text-xs text-theme-muted mt-1">配置 LLM API Key 和 Base URL，数据库配置优先于 .env</p>
          </div>
          <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="loadLlmConfig">🔄 刷新</button>
        </div>

        <div v-for="(cfg, provider) in llmProviders" :key="provider"
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
              @click="testLlmConnection(provider)">
              {{ cfg.testing ? '⏳ 测试中...' : '🔗 测试连接' }}
            </button>
            <button
              class="px-4 py-2 bg-terminal-accent rounded-sm text-sm text-theme-primary hover:bg-terminal-accent/80 transition-colors"
              :disabled="cfg.saving"
              @click="saveLlmConfig(provider)">
              {{ cfg.saving ? '💾 保存中...' : '💾 保存全局配置' }}
            </button>
            <span v-if="cfg.message" class="flex items-center text-[11px]" :class="cfg.message_ok ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'">
              {{ cfg.message }}
            </span>
          </div>
        </div>
      </div>

      <div v-else-if="activeTab === 'logs'" class="space-y-6">
        <div class="flex items-center justify-between">          <div>            <h2 class="text-lg font-bold text-theme-primary">📝 日志查看</h2>            <p class="text-xs text-theme-muted">查看系统运行日志和错误信息</p>          </div>          <div class="flex gap-2">            <select v-model="logLevel" class="px-3 py-2 bg-terminal-panel border border-theme rounded-sm text-sm">              <option value="ALL">全部级别</option>              <option value="ERROR">ERROR</option>              <option value="WARNING">WARNING</option>              <option value="INFO">INFO</option>              <option value="DEBUG">DEBUG</option>            </select>            <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="refreshLogs">🔄 刷新</button>          </div>        </div>        <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">          <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 这个功能是做什么的？</h3>          <p class="text-xs text-theme-secondary leading-relaxed">            显示系统的<strong class="text-terminal-accent">运行日志</strong>，包括数据更新记录、错误信息等。当系统异常时，可通过日志排查问题。          </p>        </div>        <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme h-96 overflow-auto font-mono text-xs" ref="logContainer">          <div v-if="logs.length === 0" class="text-theme-muted text-center py-8">            <div class="text-2xl mb-2">📭</div>            <div>暂无日志数据</div>            <div class="mt-2 text-[10px]">点击刷新按钮加载日志</div>          </div>          <div v-else class="space-y-1">            <div v-for="(log, i) in filteredLogs" :key="i" class="break-all">              <span class="text-theme-muted">{{ formatTime(log.timestamp) }}</span>              <span class="px-1.5 py-0.5 rounded-sm text-[10px] ml-2" :class="getLogLevelClass(log.level)">{{ log.level }}</span>              <span class="text-theme-secondary ml-2">{{ log.message }}</span>            </div>          </div>        </div>        <div class="p-3 bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] rounded-sm text-xs text-theme-muted">          <strong class="text-[var(--color-warning)]">日志级别说明：</strong>          <ul class="mt-1 space-y-1 list-disc list-inside">            <li><strong>DEBUG</strong>：详细的调试信息，开发时使用</li>            <li><strong>INFO</strong>：常规运行信息，如数据更新成功</li>            <li><strong>WARNING</strong>：警告信息，如数据源响应慢</li>            <li><strong>ERROR</strong>：错误信息，需要关注</li>          </ul>        </div>      </div>

    </main>

    <!-- 确认对话框 -->
    <div v-if="showConfirm" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-terminal-panel border border-theme rounded-sm p-6 max-w-md w-full mx-4">
        <h3 class="text-lg font-bold text-theme-primary mb-2">⚠️ 确认操作</h3>
        <p class="text-sm text-theme-secondary mb-4">{{ confirmMessage }}</p>
        <div class="flex gap-3 justify-end">
          <button
            class="px-4 py-2 bg-theme-secondary/50 text-theme-secondary rounded-sm text-sm cursor-not-allowed"
            :class="{ 'opacity-50': isSubmitting }"
            :disabled="isSubmitting"
            @click="showConfirm = false"
          >取消</button>
          <button
            class="px-4 py-2 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded-sm text-sm"
            :class="{ 'opacity-50 cursor-not-allowed': isSubmitting }"
            :disabled="isSubmitting"
            @click="executeConfirm"
          >
            <span v-if="isSubmitting">执行中...</span>
            <span v-else>确定执行</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, watch, computed } from 'vue'
// ECharts 通过 CDN 加载，使用全局变量
const echarts = window.echarts
import { logger } from '../utils/logger.js'
import { apiFetch } from '../utils/api.js'
import { toast } from '../composables/useToast.js'

const version = __APP_VERSION__
const activeTab = ref('sources')
const mobileNavOpen = ref(false)
const logContainer = ref(null)
const proxyUrl = ref('')
const expandedHistory = ref({})
const probeData = ref(null)

const navItems = [
  { id: 'sources', label: '数据源', desc: '控制行情数据来源的熔断和恢复', icon: '📡', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'source-health', label: '源健康度', desc: '数据源连通性监测与ECharts可视化', icon: '📊', status: false, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'scheduler', label: '定时任务', desc: '管理自动数据更新任务的启停', icon: '⏱️', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'watchdog', label: '进程保活', desc: '监控后端进程状态，自动重启', icon: '🛡️', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'cache', label: '缓存管理', desc: '清理和预热系统数据缓存', icon: '💾', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'database', label: '数据库', desc: 'SQLite数据库维护和优化', icon: '🗄️', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'monitor', label: '系统监控', desc: '查看服务器CPU内存等资源使用', icon: '📊', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'llm', label: '模型配置', desc: 'LLM API Key 和连接配置', icon: '🤖', status: true, statusClass: 'bg-[var(--color-success-light)]' },
  { id: 'logs', label: '日志查看', desc: '查看系统运行日志和错误信息', icon: '📝', status: false, statusClass: 'bg-gray-400' },
]

const showConfirm = ref(false)
const confirmMessage = ref('')
const confirmCallback = ref(null)
const isSubmitting = ref(false)

function confirmAction(title, message, callback) {
  confirmMessage.value = message
  confirmCallback.value = callback
  showConfirm.value = true
}

async function executeConfirm() {
  if (!confirmCallback.value) return
  if (isSubmitting.value) return  // 防止重复提交
  isSubmitting.value = true
  try {
    await confirmCallback.value()
  } finally {
    isSubmitting.value = false
    showConfirm.value = false
  }
}

function formatTime(isoTime) {
  if (!isoTime) return null
  const date = new Date(isoTime)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

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

const sourceStatus = reactive({
  sources: {
    tencent: { state: 'unknown', fail_count: 0, latency_ms: null, health: 'unknown', description: '腾讯财经 - 主数据源' },
    sina_kline: { state: 'unknown', fail_count: 0, latency_ms: null, health: 'unknown', description: '新浪K线 - 备用源' },
    sina: { state: 'unknown', fail_count: 0, latency_ms: null, health: 'unknown', description: '新浪财经 - 备用源' },
    eastmoney: { state: 'unknown', fail_count: 0, latency_ms: null, health: 'unknown', description: '东方财富 - 备用源' },
    tencent_hk: { state: 'unknown', fail_count: 0, latency_ms: null, health: 'unknown', description: '腾讯港股 - 备用源' },
    alpha_vantage: { state: 'unknown', fail_count: 0, latency_ms: null, health: 'unknown', description: 'AlphaVantage - 美股源' }
  }
})

const schedulerJobs = ref([])  // 启动后从后端加载（支持 SQLite 持久化）

const cacheStatus = reactive({ market: 5497, sectors: 20, news: 150, db: 22 })
const dbStatus = reactive({ size: '12.5', realtime: 22, daily: 12500, stocks: 5497 })

const systemMetrics = reactive({
  cpu_percent: 5.4,
  memory: { percent: 56.2, used_gb: 4.3, total_gb: 7.65 },
  disk: { percent: 29.0, used_gb: 17.22, total_gb: 62.6 },
  process: { memory_mb: 167, threads: 12 },
  network: { connections: 471, io_counters: { bytes_sent: 74188244056, bytes_recv: 82540093634 } }
})

// ── LLM 配置 ──────────────────────────────────────────────────────────
const llmProviders = reactive({
  deepseek: {
    label: 'DeepSeek', icon: '🧠', desc: 'DeepSeek-V3 / DeepSeek-R1',
    default_base: 'https://api.deepseek.com', default_model: 'deepseek-chat',
    api_key: '', base_url: '', model: '', has_db_config: false,
    input_key: '', input_base: '', input_model: '',
    show_key: false, saving: false, testing: false, message: '', message_ok: false,
    show_model_info: false,
    modelGroups: [
      {
        label: '💬 对话模型 (Chat)',
        models: [
          { id: 'deepseek-chat', name: 'DeepSeek V3', pricing: '¥2-6/百万Token', finance: '金融分析强，逻辑推理优秀，支持长上下文32K' },
          { id: 'deepseek-reasoner', name: 'DeepSeek R1', pricing: '¥16-32/百万Token', finance: '深度推理能力强，适合复杂金融决策场景' },
        ]
      },
      {
        label: '🔧 专用模型',
        models: [
          { id: 'deepseek-coder', name: 'DeepSeek Coder', pricing: '¥2-6/百万Token', finance: '代码能力突出，可辅助量化策略开发' },
        ]
      }
    ],
  },
  qianwen: {
    label: '通义千问', icon: '🌐', desc: 'Qwen Plus / Max / VL',
    default_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1', default_model: 'qwen-plus',
    api_key: '', base_url: '', model: '', has_db_config: false,
    input_key: '', input_base: '', input_model: '',
    show_key: false, saving: false, testing: false, message: '', message_ok: false,
    show_model_info: false,
    modelGroups: [
      {
        label: '💬 对话模型 (Chat)',
        models: [
          { id: 'qwen-plus', name: 'Qwen Plus', pricing: '¥0.04-0.12/千Token', finance: '中文理解强，股市新闻分析速度快' },
          { id: 'qwen-max', name: 'Qwen Max', pricing: '¥0.2-0.6/千Token', finance: '旗舰模型，金融研报综合分析能力强' },
          { id: 'qwen-turbo', name: 'Qwen Turbo', pricing: '¥0.015-0.045/千Token', finance: '快速响应，适合实时行情解读' },
        ]
      },
      {
        label: '👁️ 视觉模型 (VL)',
        models: [
          { id: 'qwen-vl-plus', name: 'Qwen VL Plus', pricing: '¥0.06-0.18/千Token', finance: '可解析K线图、财报图片等视觉信息' },
        ]
      }
    ],
  },
  openai: {
    label: 'OpenAI', icon: '🤖', desc: 'GPT-3.5 / GPT-4 / GPT-4o',
    default_base: 'https://api.openai.com/v1', default_model: 'gpt-3.5-turbo',
    api_key: '', base_url: '', model: '', has_db_config: false,
    input_key: '', input_base: '', input_model: '',
    show_key: false, saving: false, testing: false, message: '', message_ok: false,
    show_model_info: false,
    modelGroups: [
      {
        label: '💬 对话模型 (Chat)',
        models: [
          { id: 'gpt-4o', name: 'GPT-4o', pricing: '$6-18/百万Token', finance: '综合能力最强，多模态支持好，国际市场分析首选' },
          { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', pricing: '$10-30/百万Token', finance: '上下文128K，适合长篇金融报告分析' },
          { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', pricing: '$0.5-1.5/百万Token', finance: '低成本快速响应，适合简单行情查询' },
        ]
      },
      {
        label: '🎨 视觉模型 (Vision)',
        models: [
          { id: 'gpt-4o-mini', name: 'GPT-4o Mini', pricing: '$0.15-0.6/百万Token', finance: '性价比高，轻量级图表解析' },
        ]
      }
    ],
  },
  siliconflow: {
    label: '硅基流动', icon: '💎', desc: 'SiliconFlow - DeepSeek/Qwen 等模型聚合平台',
    default_base: 'https://api.siliconflow.cn/v1', default_model: 'deepseek-ai/DeepSeek-V3',
    api_key: '', base_url: '', model: '', has_db_config: false,
    input_key: '', input_base: '', input_model: '',
    show_key: false, saving: false, testing: false, message: '', message_ok: false,
    show_model_info: false,
    modelGroups: [
      {
        label: '🔥 热门模型',
        models: [
          { id: 'deepseek-ai/DeepSeek-V3', name: 'DeepSeek V3 (SF)', pricing: '¥1-3/百万Token', finance: '性价比极高，金融分析首选', best_for: '⭐ 性价比之选' },
          { id: 'deepseek-ai/DeepSeek-R1', name: 'DeepSeek R1 (SF)', pricing: '¥6-18/百万Token', finance: '深度推理强，复杂量化策略分析' },
          { id: 'Qwen/Qwen2.5-72B-Instruct', name: 'Qwen2.5-72B', pricing: '¥2-8/百万Token', finance: '中文理解出色，财报解读快速' },
        ]
      },
      {
        label: '🆓 Free模型 (硅基流动)',
        models: [
          { id: 'Pro/Qwen2.5-7B-Instruct', name: 'Qwen2.5-7B (Free)', pricing: '🆓 免费', finance: '免费额度充足，日常行情分析完全够用', best_for: '⭐ 免费首选' },
          { id: 'Pro/Qwen2.5-14B-Instruct', name: 'Qwen2.5-14B (Free)', pricing: '🆓 免费', finance: '更强理解力，复杂财经新闻解读' },
          { id: 'Pro/deepseek-ai/DeepSeek-V3', name: 'DeepSeek V3 (Free)', pricing: '🆓 免费', finance: '免费版DeepSeek V3，金融分析无压力' },
          { id: 'Pro/THUDM/glm-4-flash', name: 'GLM-4-Flash (Free)', pricing: '🆓 免费', finance: '极速响应，实时K线解读无延迟' },
          { id: 'Pro/Qwen/Qwen2.5-32B-Instruct', name: 'Qwen2.5-32B (Free)', pricing: '🆓 免费', finance: '中等规模，完全免费，财报分析' },
        ]
      },
      {
        label: '💰 低价模型',
        models: [
          { id: 'THUDM/glm-4-flash', name: 'GLM-4-Flash', pricing: '¥0.1-0.3/百万Token', finance: '超低价格，适合高频行情查询' },
          { id: 'Qwen/Qwen2.5-7B-Instruct', name: 'Qwen2.5-7B', pricing: '¥0.3-1/百万Token', finance: '轻量快速，实时K线解读' },
        ]
      }
    ],
  },
  opencode_go: {
    label: 'OpenCode Go', icon: '🚀', desc: 'OpenCode Go - 开源编程模型订阅服务（首月$5，之后$10/月）',
    default_base: 'https://opencode.ai/zen/go/v1', default_model: 'opencode-go/minimax-m2.7',
    api_key: '', base_url: '', model: '', has_db_config: false,
    input_key: '', input_base: '', input_model: '',
    show_key: false, saving: false, testing: false, message: '', message_ok: false,
    show_model_info: false,
    modelGroups: [
      {
        label: '🤖 旗舰模型',
        models: [
          { id: 'opencode-go/glm-5.1', name: 'GLM-5.1', pricing: '$10/月订阅', finance: '最新旗舰，开源最强编程模型' },
          { id: 'opencode-go/glm-5', name: 'GLM-5', pricing: '$10/月订阅', finance: '高性能开源编程模型' },
          { id: 'opencode-go/kimi-k2.6', name: 'Kimi K2.6', pricing: '$10/月订阅', finance: 'Kimi旗舰，开源编程能力强' },
          { id: 'opencode-go/kimi-k2.5', name: 'Kimi K2.5', pricing: '$10/月订阅', finance: '高性价比，编程任务首选' },
        ]
      },
      {
        label: '🔵 MiniMax 系列',
        models: [
          { id: 'opencode-go/minimax-m2.7', name: 'MiniMax M2.7', pricing: '$10/月订阅', finance: '当前模型，高性能低成本', best_for: '⭐ 推荐' },
          { id: 'opencode-go/minimax-m2.5', name: 'MiniMax M2.5', pricing: '$10/月订阅', finance: '最高请求额度，约3.3万次/月', best_for: '⭐ 高频使用首选' },
        ]
      },
      {
        label: '💚 Qwen 系列',
        models: [
          { id: 'opencode-go/qwen3.6-plus', name: 'Qwen3.6 Plus', pricing: '$10/月订阅', finance: '中文理解强，约1.6万次/月' },
          { id: 'opencode-go/qwen3.5-plus', name: 'Qwen3.5 Plus', pricing: '$10/月订阅', finance: '最高请求额度，约5万次/月', best_for: '⭐ 最高性价比' },
        ]
      },
      {
        label: '🔷 MiMo 系列',
        models: [
          { id: 'opencode-go/mimo-v2.5', name: 'MiMo-V2.5', pricing: '$10/月订阅', finance: '高请求额度，约1万次/月' },
          { id: 'opencode-go/mimo-v2-pro', name: 'MiMo-V2-Pro', pricing: '$10/月订阅', finance: '编程能力强' },
          { id: 'opencode-go/mimo-v2-omni', name: 'MiMo-V2-Omni', pricing: '$10/月订阅', finance: '全能型，高请求额度' },
          { id: 'opencode-go/mimo-v2.5-pro', name: 'MiMo-V2.5-Pro', pricing: '$10/月订阅', finance: '专业版编程模型' },
        ]
      },
      {
        label: '🟣 DeepSeek 系列',
        models: [
          { id: 'opencode-go/deepseek-v4-pro', name: 'DeepSeek V4 Pro', pricing: '$10/月订阅', finance: '高性能推理，约1.7万次/月' },
          { id: 'opencode-go/deepseek-v4-flash', name: 'DeepSeek V4 Flash', pricing: '$10/月订阅', finance: '最高请求额度，约15.8万次/月', best_for: '⭐ 超高频首选' },
        ]
      },
    ],
  },
  opencode_zen: {
    label: 'OpenCode Zen', icon: '⚡', desc: 'OpenCode Zen - 精选模型付费网关（含大量免费额度）',
    default_base: 'https://opencode.ai/zen/v1', default_model: 'opencode/minimax-m2.7',
    api_key: '', base_url: '', model: '', has_db_config: false,
    input_key: '', input_base: '', input_model: '',
    show_key: false, saving: false, testing: false, message: '', message_ok: false,
    show_model_info: false,
    modelGroups: [
      {
        label: '🆓 免费模型 (Zen)',
        models: [
          { id: 'opencode/big-pickle', name: 'Big Pickle', pricing: '🆓 完全免费', finance: '限时免费，隐身模型，日常分析首选', best_for: '⭐ 完全免费首选' },
          { id: 'opencode/minimax-m2.5-free', name: 'MiniMax M2.5 Free', pricing: '🆓 免费', finance: '限时免费，国产高性能模型' },
          { id: 'opencode/ling-2.6-flash', name: 'Ling 2.6 Flash', pricing: '🆓 免费', finance: '限时免费，极速响应' },
          { id: 'opencode/hy3-preview-free', name: 'Hy3 Preview', pricing: '🆓 免费', finance: '限时免费，预览版本' },
          { id: 'opencode/nemotron-3-super-free', name: 'Nemotron 3 Super', pricing: '🆓 免费', finance: 'NVIDIA提供，免费额度' },
          { id: 'opencode/gpt-5-nano', name: 'GPT-5 Nano', pricing: '🆓 免费', finance: 'OpenAI免费模型，轻量快速' },
        ]
      },
      {
        label: '💬 GPT-5 系列 (Zen)',
        models: [
          { id: 'opencode/gpt-5.5', name: 'GPT 5.5', pricing: '$5-45/百万Token', finance: '最新旗舰，≤272K: $5 in/$30 out', best_for: '⭐ 综合最强' },
          { id: 'opencode/gpt-5.5-pro', name: 'GPT 5.5 Pro', pricing: '$30-180/百万Token', finance: 'GPT-5.5专业版，性能最强' },
          { id: 'opencode/gpt-5.4', name: 'GPT 5.4', pricing: '$2.5-22.5/百万Token', finance: '≤272K: $2.5 in/$15 out，高性价比' },
          { id: 'opencode/gpt-5.4-pro', name: 'GPT 5.4 Pro', pricing: '$30-180/百万Token', finance: 'GPT-5.4专业版' },
          { id: 'opencode/gpt-5.4-mini', name: 'GPT 5.4 Mini', pricing: '$0.75-4.5/百万Token', finance: '轻量高性价比，日常分析首选' },
          { id: 'opencode/gpt-5.4-nano', name: 'GPT 5.4 Nano', pricing: '$0.2-1.25/百万Token', finance: '超低成本，简单查询' },
          { id: 'opencode/gpt-5.3-codex-spark', name: 'GPT 5.3 Codex Spark', pricing: '$1.75-14/百万Token', finance: '代码能力增强版' },
          { id: 'opencode/gpt-5.3-codex', name: 'GPT 5.3 Codex', pricing: '$1.75-14/百万Token', finance: '代码专用模型' },
          { id: 'opencode/gpt-5.2', name: 'GPT 5.2', pricing: '$1.75-14/百万Token', finance: '高性能代码模型' },
          { id: 'opencode/gpt-5.1', name: 'GPT 5.1', pricing: '$1.07-8.5/百万Token', finance: '稳定版代码模型' },
          { id: 'opencode/gpt-5', name: 'GPT 5', pricing: '$1.07-8.5/百万Token', finance: '基础版GPT-5' },
        ]
      },
      {
        label: '🧠 Claude 系列 (Zen)',
        models: [
          { id: 'opencode/claude-opus-4-7', name: 'Claude Opus 4.7', pricing: '$5-25/百万Token', finance: '最强推理，复杂金融决策', best_for: '⭐ 推理最强' },
          { id: 'opencode/claude-opus-4-6', name: 'Claude Opus 4.6', pricing: '$5-25/百万Token', finance: '旗舰推理模型' },
          { id: 'opencode/claude-opus-4-5', name: 'Claude Opus 4.5', pricing: '$5-25/百万Token', finance: '高性能推理' },
          { id: 'opencode/claude-opus-4-1', name: 'Claude Opus 4.1', pricing: '$15-75/百万Token', finance: '超长上下文推理' },
          { id: 'opencode/claude-sonnet-4-6', name: 'Claude Sonnet 4.6', pricing: '$3-15/百万Token', finance: '平衡之选，代码分析兼备' },
          { id: 'opencode/claude-sonnet-4-5', name: 'Claude Sonnet 4.5', pricing: '$3-15/百万Token', finance: '≤200K: $3 in/$15 out' },
          { id: 'opencode/claude-haiku-4-5', name: 'Claude Haiku 4.5', pricing: '$1-5/百万Token', finance: '快速响应，实时行情解读' },
        ]
      },
      {
        label: '🌟 Gemini 系列 (Zen)',
        models: [
          { id: 'opencode/gemini-3.1-pro', name: 'Gemini 3.1 Pro', pricing: '$2-18/百万Token', finance: '≤200K: $2 in/$12 out，上下文128K' },
          { id: 'opencode/gemini-3-flash', name: 'Gemini 3 Flash', pricing: '$0.5-3/百万Token', finance: '快速低价，实时K线解读' },
        ]
      },
      {
        label: '🇨🇳 国产模型 (Zen)',
        models: [
          { id: 'opencode/minimax-m2.7', name: 'MiniMax M2.7', pricing: '$0.30-1.2/百万Token', finance: '当前模型，高性能低成本' },
          { id: 'opencode/minimax-m2.5', name: 'MiniMax M2.5', pricing: '$0.30-1.2/百万Token', finance: '高性价比，国产首选' },
          { id: 'opencode/qwen3.6-plus', name: 'Qwen3.6 Plus', pricing: '$0.50-3/百万Token', finance: '中文理解强，财报解读' },
          { id: 'opencode/qwen3.5-plus', name: 'Qwen3.5 Plus', pricing: '$0.20-1.2/百万Token', finance: '高性价比，中文场景' },
          { id: 'opencode/kimi-k2.6', name: 'Kimi K2.6', pricing: '$0.95-4/百万Token', finance: '长上下文优秀，旗舰模型' },
          { id: 'opencode/kimi-k2.5', name: 'Kimi K2.5', pricing: '$0.60-3/百万Token', finance: '高性价比，编程能力强' },
          { id: 'opencode/glm-5.1', name: 'GLM-5.1', pricing: '$1.40-4.4/百万Token', finance: '国产旗舰，开源最强编程模型' },
          { id: 'opencode/glm-5', name: 'GLM-5', pricing: '$1.00-3.2/百万Token', finance: '国产高性能，开源模型' },
        ]
      },
    ],
  },
})

async function loadLlmConfig() {
  try {
    const res = await fetch('/api/v1/admin/settings/llm')
    const json = await res.json()
    if (json.code !== 0) return
    for (const [p, data] of Object.entries(json.data)) {
      const cfg = llmProviders[p]
      if (!cfg) continue
      cfg.api_key  = data.api_key || ''
      cfg.base_url = data.base_url || cfg.default_base
      cfg.model    = data.model || cfg.default_model
      cfg.has_db_config = data.has_db_config || false
      cfg.input_key  = data.api_key || ''
      cfg.input_base = data.base_url || cfg.default_base
      cfg.input_model = data.model || cfg.default_model
      cfg.message = ''
    }
  } catch (e) { console.error('[Admin] loadLlmConfig:', e) }
}

async function saveLlmConfig(provider) {
  const cfg = llmProviders[provider]
  cfg.saving = true; cfg.message = ''
  try {
    const res = await fetch('/api/v1/admin/settings/llm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, api_key: cfg.input_key, base_url: cfg.input_base, model: cfg.input_model }),
    })
    const json = await res.json()
    if (json.code === 0) {
      cfg.has_db_config = true; cfg.api_key = cfg.input_key; cfg.base_url = cfg.input_base; cfg.model = cfg.input_model
      cfg.message = '✅ 已保存'; cfg.message_ok = true
      setTimeout(() => { cfg.message = '' }, 4000)
    } else { cfg.message = '❌ ' + (json.error || '保存失败'); cfg.message_ok = false }
  } catch (e) { cfg.message = '❌ ' + e.message; cfg.message_ok = false }
  finally { cfg.saving = false }
}

async function testLlmConnection(provider) {
  const cfg = llmProviders[provider]
  if (!cfg.input_key) { cfg.message = '⚠️ 请先输入 API Key'; return }
  cfg.testing = true; cfg.message = ''
  try {
    const res = await fetch('/api/v1/admin/settings/llm/test', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, api_key: cfg.input_key, base_url: cfg.input_base, model: cfg.input_model }),
    })
    const json = await res.json()
    cfg.message = json.code === 0 ? '✅ 连接成功' : '❌ ' + (json.error || '连接失败')
    cfg.message_ok = json.code === 0
    setTimeout(() => { cfg.message = '' }, 6000)
  } catch (e) { cfg.message = '❌ ' + e.message; cfg.message_ok = false }
  finally { cfg.testing = false }
}

loadLlmConfig()

// ── 数据源健康度 ──────────────────────────────────────────────────
const sourceChartRef = ref(null)
const sourceHealthData = ref({})
const proxyConfig = ref(null)
let sourceChart = null

async function refreshSourceHealth() {
  try {
    const [statusData, configData] = await Promise.all([
      apiFetch('/api/v1/admin/sources/status'),
      apiFetch('/api/v1/admin/data-sources'),
    ])
    // 转换后端数据格式为前端所需
    const sources = statusData?.data?.sources || statusData?.sources || {}
    const converted = {}
    for (const [key, info] of Object.entries(sources)) {
      converted[key] = {
        status: info.status === 'ok' ? 'ok' : info.status === 'slow' ? 'slow' : 'error',
        latency_ms: info.latency || 0,
        fail_count: info.fail_count || 0,
      }
    }
    sourceHealthData.value = converted
    proxyConfig.value = configData?.data || configData || {}

    // 更新 ECharts 饼图
    updateSourceChart(converted)
  } catch (e) {
    logger.error('[SourceHealth] refresh failed:', e)
  }
}

function updateSourceChart(sources) {
  if (!sourceChartRef.value) return
  if (!sourceChart) {
    sourceChart = echarts.init(sourceChartRef.value)
  }
  const okCount = Object.values(sources).filter(s => s.status === 'ok').length
  const slowCount = Object.values(sources).filter(s => s.status === 'slow').length
  const errorCount = Object.values(sources).filter(s => s.status === 'error').length
  const chartData = [
    { value: okCount, name: '正常', itemStyle: { color: '#22c55e' } },
    { value: slowCount, name: '缓慢', itemStyle: { color: '#eab308' } },
    { value: errorCount, name: '异常', itemStyle: { color: '#ef4444' } },
  ]
  sourceChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} 个' },
    legend: { bottom: 0, textStyle: { color: '#9ca3af', fontSize: 11 } },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      label: { show: true, formatter: '{b} {c}', fontSize: 11, color: '#d1d5db' },
      data: chartData,
    }],
  })
}

// 监听窗口变化
onMounted(() => {
  refreshSourceHealth()
  window.addEventListener('resize', () => sourceChart?.resize())
})
onUnmounted(() => {
  window.removeEventListener('resize', () => sourceChart?.resize())
  sourceChart?.dispose()
})

// ── 日志数据 + WebSocket 实时流（替代 HTTP 轮询）────────────────────────────
const MAX_LOGS = 300
const logs = ref([])

let ws = null
let wsConnected = false

// 动态构建 WS URL（从当前页面 location 推断后端地址）
function buildWsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  // 假设后端与前端同源，WS 路径直接挂在同一 host 上
  return `${proto}//${window.location.host}/api/v1/admin/logs/stream`
}

function pushLog(log) {
  logs.value.push(log)
  if (logs.value.length > MAX_LOGS) logs.value.shift()
}

function scrollToBottom() {
  if (!logContainer.value) return
  const el = logContainer.value
  el.scrollTop = el.scrollHeight
}

function connectLogWs() {
  if (ws) {
    ws.close()
    ws = null
  }
  try {
    ws = new WebSocket(buildWsUrl())
    ws.onopen = () => {
      wsConnected = true
      logger.info('[WS] Log stream connected')
    }
    ws.onmessage = (evt) => {
      try {
        const log = JSON.parse(evt.data)
        if (log.level === 'HEARTBEAT') return  // 忽略心跳
        pushLog(log)
        // 延迟滚动：等 DOM 更新完成后再滚
        setTimeout(scrollToBottom, 50)
      } catch { /* ignore parse errors */ }
    }
    ws.onerror = (e) => { logger.warn('[WS] Log stream error', e) }
    ws.onclose = () => {
      wsConnected = false
      ws = null
    }
  } catch (e) { logger.warn('[WS] Log stream connect failed', e) }
}

function disconnectLogWs() {
  if (ws) { ws.close(); ws = null; wsConnected = false }
}

// 切换到 logs tab 时建立 WS；离开时断开
watch(activeTab, (tab) => {
  if (tab === 'logs' && !wsConnected) connectLogWs()
  else if (tab !== 'logs') disconnectLogWs()
})

// 组件销毁时清理
onUnmounted(() => { disconnectLogWs() })

// 前端纯过滤（WS 接收所有日志，computed 按级别筛选显示）
const filteredLogs = computed(() => {
  if (logLevel.value === 'ALL') return logs.value
  return logs.value.filter(l => l.level === logLevel.value)
})

function getLogLevelClass(level) {
  const classes = {
    'ERROR': 'bg-[var(--color-danger-bg)] text-[var(--color-danger)]',
    'WARNING': 'bg-[var(--color-warning-bg)] text-[var(--color-warning)]',
    'INFO': 'bg-[var(--color-info-bg)] text-[var(--color-info)]',
    'DEBUG': 'bg-[var(--color-neutral-bg)] text-[var(--text-secondary)]'
  }
  return classes[level] || classes['INFO']
}

// 保留手动刷新（作为 WS 断开时的 fallback）
async function refreshLogs() {
  try {
    const data = await apiFetch('/api/v1/admin/logs/recent?lines=100')
    if (data?.logs) {
      logs.value = data.logs.slice(0, MAX_LOGS)  // fallback 用 HTTP 时不追加只覆盖
    }
  } catch (e) { logger.error('Refresh logs failed:', e) }
}

async function refreshSourceStatus() {
  try {
    // 探测所有数据源，获取延迟、熔断状态和失败计数
    const data = await apiFetch('/api/v1/admin/sources/probe', { method: 'POST' })
    probeData.value = data

    if (data?.sources) {
      for (const [key, result] of Object.entries(data.sources)) {
        if (!sourceStatus.sources[key]) sourceStatus.sources[key] = {}
        sourceStatus.sources[key].latency_ms = result.latency ?? null
        sourceStatus.sources[key].health = result.status === 'ok' ? 'healthy' : 'unhealthy'
        sourceStatus.sources[key].state = result.state || (result.status === 'ok' ? 'closed' : 'open')
        sourceStatus.sources[key].fail_count = result.fail_count ?? 0
        sourceStatus.sources[key].status = result.status
        sourceStatus.sources[key].is_primary = result.is_primary ?? false
        sourceStatus.sources[key].history = result.history ?? []
      }
    }
  } catch (e) { logger.error('刷新失败:', e) }
}

async function saveProxy() {
  try {
    const fullProxy = proxyUrl.value.startsWith('http') ? proxyUrl.value : `http://${proxyUrl.value}`
    await apiFetch('/api/v1/source/proxy', {
      method: 'POST',
      body: JSON.stringify({ proxy: fullProxy })
    })
    toast.success('代理配置已保存，重启服务后生效')
  } catch (e) { toast.error('代理配置失败: ' + e.message) }
}

function formatHistoryTime(timestamp) {
  if (!timestamp) return '-'
  const d = new Date(timestamp * 1000)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}

function getHistoryStatusClass(status) {
  if (status === 'ok') return 'text-[var(--color-success)]'
  if (status === 'fail' || status === 'timeout') return 'text-[var(--color-danger)]'
  return 'text-[var(--color-warning)]'
}

async function controlCircuit(source, action) {
  try {
    const data = await apiFetch('/api/v1/admin/sources/circuit_breaker', {
      method: 'POST',
      body: JSON.stringify({ source, action })
    })
    toast.success(data?.message || (action === 'open' ? '熔断成功' : '恢复成功'))
    await refreshSourceStatus()
  } catch (e) { alert('操作失败: ' + e.message) }
}

async function refreshScheduler() {
  try {
    const data = await apiFetch('/api/v1/admin/scheduler/jobs')
    if (data?.jobs) schedulerJobs.value = data.jobs
  } catch (e) { logger.error('刷新失败:', e) }
}

async function controlJob(jobId, action) {
  try {
    await apiFetch(`/api/v1/admin/scheduler/jobs/${jobId}/control`, {
      method: 'POST',
      body: JSON.stringify({ action })
    })
    await refreshScheduler()
  } catch (e) { alert('操作失败: ' + e.message) }
}

async function invalidateCache(type) {
  try {
    await apiFetch('/api/v1/admin/cache/invalidate', {
      method: 'POST',
      body: JSON.stringify({ cache_type: type })
    })
    alert('缓存已清空')
  } catch (e) { alert('操作失败: ' + e.message) }
}

async function warmupCache(type) {
  try {
    await apiFetch('/api/v1/admin/cache/warmup', {
      method: 'POST',
      body: JSON.stringify({ data_type: type })
    })
    alert('缓存预热已启动')
  } catch (e) { alert('操作失败: ' + e.message) }
}

// ═══════════════════════════════════════════════════════════════
// Watchdog 进程保活
// ═══════════════════════════════════════════════════════════════

const watchdogStatus = reactive({
  enabled: false,
  running: false,
  last_check: null,
  last_restart: null,
  restart_count: 0,
  total_restarts: 0,
  recent_errors: []
})
const watchdogLoading = ref(false)
const watchdogError = ref(null)

async function refreshWatchdog() {
  watchdogLoading.value = true
  watchdogError.value = null
  try {
    const data = await apiFetch('/api/v1/admin/watchdog/status')
    logger.log('[Watchdog] Raw response:', data)
    // apiFetch 已经通过 extractData 提取了 response.data
    if (data && typeof data.enabled === 'boolean') {
      // 直接赋值，因为 apiFetch 已经提取了 data 字段
      watchdogStatus.enabled = data.enabled ?? false
      watchdogStatus.running = data.running ?? false
      watchdogStatus.last_check = data.last_check ?? null
      watchdogStatus.last_restart = data.last_restart ?? null
      watchdogStatus.restart_count = data.restart_count ?? 0
      watchdogStatus.total_restarts = data.total_restarts ?? 0
      watchdogStatus.recent_errors = data.recent_errors ?? []
      logger.log('[Watchdog] Status updated:', watchdogStatus)
    } else {
      logger.warn('[Watchdog] Invalid response format:', data)
      watchdogError.value = '响应格式错误: ' + JSON.stringify(data)
    }
  } catch (e) { 
    logger.error('[Watchdog] Refresh error:', e)
    watchdogError.value = e.message || '加载失败'
  } finally {
    watchdogLoading.value = false
  }
}

async function toggleWatchdog(enabled) {
  try {
    logger.log('[Watchdog] Toggling to:', enabled)
    watchdogLoading.value = true
    // 乐观更新：立即更新 UI
    watchdogStatus.enabled = enabled
    
    const res = await apiFetch('/api/v1/admin/watchdog/toggle', {
      method: 'POST',
      body: JSON.stringify({ enabled })
    })
    logger.log('[Watchdog] Toggle response:', res)
    // apiFetch 已经提取了 data 字段，res 直接是 {enabled: true/false}
    
    // 延迟刷新，确保后端已处理
    setTimeout(async () => {
      await refreshWatchdog()
    }, 500)
    
    alert(enabled ? '进程保活已启用' : '进程保活已禁用')
  } catch (e) { 
    logger.error('[Watchdog] Toggle failed:', e)
    watchdogError.value = e.message || '切换失败'
    // 失败时恢复原状态
    await refreshWatchdog()
    alert('操作失败: ' + e.message) 
  } finally {
    watchdogLoading.value = false
  }
}

async function manualRestart() {
  try {
    watchdogLoading.value = true
    await apiFetch('/api/v1/admin/watchdog/restart', { method: 'POST' })
    alert('后端重启指令已发送，请等待 5-10 秒后刷新页面')
    setTimeout(async () => {
      await refreshWatchdog()
    }, 3000)
  } catch (e) { 
    watchdogError.value = e.message || '重启失败'
    alert('重启失败: ' + e.message) 
  } finally {
    watchdogLoading.value = false
  }
}

async function dbMaintenance(action) {
  try {
    await apiFetch('/api/v1/admin/database/maintenance', {
      method: 'POST',
      body: JSON.stringify({ action })
    })
    alert('维护操作已执行')
  } catch (e) { alert('操作失败: ' + e.message) }
}


async function refreshDbStatus() {
  try {
    const data = await apiFetch('/api/v1/admin/database/stats')
    if (data) {
      dbStatus.size = data.db_size_mb || 0
      dbStatus.realtime = data.tables?.market_data_realtime || 0
      dbStatus.daily = data.tables?.market_data_daily || 0
      dbStatus.stocks = data.tables?.market_all_stocks || 0
    }
  } catch (e) { logger.error('Refresh db status failed:', e) }
}

async function refreshSystemMetrics() {
  try {
    const data = await apiFetch('/api/v1/admin/system/metrics')
    if (data) Object.assign(systemMetrics, data)
  } catch (e) { logger.error('Refresh failed:', e) }
}

onMounted(() => {
  refreshSourceStatus()
  refreshScheduler()
  refreshSystemMetrics()
  refreshLogs()
  refreshDbStatus()
  logger.log('[AdminDashboard] Mounting, calling refreshWatchdog...')
  refreshWatchdog().catch(e => logger.error('[AdminDashboard] refreshWatchdog failed:', e))

})
</script>
