<template>
  <div class="h-full flex flex-col bg-terminal-bg overflow-hidden">
    <!-- 顶部标题栏 -->
    <div class="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-theme-secondary">
      <div class="flex items-center gap-3">
        <span class="text-lg font-bold text-terminal-accent">📊 宏观经济</span>
        <span class="text-xs text-terminal-dim hidden sm:inline">中国宏观指标监控</span>
      </div>
      <div class="flex items-center gap-3">
        <div class="flex items-center gap-2">
          <span v-if="isPolling" class="text-xs text-success animate-pulse flex items-center gap-1">
            <span class="w-1.5 h-1.5 rounded-full bg-success"></span>
            自动刷新中
          </span>
          <span v-if="lastRefresh" class="text-xs text-terminal-dim">
            上次更新: {{ formatTime(lastRefresh) }}
          </span>
        </div>
        <button 
          class="px-3 py-1.5 rounded-sm text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition disabled:opacity-50"
          @click="refreshNow"
          :disabled="loading"
        >
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <div 
      v-if="errorSummary" 
      class="mx-3 md:mx-4 mt-3 p-3 bg-warning/10 border border-warning/30 rounded-lg"
      role="alert"
      aria-live="polite"
    >
      <div class="flex items-start justify-between gap-3">
        <div class="flex items-start gap-2">
          <span class="text-warning text-lg">⚠️</span>
          <div>
            <p class="text-sm font-medium text-warning">部分数据加载失败</p>
            <p class="text-xs text-terminal-dim mt-1">
              {{ errorSummary.count }} 个数据源加载失败: {{ errorSummary.keys.join(', ') }}
            </p>
          </div>
        </div>
        <button 
          class="px-3 py-1.5 rounded-sm text-xs bg-warning/20 text-warning hover:bg-warning/30 transition shrink-0"
          @click="retryFailed"
          :disabled="loading"
        >
          重试失败项
        </button>
      </div>
    </div>

    <!-- 主内容区域 - 可滚动 -->
    <div class="flex-1 overflow-y-auto">
      <!-- 骨架加载器 -->
      <div 
        v-if="loading && !overview" 
        class="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3 p-3 md:p-4"
        aria-busy="true"
        aria-label="正在加载宏观经济数据"
      >
        <div v-for="i in 8" :key="i" class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 animate-pulse">
          <div class="flex items-center justify-between mb-2">
            <div class="h-3 w-10 bg-terminal-bg/50 rounded"></div>
            <div class="h-2 w-16 bg-terminal-bg/50 rounded"></div>
          </div>
          <div class="h-6 w-20 bg-terminal-bg/50 rounded mt-2"></div>
          <div class="h-2 w-12 bg-terminal-bg/50 rounded mt-2"></div>
        </div>
      </div>
      
      <!-- 核心指标卡片 - 响应式网格 -->
      <div 
        v-else-if="overview" 
        class="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3 p-3 md:p-4"
        :aria-busy="loading ? 'true' : 'false'"
        aria-live="polite"
      >
        <!-- GDP卡片 -->
        <div 
          class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors"
          role="region"
          aria-label="GDP指标卡片"
          tabindex="0"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="国内生产总值" id="gdp-label">GDP</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.gdp?.period }}</span>
          </div>
          <div 
            class="text-xl md:text-2xl font-bold text-terminal-primary"
            aria-labelledby="gdp-label"
            aria-live="polite"
          >
            {{ formatNumber(overview.gdp?.yoy) }}<span class="text-sm ml-0.5">%</span>
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">同比增长</div>
          <div class="mt-2 h-1 bg-terminal-bg/50 rounded-full overflow-hidden">
            <div class="h-full bg-terminal-accent/60 rounded-full" :style="{ width: Math.min(Math.abs(overview.gdp?.yoy || 0) * 10, 100) + '%' }"></div>
          </div>
        </div>

        <!-- CPI卡片 -->
        <div 
          class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors"
          role="region"
          aria-label="CPI指标卡片"
          tabindex="0"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="消费者物价指数" id="cpi-label">CPI</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.cpi?.period }}</span>
          </div>
          <div 
            class="text-xl md:text-2xl font-bold"
            :class="getColorClass(overview.cpi?.yoy)"
            aria-labelledby="cpi-label"
            aria-live="polite"
          >
            {{ formatNumber(overview.cpi?.yoy) }}<span class="text-sm ml-0.5">%</span>
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">同比</div>
          <div class="mt-2 flex items-center gap-1">
            <span class="text-[10px]" :class="getColorClass(overview.cpi?.mom)">
              {{ overview.cpi?.mom >= 0 ? '↑' : '↓' }}{{ Math.abs(overview.cpi?.mom || 0).toFixed(1) }}%
            </span>
            <span class="text-[10px] text-terminal-dim">环比</span>
          </div>
        </div>

        <!-- PPI卡片 -->
        <div 
          class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors"
          role="region"
          aria-label="PPI指标卡片"
          tabindex="0"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="生产者物价指数" id="ppi-label">PPI</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.ppi?.period }}</span>
          </div>
          <div 
            class="text-xl md:text-2xl font-bold"
            :class="getColorClass(overview.ppi?.yoy)"
            aria-labelledby="ppi-label"
            aria-live="polite"
          >
            {{ formatNumber(overview.ppi?.yoy) }}<span class="text-sm ml-0.5">%</span>
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">同比</div>
          <div class="mt-2 h-1 bg-terminal-bg/50 rounded-full overflow-hidden">
            <div class="h-full rounded-full transition-all" 
                 :class="overview.ppi?.yoy >= 0 ? 'bg-bullish/60' : 'bg-bearish/60'"
                 :style="{ width: Math.min(Math.abs(overview.ppi?.yoy || 0) * 10, 100) + '%' }"></div>
          </div>
        </div>

        <!-- PMI卡片 -->
        <div 
          class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors"
          role="region"
          aria-label="PMI指标卡片"
          tabindex="0"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="采购经理指数" id="pmi-label">PMI</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.pmi?.period }}</span>
          </div>
          <div 
            class="text-xl md:text-2xl font-bold"
            :class="getPMIColor(overview.pmi?.manufacturing)"
            aria-labelledby="pmi-label"
            aria-live="polite"
          >
            {{ formatNumber(overview.pmi?.manufacturing) }}
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">制造业</div>
          <div class="mt-2 flex items-center gap-1">
            <span class="text-[10px]" :class="getPMIColor(overview.pmi?.manufacturing)">
              {{ overview.pmi?.manufacturing >= 50 ? '扩张' : '收缩' }}
            </span>
            <span class="text-[10px] text-terminal-dim/50">|</span>
            <span class="text-[10px] text-terminal-dim">非制造 {{ formatNumber(overview.pmi?.non_manufacturing) }}</span>
          </div>
        </div>

        <!-- M2卡片 -->
        <div 
          class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors"
          role="region"
          aria-label="M2指标卡片"
          tabindex="0"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="广义货币供应量" id="m2-label">M2</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.m2?.period }}</span>
          </div>
          <div 
            class="text-xl md:text-2xl font-bold text-terminal-primary"
            aria-labelledby="m2-label"
            aria-live="polite"
          >
            {{ formatNumber(overview.m2?.yoy) }}<span class="text-sm ml-0.5">%</span>
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">同比</div>
          <div class="mt-2 text-[10px] text-terminal-dim">
            {{ formatLargeNumber(overview.m2?.value) }}亿元
          </div>
        </div>

        <!-- 社融卡片 -->
        <div 
          class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors"
          role="region"
          aria-label="社融指标卡片"
          tabindex="0"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="社会融资规模" id="social-label">社融</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.social_financing?.period }}</span>
          </div>
          <div 
            class="text-xl md:text-2xl font-bold text-terminal-primary"
            aria-labelledby="social-label"
            aria-live="polite"
          >
            {{ formatLargeNumber(overview.social_financing?.total) }}
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">亿元</div>
          <div class="mt-2 h-1 bg-terminal-bg/50 rounded-full overflow-hidden">
            <div class="h-full bg-terminal-accent/60 rounded-full" :style="{ width: Math.min((overview.social_financing?.total || 0) / 500, 100) + '%' }"></div>
          </div>
        </div>

        <!-- 工业增加值卡片 -->
        <div 
          class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors"
          role="region"
          aria-label="工业增加值指标卡片"
          tabindex="0"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="工业增加值" id="industrial-label">工业</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.industrial_production?.period }}</span>
          </div>
          <div 
            class="text-xl md:text-2xl font-bold"
            :class="getColorClass(overview.industrial_production?.yoy)"
            aria-labelledby="industrial-label"
            aria-live="polite"
          >
            {{ formatNumber(overview.industrial_production?.yoy) }}<span class="text-sm ml-0.5">%</span>
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">同比</div>
          <div class="mt-2 h-1 bg-terminal-bg/50 rounded-full overflow-hidden">
            <div class="h-full rounded-full transition-all"
                 :class="overview.industrial_production?.yoy >= 0 ? 'bg-bullish/60' : 'bg-bearish/60'"
                 :style="{ width: Math.min(Math.abs(overview.industrial_production?.yoy || 0) * 10, 100) + '%' }"></div>
          </div>
        </div>

        <!-- 失业率卡片 -->
        <div 
          class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 hover:border-terminal-accent/50 transition-colors"
          role="region"
          aria-label="失业率指标卡片"
          tabindex="0"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-terminal-dim cursor-help font-medium" title="城镇调查失业率" id="unemployment-label">失业率</span>
            <span class="text-[10px] text-terminal-dim/70">{{ overview.unemployment?.period }}</span>
          </div>
          <div 
            class="text-xl md:text-2xl font-bold"
            :class="getUnemploymentColor(overview.unemployment?.rate)"
            aria-labelledby="unemployment-label"
            aria-live="polite"
          >
            {{ formatNumber(overview.unemployment?.rate) }}<span class="text-sm ml-0.5">%</span>
          </div>
          <div class="text-[10px] md:text-xs text-terminal-dim mt-1">城镇调查</div>
          <div class="mt-2 flex items-center gap-1">
            <div class="flex-1 h-1 bg-terminal-bg/50 rounded-full overflow-hidden">
              <div class="h-full bg-warning/60 rounded-full" :style="{ width: Math.min((overview.unemployment?.rate || 0) * 10, 100) + '%' }"></div>
            </div>
            <span class="text-[10px] text-terminal-dim">{{ overview.unemployment?.rate >= 5.5 ? '⚠️' : '✓' }}</span>
          </div>
        </div>
      </div>

      <!-- 图表区域 - PC端3列，平板2列，移动端1列 -->
      <div 
        class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 md:gap-4 px-3 md:px-4 pb-3"
        aria-live="polite"
        aria-label="宏观经济图表区域"
      >
        <!-- GDP趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">📈 GDP同比增长率</h3>
            <span class="text-[10px] text-terminal-dim/70">近20季度</span>
          </div>
          <div 
            ref="gdpChart" 
            class="flex-1 w-full h-[250px]"
            role="img"
            aria-label="GDP同比增长率趋势图"
            tabindex="0"
            @keydown.arrow-up="focusPreviousChart"
            @keydown.arrow-down="focusNextChart"
            @keydown.home="focusFirstChart"
            @keydown.end="focusLastChart"
          ></div>
        </div>

        <!-- CPI趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">📊 CPI同比/环比</h3>
            <span class="text-[10px] text-terminal-dim/70">近24月</span>
          </div>
          <div 
            ref="cpiChart" 
            class="flex-1 w-full h-[250px]"
            role="img"
            aria-label="CPI同比环比趋势图"
            tabindex="0"
            @keydown.arrow-up="focusPreviousChart"
            @keydown.arrow-down="focusNextChart"
            @keydown.home="focusFirstChart"
            @keydown.end="focusLastChart"
          ></div>
        </div>

        <!-- PMI趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">📉 PMI制造业/非制造业</h3>
            <span class="text-[10px] text-terminal-dim/70">近24月</span>
          </div>
          <div 
            ref="pmiChart" 
            class="flex-1 w-full h-[250px]"
            role="img"
            aria-label="PMI制造业非制造业趋势图"
            tabindex="0"
            @keydown.arrow-up="focusPreviousChart"
            @keydown.arrow-down="focusNextChart"
            @keydown.home="focusFirstChart"
            @keydown.end="focusLastChart"
          ></div>
        </div>

        <!-- PPI趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">📈 PPI同比</h3>
            <span class="text-[10px] text-terminal-dim/70">近24月</span>
          </div>
          <div 
            ref="ppiChart" 
            class="flex-1 w-full h-[250px]"
            role="img"
            aria-label="PPI同比趋势图"
            tabindex="0"
            @keydown.arrow-up="focusPreviousChart"
            @keydown.arrow-down="focusNextChart"
            @keydown.home="focusFirstChart"
            @keydown.end="focusLastChart"
          ></div>
        </div>

        <!-- M2趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">💰 M2货币供应量同比</h3>
            <span class="text-[10px] text-terminal-dim/70">近24月</span>
          </div>
          <div 
            ref="m2Chart" 
            class="flex-1 w-full h-[250px]"
            role="img"
            aria-label="M2货币供应量同比趋势图"
            tabindex="0"
            @keydown.arrow-up="focusPreviousChart"
            @keydown.arrow-down="focusNextChart"
            @keydown.home="focusFirstChart"
            @keydown.end="focusLastChart"
          ></div>
        </div>

        <!-- 社融趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">🏦 社会融资规模</h3>
            <span class="text-[10px] text-terminal-dim/70">近24月</span>
          </div>
          <div 
            ref="socialFinancingChart" 
            class="flex-1 w-full h-[250px]"
            role="img"
            aria-label="社会融资规模趋势图"
            tabindex="0"
            @keydown.arrow-up="focusPreviousChart"
            @keydown.arrow-down="focusNextChart"
            @keydown.home="focusFirstChart"
            @keydown.end="focusLastChart"
          ></div>
        </div>

        <!-- 工业增加值趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">🏭 工业增加值同比</h3>
            <span class="text-[10px] text-terminal-dim/70">近24月</span>
          </div>
          <div 
            ref="industrialProductionChart" 
            class="flex-1 w-full h-[250px]"
            role="img"
            aria-label="工业增加值同比趋势图"
            tabindex="0"
            @keydown.arrow-up="focusPreviousChart"
            @keydown.arrow-down="focusNextChart"
            @keydown.home="focusFirstChart"
            @keydown.end="focusLastChart"
          ></div>
        </div>

        <!-- 失业率趋势图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4 flex flex-col min-h-[280px] md:min-h-[320px]">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">👥 城镇调查失业率</h3>
            <span class="text-[10px] text-terminal-dim/70">近24月</span>
          </div>
          <div 
            ref="unemploymentChart" 
            class="flex-1 w-full h-[250px]"
            role="img"
            aria-label="城镇调查失业率趋势图"
            tabindex="0"
            @keydown.arrow-up="focusPreviousChart"
            @keydown.arrow-down="focusNextChart"
            @keydown.home="focusFirstChart"
            @keydown.end="focusLastChart"
          ></div>
        </div>
      </div>

      <!-- Hidden data tables for screen readers -->
      <div class="sr-only">
        <!-- GDP data table -->
        <table v-if="gdpData.length > 0" aria-label="GDP数据表格">
          <caption>GDP同比增长率历史数据</caption>
          <thead>
            <tr><th>季度</th><th>同比增长率(%)</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in gdpData" :key="d.quarter">
              <td>{{ d.quarter }}</td>
              <td>{{ formatNumber(d.gdp_yoy) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- CPI data table -->
        <table v-if="cpiData.length > 0" aria-label="CPI数据表格">
          <caption>CPI同比环比历史数据</caption>
          <thead>
            <tr><th>月份</th><th>同比(%)</th><th>环比(%)</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in cpiData" :key="d.month">
              <td>{{ d.month }}</td>
              <td>{{ formatNumber(d.nation_yoy) }}</td>
              <td>{{ formatNumber(d.nation_mom) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- PMI data table -->
        <table v-if="pmiData.length > 0" aria-label="PMI数据表格">
          <caption>PMI制造业非制造业历史数据</caption>
          <thead>
            <tr><th>月份</th><th>制造业指数</th><th>非制造业指数</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in pmiData" :key="d.month">
              <td>{{ d.month }}</td>
              <td>{{ formatNumber(d.manufacturing_index) }}</td>
              <td>{{ formatNumber(d.non_manufacturing_index) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- PPI data table -->
        <table v-if="ppiData.length > 0" aria-label="PPI数据表格">
          <caption>PPI同比历史数据</caption>
          <thead>
            <tr><th>月份</th><th>同比(%)</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in ppiData" :key="d.month">
              <td>{{ d.month }}</td>
              <td>{{ formatNumber(d.yoy) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- M2 data table -->
        <table v-if="m2Data.length > 0" aria-label="M2数据表格">
          <caption>M2货币供应量同比历史数据</caption>
          <thead>
            <tr><th>月份</th><th>同比(%)</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in m2Data" :key="d.month">
              <td>{{ d.month }}</td>
              <td>{{ formatNumber(d.m2_yoy) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- Social Financing data table -->
        <table v-if="socialFinancingData.length > 0" aria-label="社融数据表格">
          <caption>社会融资规模历史数据</caption>
          <thead>
            <tr><th>月份</th><th>增量(亿元)</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in socialFinancingData" :key="d.month">
              <td>{{ d.month }}</td>
              <td>{{ formatLargeNumber(d.total) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- Industrial Production data table -->
        <table v-if="industrialProductionData.length > 0" aria-label="工业增加值数据表格">
          <caption>工业增加值同比历史数据</caption>
          <thead>
            <tr><th>月份</th><th>同比(%)</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in industrialProductionData" :key="d.month">
              <td>{{ d.month }}</td>
              <td>{{ formatNumber(d.yoy) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- Unemployment data table -->
        <table v-if="unemploymentData.length > 0" aria-label="失业率数据表格">
          <caption>城镇调查失业率历史数据</caption>
          <thead>
            <tr><th>月份</th><th>失业率(%)</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in unemploymentData" :key="d.month">
              <td>{{ d.month }}</td>
              <td>{{ formatNumber(d.rate) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 经济日历 -->
      <div class="px-3 md:px-4 pb-4" aria-live="polite" aria-label="经济日历区域">
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-terminal-accent">📅 近期数据发布</h3>
            <span class="text-[10px] text-terminal-dim/70">{{ calendar.length }}项</span>
          </div>
          <div v-if="calendar.length > 0" class="space-y-2">
            <div v-for="(item, index) in calendar" :key="index" 
                 class="flex items-center justify-between py-2 px-3 rounded-md hover:bg-terminal-bg/30 transition-colors"
                 :class="index < calendar.length - 1 ? 'border-b border-theme/10' : ''">
              <div class="flex items-center gap-3">
                <span class="text-[10px] px-2 py-0.5 rounded-full font-medium" 
                      :class="getStatusClass(item.status)">
                  {{ item.status === 'released' ? '已发布' : '待发布' }}
                </span>
                <span class="text-sm text-terminal-primary font-medium">{{ item.name }}</span>
              </div>
              <div class="flex items-center gap-3 md:gap-4">
                <span class="text-[10px] md:text-xs text-terminal-dim">{{ item.date }}</span>
                <span v-if="item.value !== null" class="text-sm font-mono font-bold" :class="getColorClass(item.value)">
                  {{ formatNumber(item.value) }}{{ item.unit }}
                </span>
              </div>
            </div>
          </div>
          <div v-else class="text-center py-8 text-terminal-dim text-sm">
            暂无数据发布计划
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed, onWatcherCleanup } from 'vue'
import { apiFetchValidated } from '../utils/api.js'
import { useGracefulDegradation } from '../composables/useGracefulDegradation.js'
import { useApiError } from '../composables/useApiError.js'
import { useChartManager, safeDispose, safeResize } from '../utils/chartManager.js'
import { useEChartsErrorBoundary } from '../composables/useEChartsErrorBoundary.js'
import { useSmartPolling } from '../composables/useSmartPolling.js'
import { getECharts, initChart } from '../utils/lazyEcharts.js'
import {
  MacroOverviewSchema,
  MacroCalendarResponseSchema,
  GdpResponseSchema,
  CpiResponseSchema,
  PpiResponseSchema,
  PmiResponseSchema,
  M2ResponseSchema,
  SocialFinancingResponseSchema,
  IndustrialProductionResponseSchema,
  UnemploymentResponseSchema,
} from '../schemas/macro.js'

const { handleError, getErrorCategory } = useApiError({ showToast: true })
const { safeSetOption, validateChartData, showChartEmptyState, showChartErrorState } = useEChartsErrorBoundary()

const loading = ref(false)
const overview = ref(null)
const calendar = ref([])
const lastUpdate = ref(null)
const errorSummary = ref(null)

// Chart data for screen reader tables
const gdpData = ref([])
const cpiData = ref([])
const pmiData = ref([])
const ppiData = ref([])
const m2Data = ref([])
const socialFinancingData = ref([])
const industrialProductionData = ref([])
const unemploymentData = ref([])

const {
  requestStates,
  errors,
  fetchAll,
  getAnyLoading,
  getFailedKeys,
  getErrorSummary,
  retryAll,
} = useGracefulDegradation({
  onPartialSuccess: ({ successCount, failCount, total, errors }) => {
    const failedContexts = Object.values(errors).map(e => e.context).filter(Boolean)
    const message = failCount > 0 
      ? `${failCount}/${total} 个数据源加载失败: ${failedContexts.join(', ')}`
      : `${successCount}/${total} 个数据源加载成功`
    handleError(new Error(message), { context: '宏观数据', silent: false })
  },
  onAllFailed: (errors) => {
    const failedContexts = Object.values(errors).map(e => e.context).filter(Boolean)
    handleError(new Error(`所有 ${failedContexts.length} 个数据源加载失败`), { context: '宏观数据', silent: false })
  },
})

const gdpChart = ref(null)
const cpiChart = ref(null)
const pmiChart = ref(null)
const ppiChart = ref(null)
const m2Chart = ref(null)
const socialFinancingChart = ref(null)
const industrialProductionChart = ref(null)
const unemploymentChart = ref(null)

// Chart refs array for keyboard navigation
const chartRefs = [
  gdpChart,
  cpiChart,
  pmiChart,
  ppiChart,
  m2Chart,
  socialFinancingChart,
  industrialProductionChart,
  unemploymentChart,
]

// Keyboard navigation functions for charts
function focusPreviousChart(event) {
  event.preventDefault()
  const currentIndex = chartRefs.findIndex(ref => ref.value === event.target)
  if (currentIndex > 0) {
    chartRefs[currentIndex - 1].value?.focus()
  }
}

function focusNextChart(event) {
  event.preventDefault()
  const currentIndex = chartRefs.findIndex(ref => ref.value === event.target)
  if (currentIndex < chartRefs.length - 1) {
    chartRefs[currentIndex + 1].value?.focus()
  }
}

function focusFirstChart(event) {
  event.preventDefault()
  gdpChart.value?.focus()
}

function focusLastChart(event) {
  event.preventDefault()
  unemploymentChart.value?.focus()
}

const chartManager = useChartManager()

let gdpChartInstance = null
let cpiChartInstance = null
let pmiChartInstance = null
let ppiChartInstance = null
let m2ChartInstance = null
let socialFinancingChartInstance = null
let industrialProductionChartInstance = null
let unemploymentChartInstance = null

let fetchRequestId = 0
let abortController = null

async function fetchAllData() {
  // Cancel previous request
  if (abortController) {
    abortController.abort()
  }
  
  abortController = new AbortController()
  const signal = abortController.signal
  
  const currentRequestId = ++fetchRequestId
  loading.value = true
  errorSummary.value = null

  const requests = [
    { key: 'overview', fetchFn: () => apiFetchValidated('/api/v1/macro/overview', MacroOverviewSchema, { timeoutMs: 30000, signal }), context: { context: '宏观概览' } },
    { key: 'calendar', fetchFn: () => apiFetchValidated('/api/v1/macro/calendar', MacroCalendarResponseSchema, { timeoutMs: 30000, signal }), context: { context: '经济日历' } },
    { key: 'gdp', fetchFn: () => apiFetchValidated('/api/v1/macro/gdp?limit=20', GdpResponseSchema, { timeoutMs: 30000, signal }), context: { context: 'GDP数据' } },
    { key: 'cpi', fetchFn: () => apiFetchValidated('/api/v1/macro/cpi?limit=24', CpiResponseSchema, { timeoutMs: 30000, signal }), context: { context: 'CPI数据' } },
    { key: 'pmi', fetchFn: () => apiFetchValidated('/api/v1/macro/pmi?limit=24', PmiResponseSchema, { timeoutMs: 30000, signal }), context: { context: 'PMI数据' } },
    { key: 'ppi', fetchFn: () => apiFetchValidated('/api/v1/macro/ppi?limit=24', PpiResponseSchema, { timeoutMs: 30000, signal }), context: { context: 'PPI数据' } },
    { key: 'm2', fetchFn: () => apiFetchValidated('/api/v1/macro/m2?limit=24', M2ResponseSchema, { timeoutMs: 30000, signal }), context: { context: 'M2数据' } },
    { key: 'socialFinancing', fetchFn: () => apiFetchValidated('/api/v1/macro/social_financing?limit=24', SocialFinancingResponseSchema, { timeoutMs: 30000, signal }), context: { context: '社融数据' } },
    { key: 'industrial', fetchFn: () => apiFetchValidated('/api/v1/macro/industrial_production?limit=24', IndustrialProductionResponseSchema, { timeoutMs: 30000, signal }), context: { context: '工业增加值数据' } },
    { key: 'unemployment', fetchFn: () => apiFetchValidated('/api/v1/macro/unemployment?limit=24', UnemploymentResponseSchema, { timeoutMs: 30000, signal }), context: { context: '失业率数据' } },
  ]

  try {
    const { results, successCount, failCount, allFailed } = await fetchAll(requests)

    if (currentRequestId !== fetchRequestId) return

  const [
    overviewRes,
    calendarRes,
    gdpRes,
    cpiRes,
    pmiRes,
    ppiRes,
    m2Res,
    socialRes,
    industrialRes,
    unemploymentRes,
  ] = results.map(r => r.data)

  if (overviewRes?.overview) {
    overview.value = overviewRes.overview
    lastUpdate.value = overviewRes.last_update
  }
  if (calendarRes?.calendar) calendar.value = calendarRes.calendar
  if (gdpRes?.data) {
    gdpData.value = gdpRes.data
    drawGDPChart(gdpRes.data)
  }
  if (cpiRes?.data) {
    cpiData.value = cpiRes.data
    drawCPIChart(cpiRes.data)
  }
  if (pmiRes?.data) {
    pmiData.value = pmiRes.data
    drawPMIChart(pmiRes.data)
  }
  if (ppiRes?.data) {
    ppiData.value = ppiRes.data
    drawPPIChart(ppiRes.data)
  }
  if (m2Res?.data) {
    m2Data.value = m2Res.data
    drawM2Chart(m2Res.data)
  }
  if (socialRes?.data) {
    socialFinancingData.value = socialRes.data
    drawSocialFinancingChart(socialRes.data)
  }
  if (industrialRes?.data) {
    industrialProductionData.value = industrialRes.data
    drawIndustrialProductionChart(industrialRes.data)
  }
  if (unemploymentRes?.data) {
    unemploymentData.value = unemploymentRes.data
    drawUnemploymentChart(unemploymentRes.data)
  }

  if (failCount > 0) {
    errorSummary.value = getErrorSummary()
  }

  loading.value = false
  } catch (e) {
    // Handle abort errors gracefully - don't show error for intentional abort
    if (e.name === 'AbortError') {
      console.log('[Macro] Request aborted')
      return
    }
    // Re-throw other errors to be handled by useGracefulDegradation
    throw e
  } finally {
    loading.value = false
  }
}

const {
  isPolling,
  lastRefresh,
  nextRefresh,
  errorCount: pollingErrorCount,
  start: startPolling,
  stop: stopPolling,
  refreshNow,
} = useSmartPolling(fetchAllData, {
  interval: 5 * 60 * 1000,
  immediate: false,
  pauseWhenHidden: true,
})

async function refreshAll() {
  refreshNow()
}

async function retryFailed() {
  const failedKeys = getFailedKeys()
  if (failedKeys.length === 0) return

  // Cancel previous request
  if (abortController) {
    abortController.abort()
  }
  
  abortController = new AbortController()
  const signal = abortController.signal

  loading.value = true
  errorSummary.value = null

  const retryRequests = failedKeys.map(key => {
    const requestMap = {
      overview: { fetchFn: () => apiFetchValidated('/api/v1/macro/overview', MacroOverviewSchema, { timeoutMs: 30000, signal }), context: { context: '宏观概览' } },
      calendar: { fetchFn: () => apiFetchValidated('/api/v1/macro/calendar', MacroCalendarResponseSchema, { timeoutMs: 30000, signal }), context: { context: '经济日历' } },
      gdp: { fetchFn: () => apiFetchValidated('/api/v1/macro/gdp?limit=20', GdpResponseSchema, { timeoutMs: 30000, signal }), context: { context: 'GDP数据' } },
      cpi: { fetchFn: () => apiFetchValidated('/api/v1/macro/cpi?limit=24', CpiResponseSchema, { timeoutMs: 30000, signal }), context: { context: 'CPI数据' } },
      pmi: { fetchFn: () => apiFetchValidated('/api/v1/macro/pmi?limit=24', PmiResponseSchema, { timeoutMs: 30000, signal }), context: { context: 'PMI数据' } },
      ppi: { fetchFn: () => apiFetchValidated('/api/v1/macro/ppi?limit=24', PpiResponseSchema, { timeoutMs: 30000, signal }), context: { context: 'PPI数据' } },
      m2: { fetchFn: () => apiFetchValidated('/api/v1/macro/m2?limit=24', M2ResponseSchema, { timeoutMs: 30000, signal }), context: { context: 'M2数据' } },
      socialFinancing: { fetchFn: () => apiFetchValidated('/api/v1/macro/social_financing?limit=24', SocialFinancingResponseSchema, { timeoutMs: 30000, signal }), context: { context: '社融数据' } },
      industrial: { fetchFn: () => apiFetchValidated('/api/v1/macro/industrial_production?limit=24', IndustrialProductionResponseSchema, { timeoutMs: 30000, signal }), context: { context: '工业增加值数据' } },
      unemployment: { fetchFn: () => apiFetchValidated('/api/v1/macro/unemployment?limit=24', UnemploymentResponseSchema, { timeoutMs: 30000, signal }), context: { context: '失业率数据' } },
    }
    return { key, ...requestMap[key] }
  })

  try {
    const { results, failCount } = await fetchAll(retryRequests)

    results.forEach((result, index) => {
      if (result.success && result.data) {
        const key = retryRequests[index].key
        if (key === 'overview' && result.data.overview) {
          overview.value = result.data.overview
          lastUpdate.value = result.data.last_update
        } else if (key === 'calendar' && result.data.calendar) {
          calendar.value = result.data.calendar
        } else if (result.data?.data) {
          const drawFunctions = {
            gdp: drawGDPChart,
            cpi: drawCPIChart,
            pmi: drawPMIChart,
            ppi: drawPPIChart,
            m2: drawM2Chart,
            socialFinancing: drawSocialFinancingChart,
            industrial: drawIndustrialProductionChart,
            unemployment: drawUnemploymentChart,
          }
          if (drawFunctions[key]) {
            drawFunctions[key](result.data.data)
          }
        }
      }
    })

    errorSummary.value = failCount > 0 ? getErrorSummary() : null
  } catch (e) {
    // Handle abort errors gracefully - don't show error for intentional abort
    if (e.name === 'AbortError') {
      console.log('[Macro] Retry request aborted')
      return
    }
    // Re-throw other errors
    throw e
  } finally {
    loading.value = false
  }
}

function getChartColors() {
  return {
    primary: getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#0F52BA',
    text: getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E',
    up: getComputedStyle(document.documentElement).getPropertyValue('--color-up').trim() || '#FF6B6B',
    down: getComputedStyle(document.documentElement).getPropertyValue('--color-down').trim() || '#51CF66',
    warning: getComputedStyle(document.documentElement).getPropertyValue('--color-warning').trim() || '#FF7D00',
    success: getComputedStyle(document.documentElement).getPropertyValue('--color-success').trim() || '#51CF66',
  }
}

function drawGDPChart(data) {
  if (!gdpChartInstance || !gdpChart.value) return

  const validation = validateChartData(data, ['quarter', 'gdp_yoy'])
  if (!validation.valid) {
    showChartEmptyState(gdpChart.value, '暂无GDP数据', () => fetchAllData())
    return
  }

  const colors = getChartColors()
  const quarters = data.map(d => d.quarter)
  const yoyData = data.map(d => d.gdp_yoy)

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: quarters,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: colors.text, fontSize: 10, formatter: '{value}%' },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [{
      name: 'GDP同比',
      type: 'line',
      data: yoyData,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { color: colors.primary, width: 3 },
      itemStyle: { color: colors.primary, borderWidth: 2 },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: colors.primary + '60' },
            { offset: 1, color: colors.primary + '10' }
          ]
        }
      }
    }]
  }

  if (!safeSetOption(gdpChartInstance, option, 'gdpChart')) {
    showChartErrorState(gdpChart.value, '图表渲染失败', () => drawGDPChart(data))
  }
}

function drawCPIChart(data) {
  if (!cpiChartInstance || !cpiChart.value) return

  const validation = validateChartData(data, ['month', 'nation_yoy'])
  if (!validation.valid) {
    showChartEmptyState(cpiChart.value, '暂无CPI数据', () => fetchAllData())
    return
  }

  const colors = getChartColors()
  const months = data.map(d => d.month)
  const yoyData = data.map(d => d.nation_yoy)
  const momData = data.map(d => d.nation_mom)

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    legend: {
      data: ['同比', '环比'],
      textStyle: { color: colors.text, fontSize: 11 },
      top: 0,
      right: 0
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: colors.text, fontSize: 10, formatter: '{value}%' },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [
      {
        name: '同比',
        type: 'line',
        data: yoyData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: colors.up, width: 2 },
        itemStyle: { color: colors.up }
      },
      {
        name: '环比',
        type: 'line',
        data: momData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: colors.down, width: 2, type: 'dashed' },
        itemStyle: { color: colors.down }
      }
    ]
  }

  if (!safeSetOption(cpiChartInstance, option, 'cpiChart')) {
    showChartErrorState(cpiChart.value, '图表渲染失败', () => drawCPIChart(data))
  }
}

function drawPMIChart(data) {
  if (!pmiChartInstance || !pmiChart.value) return

  const validation = validateChartData(data, ['month', 'manufacturing_index'])
  if (!validation.valid) {
    showChartEmptyState(pmiChart.value, '暂无PMI数据', () => fetchAllData())
    return
  }

  const colors = getChartColors()
  const months = data.map(d => d.month)
  const manufacturingData = data.map(d => d.manufacturing_index)
  const nonManufacturingData = data.map(d => d.non_manufacturing_index)

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    legend: {
      data: ['制造业', '非制造业'],
      textStyle: { color: colors.text, fontSize: 11 },
      top: 0,
      right: 0
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: {
      type: 'value',
      min: 45,
      max: 60,
      axisLabel: { color: colors.text, fontSize: 10 },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [
      {
        name: '制造业',
        type: 'line',
        data: manufacturingData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: colors.primary, width: 2 },
        itemStyle: { color: colors.primary },
        markLine: {
          data: [{ yAxis: 50, lineStyle: { color: colors.warning, type: 'dashed', width: 2 } }],
          label: { formatter: '荣枯线', color: colors.warning, fontSize: 10 }
        }
      },
      {
        name: '非制造业',
        type: 'line',
        data: nonManufacturingData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: colors.success, width: 2 },
        itemStyle: { color: colors.success }
      }
    ]
  }

  if (!safeSetOption(pmiChartInstance, option, 'pmiChart')) {
    showChartErrorState(pmiChart.value, '图表渲染失败', () => drawPMIChart(data))
  }
}

function drawPPIChart(data) {
  if (!ppiChartInstance || !ppiChart.value) return

  const validation = validateChartData(data, ['month', 'yoy'])
  if (!validation.valid) {
    showChartEmptyState(ppiChart.value, '暂无PPI数据', () => fetchAllData())
    return
  }

  const colors = getChartColors()
  const months = data.map(d => d.month)
  const yoyData = data.map(d => d.yoy)

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: colors.text, fontSize: 10, formatter: '{value}%' },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [{
      name: 'PPI同比',
      type: 'line',
      data: yoyData,
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { color: colors.up, width: 2 },
      itemStyle: { color: colors.up },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: colors.up + '40' },
            { offset: 1, color: colors.up + '10' }
          ]
        }
      }
    }]
  }

  if (!safeSetOption(ppiChartInstance, option, 'ppiChart')) {
    showChartErrorState(ppiChart.value, '图表渲染失败', () => drawPPIChart(data))
  }
}

