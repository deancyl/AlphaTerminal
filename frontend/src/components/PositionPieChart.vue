<template>
  <div class="position-pie-chart">
    <div class="panel-toolbar">
      <span class="panel-title">🥧 持仓分布</span>
      <button class="btn-refresh" @click="load" :disabled="loading">
        <span v-if="loading">⟳</span>
        <span v-else>↻</span>
      </button>
    </div>

    <!-- 加载中占位 -->
    <div v-if="loading" class="chart-placeholder loading">
      <div class="w-full h-full flex flex-col items-center justify-center gap-3 p-4">
        <div class="w-24 h-24 rounded-full skeleton"></div>
        <div class="skeleton h-3 w-20 rounded-sm"></div>
        <div class="skeleton h-2 w-16 rounded-sm"></div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading && (!positions || positions.length === 0)" class="chart-placeholder empty">
      <div class="empty-icon">📊</div>
      <div class="empty-text">暂无持仓数据</div>
      <div class="empty-hint">ECharts 将在有持仓后自动渲染</div>
    </div>

    <!-- ECharts 饼图 -->
    <div v-else ref="chartEl" class="echart-container"></div>

    <!-- 底部持仓列表 -->
    <div v-if="!loading && positions.length > 0" class="pie-legend">
      <div v-for="p in positions" :key="p.symbol" class="legend-item">
        <span class="legend-dot" :style="{ background: p.color }"></span>
        <span class="legend-symbol">{{ p.symbol }}</span>
        <span class="legend-pct">{{ p.weight_pct }}%</span>
        <span class="legend-mv">¥{{ (p.market_value / 1000).toFixed(1) }}k</span>
        <span class="legend-pnl" :class="getPnlClass(p.unrealized_pnl)">
          {{ p.unrealized_pnl > 0 ? '+' : '' }}{{ (p.unrealized_pnl / 1000).toFixed(1) }}k
        </span>
      </div>
    </div>

    <!-- 全局汇总 -->
    <div v-if="!loading && totalMv > 0" class="pie-footer">
      总市值 <b>¥{{ totalMv.toLocaleString() }}</b> · 浮动盈亏
      <b :class="getPnlClass(totalPnl)">{{ totalPnl > 0 ? '+' : '' }}¥{{ totalPnl.toFixed(2) }}</b>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { apiFetch } from '../utils/api.js';

// 动态引入 echarts（SSR 友好）
let echarts = null;
async function getEcharts() {
  // 优先使用 index.html CDN 加载的全局 echarts（100% 可用）
  if (typeof window !== 'undefined' && window.echarts) {
    return window.echarts;
  }
  // fallback: Vite 动态 import（仅在 CDN 未注入时尝试）
  if (!echarts) {
    echarts = await import('echarts').catch(() => null);
  }
  if (echarts) return echarts;
  throw new Error('ECharts 不可用（window.echarts 未注入且 import 失败）');
}

