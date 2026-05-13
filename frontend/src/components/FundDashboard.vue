<template>
  <div class="flex flex-col h-full bg-terminal-bg text-terminal-fg font-mono overflow-y-auto">
    
    <!-- 顶部：选项卡 + 搜索 -->
    <div class="p-4 border-b border-theme-secondary shrink-0 bg-terminal-panel/50">
      <div class="flex flex-col gap-3">
        <!-- 选项卡 -->
        <div class="flex gap-2">
          <button 
            @click="activeTab = 'etf'"
            class="px-4 py-2 text-sm rounded-t-sm border-b-2 transition-colors"
            :class="activeTab === 'etf' 
              ? 'bg-terminal-panel border-terminal-accent text-terminal-accent' 
              : 'bg-terminal-bg border-transparent text-theme-tertiary hover:text-theme-secondary'"
          >📊 场内基金 (ETF/LOF)</button>
          <button 
            @click="activeTab = 'open'"
            class="px-4 py-2 text-sm rounded-t-sm border-b-2 transition-colors"
            :class="activeTab === 'open' 
              ? 'bg-terminal-panel border-terminal-accent text-terminal-accent' 
              : 'bg-terminal-bg border-transparent text-theme-tertiary hover:text-theme-secondary'"
          >💰 场外公募基金</button>
          <button 
            @click="activeTab = 'compare'"
            class="px-4 py-2 text-sm rounded-t-sm border-b-2 transition-colors"
            :class="activeTab === 'compare' 
              ? 'bg-terminal-panel border-terminal-accent text-terminal-accent' 
              : 'bg-terminal-bg border-transparent text-theme-tertiary hover:text-theme-secondary'"
          >🔀 基金对比</button>
        </div>
        
        <!-- 搜索栏（ETF/公募基金）-->
        <div v-if="activeTab !== 'compare'" class="flex items-center gap-2">
          <div class="relative flex-1">
            <input 
              v-model="searchQuery" 
              @keyup.enter="searchFund"
              :placeholder="activeTab === 'etf' ? '输入 ETF 代码（如 510300）' : '输入基金代码/名称/拼音'"
              class="w-full bg-terminal-bg border border-theme-secondary rounded-sm px-3 py-1.5 text-sm focus:border-terminal-accent outline-none"
            />
            <button 
              @click="searchFund"
              class="absolute right-1 top-1/2 -translate-y-1/2 px-2 py-0.5 text-xs bg-terminal-accent/20 text-terminal-accent rounded-sm hover:bg-terminal-accent/30 transition"
            >🔍</button>
          </div>
          <!-- 快捷列表 -->
          <div class="flex gap-1 flex-wrap">
            <button 
              v-for="f in (activeTab === 'etf' ? quickETFs : quickFunds)" 
              :key="f.code"
              @click="selectFund(f.code)"
              class="px-2 py-1 text-xs rounded-sm border transition-colors whitespace-nowrap"
              :class="selectedFundCode === f.code 
                ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent' 
                : 'bg-terminal-bg border-theme-secondary text-theme-tertiary hover:border-theme-secondary'"
            >
              {{ f.name }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 加载中（包括自动加载） -->
    <div v-if="loading || autoLoading" class="flex-1 p-4 space-y-4 overflow-y-auto">
      <!-- 顶部指标骨架 -->
      <div class="grid grid-cols-3 gap-3">
        <div class="skeleton h-16 rounded-sm" v-for="n in 3" :key="n"></div>
      </div>
      <!-- 图表骨架 -->
      <div class="skeleton h-64 rounded-sm"></div>
      <!-- 信息列表骨架 -->
      <div class="space-y-2">
        <div class="skeleton h-4 w-3/4 rounded-sm" v-for="n in 6" :key="n"></div>
      </div>
    </div>

    <!-- 自动加载失败 -->
    <div v-else-if="autoLoadFailed && !fundInfo" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <div class="text-4xl mb-3">⚠️</div>
        <div class="text-theme-muted text-sm mb-3">自动加载失败</div>
        <div class="text-xs text-theme-tertiary mb-4">
          请检查网络连接后重试
        </div>
        <button 
          @click="retryAutoLoad"
          class="px-4 py-2 bg-terminal-accent/20 text-terminal-accent rounded-sm text-sm hover:bg-terminal-accent/30 transition"
        >
          🔄 重试
        </button>
      </div>
    </div>

    <!-- 无数据（仅 ETF/公募基金显示） -->
    <div v-else-if="activeTab !== 'compare' && !fundInfo && !loading && !autoLoading" class="flex-1 flex items-center justify-center">
      <div class="text-center py-12">
        <div class="text-6xl mb-4">📊</div>
        <div class="text-lg text-terminal-accent font-bold mb-2">
          {{ activeTab === 'etf' ? 'ETF 基金查询' : '公募基金查询' }}
        </div>
        <div class="text-sm text-terminal-dim mb-4">
          输入基金代码或从下方快捷列表选择
        </div>

        <!-- 快捷基金按钮 -->
        <div class="bg-terminal-panel/50 border border-theme rounded-sm p-4 mb-4 max-w-2xl mx-auto">
          <div class="text-xs text-terminal-dim mb-3">💡 快速查询：</div>
          <div class="flex flex-wrap gap-2 justify-center">
            <button
              v-for="f in (activeTab === 'etf' ? quickETFs : quickFunds)"
              :key="f.code"
              @click="selectFund(f.code)"
              class="px-3 py-2 text-sm rounded-sm border transition-colors whitespace-nowrap bg-terminal-bg border-theme-secondary text-theme-secondary hover:border-terminal-accent hover:text-terminal-accent"
            >
              {{ f.name }}
            </button>
          </div>
        </div>

        <div class="text-xs text-theme-tertiary">
          {{ activeTab === 'etf' ? '支持沪深 ETF、LOF 场内基金' : '支持股票型、混合型、债券型公募基金' }}
        </div>
      </div>
    </div>

    <!-- 主内容区（ETF/公募基金/对比） -->
    <div v-if="activeTab === 'compare' || fundInfo || loading || autoLoading" class="flex-1 p-4 space-y-4 overflow-y-auto">
      
      <!-- ETF 面板 -->
      <div v-if="activeTab === 'etf'" class="space-y-4">
        <!-- 核心指标（ETF 特有） -->
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <div class="bg-terminal-panel/50 border border-theme rounded-sm p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">最新价</div>
            <div class="text-lg font-bold" :class="getChangeColor(fundInfo?.change_pct)">
              {{ fundInfo?.price ?? '-' }}
            </div>
          </div>
          <div class="bg-terminal-panel/50 border border-theme rounded-sm p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">涨跌幅</div>
            <div class="text-lg font-bold" :class="getChangeColor(fundInfo?.change_pct)">
              {{ fundInfo?.change_pct ?? '-' }}%
            </div>
          </div>
          <div class="bg-terminal-panel/50 border border-theme rounded-sm p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">IOPV 净值</div>
            <div class="text-lg font-bold text-theme-primary">
              {{ fundInfo?.iopv ?? '-' }}
            </div>
          </div>
          <div class="bg-terminal-panel/50 border border-theme rounded-sm p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">折溢价率</div>
            <div class="text-lg font-bold" :class="getChangeColor(-fundInfo?.premium_rate)">
              {{ fundInfo?.premium_rate ?? '-' }}%
            </div>
          </div>
          <div class="bg-terminal-panel/50 border border-theme rounded-sm p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">成交量</div>
            <div class="text-sm font-bold text-theme-primary">
              {{ formatVolume(fundInfo?.volume) }}
            </div>
          </div>
          <div class="bg-terminal-panel/50 border border-theme rounded-sm p-3">
            <div class="text-[10px] text-theme-tertiary mb-1">成交额</div>
            <div class="text-sm font-bold text-theme-primary">
              {{ formatAmount(fundInfo?.amount) }}
            </div>
          </div>
        </div>

        <!-- 买卖盘五档 -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- 买盘 -->
          <div class="bg-terminal-panel border border-theme rounded-sm p-4">
            <div class="flex items-center justify-between mb-3">
              <span class="text-terminal-accent font-bold text-sm">📗 买盘五档</span>
              <span class="text-[10px] text-theme-tertiary">实时</span>
            </div>
            <div class="space-y-1">
              <div v-for="bid in fundInfo?.bids || []" :key="bid.level" 
                   class="flex items-center justify-between py-1 px-2 rounded-sm"
                   :class="bid.level === 1 ? 'bg-[var(--color-danger-bg)]' : ''">
                <span class="text-xs text-theme-tertiary">买{{ bid.level }}</span>
                <span class="text-sm font-bold text-[var(--color-danger)]">{{ bid.price }}</span>
                <span class="text-xs text-theme-tertiary">{{ formatVolume(bid.volume) }}</span>
              </div>
            </div>
          </div>
          
          <!-- 卖盘 -->
          <div class="bg-terminal-panel border border-theme rounded-sm p-4">
            <div class="flex items-center justify-between mb-3">
              <span class="text-terminal-accent font-bold text-sm">📕 卖盘五档</span>
              <span class="text-[10px] text-theme-tertiary">实时</span>
            </div>
            <div class="space-y-1">
              <div v-for="ask in fundInfo?.asks || []" :key="ask.level" 
                   class="flex items-center justify-between py-1 px-2 rounded-sm"
                   :class="ask.level === 1 ? 'bg-[var(--color-success-bg)]' : ''">
                <span class="text-xs text-theme-tertiary">卖{{ ask.level }}</span>
                <span class="text-sm font-bold text-[var(--color-success)]">{{ ask.price }}</span>
                <span class="text-xs text-theme-tertiary">{{ formatVolume(ask.volume) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- K 线走势图 -->
        <div class="bg-terminal-panel border border-theme rounded-sm p-4">
          <div class="flex items-center justify-between mb-3">
            <span class="text-terminal-accent font-bold text-sm">📈 K 线走势</span>
            <div class="flex gap-1">
              <button 
                v-for="p in klinePeriods" 
                :key="p.key"
                @click="loadETFHistory(p.key)"
                class="px-2 py-0.5 text-[10px] rounded-sm border transition"
                :class="klinePeriod === p.key 
                  ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent' 
                  : 'bg-terminal-bg border-theme-secondary text-theme-tertiary hover:border-theme-secondary'"
              >{{ p.label }}</button>
            </div>
          </div>
          <div ref="klineChartRef" class="w-full sm:h-[320px]" style="height: 280px;"></div>
        </div>
      </div>

      <!-- 公募基金面板（专业级） -->
      <div v-else-if="activeTab === 'open'" class="space-y-4">
        
        <!-- A. 头部概览区 -->
        <div class="bg-terminal-panel border border-theme rounded-sm p-4">
          <div class="flex items-start justify-between mb-4">
            <div>
              <h2 class="text-xl font-bold text-theme-primary">{{ fundInfo?.name ?? '-' }}</h2>
              <div class="text-xs text-theme-tertiary mt-1">
                代码：{{ selectedFundCode }} | 类型：{{ fundInfo?.type ?? '-' }} | 成立：{{ fundInfo?.found_date ?? '-' }}
              </div>
            </div>
            <div class="text-right">
              <div class="text-3xl font-bold" :class="getChangeColor(fundInfo?.nav_change_pct)">
                {{ fundInfo?.nav ?? '-' }}
              </div>
              <div class="text-xs text-theme-tertiary">单位净值 ({{ fundInfo?.nav_date ?? '-' }})</div>
            </div>
          </div>
          
          <!-- 详细指标网格 -->
          <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
            <div class="text-center p-2 bg-terminal-bg/50 rounded-sm">
              <div class="text-[10px] text-theme-tertiary">累计净值</div>
              <div class="text-sm font-bold text-theme-primary">{{ fundInfo?.accumulated_nav ?? '-' }}</div>
            </div>
            <div class="text-center p-2 bg-terminal-bg/50 rounded-sm">
              <div class="text-[10px] text-theme-tertiary">日涨跌</div>
              <div class="text-sm font-bold" :class="getChangeColor(fundInfo?.nav_change_pct)">{{ fundInfo?.nav_change_pct ?? '-' }}%</div>
            </div>
            <div class="text-center p-2 bg-terminal-bg/50 rounded-sm">
              <div class="text-[10px] text-theme-tertiary">基金规模</div>
              <div class="text-sm font-bold text-theme-primary">{{ fundInfo?.scale ?? '-' }}亿</div>
            </div>
            <div class="text-center p-2 bg-terminal-bg/50 rounded-sm">
              <div class="text-[10px] text-theme-tertiary">晨星评级</div>
              <div class="text-sm font-bold text-theme-primary">{{ fundInfo?.rating ?? 'N/A' }}</div>
            </div>
            <div class="text-center p-2 bg-terminal-bg/50 rounded-sm">
              <div class="text-[10px] text-theme-tertiary">申购费率</div>
              <div class="text-sm font-bold text-theme-primary">{{ fundInfo?.purchase_fee ?? 'N/A' }}</div>
            </div>
            <div class="text-center p-2 bg-terminal-bg/50 rounded-sm">
              <div class="text-[10px] text-theme-tertiary">赎回费率</div>
              <div class="text-sm font-bold text-theme-primary">{{ fundInfo?.redemption_fee ?? 'N/A' }}</div>
            </div>
            <div class="text-center p-2 bg-terminal-bg/50 rounded-sm">
              <div class="text-[10px] text-theme-tertiary">分红频率</div>
              <div class="text-sm font-bold text-theme-primary">{{ fundInfo?.dividend_freq ?? 'N/A' }}</div>
            </div>
            <div class="text-center p-2 bg-terminal-bg/50 rounded-sm">
              <div class="text-[10px] text-theme-tertiary">基金经理</div>
              <div class="text-xs font-bold text-theme-primary truncate" :title="fundInfo?.manager">{{ fundInfo?.manager ?? '-' }}</div>
            </div>
          </div>
        </div>

        <!-- B. 阶段收益追踪表 (Trailing Returns) -->
        <div class="bg-terminal-panel border border-theme rounded-sm p-4">
          <div class="flex items-center justify-between mb-3">
            <span class="text-terminal-accent font-bold text-sm">📊 阶段收益追踪</span>
            <span class="text-[10px] text-theme-tertiary">与同类平均及基准对比</span>
          </div>
          <div class="overflow-x-auto scrollbar-hide">
            <table class="w-full text-xs whitespace-nowrap">
              <thead class="border-b border-theme">
                <tr class="text-terminal-dim">
                  <th class="px-2 py-2 text-left font-normal">指标</th>
                  <th class="px-2 py-2 text-right font-normal">1 周</th>
                  <th class="px-2 py-2 text-right font-normal">1 月</th>
                  <th class="px-2 py-2 text-right font-normal">3 月</th>
                  <th class="px-2 py-2 text-right font-normal">6 月</th>
                  <th class="px-2 py-2 text-right font-normal">YTD</th>
                  <th class="px-2 py-2 text-right font-normal">1 年</th>
                  <th class="px-2 py-2 text-right font-normal">3 年</th>
                  <th class="px-2 py-2 text-right font-normal">5 年</th>
                </tr>
              </thead>
              <tbody>
                <tr class="border-b border-theme/30">
                  <td class="px-2 py-2 text-theme-primary font-medium">本基金</td>
                  <td v-for="p in trailingReturns.periods" :key="p" class="px-2 py-2 text-right" :class="getChangeColor(trailingReturns.fund[p])">{{ trailingReturns.fund[p] ?? '-' }}%</td>
                </tr>
                <tr class="border-b border-theme/30 bg-theme-hover/20">
                  <td class="px-2 py-2 text-theme-secondary">同类平均</td>
                  <td v-for="p in trailingReturns.periods" :key="p" class="px-2 py-2 text-right text-theme-secondary">{{ trailingReturns.category[p] ?? '-' }}%</td>
                </tr>
                <tr>
                  <td class="px-2 py-2 text-theme-secondary">基准指数</td>
                  <td v-for="p in trailingReturns.periods" :key="p" class="px-2 py-2 text-right text-theme-secondary">{{ trailingReturns.benchmark[p] ?? '-' }}%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- C. 风险与波动指标 -->
        <div class="bg-terminal-panel border border-theme rounded-sm p-4">
          <div class="flex items-center justify-between mb-3">
            <span class="text-terminal-accent font-bold text-sm">⚠️ 风险指标</span>
          </div>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="p-3 bg-terminal-bg/50 rounded-sm">
              <div class="text-[10px] text-theme-tertiary mb-1">夏普比率</div>
              <div class="text-lg font-bold text-theme-primary">{{ riskMetrics.sharpe ?? '-' }}</div>
              <div class="text-[10px] text-theme-muted">Sharpe Ratio</div>
            </div>
            <div class="p-3 bg-terminal-bg/50 rounded-sm">
              <div class="text-[10px] text-theme-tertiary mb-1">最大回撤</div>
              <div class="text-lg font-bold text-[var(--color-danger)]">{{ riskMetrics.max_drawdown ?? '-' }}%</div>
              <div class="text-[10px] text-theme-muted">Max Drawdown</div>
            </div>
            <div class="p-3 bg-terminal-bg/50 rounded-sm">
              <div class="text-[10px] text-theme-tertiary mb-1">阿尔法</div>
              <div class="text-lg font-bold" :class="getChangeColor(riskMetrics.alpha)">{{ riskMetrics.alpha ?? '-' }}</div>
              <div class="text-[10px] text-theme-muted">Alpha</div>
            </div>
            <div class="p-3 bg-terminal-bg/50 rounded-sm">
              <div class="text-[10px] text-theme-tertiary mb-1">贝塔</div>
              <div class="text-lg font-bold text-theme-primary">{{ riskMetrics.beta ?? '-' }}</div>
              <div class="text-[10px] text-theme-muted">Beta</div>
            </div>
          </div>
        </div>

        <!-- D. 净值走势 + 资产配置 -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <!-- 净值走势图 -->
          <div class="lg:col-span-2 bg-terminal-panel border border-theme rounded-sm p-4">
            <div class="flex items-center justify-between mb-3">
              <span class="text-terminal-accent font-bold text-sm">📈 净值走势</span>
              <div class="flex gap-1">
                <button 
                  v-for="p in navPeriods" 
                  :key="p.key"
                  @click="loadNAVHistory(p.key)"
                  class="px-2 py-0.5 text-[10px] rounded-sm border transition"
                  :class="navPeriod === p.key 
                    ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent' 
                    : 'bg-terminal-bg border-theme-secondary text-theme-tertiary hover:border-theme-secondary'"
                >{{ p.label }}</button>
              </div>
            </div>
            <div ref="navChartRef" class="w-full" style="height: 280px;"></div>
          </div>

          <!-- 资产配置饼图 -->
          <div class="bg-terminal-panel border border-theme rounded-sm p-4">
            <div class="flex items-center justify-between mb-3">
              <span class="text-terminal-accent font-bold text-sm">🎯 资产配置</span>
              <span class="text-[10px] text-theme-tertiary">X-Ray</span>
            </div>
            <div ref="assetChartRef" class="w-full" style="height: 200px;"></div>
            <div class="mt-3 space-y-1">
              <div v-for="(item, i) in assetAllocation" :key="i" 
                   class="flex items-center justify-between text-xs">
                <div class="flex items-center gap-2">
                  <span class="w-2 h-2 rounded-full" :style="{ background: item.color }"></span>
                  <span class="text-theme-secondary">{{ item.name }}</span>
                </div>
                <span class="text-theme-primary font-bold">{{ item.value }}%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- E. 重仓股（带进度条可视化） -->
        <div class="bg-terminal-panel border border-theme rounded-sm p-4">
          <div class="flex items-center justify-between mb-3">
            <span class="text-terminal-accent font-bold text-sm">📊 十大重仓股</span>
            <span class="text-[10px] text-theme-tertiary">截至 {{ fundInfo?.quarter ?? '-' }}</span>
          </div>
          <div class="space-y-2">
            <div v-for="(stock, i) in topHoldings" :key="i" class="flex items-center gap-3">
              <span class="text-[10px] text-theme-tertiary w-4 text-right">{{ i + 1 }}</span>
              <div class="flex-1">
                <div class="flex items-center justify-between text-xs mb-1">
                  <span class="text-theme-primary font-medium">{{ stock.name }} ({{ stock.code }})</span>
                  <span class="text-theme-accent font-bold">{{ stock.ratio }}%</span>
                </div>
                <!-- 进度条可视化 -->
                <div class="w-full h-1.5 bg-terminal-bg rounded-full overflow-hidden">
                  <div class="h-full bg-gradient-to-r from-terminal-accent to-terminal-accent/70 rounded-full" 
                       :style="{ width: Math.min(stock.ratio * 3, 100) + '%' }"></div>
                </div>
              </div>
            </div>
            <div v-if="topHoldings.length === 0" class="text-center text-theme-muted text-sm py-8">
              暂无重仓股数据
            </div>
          </div>
        </div>

        <!-- 数据源信息 -->
        <div class="text-xs text-theme-tertiary text-center">
          数据来源：{{ dataSource }} | 最后更新：{{ lastUpdateTime }}
        </div>
      </div>

      <!-- 基金对比面板 -->
      <div v-if="activeTab === 'compare'" class="space-y-4">
        <!-- 基金选择器 -->
        <div class="bg-terminal-panel border border-theme rounded-sm p-4">
          <div class="flex items-center justify-between mb-3">
            <span class="text-terminal-accent font-bold text-sm">🔀 基金对比</span>
            <span class="text-[10px] text-theme-tertiary">最多选择 3 只基金</span>
          </div>
          <div class="flex flex-wrap gap-2 mb-3">
            <div v-for="(fund, idx) in compareFunds" :key="fund.code"
                 class="flex items-center gap-1 px-2 py-1 rounded-sm border text-xs"
                 :class="compareColors[idx]">
              <span>{{ fund.name }}</span>
              <button @click="removeCompareFund(idx)" class="hover:text-[var(--color-danger)]">×</button>
            </div>
          </div>
          <div class="flex gap-2">
            <input v-model="compareInput" @keyup.enter="addCompareFund"
                   placeholder="输入基金代码添加"
                   class="flex-1 bg-terminal-bg border border-theme-secondary rounded-sm px-3 py-1.5 text-sm focus:border-terminal-accent outline-none" />
            <button @click="addCompareFund"
                    class="px-3 py-1.5 bg-terminal-accent/20 text-terminal-accent rounded-sm text-sm hover:bg-terminal-accent/30 transition">
              添加
            </button>
            <button @click="clearCompareFunds"
                    class="px-3 py-1.5 bg-terminal-panel text-theme-tertiary rounded-sm text-sm hover:text-theme-primary transition">
              清空
            </button>
          </div>
        </div>

        <!-- 对比图表 -->
        <div v-if="compareFunds.length >= 2" class="bg-terminal-panel border border-theme rounded-sm p-4">
          <div class="flex items-center justify-between mb-3">
            <span class="text-terminal-accent font-bold text-sm">📈 净值走势对比</span>
            <span class="text-[10px] text-theme-tertiary">归一化对比</span>
          </div>
          <div ref="compareChartRef" class="w-full sm:h-[350px]" style="height: 280px;"></div>
        </div>

        <!-- 对比表格：移动端优化 -->
        <div v-if="compareFunds.length >= 2" class="bg-terminal-panel border border-theme rounded-sm p-3 md:p-4">
          <div class="flex items-center justify-between mb-3">
            <span class="text-terminal-accent font-bold text-sm">📊 收益对比</span>
          </div>
          <div class="overflow-x-auto -mx-3 md:mx-0 px-3 md:px-0">
            <table class="w-full text-xs min-w-[300px]">
              <thead>
                <tr class="border-b border-theme-secondary">
                  <th class="text-left py-2 px-1 md:px-2 text-theme-tertiary">指标</th>
                  <th v-for="(fund, idx) in compareFunds" :key="fund.code" class="text-right py-2 px-1 md:px-2"
                      :class="compareColorsText[idx]">
                    <span class="truncate max-w-[80px] inline-block">{{ fund.name }}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="period in comparePeriods" :key="period.key" class="border-b border-theme/30">
                  <td class="py-2 px-1 md:px-2 text-theme-secondary">{{ period.label }}</td>
                  <td v-for="(fund, idx) in compareFunds" :key="fund.code" class="text-right py-2 px-1 md:px-2 font-mono"
                      :class="getCompareReturnColor(fund.returns?.[period.key])">
                    {{ fund.returns?.[period.key] ?? '-' }}%
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 提示 -->
        <div v-if="compareFunds.length < 2" class="text-center py-8 text-theme-tertiary text-sm">
          请至少添加 2 只基金进行对比
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, shallowRef, reactive, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { apiFetch, extractData } from '../utils/api.js'
import { logger } from '../utils/logger.js'
import { formatVol, formatAmount } from '../utils/formatters.js'

// ECharts 通过 CDN 加载，使用全局变量
const getEcharts = () => window.echarts

// ── 状态 ────────────────────────────────────────────────────────
const loading = ref(false)
const autoLoading = ref(false)
const autoLoadFailed = ref(false)
const searchQuery = ref('')
const selectedFundCode = ref('')
const activeTab = ref('open') // 'etf' | 'open' | 'compare'
const fundInfo = ref(null)
const dataSource = ref('')
const lastUpdateTime = ref('')

// ── 基金对比状态 ────────────────────────────────────────────────
const compareFunds = ref([])
const compareInput = ref('')
const compareChartRef = ref(null)
const compareChart = shallowRef(null)
const compareColors = [
  'bg-[var(--color-danger-bg)] text-[var(--color-danger)] border-[var(--color-danger-border)]',
  'bg-[var(--color-info-bg)] text-[var(--color-info)] border-[var(--color-info-border)]',
  'bg-[var(--color-success-bg)] text-[var(--color-success)] border-[var(--color-success-border)]',
]
const compareColorsText = ['text-[var(--color-danger)]', 'text-[var(--color-info)]', 'text-[var(--color-success)]']
const comparePeriods = [
  { key: '1m', label: '近1月' },
  { key: '3m', label: '近3月' },
  { key: '6m', label: '近6月' },
  { key: '1y', label: '近1年' },
  { key: '3y', label: '近3年' },
]

// 快捷列表
const quickETFs = [
  { code: '510300', name: '沪深 300ETF' },
  { code: '510500', name: '中证 500ETF' },
  { code: '159915', name: '创业板 ETF' },
  { code: '518880', name: '黄金 ETF' },
  { code: '513050', name: '中概互联 ETF' },
]

const quickFunds = [
  { code: '005827', name: '易方达蓝筹' },
  { code: '000311', name: '景顺长城沪深 300' },
  { code: '110011', name: '易方达中小盘' },
  { code: '007119', name: '睿远成长价值' },
]

// 周期选项
const klinePeriods = [
  { key: 'daily', label: '日 K' },
  { key: 'weekly', label: '周 K' },
  { key: 'monthly', label: '月 K' },
]
const klinePeriod = ref('daily')

const navPeriods = [
  { key: '1m', label: '1 月' },
  { key: '3m', label: '3 月' },
  { key: '6m', label: '6 月' },
  { key: '1y', label: '1 年' },
]
const navPeriod = ref('6m')

// 数据
const klineHistory = ref([])
const navHistory = ref([])
const topHoldings = ref([])
const assetAllocation = ref([])

// 阶段收益追踪（Trailing Returns）
const trailingReturns = reactive({
  periods: ['1w', '1m', '3m', '6m', 'ytd', '1y', '3y', '5y'],
  fund: { '1w': null, '1m': null, '3m': null, '6m': null, 'ytd': null, '1y': null, '3y': null, '5y': null },
  category: { '1w': null, '1m': null, '3m': null, '6m': null, 'ytd': null, '1y': null, '3y': null, '5y': null },
  benchmark: { '1w': null, '1m': null, '3m': null, '6m': null, 'ytd': null, '1y': null, '3y': null, '5y': null },
})

// 风险指标
const riskMetrics = reactive({
  sharpe: null,
  max_drawdown: null,
  alpha: null,
  beta: null,
})

// Chart refs
const klineChartRef = ref(null)
const navChartRef = ref(null)
const assetChartRef = ref(null)
const klineChart = shallowRef(null)
const navChart = shallowRef(null)
const assetChart = shallowRef(null)

// ── API 调用 ────────────────────────────────────────────────────

async function searchFund() {
  const query = searchQuery.value.trim()
  if (!query) return
  await selectFund(query)
}

async function selectFund(code, retryCount = 0, maxRetries = 2) {
  if (!code) return
  selectedFundCode.value = code
  
  // Set loading state based on whether this is an auto-load
  if (retryCount === 0) {
    loading.value = true
    autoLoading.value = true
    autoLoadFailed.value = false
  }
  
  dataSource.value = ''
  
  try {
    if (activeTab.value === 'etf') {
      await Promise.all([
        loadETFInfo(code),
        loadETFHistory(klinePeriod.value),
      ])
    } else {
      await Promise.all([
        loadOpenFundInfo(code),
        loadNAVHistory(navPeriod.value),
        loadPortfolio(code),
      ])
    }
    
    lastUpdateTime.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    autoLoadFailed.value = false
  } catch (e) {
    logger.error('[FundDashboard] 加载失败:', e)
    
    // Retry logic with exponential backoff
    if (retryCount < maxRetries) {
      const delay = Math.pow(2, retryCount) * 1000 // 1s, 2s, 4s...
      logger.warn(`[FundDashboard] 重试 ${retryCount + 1}/${maxRetries}，等待 ${delay}ms`)
      await new Promise(resolve => setTimeout(resolve, delay))
      return selectFund(code, retryCount + 1, maxRetries)
    } else {
      autoLoadFailed.value = true
      logger.error('[FundDashboard] 自动加载失败，已达最大重试次数')
    }
  } finally {
    loading.value = false
    autoLoading.value = false
    // 等待 DOM 更新完成后再渲染图表
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))
    if (activeTab.value === 'etf') {
      renderKlineChart()
    } else {
      renderNavChart()
      renderAssetChart()
    }
  }
}

// ── 基金对比 ───────────────────────────────────────────────────

function addCompareFund() {
  const code = compareInput.value.trim()
  if (!code) return
  if (compareFunds.value.length >= 3) {
    alert('最多只能对比 3 只基金')
    return
  }
  if (compareFunds.value.some(f => f.code === code)) {
    alert('该基金已在对比列表中')
    return
  }
  // 添加到列表（先占位，后续异步加载数据）
  compareFunds.value.push({
    code,
    name: code, // 临时名称
    returns: {},
    history: [],
  })
  compareInput.value = ''
  loadCompareData()
}

function removeCompareFund(idx) {
  compareFunds.value.splice(idx, 1)
  if (compareFunds.value.length >= 2) {
    renderCompareChart()
  }
}

function clearCompareFunds() {
  compareFunds.value = []
}

async function loadCompareData() {
  if (compareFunds.value.length < 2) return

  for (const fund of compareFunds.value) {
    try {
      // 加载基金基本信息
      const infoRes = await apiFetch(`/api/v1/fund/open/info?code=${fund.code}`)
      const infoData = extractData(infoRes)
      if (infoData) {
        fund.name = infoData.name || fund.code
      }

      // 加载历史净值（用于对比图）
      const navRes = await apiFetch(`/api/v1/fund/open/nav/${fund.code}?period=1y`)
      const navData = extractData(navRes)
      if (Array.isArray(navData)) {
        fund.history = navData.map(d => ({
          date: d.date,
          nav: parseFloat(d.nav) || 0,
        }))
      }

      // 加载阶段收益（真实 API）
      const returnsRes = await apiFetch(`/api/v1/fund/open/returns/${fund.code}`)
      const returnsData = extractData(returnsRes)
      if (returnsData && returnsData.returns) {
        fund.returns = {
          '1m': returnsData.returns['1m'] ?? '-',
          '3m': returnsData.returns['3m'] ?? '-',
          '6m': returnsData.returns['6m'] ?? '-',
          '1y': returnsData.returns['1y'] ?? '-',
          '3y': returnsData.returns['3y'] ?? '-',
        }
      } else {
        fund.returns = { '1m': '-', '3m': '-', '6m': '-', '1y': '-', '3y': '-' }
      }
    } catch (e) {
      logger.warn(`[Compare] 加载 ${fund.code} 失败:`, e)
      fund.returns = { '1m': '-', '3m': '-', '6m': '-', '1y': '-', '3y': '-' }
    }
  }

  await nextTick()
  renderCompareChart()
}

function renderCompareChart() {
  if (!compareChartRef.value || compareFunds.value.length < 2) return
  const echarts = getEcharts()
  if (!echarts) return

  if (!compareChart.value || compareChart.value.getDom() !== compareChartRef.value) {
    if (compareChart.value) {
      try { compareChart.value.dispose() } catch (e) {}
    }
    compareChart.value = echarts.init(compareChartRef.value)
  }

  // 归一化处理：以第一天为基准 1.0
  const series = compareFunds.value.map((fund, idx) => {
    if (!fund.history || fund.history.length === 0) return null
    const baseNav = fund.history[0].nav
    const data = fund.history.map(d => [d.date, (d.nav / baseNav).toFixed(4)])
    return {
      name: fund.name,
      type: 'line',
      smooth: true,
      symbol: 'none',
      data,
      lineStyle: { width: 2 },
      itemStyle: { color: ['#ef4444', '#3b82f6', '#22c55e'][idx] },
    }
  }).filter(Boolean)

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: function(params) {
        let html = `<div style="font-size:12px">${params[0].axisValue}</div>`
        params.forEach(p => {
          html += `<div style="font-size:11px">${p.marker} ${p.seriesName}: ${p.value[1]}</div>`
        })
        return html
      }
    },
    legend: { data: compareFunds.value.map(f => f.name), textStyle: { color: '#9ca3af', fontSize: 11 }, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '30', containLabel: true },
    xAxis: {
      type: 'time',
      axisLine: { lineStyle: { color: '#374151' } },
      axisLabel: { color: '#6b7280', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#374151' } },
      axisLabel: { color: '#6b7280', fontSize: 10, formatter: v => v.toFixed(2) },
      splitLine: { lineStyle: { color: '#1f2937' } },
    },
    series,
  }
  compareChart.value.setOption(option, true)
  compareChart.value.resize()
}

