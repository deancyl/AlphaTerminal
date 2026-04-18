<template>
  <div class="flex h-full overflow-hidden bg-terminal-bg">
    <div class="w-44 shrink-0 flex flex-col gap-1 p-2 border-r border-theme overflow-y-auto">

      <!-- 标题 -->
      <div class="flex items-center justify-between mb-1">
        <span class="text-terminal-accent font-bold text-sm">💰 投资组合</span>
        <button @click="showCreateModal = true"
                class="text-[10px] px-1.5 py-0.5 rounded border border-terminal-accent/40 text-terminal-accent hover:bg-terminal-accent/10 transition">
          + 新建
        </button>
      </div>

      <!-- 账户列表（树形：只遍历主账户，子账户嵌套在主账户下） -->
      <template v-for="acc in mainAccounts" :key="acc.id">
        <!-- 主账户行 -->
        <div class="rounded border p-2 cursor-pointer transition-all text-xs"
             :class="acc.id === activePidValue
               ? 'border-terminal-accent/60 bg-terminal-accent/10'
               : 'border-theme hover:border-gray-500'"
             @click="handleSwitch(acc.id)">
          <div class="flex items-center justify-between">
            <!-- 左：折叠箭头+名称 -->
            <div class="flex items-center gap-1 min-w-0">
              <span v-if="getChildren(acc.id).length"
                    class="text-[9px] cursor-pointer select-none flex-shrink-0"
                    @click.stop="toggleCollapse(acc.id)">
                {{ collapsedIds.has(acc.id) ? '▶' : '▼' }}
                ({{ getChildren(acc.id).length }})
              </span>
              <span v-else class="w-3 flex-shrink-0"></span>
              <span class="text-theme-primary font-medium truncate">{{ acc.name }}</span>
              <!-- 类型标签 -->
              <span :class="['text-[8px] px-1 rounded flex-shrink-0', typeTagClasses[acc.type] || 'bg-gray-500/20 text-gray-400']">
                {{ acc.type === 'portfolio' ? '组合' : acc.type === 'account' ? '账户' : acc.type === 'strategy' ? '策略' : '分组' }}
              </span>
              <!-- 币种标签 -->
              <span v-if="acc.currency && acc.currency !== 'CNY'" class="text-[8px] px-1 rounded bg-blue-500/20 text-blue-400">{{ acc.currency }}</span>
              <!-- 策略标签 -->
              <span v-if="acc.strategy" class="text-[8px] px-1 rounded bg-green-500/20 text-green-400">{{ strategyLabels[acc.strategy] || acc.strategy }}</span>
            </div>
            <!-- 右：删除按钮 -->
            <button class="text-[9px] text-red-400/60 hover:text-red-400 ml-1 flex-shrink-0"
                    title="删除账户" @click.stop="confirmDelete(acc)">✕</button>
          </div>
          <!-- 实时总览（仅选中账户显示） -->
          <div v-if="acc.id === activePidValue && pnlData" class="mt-1.5 grid grid-cols-2 gap-x-1">
            <div>
              <div class="text-[9px] text-terminal-dim">总资产</div>
              <div class="text-[10px] font-mono text-theme-primary">{{ fmtYuan(store.totalValue) }}</div>
            </div>
            <div>
              <div class="text-[9px] text-terminal-dim">累计盈亏</div>
              <div class="text-[10px] font-mono" :class="store.totalPnl >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ store.totalPnl >= 0 ? '+' : '' }}{{ fmtYuan(store.totalPnl) }}
              </div>
            </div>
            <div class="col-span-2">
              <div class="text-[9px] text-terminal-dim">盈亏率</div>
              <div class="text-[10px] font-mono" :class="Number(store.totalPnlPct) >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ Number(store.totalPnlPct) >= 0 ? '+' : '' }}{{ Number(store.totalPnlPct).toFixed(2) }}%
              </div>
            </div>
          </div>
        </div>

        <!-- 子账户树（递归支持多级） -->
        <template v-if="!collapsedIds.has(acc.id)">
          <template v-for="child in getChildren(acc.id)" :key="child.id">
            <!-- 一级子账户 -->
            <div :class="['rounded border border-dashed p-2 cursor-pointer transition-all text-xs', 
                          child.id === activePidValue ? 'border-terminal-accent/60 bg-terminal-accent/10' : 'border-theme-secondary hover:border-gray-500']"
                 :style="{ marginLeft: '12px' }"
                 @click="handleSwitch(child.id)">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-1 min-w-0">
                  <!-- 如果有孙账户，显示折叠箭头 -->
                  <span v-if="getChildren(child.id).length"
                        class="text-[9px] cursor-pointer select-none flex-shrink-0"
                        @click.stop="toggleCollapse(child.id)">
                    {{ collapsedIds.has(child.id) ? '▶' : '▼' }}
                  </span>
                  <span v-else class="w-3 flex-shrink-0"></span>
                  <span class="text-theme-secondary font-medium truncate">{{ child.name }}</span>
                  <!-- 类型标签 -->
                  <span :class="['text-[8px] px-1 rounded flex-shrink-0', typeTagClasses[child.type] || 'bg-gray-500/20 text-gray-400']">
                    {{ child.type === 'portfolio' ? '组合' : child.type === 'account' ? '账户' : child.type === 'strategy' ? '策略' : '分组' }}
                  </span>
                  <!-- 币种和策略标签 -->
                  <span v-if="child.currency && child.currency !== 'CNY'" class="text-[8px] px-1 rounded bg-blue-500/20 text-blue-400">{{ child.currency }}</span>
                  <span v-if="child.strategy" class="text-[8px] px-1 rounded bg-green-500/20 text-green-400">{{ strategyLabels[child.strategy] || child.strategy }}</span>
                </div>
                <button class="text-[9px] text-red-400/60 hover:text-red-400 flex-shrink-0" @click.stop="confirmDelete(child)">✕</button>
              </div>
            </div>
            <!-- 二级及以下子账户（递归） -->
            <template v-if="!collapsedIds.has(child.id)">
              <div v-for="grandchild in getChildren(child.id)" :key="grandchild.id"
                   :class="['rounded border border-dashed p-2 cursor-pointer transition-all text-xs',
                            grandchild.id === activePidValue ? 'border-terminal-accent/60 bg-terminal-accent/10' : 'border-theme-secondary hover:border-gray-500']"
                   :style="{ marginLeft: '24px' }"
                   @click="handleSwitch(grandchild.id)">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-1 min-w-0">
                    <span class="text-[8px] text-terminal-dim flex-shrink-0">└</span>
                    <span class="text-theme-secondary font-medium truncate text-[10px]">{{ grandchild.name }}</span>
                    <span :class="['text-[7px] px-1 rounded flex-shrink-0', typeTagClasses[grandchild.type] || 'bg-gray-500/20 text-gray-400']">
                      {{ grandchild.type === 'portfolio' ? '组合' : grandchild.type === 'account' ? '账户' : grandchild.type === 'strategy' ? '策略' : '分组' }}
                    </span>
                    <span v-if="grandchild.currency && grandchild.currency !== 'CNY'" class="text-[7px] px-1 rounded bg-blue-500/20 text-blue-400">{{ grandchild.currency }}</span>
                  </div>
                  <button class="text-[8px] text-red-400/60 hover:text-red-400 flex-shrink-0" @click.stop="confirmDelete(grandchild)">✕</button>
                </div>
              </div>
            </template>
          </template>
        </template>
      </template>

      <!-- 操作按钮 -->
      <div class="flex gap-1 mt-1">
        <button @click="handleRefresh"
                class="flex-1 py-1 rounded border border-theme text-[10px] text-terminal-dim hover:border-terminal-accent/40 hover:text-theme-primary transition">
          🔄 刷新
        </button>
        <button @click="mergedView = !mergedView"
                :class="['px-2 py-1 rounded border text-[10px] transition', mergedView ? 'bg-terminal-accent/20 border-terminal-accent text-terminal-accent' : 'border-theme text-terminal-dim hover:text-theme-primary']"
                title="合并视图：显示选中账户及其所有子账户的汇总数据">
          📊 {{ mergedView ? '合并中' : '合并' }}
        </button>
      </div>

      <!-- 净值曲线图 -->
      <div class="mt-2">
        <div class="text-[9px] text-terminal-dim mb-1">📈 净值走势</div>
        <div ref="chartEl" class="w-full" style="height: 100px;"></div>
      </div>

      <!-- 风险指标面板 -->
      <div v-if="pnlData && riskMetrics" class="mt-2 p-2 rounded border border-theme bg-terminal-panel/50">
        <div class="text-[9px] text-terminal-dim mb-1">📊 风险与收益统计</div>
        <div class="grid grid-cols-2 gap-x-1 gap-y-0.5 text-[9px]">
          <!-- 年化收益 -->
          <div>
            <span class="text-terminal-dim">年化收益</span>
            <div class="font-mono text-[10px]" :class="Number(riskMetrics.annualReturn) >= 0 ? 'text-bullish' : 'text-bearish'">
              {{ Number(riskMetrics.annualReturn) >= 0 ? '+' : '' }}{{ riskMetrics.annualReturn }}%
            </div>
          </div>
          <!-- 夏普比率 -->
          <div>
            <span class="text-terminal-dim">夏普比率</span>
            <div class="font-mono text-[10px]" :class="Number(riskMetrics.sharpe) >= 1 ? 'text-bullish' : Number(riskMetrics.sharpe) > 0 ? 'text-yellow-400' : 'text-bearish'">
              {{ riskMetrics.sharpe }}
            </div>
          </div>
          <!-- 波动率 -->
          <div>
            <span class="text-terminal-dim">年化波动</span>
            <div class="font-mono text-[10px]" :class="Number(riskMetrics.volatility) > 25 ? 'text-bullish' : Number(riskMetrics.volatility) > 15 ? 'text-yellow-400' : 'text-bearish'">
              {{ riskMetrics.volatility }}%
            </div>
          </div>
          <!-- 最大回撤 -->
          <div>
            <span class="text-terminal-dim">最大回撤</span>
            <div class="font-mono text-[10px] text-bullish">{{ riskMetrics.maxDrawdown }}%</div>
          </div>
          <!-- 胜率 -->
          <div>
            <span class="text-terminal-dim">胜率</span>
            <div class="font-mono text-[10px]" :class="Number(riskMetrics.winRate) > 50 ? 'text-bullish' : 'text-bearish'">
              {{ riskMetrics.winRate }}%
            </div>
          </div>
          <!-- 盈亏比 -->
          <div>
            <span class="text-terminal-dim">盈亏比</span>
            <div class="font-mono text-[10px]" :class="Number(riskMetrics.profitLossRatio) >= 1 ? 'text-bullish' : 'text-bearish'">
              {{ riskMetrics.profitLossRatio }}
            </div>
          </div>
          <!-- 最大单日盈利 -->
          <div>
            <span class="text-terminal-dim">最佳日</span>
            <div class="font-mono text-[10px] text-bullish">+{{ riskMetrics.bestDay }}%</div>
          </div>
          <!-- 最大单日亏损 -->
          <div>
            <span class="text-terminal-dim">最差日</span>
            <div class="font-mono text-[10px] text-bearish">{{ riskMetrics.worstDay }}%</div>
          </div>
          <!-- 最大连续上涨 -->
          <div>
            <span class="text-terminal-dim">连涨最高</span>
            <div class="font-mono text-[10px] text-bullish">{{ riskMetrics.maxConsecUp }}天</div>
          </div>
          <!-- 最大连续下跌 -->
          <div>
            <span class="text-terminal-dim">连跌最高</span>
            <div class="font-mono text-[10px] text-bearish">{{ riskMetrics.maxConsecDown }}天</div>
          </div>
          <!-- 持仓集中度 -->
          <div class="col-span-2 mt-0.5">
            <span class="text-terminal-dim">集中度</span>
            <div class="font-mono text-[10px] text-theme-primary">
              Top3 {{ riskMetrics.top3Concentration }}% | Top5 {{ riskMetrics.top5Concentration }}%
            </div>
          </div>
          <!-- β系数 -->
          <div class="col-span-2">
            <span class="text-terminal-dim">β(沪深300)</span>
            <div class="font-mono text-[10px] text-theme-primary">{{ riskMetrics.portfolioBeta }}</div>
          </div>
        </div>
      </div>

      <!-- 底层资产归因面板 (Task 9) -->
      <div v-if="store.activePid" class="mt-2 rounded border border-cyan-500/30 bg-terminal-panel/50 overflow-hidden" style="height: 340px;">
        <div class="text-[9px] text-cyan-400/80 px-2 pt-1.5 pb-1 border-b border-cyan-500/20 flex items-center gap-1">
          <span>🎯</span>
          <span>底层资产归因与风险</span>
        </div>
        <AttributionPanel
          :portfolioId="store.activePid"
          class="w-full"
          style="height: calc(100% - 24px);"
        />
      </div>

      <!-- 行业归因 -->
      <div v-if="sectorAttribution && sectorAttribution.length > 0" class="mt-2 p-2 rounded border border-theme bg-terminal-panel/50">
        <div class="text-[9px] text-terminal-dim mb-1">🏭 行业分布</div>
        <div class="space-y-0.5 max-h-24 overflow-y-auto">
          <div v-for="s in sectorAttribution" :key="s.name" class="flex items-center justify-between text-[9px]">
            <span class="text-theme-primary truncate max-w-[60px]">{{ s.name }}</span>
            <div class="flex items-center gap-1">
              <div class="w-12 h-1 bg-theme-tertiary rounded-full overflow-hidden">
                <div class="h-full rounded-full" :class="s.weight > 20 ? 'bg-red-500/60' : s.weight > 10 ? 'bg-yellow-500/60' : 'bg-green-500/60'"
                     :style="{ width: Math.min(s.weight, 100) + '%' }"></div>
              </div>
              <span class="text-terminal-dim w-10 text-right">{{ s.weight.toFixed(1) }}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ 右侧主区域 ══════════════════════════════════════ -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">

      <!-- 操作栏 -->
      <div class="flex items-center gap-2 px-3 py-1.5 border-b border-theme shrink-0">
        <span class="text-xs text-terminal-dim">
          {{ store.activePortfolio?.name }} — 持仓 {{ positionsCount }} 只
        </span>
        <div class="flex items-center gap-1 ml-auto text-[10px]">
          <span class="text-terminal-dim">排序:</span>
          <button v-for="col in sortCols" :key="col.key"
                  class="px-1.5 py-0.5 rounded border transition"
                  :class="sortKey === col.key ? 'border-terminal-accent/50 text-terminal-accent' : 'border-theme text-theme-secondary hover:border-gray-500'"
                  @click="setSort(col.key)">
            {{ col.label }}
          </button>
        </div>
        <button @click="showTradeModal = true"
                class="ml-2 px-3 py-1 rounded bg-terminal-accent/20 border border-terminal-accent/50 text-terminal-accent text-[10px] hover:bg-terminal-accent/30 transition">
          + 调仓
        </button>
        <button @click="downloadReport"
                class="px-3 py-1 rounded border border-theme-secondary text-theme-secondary text-[10px] hover:border-gray-500 hover:text-theme-primary transition">
          📥 报告
        </button>
      </div>

      <!-- 持仓明细表 -->
      <div class="flex-1 overflow-y-auto">
        <table class="w-full text-[10px]">
          <thead class="sticky top-0 z-10 bg-terminal-panel text-terminal-dim">
            <tr class="border-b border-theme">
              <th class="text-left py-1 px-2">代码</th>
              <th class="text-left py-1 px-2">名称</th>
              <th class="text-right py-1 px-2">持仓</th>
              <th class="text-right py-1 px-2">成本</th>
              <th class="text-right py-1 px-2">现价</th>
              <th class="text-right py-1 px-2">今涨跌</th>
              <th class="text-right py-1 px-2">市值</th>
              <th class="text-right py-1 px-2">盈亏额</th>
              <th class="text-right py-1 px-2">盈亏率</th>
              <th class="text-right py-1 px-2">权重</th>
              <th class="text-right py-1 px-2">PE</th>
              <th class="text-right py-1 px-2">PB</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="pos in sortedPositions" :key="pos.symbol"
                class="border-b border-theme-secondary hover:bg-white/4 cursor-pointer transition"
                @click="openTrade(pos)">
              <!-- 代码 -->
              <td class="py-1 px-2 text-terminal-dim font-mono text-[9px]">{{ pos.symbol }}</td>
              <!-- 名称+市场 -->
              <td class="py-1 px-2">
                <div class="text-theme-primary text-[10px]">{{ pos.name || pos.symbol }}</div>
                <div class="text-[8px] text-terminal-dim">{{ pos.market }}</div>
              </td>
              <!-- 持仓 -->
              <td class="py-1 px-2 text-right font-mono text-theme-primary text-[9px]">{{ pos.shares }}</td>
              <!-- 成本价 -->
              <td class="py-1 px-2 text-right font-mono text-theme-secondary text-[9px]">{{ Number(pos.avg_cost||0).toFixed(2) }}</td>
              <!-- 现价 -->
              <td class="py-1 px-2 text-right font-mono text-theme-primary text-[9px]">{{ Number(pos.price||0).toFixed(2) }}</td>
              <!-- 今日涨跌 -->
              <td class="py-1 px-2 text-right font-mono text-[9px]" :class="(pos.change_pct||0) >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ (pos.change_pct||0) >= 0 ? '+' : '' }}{{ (pos.change_pct||0).toFixed(2) }}%
              </td>
              <!-- 市值 -->
              <td class="py-1 px-2 text-right font-mono text-theme-primary text-[9px]">{{ fmtYuan(pos.market_value) }}</td>
              <!-- 浮动盈亏额 -->
              <td class="py-1 px-2 text-right font-mono text-[9px]" :class="(pos.pnl||0) >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ (pos.pnl||0) >= 0 ? '+' : '' }}{{ fmtYuan(pos.pnl||0) }}
              </td>
              <!-- 盈亏率 -->
              <td class="py-1 px-2 text-right font-mono font-bold text-[9px]" :class="(pos.pnl_pct||0) >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ (pos.pnl_pct||0) >= 0 ? '+' : '' }}{{ (pos.pnl_pct||0).toFixed(2) }}%
              </td>
              <!-- 权重 -->
              <td class="py-1 px-2 text-right text-terminal-dim text-[9px]">{{ Number(pos.weight||0).toFixed(2) }}%</td>
              <!-- PE -->
              <td class="py-1 px-2 text-right text-terminal-dim text-[9px]">{{ pos.pe || '--' }}</td>
              <!-- PB -->
              <td class="py-1 px-2 text-right text-terminal-dim text-[9px]">{{ pos.pb || '--' }}</td>
            </tr>
            <tr v-if="!sortedPositions.length">
              <td colspan="12" class="py-8 text-center text-terminal-dim">
                {{ store.loading ? '加载中...' : '暂无持仓，请点击 [+ 调仓] 添加' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ═══ 调仓弹窗 ══════════════════════════════════════════ -->
    <div v-if="showTradeModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div class="bg-terminal-panel border border-theme-secondary rounded-xl w-80 p-4 shadow-2xl">
        <div class="text-sm font-bold text-theme-primary mb-3">
          {{ tradeTarget ? '调整持仓' : '新建仓位' }}
        </div>

        <!-- 标的 -->
        <div class="mb-2">
          <label class="text-[10px] text-terminal-dim">股票代码</label>
          <input v-model="tradeForm.symbol" type="text" placeholder="如 600519"
                 class="mt-1 w-full bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-xs text-theme-primary outline-none focus:border-terminal-accent" />
        </div>

        <!-- 股数 -->
        <div class="mb-2">
          <label class="text-[10px] text-terminal-dim">持仓股数（填 0 则清仓）</label>
          <input v-model.number="tradeForm.shares" type="number" min="0" placeholder="0"
                 class="mt-1 w-full bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-xs text-theme-primary outline-none focus:border-terminal-accent" />
        </div>

        <!-- 成本价 -->
        <div class="mb-3">
          <label class="text-[10px] text-terminal-dim">成本价（元）</label>
          <input v-model.number="tradeForm.avg_cost" type="number" min="0" step="0.001" placeholder="0.00"
                 class="mt-1 w-full bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-xs text-theme-primary outline-none focus:border-terminal-accent" />
        </div>

        <div class="flex gap-2 justify-end">
          <button @click="showTradeModal = false"
                  class="px-3 py-1 rounded border border-theme-secondary text-xs text-theme-secondary hover:text-theme-primary transition">
            取消
          </button>
          <button @click="submitTrade"
                  class="px-3 py-1 rounded bg-terminal-accent/20 border border-terminal-accent/50 text-xs text-terminal-accent hover:bg-terminal-accent/30 transition">
            确认
          </button>
        </div>
      </div>
    </div>

    <!-- ═══ 新建账户弹窗 ══════════════════════════════════════ -->
    <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div class="bg-terminal-panel border border-theme-secondary rounded-xl w-80 p-4 shadow-2xl max-h-[90vh] overflow-y-auto">
        <div class="text-sm font-bold text-theme-primary mb-3">新建账户</div>
        <!-- 账户名称 -->
        <div class="mb-2">
          <label class="text-[10px] text-terminal-dim">账户名称 <span class="text-red-400">*</span></label>
          <input v-model="createForm.name" type="text" placeholder="如：教育基金"
                 class="mt-1 w-full bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-xs text-theme-primary outline-none focus:border-terminal-accent" />
        </div>
        <!-- 账户类型 -->
        <div class="mb-2">
          <label class="text-[10px] text-terminal-dim">账户类型</label>
          <select v-model="createForm.type"
                  class="mt-1 w-full bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-xs text-theme-primary outline-none">
            <option value="portfolio">投资组合</option>
            <option value="account">资金账户</option>
            <option value="strategy">策略组合</option>
            <option value="group">分组文件夹</option>
          </select>
          <div class="text-[8px] text-terminal-dim mt-1">
            {{ typeDescriptions[createForm.type] }}
          </div>
        </div>
        <!-- 所属主账户（仅子账户显示） -->
        <div v-if="createForm.type === 'special_plan'" class="mb-2">
          <label class="text-[10px] text-terminal-dim">所属主账户</label>
          <select v-model="createForm.parent_id"
                  class="mt-1 w-full bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-xs text-theme-primary outline-none">
            <option value="">—选择主账户—</option>
            <option v-for="p in mainAccounts" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </div>
        <!-- 币种 -->
        <div class="mb-2">
          <label class="text-[10px] text-terminal-dim">币种</label>
          <select v-model="createForm.currency"
                  class="mt-1 w-full bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-xs text-theme-primary outline-none">
            <option value="CNY">人民币 (CNY)</option>
            <option value="USD">美元 (USD)</option>
            <option value="HKD">港币 (HKD)</option>
          </select>
        </div>
        <!-- 资产类别 -->
        <div class="mb-2">
          <label class="text-[10px] text-terminal-dim">资产类别</label>
          <select v-model="createForm.asset_class"
                  class="mt-1 w-full bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-xs text-theme-primary outline-none">
            <option value="stock">股票</option>
            <option value="bond">债券</option>
            <option value="fund">基金</option>
            <option value="futures">期货</option>
            <option value="options">期权</option>
            <option value="mixed">混合</option>
          </select>
        </div>
        <!-- 投资策略 -->
        <div class="mb-2">
          <label class="text-[10px] text-terminal-dim">投资策略</label>
          <select v-model="createForm.strategy"
                  class="mt-1 w-full bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-xs text-theme-primary outline-none">
            <option value="">—选择策略—</option>
            <option value="value">价值投资</option>
            <option value="growth">成长投资</option>
            <option value="balanced">平衡配置</option>
            <option value="index">指数跟踪</option>
            <option value="quant">量化策略</option>
            <option value="dividend">高股息</option>
          </select>
        </div>
        <!-- 业绩基准 -->
        <div class="mb-2">
          <label class="text-[10px] text-terminal-dim">业绩基准</label>
          <select v-model="createForm.benchmark"
                  class="mt-1 w-full bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-xs text-theme-primary outline-none">
            <option value="">—选择基准—</option>
            <option value="000001">上证指数</option>
            <option value="000300">沪深300</option>
            <option value="399001">深证成指</option>
            <option value="399006">创业板指</option>
            <option value="000905">中证500</option>
            <option value="HSI">恒生指数</option>
          </select>
        </div>
        <!-- 初始资金 -->
        <div class="mb-2">
          <label class="text-[10px] text-terminal-dim">初始资金 (元)</label>
          <input v-model.number="createForm.initial_capital" type="number" min="0" step="10000" placeholder="0"
                 class="mt-1 w-full bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-xs text-theme-primary outline-none focus:border-terminal-accent" />
        </div>
        <!-- 账户说明 -->
        <div class="mb-3">
          <label class="text-[10px] text-terminal-dim">账户说明</label>
          <textarea v-model="createForm.description" rows="2" placeholder="可选：输入账户描述..."
                    class="mt-1 w-full bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-xs text-theme-primary outline-none focus:border-terminal-accent resize-none"></textarea>
        </div>
        <div class="flex gap-2 justify-end">
          <button @click="showCreateModal = false"
                  class="px-3 py-1 rounded border border-theme-secondary text-xs text-theme-secondary hover:text-theme-primary transition">取消</button>
          <button @click="submitCreate"
                  class="px-3 py-1 rounded bg-terminal-accent/20 border border-terminal-accent/50 text-xs text-terminal-accent hover:bg-terminal-accent/30 transition">创建</button>
        </div>
      </div>
    </div>

    <!-- ═══ 删除账户确认弹窗 ══════════════════════════════════ -->
    <div v-if="showDeleteModal" class="fixed inset-0 z-[60] flex items-center justify-center bg-black/60">
      <div class="bg-terminal-panel border border-red-500/50 rounded-xl w-72 p-4 shadow-2xl">
        <div class="text-sm font-bold text-red-400 mb-2">确认删除账户</div>
        <div class="text-xs text-theme-secondary mb-4">
          确定要删除账户 <span class="text-theme-primary font-bold">{{ deleteTarget?.name }}</span> 吗？
          <br>该账户下的所有持仓记录将被永久删除。
        </div>
        <div class="flex gap-2 justify-end">
          <button @click="showDeleteModal = false"
                  class="px-3 py-1 rounded border border-theme text-theme-secondary text-xs hover:bg-white/5">
            取消
          </button>
          <button @click="doDelete(deleteTarget)"
                  class="px-3 py-1 rounded bg-red-500/20 border border-red-500 text-red-400 text-xs hover:bg-red-500/30">
            确认删除
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { logger } from '../utils/logger.js'
import AttributionPanel from './AttributionPanel.vue'
// echarts 从 CDN 加载 via window.echarts
import { usePortfolioStore } from '../composables/usePortfolioStore.js'

const store = usePortfolioStore()

// ── 状态 ──────────────────────────────────────────────────────
const chartEl      = ref(null)
const sortKey      = ref('pnl_pct')
const sortAsc      = ref(false)
const showTradeModal = ref(false)
const showCreateModal = ref(false)
const tradeTarget  = ref(null)
const chart        = ref(null)

// 策略标签映射
const strategyLabels = {
  'value': '价值',
  'growth': '成长',
  'balanced': '平衡',
  'index': '指数',
  'quant': '量化',
  'dividend': '股息'
}

// 账户类型描述
const typeDescriptions = {
  'portfolio': '顶级容器，可包含多个资金账户和策略组合',
  'account': '实际交易账户，包含具体持仓',
  'strategy': '策略组合，按策略归集持仓',
  'group': '纯分组文件夹，用于组织管理'
}

// 账户类型标签样式
const typeTagClasses = {
  'portfolio': 'bg-purple-500/20 text-purple-400',
  'account': 'bg-blue-500/20 text-blue-400',
  'strategy': 'bg-green-500/20 text-green-400',
  'group': 'bg-gray-500/20 text-gray-400'
}

// 是否启用合并视图
const mergedView = ref(false)

// 递归获取账户的所有后代（用于多级树）
function getDescendants(parentId) {
  const children = (store.portfolios.value || []).filter(p => p.parent_id === parentId)
  let result = [...children]
  for (const child of children) {
    result = result.concat(getDescendants(child.id))
  }
  return result
}

// ── 安全解包 store refs（Vue 不会自动解包嵌套在普通对象中的 ref）───
const positionsArray = computed(() => store.positions.value ?? [])
const positionsCount = computed(() => positionsArray.value.length)
const activePidValue = computed(() => {
  const v = store.activePid?.value ?? store.activePid
  return v ?? null
})
const pnlData = computed(() => store.pnl?.value ?? store.pnl ?? null)

// ── 树形折叠 ─────────────────────────────────────────────
const collapsedIds = ref(new Set())
function toggleCollapse(id) {
  if (collapsedIds.value.has(id)) collapsedIds.value.delete(id)
  else collapsedIds.value.add(id)
}
function getChildren(parentId) {
  return (store.portfolios.value || []).filter(p => p.parent_id === parentId)
}
// 只遍历主账户（parent_id 为空/0/None 的）
const mainAccounts = computed(() =>
  (store.portfolios.value || []).filter(p => !p.parent_id)
)

// ── 删除账户 ─────────────────────────────────────────────
const showDeleteModal = ref(false)
const deleteTarget = ref(null)
function confirmDelete(acc) {
  deleteTarget.value = acc
  showDeleteModal.value = true
}
async function doDelete(acc) {
  if (!acc || !acc.id) {
    alert('删除目标无效，请重试')
    showDeleteModal.value = false
    return
  }
  try {
    const res = await fetch('/api/v1/portfolio/' + acc.id, { method: 'DELETE' })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      alert('删除失败: ' + (body?.message || body?.detail || `HTTP ${res.status}`))
      return
    }
    showDeleteModal.value = false
    deleteTarget.value = null
    await store.fetchPortfolios()
    const remaining = (store.portfolios.value || []).filter(p => p.id !== acc.id)
    if (remaining.length > 0) {
      await store.switchAccount(remaining[0].id)
    }
  } catch(e) {
    alert('删除失败: ' + e.message)
  }
}

const sortCols = [
  { key: 'symbol',     label: '代码' },
  { key: 'pnl_pct',   label: '盈亏率' },
  { key: 'market_value', label: '市值' },
  { key: 'shares',     label: '股数' },
]

const tradeForm = ref({ symbol: '', shares: 0, avg_cost: 0 })
const createForm = ref({
  name: '',
  type: 'portfolio',
  parent_id: null,
  currency: 'CNY',
  asset_class: 'mixed',
  strategy: null,
  benchmark: null,
  status: 'active',
  initial_capital: 0,
  description: ''
})

// ── 排序 ──────────────────────────────────────────────────────
const sortedPositions = computed(() => {
  const arr = positionsArray.value
  if (!arr.length) return []
  const key = sortKey.value
  const dir = sortAsc.value ? 1 : -1
  return [...arr].sort((a, b) => {
    const av = a[key] ?? 0
    const bv = b[key] ?? 0
    return (av < bv ? -1 : av > bv ? 1 : 0) * dir
  })
})

function setSort(key) {
  if (sortKey.value === key) sortAsc.value = !sortAsc.value
  else { sortKey.value = key; sortAsc.value = false }
}

// ── 调仓 ─────────────────────────────────────────────────────
function openTrade(pos) {
  tradeTarget.value = pos
  tradeForm.value = { symbol: pos.symbol, shares: pos.shares, avg_cost: pos.avg_cost }
  showTradeModal.value = true
}

async function submitTrade() {
  if (!tradeForm.value.symbol) return
  const pid = store.activePid?.value ?? store.activePid
  await store.upsertPosition(pid, tradeForm.value.symbol, tradeForm.value.shares, tradeForm.value.avg_cost)
  showTradeModal.value = false
}

async function submitCreate() {
  if (!createForm.value.name) return
  const body = {
    name: createForm.value.name,
    type: createForm.value.type,
    currency: createForm.value.currency,
    asset_class: createForm.value.asset_class,
    strategy: createForm.value.strategy,
    benchmark: createForm.value.benchmark,
    status: createForm.value.status,
    initial_capital: Number(createForm.value.initial_capital) || 0,
    description: createForm.value.description
  }
  if (createForm.value.type === 'special_plan' && createForm.value.parent_id) {
    body.parent_id = createForm.value.parent_id
  }
  try {
    await store.createPortfolio(body)
    showCreateModal.value = false
    createForm.value = {
      name: '', type: 'portfolio', parent_id: null,
      currency: 'CNY', asset_class: 'mixed', strategy: null,
      benchmark: null, status: 'active', initial_capital: 0, description: ''
    }
  } catch (e) {
    const msg = e.message || '创建失败'
    const detail = msg.includes('UNIQUE') || msg.includes('已存在')
      ? '该账户名称已存在，请换个名字'
      : msg.includes('HTTP 4')
        ? msg
        : `创建失败: ${msg}`
    alert(detail)
  }
}

function downloadReport() {
  const positions = positionsArray.value
  if (!positions.length) return
  const totalValue = positions.reduce((s, p) => s + (p.market_value || 0), 0)
  const totalCost  = positions.reduce((s, p) => s + (p.shares || 0) * (p.avg_cost || 0), 0)
  const totalPnl  = positions.reduce((s, p) => s + (p.pnl || 0), 0)
  
  const lines = [
    `AlphaTerminal 投资组合报告 - ${new Date().toLocaleString('zh-CN')}`,
    `账户: ${store.activePortfolio?.name || 'N/A'}`,
    `总市值: ${fmtYuan(totalValue)}`,
    `总成本: ${fmtYuan(totalCost)}`,
    `累计盈亏: ${fmtYuan(totalPnl)} (${((totalPnl / (totalCost || 1)) * 100).toFixed(2)}%)`,
    '',
    '--- 持仓明细 ---',
    '代码,名称,持仓,成本价,现价,市值,盈亏,盈亏率,占比',
    ...positions.map(p =>
      `${p.symbol},${p.symbol},${p.shares},${Number(p.avg_cost||0).toFixed(2)},${Number(p.price||0).toFixed(2)},${fmtYuan(p.market_value)},${fmtYuan(p.pnl)},${Number(p.pnl_pct||0).toFixed(2)}%,${((p.market_value / (totalValue || 1)) * 100).toFixed(1)}%`
    ),
    '',
    '--- 风险指标 ---',
    `波动率: ${riskMetrics.value?.volatility || '--'}%`,
    `夏普比率: ${riskMetrics.value?.sharpe || '--'}`,
    `最大回撤: ${riskMetrics.value?.maxDrawdown || '--'}%`,
    `年化收益: ${riskMetrics.value?.annualReturn || '--'}%`,
    `持仓集中度(Top3): ${riskMetrics.value?.top3Concentration || '--'}%`,
  ]
  
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `portfolio_${store.activePortfolio?.name || 'report'}_${new Date().toISOString().slice(0,10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

async function handleSwitch(pid) {
  await store.switchAccount(pid, mergedView.value)
  await nextTick()
  renderChart()
}

async function handleRefresh() {
  // store.activePid 是 ref，需要取 .value
  const pid = store.activePid?.value ?? store.activePid
  if (pid) await store.fetchAll(pid, mergedView.value)
}

// 监听合并视图变化，自动刷新
watch(mergedView, async (newVal) => {
  const pid = store.activePid?.value ?? store.activePid
  if (pid) {
    await store.fetchAll(pid, newVal)
    await nextTick()
    renderChart()
  }
})

// ── ECharts 净值曲线 ──────────────────────────────────────────
function renderChart() {
  if (!chartEl.value || !store.snapshots.value?.length) return
  if (!chart.value) {
    chart.value = window.echarts.init(chartEl.value, 'dark')
  }
  const snaps = store.snapshots.value
  const dates = snaps.map(s => s.date)
  const assets = snaps.map(s => s.total_asset)
  const costs  = snaps.map(s => s.total_cost)

  chart.value.setOption({
    backgroundColor: 'transparent',
    grid: { top: 8, bottom: 8, left: 48, right: 8 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1e2130',
      borderColor: '#374151',
      textStyle: { color: '#9ca3af', fontSize: 9 },
      formatter: (params) => {
        const d = params[0]
        return `${d.axisValue}<br/>资产: <b>${fmtYuan(d.value)}</b>`
      }
    },
    xAxis: {
      type: 'category', data: dates,
      axisLabel: { color: '#6b7280', fontSize: 8, rotate: 30 },
      axisLine: { lineStyle: { color: '#374151' } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#6b7280', fontSize: 8, formatter: v => { const n = Number(v)||0; return (n/1e4).toFixed(0)+'w' } },
      splitLine: { lineStyle: { color: '#1f2937' } },
      axisLine: { show: false },
    },
    series: [
      {
        name: '总资产', type: 'line',
        data: assets,
        smooth: true,
        lineStyle: { color: '#60a5fa', width: 1.5 },
        itemStyle: { color: '#60a5fa' },
        areaStyle: { color: new window.echarts.graphic.LinearGradient(0,0,0,1,[
          { offset: 0, color: 'rgba(96,165,250,0.3)' },
          { offset: 1, color: 'rgba(96,165,250,0)' },
        ])},
        symbol: 'none',
      },
      {
        name: '总成本', type: 'line',
        data: costs,
        smooth: true,
        lineStyle: { color: '#6b7280', width: 1, type: 'dashed' },
        itemStyle: { color: '#6b7280' },
        symbol: 'none',
      },
    ],
  })
}

// ── 工具函数 ─────────────────────────────────────────────────
function fmtYuan(v) {
  if (v == null || v === '--' || (typeof v !== 'number' && isNaN(Number(v)))) return '--'
  const n = Number(v)
  if (isNaN(n)) return '--'
  if (Math.abs(n) >= 1e8) return (n/1e8).toFixed(2) + '亿'
  if (Math.abs(n) >= 1e4) return (n/1e4).toFixed(2) + '万'
  return n.toFixed(2)
}

// ── 风险指标计算 ─────────────────────────────────────────────

// 从 store.snapshots 计算风险指标
const riskMetrics = computed(() => {
  const snaps = store.snapshots.value
  if (!snaps || snaps.length < 2) {
    return null
  }
  const assets = snaps.map(s => s.total_asset)
  const latest = assets[assets.length - 1]
  const first = assets[0]
  
  // 收益率序列
  const returns = []
  for (let i = 1; i < assets.length; i++) {
    if (assets[i-1] > 0) {
      returns.push((assets[i] - assets[i-1]) / assets[i-1])
    }
  }
  
  if (returns.length < 2) {
    return null
  }

  // 1. 年化收益率
  const days = snaps.length
  const totalReturn = (latest - first) / first
  const annualReturn = (Math.pow(1 + totalReturn, 365 / Math.max(days, 1)) - 1) * 100

  // 2. 波动率 (年化标准差)
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length
  const variance = returns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / returns.length
  const dailyVol = Math.sqrt(variance)
  const volatility = dailyVol * Math.sqrt(252) * 100

  // 3. 夏普比率 (假设无风险利率 3%)
  const riskFree = 0.03
  const sharpe = volatility > 0 ? ((annualReturn / 100 - riskFree) / (volatility / 100)).toFixed(2) : '0.00'

  // 4. 最大回撤
  let maxDrawdown = 0
  let peak = assets[0]
  for (const a of assets) {
    if (a > peak) peak = a
    const dd = (peak - a) / peak
    if (dd > maxDrawdown) maxDrawdown = dd
  }
  const maxDrawdownPct = (maxDrawdown * 100).toFixed(2)

  // 5. 持仓集中度
  const totalValue = positionsArray.value.reduce((s, p) => s + (p.market_value || 0), 0)
  const sorted = [...positionsArray.value].sort((a, b) => (b.market_value || 0) - (a.market_value || 0))
  const top3 = sorted.slice(0, 3).reduce((s, p) => s + (p.market_value || 0), 0) / (totalValue || 1) * 100
  const top5 = sorted.slice(0, 5).reduce((s, p) => s + (p.market_value || 0), 0) / (totalValue || 1) * 100

  // 6. 组合Beta (简化估算)
  const portfolioBeta = '1.00'

  // 7. 胜率（上涨天数占比）
  const upDays = returns.filter(r => r > 0).length
  const totalDays = returns.length
  const winRate = totalDays > 0 ? (upDays / totalDays * 100) : 0

  // 8. 盈亏比（平均盈利日涨幅 / |平均亏损日跌幅|）
  const wins = returns.filter(r => r > 0)
  const losses = returns.filter(r => r < 0)
  const avgWin = wins.length > 0 ? wins.reduce((a,b)=>a+b,0)/wins.length : 0
  const avgLoss = losses.length > 0 ? Math.abs(losses.reduce((a,b)=>a+b,0)/losses.length) : 1
  const profitLossRatio = avgLoss > 0 && avgWin > 0 ? (avgWin / avgLoss) : 0

  // 9. 最大单日盈利 / 最大单日亏损
  const bestDay = returns.length > 0 ? Math.max(...returns) * 100 : 0
  const worstDay = returns.length > 0 ? Math.min(...returns) * 100 : 0

  // 10. 最大连续上涨/下跌天数
  let maxConsecUp = 0, maxConsecDown = 0, curUp = 0, curDown = 0
  for (const r of returns) {
    if (r > 0) { curUp++; curDown=0; maxConsecUp=Math.max(maxConsecUp,curUp) }
    else if (r < 0) { curDown++; curUp=0; maxConsecDown=Math.max(maxConsecDown,curDown) }
  }

  return {
    volatility: volatility.toFixed(2),
    sharpe: parseFloat(sharpe).toFixed(2),
    maxDrawdown: maxDrawdownPct,
    annualReturn: annualReturn.toFixed(2),
    top3Concentration: top3.toFixed(1),
    top5Concentration: top5.toFixed(1),
    portfolioBeta,
    winRate: winRate.toFixed(1),
    profitLossRatio: profitLossRatio.toFixed(2),
    bestDay: bestDay.toFixed(2),
    worstDay: worstDay.toFixed(2),
    maxConsecUp,
    maxConsecDown,
    totalDays,
  }
})

// 行业归因 (从持仓推断行业分布，需接入行业数据)
const sectorAttribution = computed(() => {
  const positions = positionsArray.value
  if (!positions.length) return []
  const totalValue = positions.reduce((s, p) => s + (p.market_value || 0), 0)
  if (totalValue === 0) return []
  
  const SECTOR_MAP = {
    '600519': '白酒', '000858': '白酒', '000568': '白酒',
    '601318': '金融', '600036': '银行', '601398': '银行',
    '000001': '银行', '002594': '新能源车', '300750': '新能源车',
    '600900': '电力', '600028': '石油', '601857': '石油',
  }
  
  const sectors = {}
  for (const pos of positions) {
    const sec = SECTOR_MAP[pos.symbol] || '其他'
    if (!sectors[sec]) sectors[sec] = 0
    sectors[sec] += (pos.market_value || 0)
  }
  
  return Object.entries(sectors)
    .map(([name, value]) => ({ name, weight: value / totalValue * 100 }))
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 8)
})

// ── 生命周期 ─────────────────────────────────────────────────
let _chartRO = null
onMounted(async () => {
  logger.log('[PortfolioDashboard] mounted, fetching portfolios...')
  await store.fetchPortfolios()
  logger.log('[PortfolioDashboard] portfolios after fetch:', store.portfolios?.value?.length)
  logger.log('[PortfolioDashboard] activePid:', store.activePid?.value)
  const pid = store.activePid?.value ?? store.activePid
  logger.log('[PortfolioDashboard] pid for fetchAll:', pid)
  if (pid) await store.fetchAll(pid)
  store.startPoll(20_000)
  await nextTick()
  renderChart()
  // ResizeObserver：只监听自己的容器，不影响其他图表
  if (chartEl.value) {
    _chartRO = new ResizeObserver(() => {
      const w = chartEl.value.offsetWidth
      const h = chartEl.value.offsetHeight
      if (w > 0 && h > 0) {
        console.debug(`[ECharts] 📐 resize PortfolioDashboard @ ${w}×${h}`)
        chart.value?.resize()
      }
    })
    _chartRO.observe(chartEl.value)
  }
})

onUnmounted(() => {
  store.stopPoll()
  if (chart.value) {
    console.debug('[ECharts] 🗑️  disposed instance for PortfolioDashboard')
    chart.value.dispose()
    chart.value = null
  }
  _chartRO?.disconnect()
  _chartRO = null
})

// snapshots 变化时重绘图表
watch(() => store.snapshots.value?.length ?? 0, () => {
  nextTick(renderChart)
})

// 窗口 resize 时重绘
window.addEventListener('resize', () => chart.value?.resize())
</script>
