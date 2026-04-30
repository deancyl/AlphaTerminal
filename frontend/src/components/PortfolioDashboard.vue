<template>
  <div class="p-4">
    <!-- 标题 -->
    <div class="flex items-center justify-between mb-1">
      <span class="text-terminal-accent font-bold text-sm">💰 投资组合</span>
      <div class="flex gap-2">
        <button
          v-if="selectedPortfolioId !== null"
          @click="exportPortfolio"
          class="bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 border border-blue-500/30 text-xs px-3 py-1 rounded font-bold transition-colors"
        >📥 导出</button>
        <button
          v-if="selectedPortfolioId !== null"
          @click="showTradeModal = true"
          class="bg-green-500/20 hover:bg-green-500/30 text-green-400 border border-green-500/30 text-xs px-3 py-1 rounded font-bold transition-colors"
        >📋 模拟调仓</button>
        <button @click="showCreateModal = true" class="btn-primary text-xs px-3 py-1">+ 新建</button>
      </div>
    </div>

    <!-- 树形账户选择器 + 聚合指示器 -->
    <div v-if="selectedPortfolioId !== null" class="flex items-center gap-2 mb-2">
      <span class="text-terminal-dim text-xs">账户：</span>
      <select v-model="selectedPortfolioId" class="bg-terminal-panel border border-theme-secondary rounded px-2 py-1 text-terminal-primary text-xs flex-1">
        <template v-for="node in flatTree" :key="node.id">
          <option :value="node.id">{{ node._label }}</option>
        </template>
      </select>
      <span v-if="isAggregated" class="text-xs text-yellow-400 bg-yellow-400/10 border border-yellow-400/30 rounded px-2 py-0.5">
        📂 含子账户
      </span>
    </div>

    <!-- 操作栏：过滤器 -->
    <div v-if="selectedPortfolioId !== null" class="flex gap-2 mb-3 items-center text-xs flex-wrap">
      <select v-model="filterSector" class="bg-terminal-panel border border-theme-secondary rounded px-2 py-1 text-terminal-secondary">
        <option value="">全部行业</option>
        <option v-for="s in sectorList" :key="s" :value="s">{{ s }}</option>
      </select>
      <select v-model="filterPositionType" class="bg-terminal-panel border border-theme-secondary rounded px-2 py-1 text-terminal-secondary">
        <option value="">全部类型</option>
        <option value="stock">股票</option>
        <option value="index">指数</option>
        <option value="ETF">ETF</option>
      </select>
      <select v-model="sortBy" class="bg-terminal-panel border border-theme-secondary rounded px-2 py-1 text-terminal-secondary">
        <option value="change_pct">按涨跌幅</option>
        <option value="market_value">按市值</option>
        <option value="symbol">按代码</option>
      </select>
      <button @click="loadPortfolioData" class="text-terminal-dim hover:text-terminal-primary">↺</button>
      <div class="ml-auto flex gap-2">
        <button @click="activeTab = 'positions'" :class="activeTab==='positions'?'text-terminal-accent':'text-gray-500'">持仓</button>
        <button @click="activeTab = 'analysis'" :class="activeTab==='analysis'?'text-terminal-accent':'text-gray-500'">归因分析</button>
      </div>
    </div>

    <!-- 无持仓时显示 -->
    <div v-if="positions.length === 0 && !loading" class="text-center text-terminal-dim py-8">
      <div class="text-2xl mb-2">📭</div>
      <div>暂无持仓</div>
      <div class="text-xs text-theme-tertiary mt-1">买入标的后将显示在这里</div>
    </div>

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

    <!-- 归因分析 -->
    <div v-if="activeTab === 'analysis'" class="mt-4">
      <AttributionPanel :portfolioId="selectedPortfolioId" />
    </div>
  </div>

  <!-- 新建账户弹窗 -->
  <div v-if="showCreateModal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="showCreateModal = false">
    <div class="bg-gray-900 border border-gray-700 rounded-lg p-6 w-full max-w-[384px] mx-4">
      <h3 class="text-white font-bold mb-4">新建账户</h3>
      <div class="space-y-3">
        <div>
          <label class="text-gray-400 text-xs">账户名称</label>
          <input v-model="newAccount.name" class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white mt-1" placeholder="如：我的子基金" />
        </div>
        <div>
          <label class="text-gray-400 text-xs">账户类型</label>
          <select v-model="newAccount.type" class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white mt-1">
            <option value="main">主账户（顶级账户，可包含子账户）</option>
            <option value="portfolio">子账户（隶属于主账户）</option>
          </select>
          <div class="text-gray-500 text-xs mt-1">
            <span v-if="newAccount.type === 'main'">🏦 主账户是顶级账户，可以创建子账户进行分组管理</span>
            <span v-else>📂 子账户必须隶属于一个主账户，用于细分投资策略</span>
          </div>
        </div>
        <div>
          <label class="text-gray-400 text-xs">初始本金</label>
          <input v-model.number="newAccount.initialCapital" type="number" class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white mt-1" placeholder="0.00" />
        </div>
        <div v-if="newAccount.type !== 'main'">
          <label class="text-gray-400 text-xs">所属主账户</label>
          <select v-model="newAccount.parentId" class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white mt-1">
            <option value="">请选择主账户...</option>
            <option v-for="p in selectableParentList" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <div v-if="selectableParentList.length === 0" class="text-yellow-500 text-xs mt-1">
            ⚠️ 没有可用的主账户，请先创建一个主账户
          </div>
        </div>
        <div v-if="createError" class="text-red-400 text-xs">{{ createError }}</div>
      </div>
      <div class="flex gap-2 mt-4 justify-end">
        <button @click="showCreateModal = false" class="px-4 py-2 text-gray-400 hover:text-white">取消</button>
        <button @click="createAccount" class="btn-primary px-4 py-2">创建</button>
      </div>
    </div>
  </div>

  <!-- 资金划转弹窗 -->
  <div v-if="showTransferModal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="showTransferModal = false">
    <div class="bg-gray-900 border border-gray-700 rounded-lg p-6 w-80">
      <h3 class="text-white font-bold mb-4">资金划转</h3>
      <div class="space-y-3">
        <div>
          <label class="text-gray-400 text-xs">从账户</label>
          <select v-model="transfer.from" class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white mt-1">
            <option v-for="p in portfolioList" :key="p.id" :value="p.id">{{ p.name }} ({{ p.type }})</option>
          </select>
        </div>
        <div>
          <label class="text-gray-400 text-xs">到账户</label>
          <select v-model="transfer.to" class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white mt-1">
            <option v-for="p in portfolioList" :key="p.id" :value="p.id">{{ p.name }} ({{ p.type }})</option>
          </select>
        </div>
        <div>
          <label class="text-gray-400 text-xs">金额 (¥)</label>
          <input v-model.number="transfer.amount" type="number" class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white mt-1" />
        </div>
        <div v-if="transferError" class="text-red-400 text-xs">{{ transferError }}</div>
      </div>
      <div class="flex gap-2 mt-4 justify-end">
        <button @click="showTransferModal = false" class="px-4 py-2 text-gray-400 hover:text-white">取消</button>
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
import { ref, computed, watch, onMounted } from 'vue';
import { apiFetch } from '../utils/api.js';
import OpenLotsPanel from './OpenLotsPanel.vue';
import PositionPieChart from './PositionPieChart.vue';
import AttributionPanel from './AttributionPanel.vue';
import SimulatedTradeModal from './SimulatedTradeModal.vue';
import ConservationAuditCard from './ConservationAuditCard.vue';

