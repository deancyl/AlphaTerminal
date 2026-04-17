<template>
  <div class="flex h-full">
    <!-- 左侧导航 -->
    <aside class="w-64 border-r border-theme bg-theme-panel flex-shrink-0">
      <div class="p-4 border-b border-theme">
        <span class="text-sm font-bold text-terminal-accent">⚙️ 系统管理</span>
        <div class="text-[10px] text-theme-muted mt-1">v{{ version }}</div>
        <div class="text-[10px] text-yellow-400 mt-2">⚠️ 以下功能会影响系统运行，请谨慎操作</div>
      </div>
      <nav class="py-2">
        <button
          v-for="item in navItems"
          :key="item.id"
          class="w-full flex items-center gap-3 px-4 py-3 text-sm transition-all text-left"
          :class="activeTab === item.id
            ? 'bg-terminal-accent/15 text-terminal-accent border-r-2 border-terminal-accent'
            : 'text-theme-secondary hover:bg-theme-hover hover:text-theme-primary'"
          @click="activeTab = item.id"
        >
          <span class="text-base">{{ item.icon }}</span>
          <div class="flex-1">
            <div class="font-medium">{{ item.label }}</div>
            <div class="text-[10px] text-theme-muted leading-tight">{{ item.desc }}</div>
          </div>
          <span v-if="item.status" class="w-2 h-2 rounded-full flex-shrink-0" :class="item.statusClass"></span>
        </button>
      </nav>
    </aside>

    <!-- 右侧内容 -->
    <main class="flex-1 overflow-auto p-6">
      
      <!-- 数据源控制 -->
      <div v-if="activeTab === 'sources'" class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-theme-primary">📡 数据源控制</h2>
            <p class="text-xs text-theme-muted mt-1">管理股票行情数据的来源，控制数据质量和系统稳定性</p>
          </div>
          <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-lg text-sm" @click="refreshSourceStatus">🔄 刷新状态</button>
        </div>

        <div class="p-4 bg-blue-500/5 border border-blue-500/30 rounded-lg">
          <h3 class="text-sm font-bold text-blue-400 mb-2">💡 这个功能是做什么的？</h3>
          <p class="text-xs text-theme-secondary leading-relaxed">
            系统从多个数据源（腾讯、新浪、东方财富）获取股票行情。当某个数据源出现故障时，
            <strong class="text-terminal-accent">熔断机制</strong>会自动切断该源，防止错误数据进入系统。
            你可以手动控制熔断状态，或查看各数据源的响应速度。
          </p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div v-for="(source, key) in sourceStatus.sources" :key="key" class="p-4 rounded-lg border" :class="source.health === 'healthy' ? 'bg-green-500/5 border-green-500/30' : 'bg-red-500/5 border-red-500/30'">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-2">
                <span class="w-3 h-3 rounded-full" :class="source.state === 'closed' ? 'bg-green-400' : 'bg-red-400'"></span>
                <span class="font-medium text-theme-primary">{{ key }}</span>
              </div>
              <span class="text-[10px] px-2 py-0.5 rounded" :class="source.health === 'healthy' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'">
                {{ source.health === 'healthy' ? '健康' : '异常' }}
              </span>
            </div>
            <div class="space-y-2 text-sm">
              <div class="flex justify-between"><span class="text-theme-muted">响应延迟</span><span :class="source.latency_ms < 100 ? 'text-green-400' : 'text-yellow-400'">{{ source.latency_ms }}ms</span></div>
              <div class="flex justify-between"><span class="text-theme-muted">连续失败</span><span :class="source.fail_count === 0 ? 'text-green-400' : 'text-red-400'">{{ source.fail_count }} 次</span></div>
            </div>
            <div class="flex gap-2 mt-4 pt-3 border-t border-theme/50">
              <button v-if="source.state !== 'open'" class="flex-1 px-3 py-1.5 bg-red-500/20 text-red-400 rounded text-xs" @click="confirmAction(`熔断 ${key}`, `系统将停止从 ${key} 获取数据，转到其他数据源。确定？`, () => controlCircuit(key, 'open'))">⚠️ 熔断</button>
              <button v-if="source.state === 'open'" class="flex-1 px-3 py-1.5 bg-green-500/20 text-green-400 rounded text-xs" @click="confirmAction(`恢复 ${key}`, `系统将重新从 ${key} 获取数据。确定？`, () => controlCircuit(key, 'close'))">✅ 恢复</button>
            </div>
          </div>
        </div>

        <div class="p-3 bg-yellow-500/5 border border-yellow-500/20 rounded text-xs text-theme-muted">
          <strong class="text-yellow-400">操作后果说明：</strong>
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
          <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-lg text-sm" @click="refreshScheduler">🔄 刷新</button>
        </div>

        <div class="p-4 bg-blue-500/5 border border-blue-500/30 rounded-lg">
          <h3 class="text-sm font-bold text-blue-400 mb-2">💡 这个功能是做什么的？</h3>
          <p class="text-xs text-theme-secondary leading-relaxed">
            系统通过<strong class="text-terminal-accent">定时任务</strong>自动更新股票行情、板块数据、新闻快讯等。
            你可以暂停某个任务，或手动触发立即执行。
          </p>
        </div>

        <div class="space-y-3">
          <div v-for="job in schedulerJobs" :key="job.id" class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-3">
                <span class="w-2 h-2 rounded-full" :class="job.state === 'running' ? 'bg-green-400 animate-pulse' : 'bg-yellow-400'"></span>
                <div>
                  <span class="font-medium text-theme-primary">{{ job.name }}</span>
                  <div class="text-[10px] text-theme-muted">{{ job.id }}</div>
                </div>
              </div>
              <div class="flex gap-2">
                <button v-if="job.state === 'running'" class="px-3 py-1.5 bg-yellow-500/20 text-yellow-400 rounded text-xs" @click="confirmAction(`暂停 ${job.name}`, `该任务将停止自动执行，相关数据不再更新。确定？`, () => controlJob(job.id, 'pause'))">⏸️ 暂停</button>
                <button v-else class="px-3 py-1.5 bg-green-500/20 text-green-400 rounded text-xs" @click="controlJob(job.id, 'resume')">▶️ 恢复</button>
                <button class="px-3 py-1.5 bg-blue-500/20 text-blue-400 rounded text-xs" @click="confirmAction(`立即执行 ${job.name}`, `立即执行一次该任务，不影响定时计划。确定？`, () => controlJob(job.id, 'trigger_now'))">⚡ 立即执行</button>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-4 text-xs text-theme-muted">
              <div><span class="text-theme-secondary">执行频率：</span><span>{{ job.trigger }}</span></div>
              <div><span class="text-theme-secondary">下次执行：</span><span>{{ formatTime(job.next_run) || '已暂停' }}</span></div>
            </div>
          </div>
        </div>

        <div class="p-3 bg-yellow-500/5 border border-yellow-500/20 rounded text-xs text-theme-muted">
          <strong class="text-yellow-400">常用任务说明：</strong>
          <ul class="mt-1 space-y-1 list-disc list-inside">
            <li><strong>data_fetch</strong>：每30秒拉取股票实时行情，暂停后行情不再更新</li>
            <li><strong>sectors_update</strong>：每5分钟更新板块数据</li>
            <li><strong>news_refresh</strong>：每10分钟获取新闻快讯</li>
          </ul>
        </div>
      </div>

      <!-- 缓存管理 -->
      <div v-else-if="activeTab === 'cache'" class="space-y-6">
        <h2 class="text-lg font-bold text-theme-primary">💾 缓存管理</h2>
        <p class="text-xs text-theme-muted">清理和预热系统缓存，优化数据加载速度</p>

        <div class="p-4 bg-blue-500/5 border border-blue-500/30 rounded-lg">
          <h3 class="text-sm font-bold text-blue-400 mb-2">💡 这个功能是做什么的？</h3>
          <p class="text-xs text-theme-secondary leading-relaxed">
            系统使用<strong class="text-terminal-accent">缓存</strong>加速数据加载。<strong class="text-terminal-accent">预热</strong>是提前加载常用数据，提升首次访问速度。
          </p>
        </div>

        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">行情数据缓存</div>
            <div class="text-xl font-bold text-terminal-accent">{{ cacheStatus.market || 5497 }}</div>
            <div class="text-[10px] text-theme-muted">只股票</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">板块数据缓存</div>
            <div class="text-xl font-bold text-terminal-accent">{{ cacheStatus.sectors || 20 }}</div>
            <div class="text-[10px] text-theme-muted">个板块</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">新闻缓存</div>
            <div class="text-xl font-bold text-terminal-accent">{{ cacheStatus.news || 150 }}</div>
            <div class="text-[10px] text-theme-muted">条快讯</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">数据库缓存</div>
            <div class="text-xl font-bold text-terminal-accent">{{ cacheStatus.db || 22 }}</div>
            <div class="text-[10px] text-theme-muted">条实时数据</div>
          </div>
        </div>

        <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
          <h3 class="text-sm font-bold text-theme-primary mb-4">缓存操作</h3>
          <div class="flex flex-wrap gap-3">
            <button class="px-4 py-2 bg-red-500/20 text-red-400 rounded text-sm" @click="confirmAction('清空行情缓存', '清空后系统会重新从数据源获取，可能有短暂延迟。确定？', () => invalidateCache('market'))">🗑️ 清空行情缓存</button>
            <button class="px-4 py-2 bg-red-500/20 text-red-400 rounded text-sm" @click="confirmAction('清空板块缓存', '板块列表可能需要几秒重新加载。确定？', () => invalidateCache('sectors'))">🗑️ 清空板块缓存</button>
            <button class="px-4 py-2 bg-blue-500/20 text-blue-400 rounded text-sm" @click="confirmAction('预热板块缓存', '提前加载板块数据，提升访问速度。确定？', () => warmupCache('sectors'))">🔥 预热板块缓存</button>
          </div>
        </div>

        <div class="p-3 bg-yellow-500/5 border border-yellow-500/20 rounded text-xs text-theme-muted">
          <strong class="text-yellow-400">操作后果说明：</strong>
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

        <div class="p-4 bg-blue-500/5 border border-blue-500/30 rounded-lg">
          <h3 class="text-sm font-bold text-blue-400 mb-2">💡 这个功能是做什么的？</h3>
          <p class="text-xs text-theme-secondary leading-relaxed">
            系统使用<strong class="text-terminal-accent">SQLite数据库</strong>存储股票历史数据、投资组合等。长期使用后通过维护操作可以优化性能。
          </p>
        </div>

        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">数据库大小</div>
            <div class="text-xl font-bold text-terminal-accent">{{ dbStatus.size || '12.5' }} MB</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">实时数据表</div>
            <div class="text-xl font-bold text-terminal-accent">{{ dbStatus.realtime || 22 }}</div>
            <div class="text-[10px] text-theme-muted">行</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">日K数据表</div>
            <div class="text-xl font-bold text-terminal-accent">{{ dbStatus.daily || 12500 }}</div>
            <div class="text-[10px] text-theme-muted">行</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">股票列表</div>
            <div class="text-xl font-bold text-terminal-accent">{{ dbStatus.stocks || 5497 }}</div>
            <div class="text-[10px] text-theme-muted">只</div>
          </div>
        </div>

        <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
          <h3 class="text-sm font-bold text-theme-primary mb-4">数据库维护</h3>
          <div class="flex flex-wrap gap-3">
            <button class="px-4 py-2 bg-terminal-accent/20 text-terminal-accent rounded text-sm" @click="confirmAction('VACUUM 优化', '重组数据库文件，释放空间，优化性能。可能需要几秒到几分钟。确定？', () => dbMaintenance('vacuum'))">🔧 VACUUM 优化</button>
            <button class="px-4 py-2 bg-blue-500/20 text-blue-400 rounded text-sm" @click="confirmAction('ANALYZE 分析', '分析表结构，更新查询优化器统计信息。操作快速安全。确定？', () => dbMaintenance('analyze'))">📊 ANALYZE 分析</button>
            <button class="px-4 py-2 bg-green-500/20 text-green-400 rounded text-sm" @click="confirmAction('WAL 检查点', '把内存日志写入磁盘，确保数据持久化。安全快速。确定？', () => dbMaintenance('wal_checkpoint'))">💾 WAL检查点</button>
          </div>
        </div>

        <div class="p-3 bg-yellow-500/5 border border-yellow-500/20 rounded text-xs text-theme-muted">
          <strong class="text-yellow-400">维护操作说明：</strong>
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
          <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-lg text-sm" @click="refreshSystemMetrics">🔄 刷新</button>
        </div>

        <div class="p-4 bg-blue-500/5 border border-blue-500/30 rounded-lg">
          <h3 class="text-sm font-bold text-blue-400 mb-2">💡 这个功能是做什么的？</h3>
          <p class="text-xs text-theme-secondary leading-relaxed">
            显示运行系统的服务器的<strong class="text-terminal-accent">实时资源使用情况</strong>。当系统变慢时，可以查看这些指标判断原因。
          </p>
        </div>

        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">CPU 使用率</div>
            <div class="text-2xl font-bold" :class="getCpuColor(systemMetrics.cpu_percent)">{{ systemMetrics.cpu_percent?.toFixed(1) || 0 }}%</div>
            <div class="text-[10px] text-theme-muted mt-1">{{ getCpuStatus(systemMetrics.cpu_percent) }}</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">内存使用</div>
            <div class="text-2xl font-bold" :class="getMemoryColor(systemMetrics.memory?.percent)">{{ systemMetrics.memory?.percent?.toFixed(1) || 0 }}%</div>
            <div class="text-[10px] text-theme-muted mt-1">{{ systemMetrics.memory?.used_gb?.toFixed(1) || 0 }} / {{ systemMetrics.memory?.total_gb?.toFixed(1) || 0 }} GB</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">磁盘使用</div>
            <div class="text-2xl font-bold" :class="getDiskColor(systemMetrics.disk?.percent)">{{ systemMetrics.disk?.percent?.toFixed(1) || 0 }}%</div>
            <div class="text-[10px] text-theme-muted mt-1">{{ systemMetrics.disk?.used_gb?.toFixed(1) || 0 }} / {{ systemMetrics.disk?.total_gb?.toFixed(1) || 0 }} GB</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">后端进程内存</div>
            <div class="text-2xl font-bold text-terminal-accent">{{ systemMetrics.process?.memory_mb?.toFixed(0) || 0 }} MB</div>
            <div class="text-[10px] text-theme-muted mt-1">{{ systemMetrics.process?.threads || 0 }} 线程</div>
          </div>
        </div>

        <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
          <h3 class="text-sm font-bold text-theme-primary mb-3">🌐 网络状态</h3>
          <div class="grid grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
            <div><span class="text-theme-muted">活跃连接：</span><span class="text-terminal-accent font-bold">{{ systemMetrics.network?.connections || 0 }}</span></div>
            <div><span class="text-theme-muted">发送数据：</span><span class="text-theme-secondary">{{ formatBytes(systemMetrics.network?.io_counters?.bytes_sent) }}</span></div>
            <div><span class="text-theme-muted">接收数据：</span><span class="text-theme-secondary">{{ formatBytes(systemMetrics.network?.io_counters?.bytes_recv) }}</span></div>
          </div>
        </div>

        <div class="p-3 bg-green-500/5 border border-green-500/20 rounded text-xs text-theme-muted">
          <strong class="text-green-400">指标说明：</strong>
          <ul class="mt-1 space-y-1 list-disc list-inside">
            <li><strong>CPU</strong>：处理器使用率，持续高于80%可能导致系统响应变慢</li>
            <li><strong>内存</strong>：RAM使用情况，接近100%时系统可能变慢</li>
            <li><strong>磁盘</strong>：硬盘使用率，接近100%时需要清理空间</li>
            <li><strong>网络连接</strong>：当前活跃的网络连接数</li>
          </ul>
        </div>
      </div>

      <!-- 日志管理 -->