function getCompareReturnColor(val) {
  if (val === undefined || val === null || val === '-') return 'text-theme-muted'
  const v = parseFloat(val)
  if (v > 0) return 'text-[var(--color-danger)]'
  if (v < 0) return 'text-[var(--color-success)]'
  return 'text-theme-primary'
}

// ── ETF 相关 ───────────────────────────────────────────────────

async function loadETFInfo(code) {
  try {
    const res = await apiFetch(`/api/v1/fund/etf/info?code=${code}`)
    const data = extractData(res)
    if (data) {
      fundInfo.value = {
        code: data.code || code,
        name: data.name || '-',
        price: data.price || '-',
        change_pct: data.change_pct ? parseFloat(data.change_pct).toFixed(2) : '-',
        change: data.change || 0,
        volume: data.volume || 0,
        amount: data.amount || 0,
        iopv: data.iopv || '-',
        premium_rate: data.premium_rate ? parseFloat(data.premium_rate).toFixed(2) : '-',
        bids: data.bids || [],
        asks: data.asks || [],
      }
      dataSource.value = data.source || 'unknown'
    }
  } catch (e) {
    logger.warn('[ETF Info] 获取失败:', e)
  }
}

async function loadETFHistory(period) {
  klinePeriod.value = period
  const code = selectedFundCode.value
  if (!code) return
  
  try {
    const res = await apiFetch(`/api/v1/fund/etf/history?code=${code}&period=${period}`)
    const data = extractData(res)
    klineHistory.value = Array.isArray(data) ? data : []
    
    await nextTick()
    renderKlineChart()
  } catch (e) {
    logger.warn('[ETF History] 获取失败:', e)
  }
}

