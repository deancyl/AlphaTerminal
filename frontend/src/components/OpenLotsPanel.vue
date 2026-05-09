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

    <!-- 批次表格 -->
    <table v-else class="lots-table">
      <thead>
        <tr>
          <th>标的</th>
          <th class="num">剩余股数</th>
          <th class="num">成本价(元)</th>
          <th class="num">浮动盈亏</th>
          <th class="num">浮动收益率</th>
          <th>买入日期</th>
          <th>状态</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="lot in lots" :key="lot.id" class="lot-row">
          <td class="symbol">{{ lot.symbol }}</td>
          <td class="num">{{ lot.shares.toLocaleString() }}</td>
          <td class="num">¥{{ lot.avg_cost.toFixed(3) }}</td>
          <td class="num" :class="getPnlClass(lot.unrealized_pnl)">
            {{ lot.unrealized_pnl > 0 ? '+' : '' }}{{ lot.unrealized_pnl.toFixed(2) }}
          </td>
          <td class="num" :class="getPnlClass(lot.unrealized_pnl)">
            {{ getPnlPct(lot) }}
          </td>
          <td>{{ lot.buy_date }}</td>
          <td>
            <span class="badge" :class="lot.status === 'open' ? 'badge-open' : 'badge-closed'">
              {{ lot.status === 'open' ? '● 持仓中' : '✗ 已平' }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>

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

export default {
  name: 'OpenLotsPanel',
  props: {
    portfolioId: { type: Number, required: true },
    includeChildren: { type: Boolean, default: false },
  },
  setup(props) {
    const loading = ref(false);
    const lots = ref([]);
    const error = ref(null);

    // 当前价格映射（简单用最后成交价，未知则用成本价）
    async function loadLots() {
      loading.value = true;
      error.value = null;
      const agg = props.includeChildren ? '?include_children=true' : '';
      try {
        const res = await apiFetch(`/api/v1/portfolio/${props.portfolioId}/lots${agg}`);
        const data = res.data || res;
        const rawLots = data.lots || [];

        // 对每个 lot 估算浮动盈亏（用 avg_cost 作为参考价）
        // 实际项目中应从 position_summary 取 market_value
        lots.value = rawLots.map(l => ({
          ...l,
          unrealized_pnl: 0,   // 由 position_summary 提供
        }));

        // 补充 position_summary
        try {
          const summRes = await apiFetch(`/api/v1/portfolio/${props.portfolioId}/lots/summary${agg}`);
          const summData = summRes.data || summRes;
          const summaryMap = {};
          (summData.summary || []).forEach(s => {
            summaryMap[s.symbol] = s;
          });
          lots.value = rawLots.map(l => {
            const s = summaryMap[l.symbol] || {};
            return {
              ...l,
              unrealized_pnl: s.unrealized_pnl || 0,
              market_value: s.market_value || 0,
            };
          });
        } catch (parseError) {
          console.warn('[OpenLotsPanel] Failed to parse summary data:', parseError.message);
          // Continue with empty summary map
        }
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

    return { loading, lots, error, loadLots, totalShares, totalUnrealizedPnl, getPnlClass, getPnlPct };
  },
};
</script>

<style scoped>
.open-lots-panel { background: #0f1419; border-radius: 8px; overflow: hidden; }
.panel-toolbar { display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; background: #1a2030; border-bottom: 1px solid #2a3444; }
.panel-title { color: #c8d4e8; font-size: 13px; font-weight: 600; }
.btn-refresh { background: none; border: 1px solid #2a3444; color: #7a8ba8; padding: 3px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.btn-refresh:hover { border-color: #4a6fa5; color: #c8d4e8; }
.loading-state { padding: 12px 16px; }
.skeleton-row { display: flex; gap: 8px; margin-bottom: 8px; }
.skeleton-cell { flex: 1; height: 20px; background: #1e2535; border-radius: 3px; animation: pulse 1.4s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
.empty-state { text-align: center; padding: 40px 0; color: #4a5a6a; }
.empty-icon { font-size: 32px; margin-bottom: 8px; }
.empty-text { font-size: 14px; font-weight: 600; }
.empty-hint { font-size: 12px; margin-top: 4px; color: #3a4a5a; }
.lots-table { width: 100%; min-height: 60px; border-collapse: collapse; font-size: 12px; }
.lots-table th { padding: 8px 12px; text-align: left; color: #4a5a6a; font-weight: 500; font-size: 11px; border-bottom: 1px solid #1e2535; }
.lots-table td { padding: 8px 12px; border-bottom: 1px solid #1a2030; color: #c8d4e8; }
.lots-table tr:hover td { background: #131a28; }
.num { text-align: right; }
.symbol { color: #7dd3fc; font-weight: 600; }
.pnl-pos { color: #34d399; }
.pnl-neg { color: #f87171; }
.pnl-zero { color: #4a5a6a; }
.badge { padding: 2px 6px; border-radius: 3px; font-size: 11px; }
.badge-open { background: #0d2820; color: #34d399; }
.badge-closed { background: #1e2535; color: #4a5a6a; }
.panel-footer { padding: 8px 16px; font-size: 11px; color: #4a5a6a; border-top: 1px solid #1e2535; text-align: right; }
</style>