<!-- ═══ 日志管理 ══════════════════════════════════════════ -->      <div v-else-if="activeTab === 'logs'" class="space-y-6">        <div class="flex items-center justify-between">          <div>            <h2 class="text-lg font-bold text-theme-primary">📝 日志查看</h2>            <p class="text-xs text-theme-muted">查看系统运行日志和错误信息</p>          </div>          <div class="flex gap-2">            <select v-model="logLevel" class="px-3 py-2 bg-theme-panel border border-theme rounded text-sm">              <option value="ALL">全部级别</option>              <option value="ERROR">ERROR</option>              <option value="WARNING">WARNING</option>              <option value="INFO">INFO</option>              <option value="DEBUG">DEBUG</option>            </select>            <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-lg text-sm" @click="refreshLogs">🔄 刷新</button>          </div>        </div>        <div class="p-4 bg-blue-500/5 border border-blue-500/30 rounded-lg">          <h3 class="text-sm font-bold text-blue-400 mb-2">💡 这个功能是做什么的？</h3>          <p class="text-xs text-theme-secondary leading-relaxed">            显示系统的<strong class="text-terminal-accent">运行日志</strong>，包括数据更新记录、错误信息等。当系统异常时，可通过日志排查问题。          </p>        </div>        <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme h-96 overflow-auto font-mono text-xs" ref="logContainer">          <div v-if="logs.length === 0" class="text-theme-muted text-center py-8">            <div class="text-2xl mb-2">📭</div>            <div>暂无日志数据</div>            <div class="mt-2 text-[10px]">点击刷新按钮加载日志</div>          </div>          <div v-else class="space-y-1">            <div v-for="(log, i) in filteredLogs" :key="i" class="break-all">              <span class="text-theme-muted">{{ formatTime(log.timestamp) }}</span>              <span class="px-1.5 py-0.5 rounded text-[10px] ml-2" :class="getLogLevelClass(log.level)">{{ log.level }}</span>              <span class="text-theme-secondary ml-2">{{ log.message }}</span>            </div>          </div>        </div>        <div class="p-3 bg-yellow-500/5 border border-yellow-500/20 rounded text-xs text-theme-muted">          <strong class="text-yellow-400">日志级别说明：</strong>          <ul class="mt-1 space-y-1 list-disc list-inside">            <li><strong>DEBUG</strong>：详细的调试信息，开发时使用</li>            <li><strong>INFO</strong>：常规运行信息，如数据更新成功</li>            <li><strong>WARNING</strong>：警告信息，如数据源响应慢</li>            <li><strong>ERROR</strong>：错误信息，需要关注</li>          </ul>        </div>      </div>

    </main>

    <!-- 确认对话框 -->
    <div v-if="showConfirm" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-theme-panel border border-theme rounded-lg p-6 max-w-md w-full mx-4">
        <h3 class="text-lg font-bold text-theme-primary mb-2">⚠️ 确认操作</h3>
        <p class="text-sm text-theme-secondary mb-4">{{ confirmMessage }}</p>
        <div class="flex gap-3 justify-end">
          <button
            class="px-4 py-2 bg-theme-secondary/50 text-theme-secondary rounded text-sm cursor-not-allowed"
            :class="{ 'opacity-50': isSubmitting }"
            :disabled="isSubmitting"
            @click="showConfirm = false"
          >取消</button>
          <button
            class="px-4 py-2 bg-red-500/20 text-red-400 rounded text-sm"
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
import { ref, reactive, onMounted, watch, onUnmounted, computed } from 'vue'
import { logger } from '../utils/logger.js'
import { apiFetch } from '../utils/api.js'