// ── 公募基金相关 ───────────────────────────────────────────────

async function loadOpenFundInfo(code) {
  try {
    // 并发加载基金信息、阶段收益和风险指标
    const [infoRes, returnsRes, riskRes] = await Promise.all([
      apiFetch(`/api/v1/fund/open/info?code=${code}`),
      apiFetch(`/api/v1/fund/open/returns/${code}`),
      apiFetch(`/api/v1/fund/open/risk/${code}`),
    ])
    
    const data = extractData(infoRes)
    const returnsData = extractData(returnsRes)
    const riskData = extractData(riskRes)
    
    if (data) {
      fundInfo.value = {
        code: data.code || code,
        name: data.name || '-',
        type: data.type || '-',
        nav: data.nav || '-',
        accumulated_nav: data.accumulated_nav || '-',
        nav_change_pct: data.nav_change_pct ? parseFloat(data.nav_change_pct).toFixed(2) : '-',
        nav_date: data.nav_date || '-',
        scale: data.scale || '-',
        found_date: data.found_date || '-',
        manager: data.manager || '-',
        company: data.company || '-',
        quarter: data.quarter || '-',
        rating: data.rating || 'N/A',
        purchase_fee: data.purchase_fee || 'N/A',
        redemption_fee: data.redemption_fee || 'N/A',
        dividend_freq: data.dividend_freq || 'N/A',
      }
      dataSource.value = data.source || 'unknown'
    }
    
    // 使用真实阶段收益数据
    if (returnsData && returnsData.returns) {
      trailingReturns.fund = {
        '1w': returnsData.returns['1w'] ?? null,
        '1m': returnsData.returns['1m'] ?? null,
        '3m': returnsData.returns['3m'] ?? null,
        '6m': returnsData.returns['6m'] ?? null,
        'ytd': returnsData.returns['ytd'] ?? null,
        '1y': returnsData.returns['1y'] ?? null,
        '3y': returnsData.returns['3y'] ?? null,
        '5y': returnsData.returns['since_inception'] ?? null,
      }
      // 同类平均和基准指数暂无数据源，显示为 null
      trailingReturns.category = { '1w': null, '1m': null, '3m': null, '6m': null, 'ytd': null, '1y': null, '3y': null, '5y': null }
      trailingReturns.benchmark = { '1w': null, '1m': null, '3m': null, '6m': null, 'ytd': null, '1y': null, '3y': null, '5y': null }
    }
    
    // 使用真实风险指标数据
    if (riskData) {
      riskMetrics.sharpe = riskData.sharpe ?? null
      riskMetrics.max_drawdown = riskData.max_drawdown ?? null
      riskMetrics.alpha = riskData.alpha ?? null
      riskMetrics.beta = riskData.beta ?? null
    }
  } catch (e) {
    logger.warn('[Open Fund Info] 获取失败:', e)
  }
}