function drawM2Chart(data) {
  if (!m2ChartInstance || !m2Chart.value) return

  const validation = validateChartData(data, ['month', 'm2_yoy'])
  if (!validation.valid) {
    showChartEmptyState(m2Chart.value, '暂无M2数据', () => fetchAllData())
    return
  }

  const colors = getChartColors()
  const months = data.map(d => d.month)
  const yoyData = data.map(d => d.m2_yoy)

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: colors.text, fontSize: 10, formatter: '{value}%' },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [{
      name: 'M2同比',
      type: 'line',
      data: yoyData,
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { color: colors.primary, width: 2 },
      itemStyle: { color: colors.primary },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: colors.primary + '40' },
            { offset: 1, color: colors.primary + '10' }
          ]
        }
      }
    }]
  }

  if (!safeSetOption(m2ChartInstance, option, 'm2Chart')) {
    showChartErrorState(m2Chart.value, '图表渲染失败', () => drawM2Chart(data))
  }
}

function drawSocialFinancingChart(data) {
  if (!socialFinancingChartInstance || !socialFinancingChart.value) return

  const validation = validateChartData(data, ['month', 'total'])
  if (!validation.valid) {
    showChartEmptyState(socialFinancingChart.value, '暂无社融数据', () => fetchAllData())
    return
  }

  const colors = getChartColors()
  const months = data.map(d => d.month)
  const totalData = data.map(d => d.total)

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: colors.text, fontSize: 10 },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [{
      name: '社融增量',
      type: 'bar',
      data: totalData,
      itemStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: colors.up },
            { offset: 1, color: colors.up + '60' }
          ]
        },
        borderRadius: [4, 4, 0, 0]
      },
      barMaxWidth: 30
    }]
  }

  if (!safeSetOption(socialFinancingChartInstance, option, 'socialFinancingChart')) {
    showChartErrorState(socialFinancingChart.value, '图表渲染失败', () => drawSocialFinancingChart(data))
  }
}

