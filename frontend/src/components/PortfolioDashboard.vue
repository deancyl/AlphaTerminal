<template>
  <div class="p-4">
    <!-- 标题 -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between mb-3 gap-2">
      <span class="text-terminal-accent font-bold text-sm">💰 投资组合</span>
      <div class="flex gap-2 flex-wrap">
        <button
          v-if="selectedPortfolioId !== null"
          @click="exportPortfolio"
          class="bg-[var(--color-info-bg)] hover:bg-[var(--color-info-hover)]/30 text-[var(--color-info)] border border-[var(--color-info-border)] text-xs px-3 py-1.5 rounded-sm font-bold transition-colors"
        >📥 导出</button>
        <button
          v-if="selectedPortfolioId !== null"
          @click="showTradeModal = true"
          class="bg-[var(--color-success-bg)] hover:bg-[var(--color-success-bg)] text-[var(--color-success)] border border-[var(--color-success-border)] text-xs px-3 py-1.5 rounded-sm font-bold transition-colors"
        >📋 模拟调仓</button>
        <button @click="showCreateModal = true" class="btn-primary text-xs px-3 py-1.5">+ 新建</button>
      </div>
    </div>

    <!-- 树形账户选择器 + 聚合指示器 -->
    <div v-if="selectedPortfolioId !== null" class="flex items-center gap-2 mb-2">
      <span class="text-terminal-dim text-xs">账户：</span>
      <select v-model="selectedPortfolioId" class="bg-terminal-panel border border-theme-secondary rounded-sm px-2 py-1 text-terminal-primary text-xs flex-1">
        <template v-for="node in flatTree" :key="node.id">
          <option :value="node.id">{{ node._label }}</option>
        </template>
      </select>
      <span v-if="isAggregated" class="text-xs text-[var(--color-warning)] bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] rounded-sm px-2 py-0.5">
        📂 含子账户
      </span>
    </div>

    <!-- 操作栏：过滤器 -->
    <div v-if="selectedPortfolioId !== null" class="flex gap-2 mb-3 items-center text-xs flex-wrap">
      <select v-model="filterSector" class="bg-terminal-panel border border-theme-secondary rounded-sm px-2 py-1 text-terminal-secondary">
        <option value="">全部行业</option>
        <option v-for="s in sectorList" :key="s" :value="s">{{ s }}</option>
      </select>
      <select v-model="filterPositionType" class="bg-terminal-panel border border-theme-secondary rounded-sm px-2 py-1 text-terminal-secondary">
        <option value="">全部类型</option>
        <option value="stock">股票</option>
        <option value="index">指数</option>
        <option value="ETF">ETF</option>
      </select>
      <select v-model="sortBy" class="bg-terminal-panel border border-theme-secondary rounded-sm px-2 py-1 text-terminal-secondary">
        <option value="change_pct">按涨跌幅</option>
        <option value="market_value">按市值</option>
        <option value="symbol">按代码</option>
      </select>
      <button @click="loadPortfolioData" class="text-terminal-dim hover:text-terminal-primary">↺</button>
      <div class="flex gap-2 flex-wrap w-full sm:w-auto sm:ml-auto">
        <button @click="activeTab = 'positions'" :class="activeTab==='positions'?'text-terminal-accent':'text-[var(--text-muted)]'" class="text-xs whitespace-nowrap">持仓</button>
        <button @click="activeTab = 'performance'" :class="activeTab==='performance'?'text-terminal-accent':'text-[var(--text-muted)]'" class="text-xs whitespace-nowrap">业绩评价</button>
        <button @click="activeTab = 'risk'" :class="activeTab==='risk'?'text-terminal-accent':'text-[var(--text-muted)]'" class="text-xs whitespace-nowrap">风险分析</button>
        <button @click="activeTab = 'benchmark'" :class="activeTab==='benchmark'?'text-terminal-accent':'text-[var(--text-muted)]'" class="text-xs whitespace-nowrap">基准对比</button>
        <button @click="activeTab = 'analysis'" :class="activeTab==='analysis'?'text-terminal-accent':'text-[var(--text-muted)]'" class="text-xs whitespace-nowrap">归因分析</button>
      </div>
    </div>

    <!-- 加载状态 -->
    <LoadingSpinner v-if="loading" text="加载投资组合数据..." />
    
    <!-- 错误状态 -->
    <ErrorDisplay v-else-if="error" :error="error" :retry="loadPortfolioData" />

    <!-- 无账户时显示引导 -->
    <div v-else-if="portfolioList.length === 0" class="flex-1 flex items-center justify-center py-12">
      <div class="text-center">
        <div class="text-6xl mb-4">🏦</div>
        <div class="text-lg text-terminal-accent font-bold mb-2">欢迎使用投资组合管理</div>
        <div class="text-sm text-terminal-dim mb-4">创建您的第一个账户，开始管理投资组合</div>
        
        <!-- 功能预览卡片 -->
        <div class="bg-terminal-panel/50 border border-theme rounded-sm p-4 mb-4 max-w-2xl mx-auto">
          <div class="text-xs text-terminal-dim mb-3">💡 您将获得以下功能：</div>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div class="flex flex-col items-center gap-1 p-2 bg-terminal-bg/50 rounded-sm">
              <span class="text-2xl">📊</span>
              <span class="text-theme-secondary">持仓管理</span>
            </div>
            <div class="flex flex-col items-center gap-1 p-2 bg-terminal-bg/50 rounded-sm">
              <span class="text-2xl">📈</span>
              <span class="text-theme-secondary">业绩追踪</span>
            </div>
            <div class="flex flex-col items-center gap-1 p-2 bg-terminal-bg/50 rounded-sm">
              <span class="text-2xl">📋</span>
              <span class="text-theme-secondary">模拟调仓</span>
            </div>
            <div class="flex flex-col items-center gap-1 p-2 bg-terminal-bg/50 rounded-sm">
              <span class="text-2xl">⚠️</span>
              <span class="text-theme-secondary">风险分析</span>
            </div>
          </div>
        </div>
        
        <!-- 快速上手指南 -->
        <div class="bg-terminal-panel/50 border border-theme rounded-sm p-4 mb-4 max-w-md mx-auto">
          <div class="text-xs text-terminal-dim mb-3">🚀 快速上手指南：</div>
          <div class="space-y-2 text-xs text-theme-secondary">
            <div class="flex items-start gap-2">
              <span class="text-terminal-accent font-bold">1.</span>
              <span>点击下方按钮创建账户</span>
            </div>
            <div class="flex items-start gap-2">
              <span class="text-terminal-accent font-bold">2.</span>
              <span>选择「主账户」类型（可包含子账户）</span>
            </div>
            <div class="flex items-start gap-2">
              <span class="text-terminal-accent font-bold">3.</span>
              <span>输入账户名称和初始本金</span>
            </div>
            <div class="flex items-start gap-2">
              <span class="text-terminal-accent font-bold">4.</span>
              <span>添加持仓，开始追踪业绩</span>
            </div>
          </div>
        </div>
        
        <button @click="showCreateModal = true" class="btn-primary px-6 py-3 text-sm font-bold shadow-lg hover:shadow-xl transition-shadow">
          ➕ 创建第一个账户
        </button>
      </div>
    </div>

    <!-- 无持仓时显示 -->
    <div v-else-if="positions.length === 0 && selectedPortfolioId !== null" class="flex-1 flex items-center justify-center py-8">
      <div class="text-center">
        <div class="text-5xl mb-3">📭</div>
        <div class="text-base text-terminal-accent font-bold mb-2">暂无持仓</div>
        
        <!-- 显示当前账户信息 -->
        <div class="bg-terminal-panel/50 border border-theme rounded-sm p-3 mb-4 max-w-sm mx-auto">
          <div class="grid grid-cols-2 gap-3 text-xs">
            <div class="text-left">
              <div class="text-theme-tertiary mb-1">当前账户</div>
              <div class="text-theme-primary font-medium">{{ currentPortfolioName || '-' }}</div>
            </div>
            <div class="text-right">
              <div class="text-theme-tertiary mb-1">现金余额</div>
              <div class="text-terminal-accent font-bold">¥{{ (cashBalance||0).toLocaleString() }}</div>
            </div>
          </div>
        </div>
        
        <div class="text-xs text-theme-tertiary mb-4">
          点击「模拟调仓」添加您的第一笔持仓
        </div>
        
        <button @click="showTradeModal = true" class="bg-[var(--color-success-bg)] hover:bg-[var(--color-success-bg)] text-[var(--color-success)] border border-[var(--color-success-border)] px-6 py-2.5 text-sm font-bold rounded-sm transition-colors">
          📋 开始模拟调仓
        </button>
      </div>
    </div>

    <!-- 主内容区域（有持仓时显示） -->
    <div v-else>
      <!-- Phase 4: PnL 三分卡片 -->
      <div v-if="selectedPortfolioId !== null" class="pnl-cards-row">
      <div class="pnl-card">
        <div class="pnl-card-label">💰 现金余额</div>
        <div class="pnl-card-value">¥{{ (cashBalance||0).toLocaleString() }}</div>
      </div>
      <div class="pnl-card" :class="pnlClass(dailyPnl)">
        <div class="pnl-card-label">📈 当日盈亏</div>
        <div class="pnl-card-value">{{ fmtPnl(dailyPnl) }}</div>
      </div>
      <div class="pnl-card" :class="pnlClass(realizedPnl)">
        <div class="pnl-card-label">✅ 已实现盈亏</div>
        <div class="pnl-card-value">{{ fmtPnl(realizedPnl) }}</div>
      </div>
      <div class="pnl-card" :class="pnlClass(unrealizedPnl)">
        <div class="pnl-card-label">🔄 浮动盈亏</div>
        <div class="pnl-card-value">{{ fmtPnl(unrealizedPnl) }}</div>
      </div>
      <div class="pnl-card total">
        <div class="pnl-card-label">📊 总盈亏</div>
        <div class="pnl-card-value" :class="pnlClass(totalPnl)">{{ fmtPnl(totalPnl) }}</div>
      </div>
    </div>

    <!-- Phase 4: 持仓分布饼图 -->
    <div class="pie-chart-wrapper" v-if="selectedPortfolioId">
      <PositionPieChart v-if="selectedPortfolioId" :portfolioId="selectedPortfolioId" :includeChildren="isAggregated" />
    </div>

    <!-- Phase 5: 对账审计卡片 -->
    <div v-if="selectedPortfolioId" class="audit-card-wrapper">
      <ConservationAuditCard :portfolioId="selectedPortfolioId" />
    </div>

    <!-- Phase 4: Open Lots 批次明细 -->
    <OpenLotsPanel v-if="selectedPortfolioId" :portfolioId="selectedPortfolioId" :includeChildren="isAggregated" />

    <!-- 业绩评价 -->
    <div v-if="activeTab === 'performance'" class="mt-4 flex-1 min-h-0">
      <PerformancePanel :portfolioId="selectedPortfolioId" />
    </div>

    <!-- 风险分析 -->
    <div v-if="activeTab === 'risk'" class="mt-4 flex-1 min-h-0">
      <RiskPanel :portfolioId="selectedPortfolioId" />
    </div>

    <!-- 基准对比 -->
    <div v-if="activeTab === 'benchmark'" class="mt-4 flex-1 min-h-0">
      <BenchmarkPanel :portfolioId="selectedPortfolioId" />
    </div>

    <!-- 归因分析 -->
    <div v-if="activeTab === 'analysis'" class="mt-4">
      <AttributionPanel :portfolioId="selectedPortfolioId" />
    </div>
    </div>
  </div>

  <!-- 新建账户弹窗 -->
  <div v-if="showCreateModal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="showCreateModal = false">
    <div role="dialog" class="bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-sm p-6 w-full max-w-[384px] mx-4">
      <h3 class="text-theme-primary font-bold mb-4">新建账户</h3>
      <div class="space-y-3">
        <div>
          <label class="text-[var(--text-secondary)] text-xs">账户名称</label>
          <input v-model="newAccount.name" class="w-full bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-sm px-3 py-2 text-theme-primary mt-1" placeholder="如：我的子基金" />
        </div>
        <div>
          <label class="text-[var(--text-secondary)] text-xs">账户类型</label>
          <select v-model="newAccount.type" class="w-full bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-sm px-3 py-2 text-theme-primary mt-1">
            <option value="main">主账户（顶级账户，可包含子账户）</option>
            <option value="portfolio">子账户（隶属于主账户）</option>
          </select>
          <div class="text-[var(--text-muted)] text-xs mt-1">
            <span v-if="newAccount.type === 'main'">🏦 主账户是顶级账户，可以创建子账户进行分组管理</span>
            <span v-else>📂 子账户必须隶属于一个主账户，用于细分投资策略</span>
          </div>
        </div>
        <div>
          <label class="text-[var(--text-secondary)] text-xs">初始本金</label>
          <input v-model.number="newAccount.initialCapital" type="number" class="w-full bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-sm px-3 py-2 text-theme-primary mt-1" placeholder="0.00" />
        </div>
        <div v-if="newAccount.type !== 'main'">
          <label class="text-[var(--text-secondary)] text-xs">所属主账户</label>
          <select v-model="newAccount.parentId" class="w-full bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-sm px-3 py-2 text-theme-primary mt-1">
            <option value="">请选择主账户...</option>
            <option v-for="p in selectableParentList" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <div v-if="selectableParentList.length === 0" class="text-[var(--color-warning)] text-xs mt-1">
            ⚠️ 没有可用的主账户，请先创建一个主账户
          </div>
        </div>
        <div v-if="createError" class="text-[var(--color-danger)] text-xs">{{ createError }}</div>
      </div>
      <div class="flex gap-2 mt-4 justify-end">
        <button @click="showCreateModal = false" class="px-4 py-2 text-[var(--text-secondary)] hover:text-theme-primary">取消</button>
        <button @click="createAccount" class="btn-primary px-4 py-2">创建</button>
      </div>
    </div>
  </div>

  <!-- 资金划转弹窗 -->
  <div v-if="showTransferModal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="showTransferModal = false">
    <div class="bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-sm p-6 w-80">
      <h3 class="text-theme-primary font-bold mb-4">资金划转</h3>
      <div class="space-y-3">
        <div>
          <label class="text-[var(--text-secondary)] text-xs">从账户</label>
          <select v-model="transfer.from" class="w-full bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-sm px-3 py-2 text-theme-primary mt-1">
            <option v-for="p in portfolioList" :key="p.id" :value="p.id">{{ p.name }} ({{ p.type }})</option>
          </select>
        </div>
        <div>
          <label class="text-[var(--text-secondary)] text-xs">到账户</label>
          <select v-model="transfer.to" class="w-full bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-sm px-3 py-2 text-theme-primary mt-1">
            <option v-for="p in portfolioList" :key="p.id" :value="p.id">{{ p.name }} ({{ p.type }})</option>
          </select>
        </div>
        <div>
          <label class="text-[var(--text-secondary)] text-xs">金额 (¥)</label>
          <input v-model.number="transfer.amount" type="number" class="w-full bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-sm px-3 py-2 text-theme-primary mt-1" />
        </div>
        <div v-if="transferError" class="text-[var(--color-danger)] text-xs">{{ transferError }}</div>
      </div>
      <div class="flex gap-2 mt-4 justify-end">
        <button @click="showTransferModal = false" class="px-4 py-2 text-[var(--text-secondary)] hover:text-theme-primary">取消</button>
        <button @click="handleTransfer" class="btn-primary px-4 py-2">确认划转</button>
      </div>
    </div>
  </div>

  <!-- 模拟调仓弹窗 -->
  <SimulatedTradeModal
    v-if="selectedPortfolioId !== null"
    :visible="showTradeModal"
    :portfolioId="selectedPortfolioId"
    :portfolioName="currentPortfolioName"
    :isAggregated="isAggregated"
    @trade-done="onTradeDone"
    @close="showTradeModal = false"
  />
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { apiFetch } from '../utils/api.js';
import OpenLotsPanel from './OpenLotsPanel.vue';
import PositionPieChart from './PositionPieChart.vue';
import AttributionPanel from './AttributionPanel.vue';
import PerformancePanel from './PerformancePanel.vue';
import RiskPanel from './RiskPanel.vue';
import BenchmarkPanel from './BenchmarkPanel.vue';
import SimulatedTradeModal from './SimulatedTradeModal.vue';
import ConservationAuditCard from './ConservationAuditCard.vue';
import LoadingSpinner from './f9/LoadingSpinner.vue';
import ErrorDisplay from './f9/ErrorDisplay.vue';