async function loadNAVHistory(period) {
  navPeriod.value = period
  const code = selectedFundCode.value
  if (!code) return
  
  try {
    const res = await apiFetch(`/api/v1/fund/open/nav/${code}?period=${period}`)
    const data = extractData(res)
    navHistory.value = Array.isArray(data) ? data : []
    
    console.log('[NAV History] 获取成功，数据条数:', navHistory.value.length)
    console.log('[NAV History] 第一条数据:', navHistory.value[0])
    console.log('[NAV History] navChartRef:', !!navChartRef.value)
    
    await nextTick()
    console.log('[NAV History] after nextTick, navChartRef:', !!navChartRef.value)
    renderNavChart()
  } catch (e) {
    logger.warn('[NAV History] 获取失败:', e)
  }
}

async function loadPortfolio(code) {
  try {
    const res = await apiFetch(`/api/v1/fund/portfolio/${code}`)
    const data = extractData(res)
    if (data) {
      topHoldings.value = (data.stocks || []).slice(0, 10)
      fundInfo.value = { ...fundInfo.value, quarter: data.quarter || '' }
      
      if (data.assets && data.assets.length > 0) {
        assetAllocation.value = data.assets.map((a, i) => ({
          name: a.name,
          value: a.ratio,
          color: ['#60a5fa', '#34d399', '#fbbf24', '#f87171', '#a78bfa'][i % 5]
        }))
      } else {
        assetAllocation.value = [
          { name: '股票', value: 85.5, color: '#60a5fa' },
          { name: '债券', value: 5.2, color: '#34d399' },
          { name: '现金', value: 8.3, color: '#fbbf24' },
          { name: '其他', value: 1.0, color: '#a78bfa' }
        ]
      }
      
      await nextTick()
      renderAssetChart()
    }
  } catch (e) {
    logger.warn('[Portfolio] 获取失败:', e)
  }
}