function drawIndustrialProductionChart(data) {
  if (!industrialProductionChartInstance || !industrialProductionChart.value) return

  const validation = validateChartData(data, ['month', 'yoy'])
  if (!validation.valid) {
    showChartEmptyState(industrialProductionChart.value, '暂无工业增加值数据', () => fetchAllData())
    return
  }

  const colors = getChartColors()
  const months = data.map(d => d.month)
  const yoyData = data.map(d => d.yoy)

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: colors.text, fontSize: 10, formatter: '{value}%' },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [{
      name: '工业增加值同比',
      type: 'line',
      data: yoyData,
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { color: colors.success, width: 2 },
      itemStyle: { color: colors.success },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: colors.success + '40' },
            { offset: 1, color: colors.success + '10' }
          ]
        }
      }
    }]
  }

  if (!safeSetOption(industrialProductionChartInstance, option, 'industrialProductionChart')) {
    showChartErrorState(industrialProductionChart.value, '图表渲染失败', () => drawIndustrialProductionChart(data))
  }
}

function drawUnemploymentChart(data) {
  if (!unemploymentChartInstance || !unemploymentChart.value) return

  const validation = validateChartData(data, ['month', 'rate'])
  if (!validation.valid) {
    showChartEmptyState(unemploymentChart.value, '暂无失业率数据', () => fetchAllData())
    return
  }

  const colors = getChartColors()
  const months = data.map(d => d.month)
  const rateData = data.map(d => d.rate)

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: colors.text, fontSize: 10, formatter: '{value}%' },
      axisLine: { lineStyle: { color: colors.text + '40' } },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [{
      name: '失业率',
      type: 'line',
      data: rateData,
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { color: colors.warning, width: 2 },
      itemStyle: { color: colors.warning },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: colors.warning + '40' },
            { offset: 1, color: colors.warning + '10' }
          ]
        }
      },
      markLine: {
        data: [{ yAxis: 5.5, lineStyle: { color: colors.up, type: 'dashed', width: 2 } }],
        label: { formatter: '警戒线', color: colors.up, fontSize: 10 }
      }
    }]
  }

  if (!safeSetOption(unemploymentChartInstance, option, 'unemploymentChart')) {
    showChartErrorState(unemploymentChart.value, '图表渲染失败', () => drawUnemploymentChart(data))
  }
}

