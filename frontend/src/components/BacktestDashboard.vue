<template>
  <div class="flex flex-col md:flex-row w-full h-full overflow-hidden" role="main" aria-label="回测实验室">
    
    <!-- Error display for caught errors -->
    <div v-if="componentError" class="flex-1 flex flex-col items-center justify-center p-8" role="alert" aria-live="assertive">
      <div class="text-4xl mb-4" aria-hidden="true">⚠️</div>
      <div class="text-lg text-terminal-dim mb-2">回测实验室加载失败</div>
      <div class="text-sm text-theme-muted mb-4 max-w-md text-center">{{ componentError.message }}</div>
      <button
        class="px-4 py-2 text-sm rounded border border-terminal-accent text-terminal-accent hover:bg-terminal-accent hover:text-white transition"
        @click="handleRetry"
        aria-label="重试加载"
        type="button"
      >
        重试
      </button>
    </div>

    <!-- Main content (hidden when error) -->
    <template v-else>

    <!-- ═══════════════ 左侧边栏 ═══════════════ -->
    <aside class="shrink-0 w-full md:w-56 border-b md:border-b-0 md:border-r border-theme bg-terminal-panel/90 p-3 overflow-y-auto max-h-[45vh] md:max-h-none flex flex-col gap-3" role="form" aria-label="回测参数配置">

      <!-- 策略模板预设（新增） -->
      <div class="px-3 py-2 border-b border-theme">
        <div class="text-[10px] text-theme-accent font-bold mb-2">🎯 快速预设</div>
        <div class="flex flex-wrap gap-1.5" role="group" aria-label="策略预设选择">
          <button
            v-for="preset in strategyPresets" :key="preset.name"
            @click="applyPreset(preset)"
            class="min-h-[44px] px-3 py-2 text-[10px] rounded-sm border transition-colors"
            :class="isPresetActive(preset)
              ? 'bg-[var(--color-info-bg)] border-[var(--color-info-border)] text-[var(--color-info)]'
              : 'border-theme-secondary text-theme-secondary hover:border-[var(--color-info-border)] hover:text-[var(--color-info-light)]'"
            :aria-pressed="isPresetActive(preset)"
            :aria-label="`${preset.name}: ${preset.desc}`"
            type="button"
          >
            {{ preset.icon }} {{ preset.name }}
          </button>
        </div>
      </div>

      <!-- 策略参数 -->
      <div class="px-3 py-2.5 border-b border-theme">
        <div class="text-[10px] text-theme-accent font-bold mb-2">⚙️ 策略参数</div>

        <div class="space-y-1.5">
          <!-- 策略选择 -->
          <div class="flex items-center justify-between">
            <span class="text-[10px] text-theme-muted w-8">策略</span>
            <select v-model="strategyType"
              class="bg-terminal-bg/60 border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[10px] text-[var(--color-info)] focus:outline-none">
              <option value="ma_crossover">双均线</option>
              <option value="rsi_oversold">RSI超卖</option>
              <option value="bollinger_bands">布林带</option>
            </select>
          </div>

          <!-- 双均线参数 -->
          <template v-if="strategyType === 'ma_crossover'">
            <div class="grid grid-cols-2 md:flex md:flex-col gap-2">
              <div class="flex items-center justify-between">
                <span class="text-[10px] text-theme-muted w-8">快线</span>
                <input v-model.number="fastMa" type="number" min="2" max="60"
                  class="bg-terminal-bg/60 border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[10px] text-[var(--color-info)] w-14 text-center focus:outline-none focus:border-[var(--color-info)]/60" />
              </div>
              <div class="flex items-center justify-between">
                <span class="text-[10px] text-theme-muted w-8">慢线</span>
                <input v-model.number="slowMa" type="number" min="5" max="250"
                  class="bg-terminal-bg/60 border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[10px] text-[var(--color-info)] w-14 text-center focus:outline-none focus:border-[var(--color-info)]/60" />
              </div>
            </div>
            <div class="hidden md:block text-[10px] text-theme-muted leading-tight">短期趋势（如 5 日），反应近期价格敏感变化</div>
            <div class="hidden md:block text-[10px] text-theme-muted leading-tight">长期趋势（如 20 日），代表中长线支撑与阻力</div>
          </template>

          <!-- RSI 参数 -->
          <template v-if="strategyType === 'rsi_oversold'">
            <div class="grid grid-cols-2 md:flex md:flex-col gap-2">
              <div class="flex items-center justify-between">
                <span class="text-[10px] text-theme-muted w-8">周期</span>
                <input v-model.number="rsiPeriod" type="number" min="7" max="30"
                  class="bg-terminal-bg/60 border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[10px] text-[var(--color-info)] w-14 text-center focus:outline-none focus:border-[var(--color-info)]/60" />
              </div>
              <div class="flex items-center justify-between">
                <span class="text-[10px] text-theme-muted w-8">买入</span>
                <input v-model.number="rsiBuy" type="number" min="10" max="50"
                  class="bg-terminal-bg/60 border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[10px] text-[var(--color-info)] w-14 text-center focus:outline-none focus:border-[var(--color-info)]/60" />
              </div>
            </div>
            <div class="hidden md:block text-[10px] text-theme-muted leading-tight">RSI &lt; 此值买入（默认30超卖）</div>
            <div class="grid grid-cols-2 md:flex md:flex-col gap-2">
              <div class="flex items-center justify-between">
                <span class="text-[10px] text-theme-muted w-8">卖出</span>
                <input v-model.number="rsiSell" type="number" min="50" max="90"
                  class="bg-terminal-bg/60 border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[10px] text-[var(--color-info)] w-14 text-center focus:outline-none focus:border-[var(--color-info)]/60" />
              </div>
            </div>
            <div class="hidden md:block text-[10px] text-theme-muted leading-tight">RSI &gt; 此值卖出（默认70超买）</div>
          </template>

          <!-- 布林带参数 -->
          <template v-if="strategyType === 'bollinger_bands'">
            <div class="grid grid-cols-2 md:flex md:flex-col gap-2">
              <div class="flex items-center justify-between">
                <span class="text-[10px] text-theme-muted w-8">周期</span>
                <input v-model.number="bbPeriod" type="number" min="10" max="60"
                  class="bg-terminal-bg/60 border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[10px] text-[var(--color-info)] w-14 text-center focus:outline-none focus:border-[var(--color-info)]/60" />
              </div>
              <div class="flex items-center justify-between">
                <span class="text-[10px] text-theme-muted w-8">倍数</span>
                <input v-model.number="bbStd" type="number" min="1" max="4" step="0.5"
                  class="bg-terminal-bg/60 border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[10px] text-[var(--color-info)] w-14 text-center focus:outline-none focus:border-[var(--color-info)]/60" />
              </div>
            </div>
            <div class="hidden md:block text-[10px] text-theme-muted leading-tight">布林带标准差倍数（默认2倍）</div>
          </template>

          <!-- 窗口 -->
          <div class="flex items-center justify-between">
            <span class="text-[10px] text-theme-muted w-8">窗口</span>
            <select v-model="windowPreset"
              class="bg-terminal-bg/60 border border-theme-secondary rounded-sm px-1.5 py-0.5 text-[10px] text-[var(--color-info)] focus:outline-none">
              <option value="1m">近1月</option>
              <option value="3m">近3月</option>
              <option value="6m">近6月</option>
              <option value="1y" selected>近1年</option>
              <option value="2y">近2年</option>
              <option value="5y">近5年</option>
            </select>
          </div>
          <!-- 初始资金 -->
          <div class="flex items-center justify-between">
            <span class="text-[10px] text-theme-muted w-8">资金</span>
            <span class="text-[10px] font-mono text-theme-secondary">{{ (initialCapital / 10000).toFixed(0) }}万</span>
          </div>

          <!-- 策略规则提示（根据所选策略动态切换） -->
          <div class="hidden md:block mt-2 px-2 py-1.5 rounded-sm bg-[var(--color-info-bg)] border border-[var(--color-info-border)] text-[10px] leading-snug">
            <template v-if="strategyType === 'ma_crossover'">
              💡 <span class="text-[var(--color-info-light)] font-medium">双均线策略：</span>
              <span class="text-[var(--color-info-light)]/70">快线向上穿越慢线时<span class="text-[var(--color-success)]">金叉→全仓买入</span>；</span>
              <span class="text-[var(--color-info-light)]/70">快线向下穿越慢线时<span class="text-[var(--color-danger)]">死叉→全仓清仓</span>。</span>
            </template>
            <template v-else-if="strategyType === 'rsi_oversold'">
              💡 <span class="text-[var(--color-info-light)] font-medium">RSI超卖策略：</span>
              <span class="text-[var(--color-info-light)]/70">RSI &lt; {{ rsiBuy }} 时<span class="text-[var(--color-success)]">超卖→买入</span>；</span>
              <span class="text-[var(--color-info-light)]/70">RSI &gt; {{ rsiSell }} 时<span class="text-[var(--color-danger)]">超买→卖出</span>。</span>
            </template>
            <template v-else-if="strategyType === 'bollinger_bands'">
              💡 <span class="text-[var(--color-info-light)] font-medium">布林带回归策略：</span>
              <span class="text-[var(--color-info-light)]/70">价格触下轨时<span class="text-[var(--color-success)]">买入</span>；</span>
              <span class="text-[var(--color-info-light)]/70">价格触上轨时<span class="text-[var(--color-danger)]">卖出</span>。</span>
            </template>
          </div>
        </div>
      </div>

      <!-- 标的输入（股票模式） -->
      <div v-if="targetMode === 'stock'" class="px-3 py-2.5 border-b border-theme">
        <div class="flex items-center justify-between mb-2">
          <div class="text-[10px] text-theme-accent font-bold">🎯 标的</div>
          <!-- 股票/组合切换 -->
          <div class="flex rounded-sm border border-theme-secondary overflow-hidden text-[10px]">
            <button
              @click="targetMode = 'stock'"
              :class="targetMode === 'stock' ? 'bg-[var(--color-info-bg)] text-[var(--color-info)] border-r border-theme-secondary' : 'text-theme-secondary'"
              class="min-h-[44px] px-3 py-2">股票</button>
            <button
              @click="targetMode = 'portfolio'"
              :class="targetMode === 'portfolio' ? 'bg-[var(--color-info-bg)] text-[var(--color-info)]' : 'text-theme-secondary'"
              class="min-h-[44px] px-3 py-2">组合</button>
          </div>
        </div>
        <div class="flex items-center gap-1.5">
          <input 
            v-model="symbol"
            class="flex-1 min-h-[44px] bg-terminal-bg/60 border rounded-sm px-3 py-2 text-[10px] text-[var(--color-info)] focus:outline-none placeholder:text-theme-tertiary transition-colors"
            :class="symbolValidation.showError ? 'border-[var(--color-danger)] focus:border-[var(--color-danger)]' : 'border-theme-secondary focus:border-terminal-accent/60'"
            placeholder="输入代码 (例: sh600519)"
            @blur="handleSymbolBlur"
            @input="handleSymbolInput"
            @keyup.enter="runBacktest"
            :aria-invalid="symbolValidation.showError ? 'true' : 'false'"
            :aria-describedby="symbolValidation.showError ? 'symbol-error' : undefined"
            aria-label="股票代码"
          />
          <!-- 格式校验 -->
          <span v-if="symbolValid"
            class="shrink-0 text-[12px] leading-none text-[var(--color-success)] select-none">✅</span>
          <span v-else-if="symbol.length > 0 && symbolValidation.touched"
            class="shrink-0 text-[12px] leading-none text-[var(--color-danger)] select-none">❌</span>
        </div>
        <!-- 验证错误消息 -->
        <div v-if="symbolValidation.showError" 
          id="symbol-error"
          class="mt-1 text-[10px] text-[var(--color-danger)] flex items-center gap-1"
          role="alert"
          aria-live="polite">
          <span>⚠️</span>
          <span>{{ symbolValidation.error }}</span>
        </div>
        <!-- 名称+行业显示 -->
        <div v-else-if="symbolInfo"
          class="mt-1 text-[10px] text-[var(--color-info-light)] truncate">
          {{ symbolInfo.name }}<span class="text-cyan-500 ml-1">[{{ symbolInfo.industry }}]</span>
        </div>
        <div v-else-if="symbolValid && symbolNoData"
          class="mt-1 text-[10px] text-[var(--color-warning)] italic">本地无此标的历史数据</div>
        <div v-else-if="symbolValid"
          class="mt-1 text-[10px] text-theme-tertiary italic">回车执行回测</div>
      </div>

      <!-- 投资组合模式 -->
      <div v-else-if="targetMode === 'portfolio'" class="px-3 py-2.5 border-b border-theme">
        <div class="flex items-center justify-between mb-2">
          <div class="text-[10px] text-theme-accent font-bold">📦 组合回测</div>
          <!-- 股票/组合切换 -->
          <div class="flex rounded-sm border border-theme-secondary overflow-hidden text-[10px]">
            <button
              @click="targetMode = 'stock'"
              :class="targetMode === 'stock' ? 'bg-[var(--color-info-bg)] text-[var(--color-info)] border-r border-theme-secondary' : 'text-theme-secondary'"
              class="min-h-[44px] px-3 py-2">股票</button>
            <button
              @click="targetMode = 'portfolio'"
              :class="targetMode === 'portfolio' ? 'bg-[var(--color-info-bg)] text-[var(--color-info)]' : 'text-theme-secondary'"
              class="min-h-[44px] px-3 py-2">组合</button>
          </div>
        </div>

        <!-- 组合下拉 -->
        <select v-model="selectedPortfolioId"
          @change="onPortfolioChange"
          class="w-full min-h-[44px] bg-terminal-bg/60 border border-theme-secondary rounded-sm px-3 py-2 text-[10px] text-[var(--color-info)] mb-2 focus:outline-none">
          <option value="">— 选择组合账户 —</option>
          <option v-for="p in portfolioOptions" :key="p.id" :value="p.id">
            {{ p.parent_id ? '  └ ' : '' }}{{ p.name }}
          </option>
        </select>

        <!-- 持仓标签 -->
        <div v-if="positionTags.length" class="flex flex-wrap gap-1">
          <button
            v-for="pos in positionTags"
            :key="pos.symbol"
            @click="runBacktestWithSymbol(pos.symbol)"
            :disabled="running"
            class="min-h-[44px] px-3 py-2 text-[10px] rounded-sm border transition-colors"
            :class="running
              ? 'border-theme-tertiary text-theme-muted cursor-not-allowed opacity-50'
              : 'border-[var(--color-info-border)] text-[var(--color-info)] hover:bg-[var(--color-info-bg)] cursor-pointer'"
          >
            {{ pos.name || pos.normalized }}<span class="opacity-60 ml-0.5">{{ pos.normalized }}</span>
          </button>
        </div>
        <div v-else-if="selectedPortfolioId && positionTagsLoading"
          class="text-[10px] text-theme-muted italic">加载中...</div>
        <div v-else-if="selectedPortfolioId"
          class="text-[10px] text-theme-muted italic">该组合暂无持仓</div>
        <div v-else class="text-[10px] text-theme-muted italic">选择组合后，点击持仓标签即可回测</div>
      </div>

      <!-- 执行按钮（底部撑满） -->
      <div class="mt-auto px-3 py-2.5 border-t border-theme">
        <button
          @click="runBacktest"
          :disabled="running"
          class="w-full min-h-[44px] py-3 rounded-sm text-[11px] font-medium transition-colors"
          :class="running
            ? 'bg-[var(--color-neutral-bg)] text-theme-muted cursor-not-allowed'
            : 'bg-[var(--color-info-bg)] text-[var(--color-info)] hover:bg-[var(--color-info-hover)]/30 border border-[var(--color-info-border)]'"
          :aria-busy="running"
          type="button"
        >
          {{ running ? '⏳ 回测中...' : '▶ 执行回测' }}
        </button>
        <!-- 状态行 -->
        <div v-if="statusMsg" class="mt-1.5 text-[10px] text-center"
          :class="statusMsg.startsWith('❌') ? 'text-[var(--color-danger)]' : statusMsg.startsWith('⚠️') ? 'text-[var(--color-warning)]' : 'text-theme-muted'"
          role="status"
          aria-live="polite"
        >
          {{ statusMsg }}
        </div>
      </div>
    </aside>

    <!-- ═══════════════ 右侧主区 ═══════════════ -->
    <main class="flex-1 flex flex-col min-w-0 overflow-hidden">

      <!-- 回测结果摘要卡片（新增） -->
      <div v-if="backtestResult" class="shrink-0 border-b border-theme bg-terminal-panel/80">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-2 px-3 py-2">
          <div class="flex flex-col items-center bg-terminal-bg rounded-sm p-2 border border-theme">
            <span class="text-[10px] text-theme-muted mb-0.5">总收益率</span>
            <span class="text-sm font-mono font-bold" :class="(backtestResult.total_return_pct||0) >= 0 ? 'text-bullish' : 'text-bearish'">
              {{ (backtestResult.total_return_pct||0) >= 0 ? '+' : '' }}{{ (backtestResult.total_return_pct||0).toFixed(2) }}%
            </span>
          </div>
          <div class="flex flex-col items-center bg-terminal-bg rounded-sm p-2 border border-theme">
            <span class="text-[10px] text-theme-muted mb-0.5">年化收益</span>
            <span class="text-sm font-mono" :class="(backtestResult.annualized_return_pct||0) >= 0 ? 'text-bullish' : 'text-bearish'">
              {{ (backtestResult.annualized_return_pct||0) >= 0 ? '+' : '' }}{{ (backtestResult.annualized_return_pct||0).toFixed(2) }}%
            </span>
          </div>
          <div class="flex flex-col items-center bg-terminal-bg rounded-sm p-2 border border-theme">
            <span class="text-[10px] text-theme-muted mb-0.5 cursor-help" title="最大回撤：策略在回测期间从峰值到谷值的最大跌幅，衡量策略可能面临的最大亏损风险">最大回撤</span>
            <span class="text-sm font-mono text-bearish">
              {{ (backtestResult.max_drawdown_pct||0).toFixed(2) }}%
            </span>
          </div>
          <div class="flex flex-col items-center bg-terminal-bg rounded-sm p-2 border border-theme">
            <span class="text-[10px] text-theme-muted mb-0.5 cursor-help" title="夏普比率：(年化收益率-无风险利率) / 年化波动率，衡量每承担一单位风险所获得的超额收益。>1为良好，>2为优秀，>3为卓越">夏普比率</span>
            <span class="text-sm font-mono" :class="(backtestResult.sharpe_ratio||0) >= 1 ? 'text-bullish' : 'text-theme-muted'">
              {{ (backtestResult.sharpe_ratio||0).toFixed(2) || '—' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 图表区 -->
      <div class="flex-1 flex flex-col min-h-[50vh] md:min-h-0 relative" ref="chartWrapRef">
        <BacktestChart
          v-if="histData.length > 0"
          ref="chartRef"
          :key="chartKey"
          :hist="histData"
          :trades="backtestResult?.trades || []"
          :symbol="symbol"
          class="w-full h-full"
        />
        <div v-else-if="!running"
          class="absolute inset-0 flex flex-col items-center justify-center text-theme-muted text-[11px] gap-2">
          <span class="text-xl">📊</span>
          <span>配置参数或选择持仓后点击"执行回测"</span>
        </div>
        <!-- Loading 遮罩 -->
        <div v-if="running"
          class="absolute inset-0 z-10 flex flex-col items-center justify-center"
          style="background: rgba(15,23,42,0.75); backdrop-filter: blur(2px);">
          <div class="text-[var(--color-info)] text-xs font-mono">⏳ 回测引擎运行中...</div>
        </div>
      </div>

      <!-- 底部指标 + 交易记录 -->
      <div v-if="backtestResult" class="shrink-0 border-t border-theme bg-terminal-panel/80 max-h-48 overflow-y-auto">

        <!-- 核心指标行 -->
        <div class="flex items-center gap-3 px-3 py-1.5 overflow-x-auto text-[10px]">
          <div class="shrink-0 flex items-center gap-1">
            <span class="text-theme-muted">收益率</span>
            <span class="font-mono font-bold" :class="(backtestResult.total_return_pct||0) >= 0 ? 'text-bullish' : 'text-bearish'">
              {{ (backtestResult.total_return_pct||0) >= 0 ? '+' : '' }}{{ (backtestResult.total_return_pct||0).toFixed(2) }}%
            </span>
          </div>
          <div class="shrink-0 flex items-center gap-1">
            <span class="text-theme-muted">年化</span>
            <span class="font-mono" :class="(backtestResult.annualized_return_pct||0) >= 0 ? 'text-bullish' : 'text-bearish'">
              {{ (backtestResult.annualized_return_pct||0) >= 0 ? '+' : '' }}{{ (backtestResult.annualized_return_pct||0).toFixed(2) }}%
            </span>
          </div>
          <div class="shrink-0 flex items-center gap-1">
            <span class="text-theme-muted cursor-help" title="最大回撤：策略在回测期间从峰值到谷值的最大跌幅，衡量策略可能面临的最大亏损风险。数值越小越好，通常应控制在20%以内">最大回撤</span>
            <span class="font-mono text-bearish">{{ (backtestResult.max_drawdown_pct||0).toFixed(2) }}%</span>
          </div>
          <div class="shrink-0 flex items-center gap-1">
            <span class="text-theme-muted cursor-help" title="胜率：盈利交易次数占总交易次数的比例。胜率×平均盈利 > (1-胜率)×平均亏损 时策略才能盈利">胜率</span>
            <span class="font-mono text-theme-primary">{{ (backtestResult.win_rate||0).toFixed(1) }}%</span>
          </div>
          <div class="shrink-0 flex items-center gap-1">
            <span class="text-theme-muted">交易</span>
            <span class="font-mono text-theme-primary">{{ backtestResult.trades_count||0 }}</span>
          </div>
          <div class="shrink-0 flex items-center gap-1">
            <span class="text-theme-muted cursor-help" title="夏普比率：(年化收益率-无风险利率) / 年化波动率，衡量每承担一单位风险所获得的超额收益。>1为良好，>2为优秀，>3为卓越">夏普</span>
            <span class="font-mono" :class="(backtestResult.sharpe_ratio||0) >= 1 ? 'text-bullish' : 'text-theme-muted'">
              {{ (backtestResult.sharpe_ratio||0).toFixed(2) || '—' }}
            </span>
          </div>
          <div class="shrink-0 flex items-center gap-1">
            <span class="text-theme-muted cursor-help" title="盈亏比：平均盈利金额 / 平均亏损金额。盈亏比>1表示盈利时赚的比亏损时亏的多，是策略长期盈利的关键指标">盈亏比</span>
            <span class="font-mono text-theme-primary">{{ profitFactor }}</span>
          </div>
          <button
            class="shrink-0 min-h-[44px] text-[10px] px-3 py-2 text-[var(--color-info)] hover:text-[var(--color-info-light)] transition-colors border border-[var(--color-info-border)] rounded-sm"
            @click="exportBacktest"
            :disabled="!backtestResult">
            📥 导出
          </button>
          <button
            class="ml-auto shrink-0 min-h-[44px] text-[10px] px-3 py-2 text-theme-muted hover:text-[var(--color-info)] transition-colors"
            @click="showTrades = !showTrades">
            {{ showTrades ? '▲ 收起' : '▼ 交易' }} ({{ backtestResult.trades?.length||0 }})
          </button>
        </div>

        <!-- ═══ 策略体检报告 ═══ -->
        <div class="border-t border-theme/30 px-3 py-1.5">
          <div class="flex items-center gap-4 text-[10px]">
            <!-- 策略 vs 基准对比 -->
            <div class="flex items-center gap-1.5 shrink-0">
              <span class="text-theme-muted">策略</span>
              <span class="font-mono font-bold" :class="(backtestResult.total_return_pct||0) >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ (backtestResult.total_return_pct||0) >= 0 ? '+' : '' }}{{ (backtestResult.total_return_pct||0).toFixed(2) }}%
              </span>
            </div>
            <div class="text-theme-muted shrink-0">|</div>
            <div class="flex items-center gap-1.5 shrink-0">
              <span class="text-theme-muted">基准</span>
              <span class="font-mono text-[var(--color-warning)]">
                +{{ (backtestResult.benchmark_return_pct||0).toFixed(2) }}%
              </span>
            </div>
            <div class="text-theme-muted shrink-0">|</div>
            <div class="flex items-center gap-1 shrink-0">
              <span class="text-theme-muted">评级</span>
              <span :class="strategyGradeClass">{{ strategyGradeText }}</span>
            </div>
            <div class="flex items-center gap-1 shrink-0 text-[var(--color-info-light)]">
              {{ strategyVerdict }}
            </div>
          </div>
        </div>

        <!-- 交易记录表格（虚拟化） -->
        <div v-if="showTrades && backtestResult.trades?.length"
          class="border-t border-theme/30 overflow-hidden">
          <!-- 表头 -->
          <div class="flex items-center text-xs border-b border-theme/20 bg-terminal-panel text-theme-muted">
            <div class="px-2 w-12 shrink-0">方向</div>
            <div class="px-2 w-24 shrink-0 text-right">买日期</div>
            <div class="px-2 w-20 shrink-0 text-right">买价</div>
            <div class="px-2 w-24 shrink-0 text-right">卖日期</div>
            <div class="px-2 w-20 shrink-0 text-right">卖价</div>
            <div class="px-2 w-16 shrink-0 text-right">数量</div>
            <div class="px-2 w-20 shrink-0 text-right">盈亏额</div>
            <div class="px-2 flex-1 text-right">盈亏%</div>
          </div>
          <RecycleScroller
            class="virtualized-trades"
            :items="virtualizedTrades"
            :item-size="28"
            key-field="id"
            :buffer="200"
            v-slot="{ item, index }"
          >
            <div
              class="flex items-center text-xs border-b border-theme/10 hover:bg-theme-tertiary/20 cursor-pointer"
              :style="{ height: '28px' }"
              @click="chartRef?.focusDate(item.entry_date)"
            >
              <div class="px-2 w-12 shrink-0">
                <span class="font-mono font-bold" :class="(item.pnl||0) >= 0 ? 'text-bullish' : 'text-bearish'">
                  {{ (item.pnl||0) >= 0 ? '多' : '空' }}
                </span>
              </div>
              <div class="px-2 w-24 shrink-0 text-right text-theme-secondary font-mono">{{ item.entry_date }}</div>
              <div class="px-2 w-20 shrink-0 text-right text-theme-primary font-mono">{{ (item.entry_price||0).toFixed(2) }}</div>
              <div class="px-2 w-24 shrink-0 text-right text-theme-secondary font-mono">{{ item.exit_date || '持仓中' }}</div>
              <div class="px-2 w-20 shrink-0 text-right text-theme-primary font-mono">{{ item.exit_price != null ? item.exit_price.toFixed(2) : '—' }}</div>
              <div class="px-2 w-16 shrink-0 text-right text-theme-primary font-mono">{{ item.shares }}</div>
              <div class="px-2 w-20 shrink-0 text-right font-mono font-bold"
                :class="(item.pnl||0) >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ (item.pnl||0) >= 0 ? '+' : '' }}{{ (item.pnl||0).toFixed(2) }}
              </div>
              <div class="px-2 flex-1 text-right font-mono"
                :class="(item.pnl_pct||0) >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ (item.pnl_pct||0) >= 0 ? '+' : '' }}{{ (item.pnl_pct||0).toFixed(2) }}%
              </div>
            </div>
          </RecycleScroller>
        </div>
      </div>
    </main>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, onUnmounted, onErrorCaptured } from 'vue'
import { apiFetch } from '../utils/api.js'
import { usePortfolioStore } from '../composables/usePortfolioStore.js'
import { safeDivide } from '../utils/safeMath.js'
import { useValidation } from '../composables/useValidation.js'
import BacktestChart from './BacktestChart.vue'

// ── Error Boundary State ─────────────────────────────────────────────
const componentError = ref(null)

onErrorCaptured((err, instance, info) => {
  console.error('[BacktestDashboard] Uncaught error:', err)
  console.error('[BacktestDashboard] Component:', instance?.$options?.name || 'unknown')
  console.error('[BacktestDashboard] Info:', info)
  
  componentError.value = {
    message: err.message || String(err),
    component: instance?.$options?.name || 'unknown',
    info,
    timestamp: Date.now(),
  }
  
  // Report to monitoring if available
  if (typeof window !== 'undefined' && typeof window.reportError === 'function') {
    try {
      window.reportError(err)
    } catch (e) {
      console.error('[BacktestDashboard] Failed to report error:', e)
    }
  }
  
  // Prevent propagation to parent
  return false
})

function handleRetry() {
  componentError.value = null
  // Reset state for retry
  backtestResult.value = null
  histData.value = []
  statusMsg.value = ''
}

// ── 已知标的字典（用于联想显示，不依赖外部请求）────────────────
const KNOWN_SYMBOLS = [
  // 主要指数
  { symbol: 'sh000001', name: '上证指数',    industry: '大盘指数' },
  { symbol: 'sh000300', name: '沪深300',     industry: '大盘指数' },
  { symbol: 'sz399001', name: '深证成指',    industry: '大盘指数' },
  { symbol: 'sz399006', name: '创业板指',   industry: '大盘指数' },
  { symbol: 'sh000688', name: '科创50',      industry: '大盘指数' },
  // 食品饮料
  { symbol: 'sh600519', name: '贵州茅台',    industry: '白酒' },
  { symbol: 'sh600887', name: '伊利股份',    industry: '乳制品' },
  { symbol: 'sz000858', name: '五粮液',      industry: '白酒' },
  { symbol: 'sh600132', name: '重庆啤酒',    industry: '啤酒' },
  // 金融
  { symbol: 'sh600036', name: '招商银行',    industry: '银行' },
  { symbol: 'sh601318', name: '中国平安',    industry: '保险' },
  { symbol: 'sh600016', name: '民生银行',    industry: '银行' },
  { symbol: 'sz000001', name: '平安银行',    industry: '银行' },
  // 科技
  { symbol: 'sz000651', name: '格力电器',    industry: '家电' },
  { symbol: 'sz000333', name: '美的集团',    industry: '家电' },
  { symbol: 'sh600276', name: '恒瑞医药',    industry: '医药' },
  { symbol: 'sz300750', name: '宁德时代',    industry: '新能源' },
  { symbol: 'sh688981', name: '中芯国际',    industry: '半导体' },
  { symbol: 'sh601127', name: '赛力斯',      industry: '新能源汽车' },
]

// ── 策略模板预设 ──────────────────────────────────────────────
const strategyPresets = [
  {
    name: '金叉买入',
    icon: '📈',
    strategyType: 'ma_crossover',
    fastMa: 5,
    slowMa: 20,
    windowPreset: '1y',
    desc: '短线激进，5日上穿20日买入'
  },
  {
    name: '趋势跟踪',
    icon: '📊',
    strategyType: 'ma_crossover',
    fastMa: 10,
    slowMa: 30,
    windowPreset: '1y',
    desc: '中线稳健，10日上穿30日买入'
  },
  {
    name: 'RSI抄底',
    icon: '🛒',
    strategyType: 'rsi_oversold',
    rsiPeriod: 14,
    rsiBuy: 30,
    rsiSell: 70,
    windowPreset: '6m',
    desc: 'RSI<30超卖买入，>70超买卖出'
  },
  {
    name: '布林带',
    icon: '🎯',
    strategyType: 'bollinger_bands',
    bbPeriod: 20,
    bbStd: 2,
    windowPreset: '1y',
    desc: '触下轨买入，触上轨卖出'
  },
]

function applyPreset(preset) {
  strategyType.value = preset.strategyType
  if (preset.fastMa != null) fastMa.value = preset.fastMa
  if (preset.slowMa != null) slowMa.value = preset.slowMa
  if (preset.rsiPeriod != null) rsiPeriod.value = preset.rsiPeriod
  if (preset.rsiBuy != null) rsiBuy.value = preset.rsiBuy
  if (preset.rsiSell != null) rsiSell.value = preset.rsiSell
  if (preset.bbPeriod != null) bbPeriod.value = preset.bbPeriod
  if (preset.bbStd != null) bbStd.value = preset.bbStd
  if (preset.windowPreset) windowPreset.value = preset.windowPreset
}

function isPresetActive(preset) {
  if (strategyType.value !== preset.strategyType) return false
  if (preset.fastMa != null && fastMa.value !== preset.fastMa) return false
  if (preset.slowMa != null && slowMa.value !== preset.slowMa) return false
  if (preset.rsiPeriod != null && rsiPeriod.value !== preset.rsiPeriod) return false
  if (preset.rsiBuy != null && rsiBuy.value !== preset.rsiBuy) return false
  if (preset.rsiSell != null && rsiSell.value !== preset.rsiSell) return false
  if (preset.bbPeriod != null && bbPeriod.value !== preset.bbPeriod) return false
  if (preset.bbStd != null && bbStd.value !== preset.bbStd) return false
  return true
}

// ── 标的输入模式 ────────────────────────────────────────────────
const targetMode = ref('stock')  // 'stock' | 'portfolio'

// ── 组合数据 ────────────────────────────────────────────────────
const portfolioStore = usePortfolioStore()

// 主动触发一次数据拉取（await 确保组件首次渲染前数据已就位）
onMounted(async () => {
  await portfolioStore.fetchPortfolios()
})

onUnmounted(() => {
  // Cancel any pending fetch requests
  _fetchController?.abort()
  _fetchController = null
})

// portfolioStore.portfolios 在 reactive 代理中已自动解包，无需 .value
// 显示所有账户（包括主账户和子账户），用 parent_id 判断层级
const portfolioOptions = computed(() => {
  const raw = portfolioStore.portfolios
  return Array.isArray(raw) ? raw : []
})

const selectedPortfolioId = ref('')
const positionTags = ref([])
const positionTagsLoading = ref(false)

// 将后端返回的无前缀代码（如 "600519"）补全为带市场前缀格式（"sh600519"）
function normalizeSymbol(code) {
  if (!code) return ''
  const c = code.trim()
  if (c.startsWith('sh') || c.startsWith('sz') || c.startsWith('hk') || c.startsWith('us')) {
    return c.toLowerCase()
  }
  // A股：根据代码规则自动推断前缀
  const num = c.replace(/[^0-9]/g, '')
  if (num.startsWith('6') || num.startsWith('5') || num.startsWith('9')) return 'sh' + num
  if (num.startsWith('0') || num.startsWith('1') || num.startsWith('2') || num.startsWith('3')) return 'sz' + num
  return c
}

async function onPortfolioChange() {
  positionTags.value = []
  const pid = selectedPortfolioId.value
  if (!pid) return
  positionTagsLoading.value = true
  try {
    // Abort any pending request before starting a new one
    _fetchController?.abort()
    _fetchController = new AbortController()
    const d = await apiFetch(`/api/v1/portfolio/${pid}/positions`, { signal: _fetchController.signal })
    const list = Array.isArray(d) ? d : (d?.positions || [])
    positionTags.value = list.map(p => ({
      symbol:     p.symbol || '',
      name:       p.name || (p.symbol ? normalizeSymbol(p.symbol).toUpperCase() : ''),
      normalized: normalizeSymbol(p.symbol),
    }))
  } catch (e) {
    // Ignore abort errors silently
    if (e.name === 'AbortError' || e.message?.includes('aborted')) return
    positionTags.value = []
  } finally {
    _fetchController = null
    positionTagsLoading.value = false
  }
}

// 从组合持仓标签点击触发回测（自动补全市场前缀）
function runBacktestWithSymbol(rawSymbol) {
  symbol.value = normalizeSymbol(rawSymbol)
  runBacktest()
}

// ── 回测参数 ────────────────────────────────────────────────────
const symbol        = ref('sh600519')
const strategyType  = ref('ma_crossover')
const fastMa        = ref(5)
const slowMa        = ref(20)
const rsiPeriod     = ref(14)
const rsiBuy        = ref(30)
const rsiSell       = ref(70)
const bbPeriod      = ref(20)
const bbStd         = ref(2)
const windowPreset  = ref('1y')
const initialCapital = 100000

// ── 标的格式校验（8位 = 市场前缀 + 6位代码）─────────────────────
const symbolValid = computed(() => /^(sh|sz)[0-9]{6}$/.test(symbol.value.trim()))
const symbolMatchedName = computed(() => {
  const norm = symbol.value.trim()
  const known = KNOWN_SYMBOLS.find(o => o.symbol === norm)
  return known?.name || null
})

// ── 标的验证状态 ────────────────────────────────────────────────────
const symbolValidation = reactive({
  error: '',
  touched: false,
  showError: false,
})

const STOCK_SYMBOL_PATTERN = /^(sh|sz)[0-9]{6}$/

function validateSymbol() {
  const value = symbol.value.trim()
  if (!value) {
    symbolValidation.error = '请输入股票代码'
    symbolValidation.showError = true
    return false
  }
  if (!STOCK_SYMBOL_PATTERN.test(value)) {
    symbolValidation.error = '格式错误：应为 sh/sz + 6位数字（如 sh600519）'
    symbolValidation.showError = true
    return false
  }
  symbolValidation.error = ''
  symbolValidation.showError = false
  return true
}

function handleSymbolBlur() {
  symbolValidation.touched = true
  validateSymbol()
}

function handleSymbolInput() {
  if (symbolValidation.touched) {
    validateSymbol()
  }
}

// 标的完整信息（名称+行业）
const symbolInfo = computed(() => {
  const norm = symbol.value.trim()
  return KNOWN_SYMBOLS.find(o => o.symbol === norm) || null
})

// 格式正确但不在本地字典 → 可能是用户自定义代码，不阻断但提示
const symbolNoData = computed(() =>
  symbolValid.value && !KNOWN_SYMBOLS.find(o => o.symbol === symbol.value.trim())
)

const running        = ref(false)
const statusMsg     = ref('')
const backtestResult = ref(null)
const histData      = ref([])
const chartKey      = ref(0)
const showTrades    = ref(false)
const chartWrapRef  = ref(null)
const chartRef      = ref(null)  // BacktestChart 实例，用于联动

let _fetchController = null  // AbortController：组件卸载时取消 pending 请求

function presetDates(preset) {
  const end = new Date()
  const start = new Date()
  switch (preset) {
    case '1m':  start.setMonth(end.getMonth() - 1);  break
    case '3m':  start.setMonth(end.getMonth() - 3);  break
    case '6m':  start.setMonth(end.getMonth() - 6);  break
    case '1y':  start.setFullYear(end.getFullYear() - 1); break
    case '2y':  start.setFullYear(end.getFullYear() - 2); break
    case '5y':  start.setFullYear(end.getFullYear() - 5); break
  }
  return { start_date: start.toISOString().slice(0, 10), end_date: end.toISOString().slice(0, 10) }
}

// ── 核心：执行回测 ──────────────────────────────────────────────
async function runBacktest() {
  if (running.value) return
  
  // 验证标的代码
  symbolValidation.touched = true
  if (!validateSymbol()) {
    return
  }
  
  running.value = true
  statusMsg.value = ''
  backtestResult.value = null
  histData.value = []

  try {
    // Abort any pending request before starting a new one
    _fetchController?.abort()
    _fetchController = new AbortController()
    const { start_date, end_date } = presetDates(windowPreset.value)
    const sym = symbol.value.trim() || 'sh600519'

    statusMsg.value = '📡 拉取历史数据...'
    const histResp = await apiFetch(
      `/api/v1/market/history/${sym}?period=daily&limit=5000&offset=0`,
      { signal: _fetchController.signal }
    )
    // 统一解包: apiFetch 已解包 data，需兼容 history 在不同层级
    const histDataRaw = histResp?.data?.history || histResp?.history || histResp || []
    const rawHist = histDataRaw.map(s => ({
      date:   s.date || s.time || '',
      open:   Number(s.open)  || 0,
      high:   Number(s.high)  || 0,
      low:    Number(s.low)   || 0,
      close:  Number(s.close) || 0,
      volume: Number(s.volume)|| 0,
    })).filter(s => s.date >= start_date && s.date <= end_date)

    if (!rawHist.length) {
      statusMsg.value = '⚠️ 该时段无历史数据'
      return
    }
    histData.value = rawHist

    statusMsg.value = '⚙️ 运行回测引擎...'
    const btResp = await apiFetch('/api/v1/backtest/run', {
      method: 'POST',
      body: {
        symbol:         sym,
        period:         'daily',
        start_date,
        end_date,
        initial_capital: initialCapital,
        strategy_type:  strategyType.value,
        params: (() => {
          switch (strategyType.value) {
            case 'ma_crossover':    return { fast_ma: fastMa.value,  slow_ma: slowMa.value }
            case 'rsi_oversold':   return { rsi_period: rsiPeriod.value, rsi_buy: rsiBuy.value, rsi_sell: rsiSell.value }
            case 'bollinger_bands': return { bb_period: bbPeriod.value, bb_std: bbStd.value }
            default:                return {}
          }
        })(),
      },
      signal: _fetchController.signal,
    })

    // 兼容后端报错格式 {code, message, ...}
    if (btResp?.code !== 0 && btResp?.code !== undefined) {
      statusMsg.value = `❌ ${btResp?.message || '回测失败'}`
      return
    }

    const data = btResp?.data || btResp || {}
    backtestResult.value = data
    statusMsg.value = `✅ 完成 ${data.trades_count||0} 笔交易`
    chartKey.value++
  } catch (e) {
    // Ignore abort errors silently
    if (e.name === 'AbortError' || e.message?.includes('aborted')) return
    statusMsg.value = `❌ ${e.message || '回测失败'}`
  } finally {
    _fetchController = null
    running.value = false
  }
}

// ── 盈亏比 ──────────────────────────────────────────────────────
const profitFactor = computed(() => {
  const t = backtestResult.value?.trades || []
  if (!t.length) return '—'
  const wins   = t.filter(x => (x.pnl || 0) > 0)
  const losses = t.filter(x => (x.pnl || 0) < 0)
  const avgWin  = safeDivide(wins.reduce((s, x) => s + x.pnl, 0), wins.length)
  const avgLoss = safeDivide(Math.abs(losses.reduce((s, x) => s + x.pnl, 0)), losses.length)
  if (!avgLoss) return avgWin ? '∞' : '—'
  return safeDivide(avgWin, avgLoss, 0).toFixed(2)
})

// ── 虚拟化交易记录 ──────────────────────────────────────────────
const virtualizedTrades = computed(() => {
  const trades = backtestResult.value?.trades || []
  return trades.map((t, i) => ({
    ...t,
    id: i,
  }))
})

// ── 策略体检报告 ─────────────────────────────────────────────────
const strategyGradeText = computed(() => {
  const r = backtestResult.value
  if (!r) return '—'
  const ret = r.total_return_pct || 0
  const bm  = r.benchmark_return_pct || 0
  const sh  = r.sharpe_ratio || 0
  const dd  = r.max_drawdown_pct || 100
  const excess = ret - bm
  if (excess > 10 && sh >= 1.5) return '🏆 优秀'
  if (excess > 0  && sh >= 1.0) return '✅ 良好'
  if (excess > 0)               return '🆗 及格'
  return '⚠️ 需优化'
})

const strategyGradeClass = computed(() => {
  const g = strategyGradeText.value
  if (g.startsWith('🏆')) return 'font-bold text-[var(--color-warning-light)]'
  if (g.startsWith('✅')) return 'font-bold text-[var(--color-success)]'
  if (g.startsWith('🆗')) return 'font-medium text-[var(--color-info)]'
  return 'font-medium text-[var(--color-danger)]'
})

const strategyVerdict = computed(() => {
  const ret = backtestResult.value?.total_return_pct || 0
  const bm  = backtestResult.value?.benchmark_return_pct || 0
  const excess = ret - bm
  if (ret > bm * 1.5 && excess > 10) return `🚀 极度优秀！超额收益 ${excess.toFixed(1)}%`
  if (excess > 10) return `🌟 显著跑赢基准 ${excess.toFixed(1)}%，策略具备阿尔法`
  if (excess > 0)  return `📈 跑赢基准 ${excess.toFixed(1)}%，策略有效`
  if (excess > -5) return `⚠️ 略输持股不动 ${Math.abs(excess).toFixed(1)}%，可调整参数`
  return `🐢 不如买入持有 ${Math.abs(excess).toFixed(1)}%，建议换策略或扩大回测窗口`
})

// ── 导出回测结果 ─────────────────────────────────────────────────
async function exportBacktest() {
  if (!backtestResult.value) return
  
  try {
    const response = await fetch('/api/v1/export/backtest/result', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      },
      body: JSON.stringify({
        result: backtestResult.value,
        strategy_type: strategyType.value,
        symbol: symbol.value,
        start_date: startDate.value,
        end_date: endDate.value
      })
    })
    
    if (!response.ok) {
      throw new Error(`Export failed: ${response.statusText}`)
    }
    
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `backtest_${symbol.value}_${new Date().toISOString().slice(0,10)}.xlsx`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  } catch (e) {
    console.error('[Backtest] Export failed:', e)
    alert('导出失败: ' + e.message)
  }
}
</script>