// ── ECharts 渲染 ───────────────────────────────────────────────

function renderKlineChart() {
  if (!klineChartRef.value || !window.echarts) return
  
  const echarts = window.echarts
  
  // 如果实例不存在或关联的 DOM 已改变，重新初始化
  if (!klineChart.value || klineChart.value.getDom() !== klineChartRef.value) {
    if (klineChart.value) {
      try { klineChart.value.dispose() } catch (e) {}
    }
    klineChart.value = echarts.init(klineChartRef.value)
  }
  
  const data = klineHistory.value.map(d => ({
    date: d.date || d.trade_date,
    value: d.close || d.nav
  })).reverse()
  
  const option = {
    tooltip: { trigger: 'axis' },
    grid: { top: 10, right: 10, bottom: 20, left: 40 },
    xAxis: {
      type: 'category',
      data: data.map(d => d.date),
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisLabel: { color: '#9ca3af', fontSize: 10, maxRotation: 45 }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisLabel: { color: '#9ca3af', fontSize: 10 },
      splitLine: { lineStyle: { color: '#374151' } }
    },
    series: [{
      type: 'line',
      data: data.map(d => d.value),
      smooth: false,
      lineStyle: { color: '#60a5fa', width: 1.5 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(96, 165, 250, 0.3)' },
            { offset: 1, color: 'rgba(96, 165, 250, 0)' }
          ]
        }
      }
    }]
  }
  klineChart.value.setOption(option)
  klineChart.value.resize()
}