function formatNumber(val) {
  if (val === null || val === undefined) return '--'
  return Number(val).toFixed(2)
}

function formatLargeNumber(val) {
  if (val === null || val === undefined) return '--'
  if (val >= 10000) {
    return (val / 10000).toFixed(2) + '万'
  }
  return Number(val).toFixed(2)
}

function formatTime(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function getColorClass(val) {
  if (val === null || val === undefined) return 'text-terminal-dim'
  return val >= 0 ? 'text-bullish' : 'text-bearish'
}

function getPMIColor(val) {
  if (val === null || val === undefined) return 'text-terminal-dim'
  return val >= 50 ? 'text-bullish' : 'text-bearish'
}

function getUnemploymentColor(val) {
  if (val === null || val === undefined) return 'text-terminal-dim'
  return val >= 5.5 ? 'text-bearish' : 'text-bullish'
}

function getStatusClass(status) {
  return status === 'released' 
    ? 'bg-success/20 text-success' 
    : 'bg-warning/20 text-warning'
}

let resizeTimer = null
function handleResize() {
  clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    chartManager.resizeAll()
  }, 150)
}

onMounted(async () => {
  await nextTick()

  // Preload ECharts before initializing charts
  const echarts = await getECharts()

  const chartConfigs = [
    { ref: gdpChart.value, id: 'gdpChart', setter: (v) => gdpChartInstance = v },
    { ref: cpiChart.value, id: 'cpiChart', setter: (v) => cpiChartInstance = v },
    { ref: pmiChart.value, id: 'pmiChart', setter: (v) => pmiChartInstance = v },
    { ref: ppiChart.value, id: 'ppiChart', setter: (v) => ppiChartInstance = v },
    { ref: m2Chart.value, id: 'm2Chart', setter: (v) => m2ChartInstance = v },
    { ref: socialFinancingChart.value, id: 'socialFinancingChart', setter: (v) => socialFinancingChartInstance = v },
    { ref: industrialProductionChart.value, id: 'industrialProductionChart', setter: (v) => industrialProductionChartInstance = v },
    { ref: unemploymentChart.value, id: 'unemploymentChart', setter: (v) => unemploymentChartInstance = v },
  ]

  chartConfigs.forEach(({ ref, id, setter }) => {
    if (ref) {
      try {
        const instance = echarts.init(ref)
        setter(instance)
        chartManager.register(id, instance, ref)
      } catch (e) {
        console.warn(`[MacroDashboard] Failed to init ${id} chart:`, e.message)
      }
    }
  })

  startPolling()

  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  clearTimeout(resizeTimer)
  stopPolling()
  window.removeEventListener('resize', handleResize)

  // Abort any pending requests
  if (abortController) {
    abortController.abort()
    abortController = null
  }

  chartManager.disposeAll()

  gdpChartInstance = null
  cpiChartInstance = null
  pmiChartInstance = null
  ppiChartInstance = null
  m2ChartInstance = null
  socialFinancingChartInstance = null
  industrialProductionChartInstance = null
  unemploymentChartInstance = null
})

// Abort requests on watcher cleanup (handles async watcher cancellation)
onWatcherCleanup(() => {
  if (abortController) {
    abortController.abort()
  }
})
</script>

<style scoped>
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

.bg-terminal-panel {
  background: var(--bg-secondary, #1a1f2e);
}

.text-terminal-accent {
  color: var(--color-primary, #0F52BA);
}

.text-terminal-primary {
  color: var(--text-primary, #E5E7EB);
}

.text-terminal-dim {
  color: var(--text-secondary, #8B949E);
}

.text-bullish {
  color: var(--color-up, #FF6B6B);
}

.text-bearish {
  color: var(--color-down, #51CF66);
}

.text-success {
  color: var(--color-success, #51CF66);
}

.text-warning {
  color: var(--color-warning, #FF7D00);
}

.border-theme-secondary {
  border-color: var(--border-color, #2d3748);
}

.bg-terminal-bg {
  background: var(--bg-primary, #0f1419);
}

@media (max-width: 768px) {
  .text-xl {
    font-size: 1.25rem;
  }
  
  .text-2xl {
    font-size: 1.5rem;
  }
}
</style>
