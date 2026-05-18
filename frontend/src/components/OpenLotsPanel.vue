<template>
  <div class="open-lots-panel">
    <!-- 工具栏 -->
    <div class="panel-toolbar">
      <span class="panel-title">📊 持仓批次明细</span>
      <button class="btn-refresh" @click="loadLots" :disabled="loading">
        <span v-if="loading">⟳ 加载中</span>
        <span v-else>↻ 刷新</span>
      </button>
    </div>

    <!-- 加载中骨架屏 -->
    <div v-if="loading" class="loading-state">
      <div v-for="n in 3" :key="n" class="skeleton-row">
        <div class="skeleton-cell"></div>
        <div class="skeleton-cell"></div>
        <div class="skeleton-cell"></div>
        <div class="skeleton-cell"></div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading && lots.length === 0" class="empty-state">
      <div class="empty-icon">📭</div>
      <div class="empty-text">暂无持仓批次</div>
      <div class="empty-hint">买入标的后将显示在这里</div>
    </div>

    <!-- 批次表格（虚拟化） -->
    <VirtualizedTable
      v-else
      :items="lots"
      :columns="tableColumns"
      :item-size="36"
      :buffer="200"
      :loading="loading"
      empty-text="暂无持仓批次"
      class="lots-table-virtualized"
    >
      <template #cell-symbol="{ item }">
        <span class="symbol">{{ item.symbol }}</span>
      </template>
      <template #cell-shares="{ item }">
        <span class="num">{{ item.shares.toLocaleString() }}</span>
      </template>
      <template #cell-avg_cost="{ item }">
        <span class="num">¥{{ item.avg_cost.toFixed(3) }}</span>
      </template>
      <template #cell-unrealized_pnl="{ item }">
        <span class="num" :class="getPnlClass(item.unrealized_pnl)">
          {{ item.unrealized_pnl > 0 ? '+' : '' }}{{ item.unrealized_pnl.toFixed(2) }}
        </span>
      </template>
      <template #cell-unrealized_pnl_pct="{ item }">
        <span class="num" :class="getPnlClass(item.unrealized_pnl)">
          {{ getPnlPct(item) }}
        </span>
      </template>
      <template #cell-status="{ item }">
        <span class="badge" :class="item.status === 'open' ? 'badge-open' : 'badge-closed'">
          {{ item.status === 'open' ? '● 持仓中' : '✗ 已平' }}
        </span>
      </template>
    </VirtualizedTable>

    <!-- 底部汇总 -->
    <div v-if="!loading && lots.length > 0" class="panel-footer">
      <span>共 {{ lots.length }} 个批次，</span>
      <span>合计 {{ totalShares.toLocaleString() }} 股，</span>
      <span>浮动盈亏合计：
        <b :class="getPnlClass(totalUnrealizedPnl)">
          {{ totalUnrealizedPnl > 0 ? '+' : '' }}¥{{ totalUnrealizedPnl.toFixed(2) }}
        </b>
      </span>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { apiFetch } from '../utils/api.js';
import VirtualizedTable from './VirtualizedTable.vue';