function renderNavChart() {
  if (!navChartRef.value || !window.echarts) return
  
  const echarts = window.echarts
  
  // 如果实例不存在或关联的 DOM 已改变，重新初始化
  if (!navChart.value || navChart.value.getDom() !== navChartRef.value) {
    if (navChart.value) {
      try { navChart.value.dispose() } catch (e) {}
    }
    navChart.value = echarts.init(navChartRef.value)
  }
  
  const data = navHistory.value.map(d => ({
    date: d.date,
    nav: d.nav,
    accumulated: d.accumulated_nav
  }))
  
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['单位净值', '累计净值'], textStyle: { color: '#9ca3af', fontSize: 10 } },
    grid: { top: 30, right: 10, bottom: 20, left: 40 },
    xAxis: {
      type: 'category',
      data: data.map(d => d.date),
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisLabel: { color: '#9ca3af', fontSize: 10, maxRotation: 45 }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisLabel: { color: '#9ca3af', fontSize: 10 },
      splitLine: { lineStyle: { color: '#374151' } }
    },
    series: [
      { name: '单位净值', type: 'line', data: data.map(d => d.nav), smooth: true, lineStyle: { color: '#60a5fa', width: 2 } },
      { name: '累计净值', type: 'line', data: data.map(d => d.accumulated), smooth: true, lineStyle: { color: '#34d399', width: 2, type: 'dashed' } }
    ]
  }
  navChart.value.setOption(option)
  navChart.value.resize()
}