export default {
  name: 'PositionPieChart',
  props: {
    portfolioId: { type: Number, required: true },
    includeChildren: { type: Boolean, default: false },
  },
  setup(props) {
    const chartEl = ref(null);
    const loading = ref(false);
    const positions = ref([]);
    const totalMv = ref(0);
    const totalPnl = ref(0);
    let chartInstance = null;

    const ECHART_COLORS = [
      '#7dd3fc', '#34d399', '#fbbf24', '#f87171',
      '#c084fc', '#fb923c', '#a3e635', '#38bdf8',
    ];

    async function load() {
      loading.value = true;
      const agg = props.includeChildren ? '?include_children=true' : '';
      try {
        const res = await apiFetch(`/api/v1/portfolio/${props.portfolioId}/lots/echarts${agg}`);
        const data = res.data || res;
        const pos = data.positions || [];
        totalMv.value = data.total_market_value || 0;
        totalPnl.value = pos.reduce((s, p) => s + (p.unrealized_pnl || 0), 0);

        positions.value = pos.map((p, i) => ({
          ...p,
          color: ECHART_COLORS[i % ECHART_COLORS.length],
        }));

        await renderChart();
      } catch (e) {
        console.warn('[PositionPieChart] load error:', e.message);
      } finally {
        loading.value = false;
      }
    }

    async function renderChart() {
      // Try ref first, fall back to DOM query (fixes ref binding race in Options API + setup() mix)
      const domEl = chartEl.value || document.querySelector('.echart-container');
      if (!domEl) {
        console.log('[PPC] renderChart: no DOM element (.echart-container) found');
        return;
      }
      if (positions.value.length === 0) {
        console.log('[PPC] renderChart: 0 positions, skip');
        return;
      }
      console.log('[PPC] renderChart using', domEl.className, 'w=', domEl.offsetWidth, 'h=', domEl.offsetHeight);
      let ec;
      try { ec = await getEcharts(); console.log('[PPC] echarts version:', ec?.version); }
      catch(e) { console.error('[PPC] getEcharts FAILED:', e.message); return; }

      if (chartInstance) { chartInstance.dispose(); chartInstance = null; }

      const chartData = positions.value.map(p => ({
        name: p.symbol, value: p.market_value, itemStyle: { color: p.color },
      }));
      console.log('[PPC] chartData:', JSON.stringify(chartData));

      try {
        chartInstance = ec.init(domEl, null, { renderer: 'canvas' });
        console.log('[PPC] ec.init succeeded, instance=', !!chartInstance);
      } catch(e) { console.error('[PPC] init FAILED:', e.message); return; }

      try {
        chartInstance.setOption({
          backgroundColor: 'transparent',
          tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)', backgroundColor: '#1e2535', borderColor: '#2a3444', textStyle: { color: '#c8d4e8', fontSize: 12 } },
          series: [{
            type: 'pie', radius: ['35%', '65%'], center: ['50%', '50%'], data: chartData,
            label: { show: true, formatter: '{b}\n{d}%', color: '#7a8ba8', fontSize: 11 },
            labelLine: { show: true, lineStyle: { color: '#2a3444' } },
            emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' }, label: { show: true, fontSize: 13, fontWeight: 'bold', color: '#fff' } },
            itemStyle: { borderRadius: 4, borderColor: '#0f1419', borderWidth: 2 },
          }],
        });
        console.log('[PPC] setOption ok, canvas count=', document.querySelectorAll('canvas').length);
      } catch(e) { console.error('[PPC] setOption FAILED:', e.message); }
    }

    function handleResize() {
      chartInstance?.resize();
    }

    function getPnlClass(val) {
      if (val > 0) return 'pnl-pos';
      if (val < 0) return 'pnl-neg';
      return 'pnl-zero';
    }

    watch(() => props.portfolioId, load);

    onMounted(() => {
      load();
      window.addEventListener('resize', handleResize);
    });

    onUnmounted(() => {
      window.removeEventListener('resize', handleResize);
      chartInstance?.dispose();
    });

    return { chartEl, loading, positions, totalMv, totalPnl, load, getPnlClass };
  },
};
</script>

<style scoped>
.position-pie-chart { background: #0f1419; border-radius: 8px; overflow: hidden; display: flex; flex-direction: column; }
.panel-toolbar { display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; background: #1a2030; border-bottom: 1px solid #2a3444; }
.panel-title { color: #c8d4e8; font-size: 13px; font-weight: 600; }
.btn-refresh { background: none; border: 1px solid #2a3444; color: #7a8ba8; width: 24px; height: 24px; border-radius: 4px; cursor: pointer; font-size: 12px; display: flex; align-items: center; justify-content: center; }
.btn-refresh:hover { border-color: #4a6fa5; color: #c8d4e8; }
.chart-placeholder { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 200px; color: #4a5a6a; }
.loading .spinner { font-size: 24px; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { font-size: 12px; margin-top: 8px; }
.empty-icon { font-size: 32px; margin-bottom: 8px; }
.empty-text { font-size: 14px; font-weight: 600; }
.empty-hint { font-size: 12px; margin-top: 4px; color: #3a4a5a; }
.echart-container {
  height: 220px;
  width: 100%;
  min-height: 220px;   /* 强制撑开，防止父容器 flex 压缩为 0 */
  flex-shrink: 0;
  /* ECharts 画布安全区，确保 canvas 可见 */
  position: relative;
  z-index: 1;
}
.pie-legend { padding: 8px 12px; }
.legend-item { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px; color: #7a8ba8; border-bottom: 1px solid #1a2030; }
.legend-item:last-child { border-bottom: none; }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.legend-symbol { color: #7dd3fc; font-weight: 600; min-width: 60px; }
.legend-pct { margin-left: auto; color: #c8d4e8; min-width: 40px; text-align: right; }
.legend-mv { color: #7a8ba8; min-width: 50px; text-align: right; font-size: 11px; }
.legend-pnl { min-width: 50px; text-align: right; font-size: 11px; font-weight: 600; }
.pnl-pos { color: #34d399; }
.pnl-neg { color: #f87171; }
.pnl-zero { color: #4a5a6a; }
.pie-footer { padding: 8px 16px; font-size: 12px; color: #4a5a6a; border-top: 1px solid #1e2535; text-align: right; }
.pie-footer b { color: #c8d4e8; }
</style>