export default {
  name: 'OpenLotsPanel',
  components: { VirtualizedTable },
  props: {
    portfolioId: { type: Number, required: true },
    includeChildren: { type: Boolean, default: false },
  },
  setup(props) {
    const loading = ref(false);
    const lots = ref([]);
    const error = ref(null);

    // 表格列配置
    const tableColumns = [
      { key: 'symbol', label: '标的', width: '80px' },
      { key: 'shares', label: '剩余股数', width: '100px', align: 'right' },
      { key: 'avg_cost', label: '成本价(元)', width: '100px', align: 'right' },
      { key: 'unrealized_pnl', label: '浮动盈亏', width: '100px', align: 'right' },
      { key: 'unrealized_pnl_pct', label: '浮动收益率', width: '100px', align: 'right' },
      { key: 'buy_date', label: '买入日期', width: '100px' },
      { key: 'status', label: '状态', width: '80px' },
    ];

    // 当前价格映射（简单用最后成交价，未知则用成本价）
    async function loadLots() {
      loading.value = true;
      error.value = null;
      const agg = props.includeChildren ? '?include_children=true' : '';
      try {
        const res = await apiFetch(`/api/v1/portfolio/${props.portfolioId}/lots/with_summary${agg}`);
        const data = res.data || res;
        lots.value = data.lots || [];
      } catch (e) {
        error.value = e.message;
        console.warn('[OpenLotsPanel] load error:', e.message);
      } finally {
        loading.value = false;
      }
    }

    const totalShares = computed(() => lots.value.reduce((s, l) => s + l.shares, 0));
    const totalUnrealizedPnl = computed(() => lots.value.reduce((s, l) => s + (l.unrealized_pnl || 0), 0));

    function getPnlClass(val) {
      if (val > 0) return 'pnl-pos';
      if (val < 0) return 'pnl-neg';
      return 'pnl-zero';
    }

    function getPnlPct(lot) {
      if (!lot.avg_cost || lot.shares === 0) return '—';
      // 用 unrealized_pnl / (shares * avg_cost) 反推 current_price
      const cost = lot.shares * lot.avg_cost;
      if (cost === 0) return '—';
      return ((lot.unrealized_pnl || 0) / cost * 100).toFixed(2) + '%';
    }

    onMounted(loadLots);

    return { loading, lots, error, loadLots, totalShares, totalUnrealizedPnl, getPnlClass, getPnlPct, tableColumns };
  },
};
</script>

<style scoped>
.open-lots-panel { background: var(--bg-surface); border-radius: var(--radius-lg); overflow: hidden; display: flex; flex-direction: column; height: 100%; }
.panel-toolbar { display: flex; justify-content: space-between; align-items: center; padding: var(--space-sm) var(--space-md); background: var(--bg-elevated); border-bottom: 1px solid var(--border-base); }
.panel-title { color: var(--text-secondary); font-size: 13px; font-weight: 600; }
.btn-refresh { background: none; border: 1px solid var(--border-base); color: var(--text-muted); padding: 3px 10px; border-radius: var(--radius-sm); cursor: pointer; font-size: 12px; transition: all var(--duration-fast) var(--easing-default); }
.btn-refresh:hover { border-color: var(--color-primary); color: var(--text-secondary); }
.btn-refresh:disabled { opacity: 0.5; cursor: not-allowed; }
.loading-state { padding: var(--space-sm) var(--space-md); }
.skeleton-row { display: flex; gap: var(--space-xs); margin-bottom: var(--space-xs); }
.skeleton-cell { flex: 1; height: 20px; background: var(--bg-elevated); border-radius: 3px; animation: pulse 1.4s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
.empty-state { text-align: center; padding: var(--space-xl) 0; color: var(--text-muted); }
.empty-icon { font-size: 32px; margin-bottom: var(--space-xs); }
.empty-text { font-size: 14px; font-weight: 600; }
.empty-hint { font-size: 12px; margin-top: 4px; color: var(--text-disabled); }
.lots-table-virtualized { flex: 1; min-height: 0; }
.lots-table-virtualized :deep(.symbol) { color: var(--color-primary); font-weight: 600; }
.lots-table-virtualized :deep(.num) { font-family: var(--font-number); }
.lots-table-virtualized :deep(.pnl-pos) { color: var(--color-bull); }
.lots-table-virtualized :deep(.pnl-neg) { color: var(--color-bear); }
.lots-table-virtualized :deep(.pnl-zero) { color: var(--text-muted); }
.lots-table-virtualized :deep(.badge) { padding: 2px 6px; border-radius: 3px; font-size: 11px; }
.lots-table-virtualized :deep(.badge-open) { background: rgba(52, 211, 153, 0.1); color: var(--color-bull); }
.lots-table-virtualized :deep(.badge-closed) { background: var(--bg-elevated); color: var(--text-muted); }
.panel-footer { padding: var(--space-xs) var(--space-md); font-size: 11px; color: var(--text-muted); border-top: 1px solid var(--border-light); text-align: right; }
.panel-footer b.pnl-pos { color: var(--color-bull); }
.panel-footer b.pnl-neg { color: var(--color-bear); }
</style>