function renderAssetChart() {
  if (!assetChartRef.value || !window.echarts) return
  
  const echarts = window.echarts
  
  // 如果实例不存在或关联的 DOM 已改变，重新初始化
  if (!assetChart.value || assetChart.value.getDom() !== assetChartRef.value) {
    if (assetChart.value) {
      try { assetChart.value.dispose() } catch (e) {}
    }
    assetChart.value = echarts.init(assetChartRef.value)
  }
  
  const option = {
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '50%'],
      itemStyle: { borderRadius: 4, borderColor: '#1f2937', borderWidth: 2 },
      label: { show: false },
      data: assetAllocation.value.map(a => ({ name: a.name, value: a.value, itemStyle: { color: a.color } }))
    }]
  }
  assetChart.value.setOption(option)
  assetChart.value.resize()
}

// ── 工具函数 ───────────────────────────────────────────────────

function getChangeColor(pct) {
  if (pct === '-' || pct === undefined || pct === null) return 'text-theme-muted'
  const v = parseFloat(pct)
  if (v > 0) return 'text-[var(--color-danger)]'
  if (v < 0) return 'text-[var(--color-success)]'
  return 'text-theme-primary'
}

// 使用从 formatters.js 导入的 formatVol 和 formatAmount
// 重命名以避免与本地变量冲突
const formatVolume = formatVol