// ── 常量 ─────────────────────────────────────────────────────────
const CURRENCIES = ['CNY', 'USD', 'HKD', 'EUR'];

// ── State ────────────────────────────────────────────────────────
const loading = ref(false);
const error = ref('');
const positions = ref([]);
const portfolioList = ref([]);
const showCreateModal = ref(false);
const showTransferModal = ref(false);
const showTradeModal = ref(false);
const activeTab = ref('positions');
const filterSector = ref('');
const filterPositionType = ref('');

let _fetchController = null  // AbortController：组件卸载时取消 pending 请求

const sortBy = ref('change_pct');
const cashBalance  = ref(0);
const dailyPnl     = ref(0);
const realizedPnl  = ref(0);
const unrealizedPnl = ref(0);
const totalPnl     = ref(0);

const newAccount = ref({ name: '', type: 'main', initialCapital: 0, parentId: null });
const transfer  = ref({ from: null, to: null, amount: 0 });
const createError   = ref('');
const transferError = ref('');

// ── Computed ────────────────────────────────────────────────────
const selectedPortfolioId = ref(null);

const filteredPositions = computed(() => {
  let list = positions.value;
  if (filterSector.value)       list = list.filter(p => p.sector === filterSector.value);
  if (filterPositionType.value) list = list.filter(p => (p.type || '') === filterPositionType.value);
  if (sortBy.value === 'change_pct')  list = [...list].sort((a, b) => b.changePct - a.changePct);
  if (sortBy.value === 'market_value') list = [...list].sort((a, b) => (b.marketValue||0) - (a.marketValue||0));
  if (sortBy.value === 'symbol')     list = [...list].sort((a, b) => (a.symbol||'').localeCompare(b.symbol||''));
  return list;
});