// ── 常量 ─────────────────────────────────────────────────────────
const CURRENCIES = ['CNY', 'USD', 'HKD', 'EUR'];

// ── State ────────────────────────────────────────────────────────
const loading = ref(false);
const positions = ref([]);
const portfolioList = ref([]);
const showCreateModal = ref(false);
const showTransferModal = ref(false);
const showTradeModal = ref(false);
const activeTab = ref('positions');
const filterSector = ref('');
const filterPositionType = ref('');
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
  const pid = selectedPortfolioId.value;
  const agg = isAggregated.value ? '?include_children=true' : '';
  try {
    // 使用 /pnl 端点获取聚合视图（包含 cash_balance + 全量 PnL）
    const res = await apiFetch(`/api/v1/portfolio/${pid}/pnl${agg}`);
    const data = res.data || res;
    // positions 端点返回 { positions: [...] }（无 data 包装）
    const posRes = await apiFetch(`/api/v1/portfolio/${pid}/positions${agg}`);
    positions.value = posRes.positions || posRes.data?.positions || [];
    cashBalance.value  = data.cash_balance   || 0;
    dailyPnl.value      = data.daily_pnl      || 0;
    realizedPnl.value   = data.realized_pnl  || 0;
    unrealizedPnl.value = data.unrealized_pnl || 0;
    totalPnl.value     = data.total_pnl      || 0;
  } catch (e) {
    console.warn('[Portfolio] loadPortfolioData failed', e.message);
    positions.value = [];
  } finally {
    loading.value = false;
  }
}

async function loadPortfolios() {
  try {
    const res = await apiFetch('/api/v1/portfolio/');
    portfolioList.value = res.portfolios || [];
    if (portfolioList.value.length && selectedPortfolioId.value === null) {
      selectedPortfolioId.value = portfolioList.value[0].id;
    }
  } catch (e) { console.warn('[Portfolio] loadPortfolios failed', e.message); }
}

onMounted(async () => {
  await loadPortfolios();
  await loadPortfolioData();
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
  display: flex;
  gap: 10px;
  padding: 0 0 12px;
  flex-wrap: wrap;
}
.pnl-card {
  background: #131a28;
  border: 1px solid #1e2535;
  border-radius: 8px;
  padding: 10px 14px;
  flex: 1;
  min-width: 120px;
}
.pnl-card.total { border-color: #2a3444; background: #1a2030; }
.pnl-card-label { font-size: 11px; color: #4a5a6a; margin-bottom: 4px; white-space: nowrap; }
.pnl-card-value { font-size: 14px; font-weight: 700; color: #c8d4e8; }
.pnl-pos .pnl-card-value { color: #34d399; }
.pnl-neg .pnl-card-value { color: #f87171; }
.pnl-zero .pnl-card-value { color: #4a5a6a; }
.pie-chart-wrapper { padding: 0 0 12px; }
.pie-chart-wrapper :deep(.position-pie-chart) { min-height: 300px; display: flex; flex-direction: column; }
.pie-chart-wrapper :deep(.echart-container) { min-height: 260px; height: 260px; }
.audit-card-wrapper { padding: 0 0 12px; }
.audit-card-wrapper :deep(.conservation-audit-card) { min-height: 180px; }
</style>