// ── 生命周期 ───────────────────────────────────────────────────

function retryAutoLoad() {
  autoLoadFailed.value = false
  // Retry with the last selected fund code or default
  const code = selectedFundCode.value || (activeTab.value === 'etf' ? quickETFs[0]?.code : quickFunds[0]?.code)
  if (code) {
    selectFund(code)
  }
}

function handleResize() {
  klineChart.value?.resize()
  navChart.value?.resize()
  assetChart.value?.resize()
  compareChart.value?.resize()
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  
  // 默认加载第一个快捷基金（根据当前选项卡）
  if (activeTab.value === 'etf' && quickETFs.length > 0) {
    selectFund(quickETFs[0].code)
  } else if (activeTab.value === 'open' && quickFunds.length > 0) {
    selectFund(quickFunds[0].code)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (klineChart.value) { try { klineChart.value.dispose() } catch (e) {} }
  if (navChart.value) { try { navChart.value.dispose() } catch (e) {} }
  if (assetChart.value) { try { assetChart.value.dispose() } catch (e) {} }
  if (compareChart.value) { try { compareChart.value.dispose() } catch (e) {} }
  // Clear references
  klineChart.value = null
  navChart.value = null
  assetChart.value = null
  compareChart.value = null
})

// 监听选项卡切换
watch(activeTab, () => {
  searchQuery.value = ''
  fundInfo.value = null
  selectedFundCode.value = ''
  // 切换到对比标签时，如果有足够的基金，重新渲染对比图
  if (activeTab.value === 'compare' && compareFunds.value.length >= 2) {
    nextTick(() => {
      setTimeout(() => renderCompareChart(), 100)
    })
  }
})
</script>

<style scoped>
/* 响应式布局已使用 Tailwind 类实现 */
</style>