const totalValue = computed(() => positions.value.reduce((s, p) => s + (p.marketValue || 0), 0));
const totalCost  = computed(() => positions.value.reduce((s, p) => s + (p.cost||0), 0));
const totalPnL  = computed(() => totalValue.value - totalCost.value);
const sectorList = computed(() => [...new Set(positions.value.map(p => p.sector).filter(Boolean))]);

const selectableParentList = computed(() =>
  portfolioList.value.filter(p => p.type === 'main')
);

// 当前选中账户名称（供模拟调仓弹窗显示）
const currentPortfolioName = computed(() => {
  const node = flatTree.value.find(n => n.id === selectedPortfolioId.value);
  return node ? node.name : '';
});

// 模拟调仓完成后 → 刷新全部资产视图
function onTradeDone() {
  showTradeModal.value = false;
  loadPortfolioData();
}

// ── 父子关系映射（共享，避免重复计算）────────────────────
const portfolioChildMap = computed(() => {
  const m = {};
  portfolioList.value.forEach(p => {
    const parent = p.parent_id ?? null;
    if (!m[parent]) m[parent] = [];
    m[parent].push(p);
  });
  return m;
});

// ── 树形结构（扁平化带缩进，供 select 渲染）────────────────────
const flatTree = computed(() => {
  const childMap = portfolioChildMap.value; // 共享映射，避免重复计算
  const indent = (depth) => '　'.repeat(depth) + (depth > 0 ? '└─ ' : '');

  const result = [];
  function traverse(pid, depth) {
    const nodes = childMap[pid] || [];
    // 只显示主账户作为顶级节点
    const filteredNodes = depth === 0 
      ? nodes.filter(n => n.type === 'main')
      : nodes;
    filteredNodes.forEach(node => {
      result.push({ ...node, _label: indent(depth) + (depth > 0 ? '📂 ' : '🏦 ') + node.name });
      traverse(node.id, depth + 1);
    });
  }
  traverse(null, 0);
  return result;
});