const version = __APP_VERSION__
const activeTab = ref('sources')
const logContainer = ref(null)

const navItems = [
  { id: 'sources', label: '数据源', desc: '控制行情数据来源的熔断和恢复', icon: '📡', status: true, statusClass: 'bg-green-400' },
  { id: 'scheduler', label: '定时任务', desc: '管理自动数据更新任务的启停', icon: '⏱️', status: true, statusClass: 'bg-green-400' },
  { id: 'cache', label: '缓存管理', desc: '清理和预热系统数据缓存', icon: '💾', status: true, statusClass: 'bg-green-400' },
  { id: 'database', label: '数据库', desc: 'SQLite数据库维护和优化', icon: '🗄️', status: true, statusClass: 'bg-green-400' },
  { id: 'monitor', label: '系统监控', desc: '查看服务器CPU内存等资源使用', icon: '📊', status: true, statusClass: 'bg-green-400' },
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

function getCpuColor(p) { return !p ? 'text-theme-muted' : p < 50 ? 'text-green-400' : p < 80 ? 'text-yellow-400' : 'text-red-400' }
function getCpuStatus(p) { return !p ? '未知' : p < 50 ? '正常' : p < 80 ? '较高' : '过高' }
function getMemoryColor(p) { return !p ? 'text-theme-muted' : p < 70 ? 'text-green-400' : p < 90 ? 'text-yellow-400' : 'text-red-400' }
function getDiskColor(p) { return !p ? 'text-theme-muted' : p < 70 ? 'text-green-400' : p < 90 ? 'text-yellow-400' : 'text-red-400' }

const sourceStatus = reactive({
  sources: {
    tencent: { state: 'closed', fail_count: 0, last_success: '09:15:32', latency_ms: 85, health: 'healthy' },
    sina: { state: 'closed', fail_count: 1, last_success: '09:15:28', latency_ms: 120, health: 'healthy' },
    eastmoney: { state: 'open', fail_count: 5, last_failure: '09:14:18', health: 'unhealthy' }
  }
})

const schedulerJobs = ref([
  { id: 'data_fetch', name: '行情数据拉取', trigger: 'interval (30s)', state: 'running' },
  { id: 'sectors_update', name: '板块数据更新', trigger: 'interval (300s)', state: 'running' },
  { id: 'news_refresh', name: '新闻快讯刷新', trigger: 'interval (600s)', state: 'running' }
])

const cacheStatus = reactive({ market: 5497, sectors: 20, news: 150, db: 22 })
const dbStatus = reactive({ size: '12.5', realtime: 22, daily: 12500, stocks: 5497 })

const systemMetrics = reactive({
  cpu_percent: 5.4,
  memory: { percent: 56.2, used_gb: 4.3, total_gb: 7.65 },
  disk: { percent: 29.0, used_gb: 17.22, total_gb: 62.6 },
  process: { memory_mb: 167, threads: 12 },
  network: { connections: 471, io_counters: { bytes_sent: 74188244056, bytes_recv: 82540093634 } }
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
    'ERROR': 'bg-red-500/20 text-red-400',
    'WARNING': 'bg-yellow-500/20 text-yellow-400',
    'INFO': 'bg-blue-500/20 text-blue-400',
    'DEBUG': 'bg-gray-500/20 text-gray-400'
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
    const data = await apiFetch('/api/v1/admin/sources/status')
    if (data) Object.assign(sourceStatus, data)
  } catch (e) { logger.error('刷新失败:', e) }
}

async function controlCircuit(source, action) {
  try {
    await apiFetch('/api/v1/admin/sources/circuit_breaker', {
      method: 'POST',
      body: JSON.stringify({ source, action })
    })
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

async function dbMaintenance(action) {
  try {
    await apiFetch('/api/v1/admin/database/maintenance', {
      method: 'POST',
      body: JSON.stringify({ action })
    })
    alert('维护操作已执行')
  } catch (e) { alert('操作失败: ' + e.message) }
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
})
</script>