// ── 当前选中账户是否有子账户（用于触发 include_children）────────
const isAggregated = computed(() => {
  const node = flatTree.value.find(n => n.id === selectedPortfolioId.value);
  if (!node) return false;
  // 使用共享的 portfolioChildMap，避免重复计算
  return (portfolioChildMap.value[node.id] || []).length > 0;
});

const canTransfer = computed(() =>
  transfer.value.from !== null &&
  transfer.value.to !== null &&
  transfer.value.from !== transfer.value.to &&
  transfer.value.amount > 0
);

// ── Helpers ────────────────────────────────────────────────────
function fmtPnl(v) {
  if (!v && v !== 0) return '—';
  return (v > 0 ? '+¥' : '¥') + Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function pnlClass(v) {
  if (!v && v !== 0) return 'pnl-zero';
  return v > 0 ? 'pnl-pos' : 'pnl-neg';
}

// ── Load ────────────────────────────────────────────────────
async function loadPortfolioData() {
  if (!selectedPortfolioId.value) return;
  loading.value = true;
  error.value = '';
  const pid = selectedPortfolioId.value;
  const agg = isAggregated.value ? '?include_children=true' : '';
  try {
    // Abort any pending request before starting a new one
    _fetchController?.abort()
    _fetchController = new AbortController()
    // 使用 /pnl 端点获取聚合视图（包含 cash_balance + 全量 PnL）
    const res = await apiFetch(`/api/v1/portfolio/${pid}/pnl${agg}`, { signal: _fetchController.signal });
    const data = res.data || res;
    // positions 端点返回 { positions: [...] }（无 data 包装）
    const posRes = await apiFetch(`/api/v1/portfolio/${pid}/positions${agg}`, { signal: _fetchController.signal });
    positions.value = posRes.positions || posRes.data?.positions || [];
    cashBalance.value  = data.cash_balance   || 0;
    dailyPnl.value      = data.daily_pnl      || 0;
    realizedPnl.value   = data.realized_pnl  || 0;
    unrealizedPnl.value = data.unrealized_pnl || 0;
    totalPnl.value     = data.total_pnl      || 0;
  } catch (e) {
    // Ignore abort errors silently
    if (e.name === 'AbortError' || e.message?.includes('aborted')) return
    console.warn('[Portfolio] loadPortfolioData failed', e.message);
    error.value = e.message || '加载投资组合数据失败';
    positions.value = [];
  } finally {
    _fetchController = null;
    loading.value = false;
  }
}

async function loadPortfolios() {
  try {
    // Abort any pending request before starting a new one
    _fetchController?.abort()
    _fetchController = new AbortController()
    const res = await apiFetch('/api/v1/portfolio/', { signal: _fetchController.signal });
    portfolioList.value = res.portfolios || [];
    if (portfolioList.value.length && selectedPortfolioId.value === null) {
      selectedPortfolioId.value = portfolioList.value[0].id;
    }
  } catch (e) {
    // Ignore abort errors silently
    if (e.name === 'AbortError' || e.message?.includes('aborted')) return
    console.warn('[Portfolio] loadPortfolios failed', e.message);
  } finally {
    _fetchController = null;
  }
}

onMounted(async () => {
  try {
    await loadPortfolios();
    await loadPortfolioData();
  } catch (e) {
    console.error('[Portfolio] Mount failed:', e);
  }
});

onUnmounted(() => {
  // Cancel any pending fetch requests
  _fetchController?.abort();
  _fetchController = null;
});

watch(selectedPortfolioId, loadPortfolioData);

// ── Actions ─────────────────────────────────────────────────
async function createAccount() {
  createError.value = '';
  if (!newAccount.value.name.trim()) { createError.value = '请填写账户名称'; return; }
  try {
    const res = await apiFetch('/api/v1/portfolio/', {
      method: 'POST',
      body: JSON.stringify({
        name: newAccount.value.name,
        type: newAccount.value.type,
        parent_id: newAccount.value.parentId || undefined,
        initial_capital: newAccount.value.initialCapital || 0,
      }),
    });
    if (res.code === 0 || res.code === undefined) {
      showCreateModal.value = false;
      newAccount.value = { name: '', type: 'main', initialCapital: 0, parentId: null };
      await loadPortfolios();
    } else {
      createError.value = res.message || '创建失败';
    }
  } catch (e) { createError.value = e.message; }
}

async function handleTransfer() {
  if (!canTransfer.value) { transferError.value = '请选择账户和金额'; return; }
  transferError.value = '';
  try {
    const res = await apiFetch('/api/v1/portfolio/transfer/direct', {
      method: 'POST',
      body: JSON.stringify({
        from_portfolio_id: transfer.value.from,
        to_portfolio_id:   transfer.value.to,
        amount:            transfer.value.amount,
      }),
    });
    if (res.code === 0) {
      showTransferModal.value = false;
      transfer.value = { from: null, to: null, amount: 0 };
    } else {
      transferError.value = res.message || '划转失败';
    }
  } catch (e) { transferError.value = e.message; }
}

function handleTransferOk() {
  showTransferModal.value = false;
  loadPortfolioData();
}

// ── Export ────────────────────────────────────────────────────
async function exportPortfolio() {
  if (!selectedPortfolioId.value) return;
  
  try {
    const pid = selectedPortfolioId.value;
    const response = await fetch(`/api/v1/export/portfolio/${pid}?format=excel`, {
      method: 'GET',
      headers: {
        'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      }
    });
    
    if (!response.ok) {
      throw new Error(`Export failed: ${response.statusText}`);
    }
    
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `portfolio_${pid}_${new Date().toISOString().slice(0,10)}.xlsx`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (e) {
    console.error('[Portfolio] Export failed:', e);
    alert('导出失败: ' + e.message);
  }
}
</script>

<style scoped>
.pnl-cards-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  padding: 0 0 12px;
}
@media (min-width: 640px) {
  .pnl-cards-row {
    grid-template-columns: repeat(3, 1fr);
  }
}
@media (min-width: 1024px) {
  .pnl-cards-row {
    grid-template-columns: repeat(5, 1fr);
  }
}
.pnl-card {
  background: var(--bg-primary);
  border: 1px solid var(--bg-secondary);
  border-radius: 8px;
  padding: 10px 14px;
}
.pnl-card.total { border-color: var(--border-primary); background: var(--bg-secondary); }
.pnl-card-label { font-size: 11px; color: var(--text-tertiary); margin-bottom: 4px; white-space: nowrap; }
.pnl-card-value { font-size: 14px; font-weight: 700; color: var(--text-primary); }
.pnl-pos .pnl-card-value { color: var(--bearish); }
.pnl-neg .pnl-card-value { color: var(--bullish); }
.pnl-zero .pnl-card-value { color: var(--text-tertiary); }
.pie-chart-wrapper { padding: 0 0 12px; }
.pie-chart-wrapper :deep(.position-pie-chart) { min-height: 300px; display: flex; flex-direction: column; }
.pie-chart-wrapper :deep(.echart-container) { min-height: 260px; height: 260px; }
.audit-card-wrapper { padding: 0 0 12px; }
.audit-card-wrapper :deep(.conservation-audit-card) { min-height: 180px; }
</style>
