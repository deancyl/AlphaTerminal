<template>
  <div class="h-full flex flex-col bg-terminal-bg">
    <!-- 顶部证券代码栏 -->
    <div class="flex items-center gap-3 px-4 py-2 border-b border-theme-secondary bg-terminal-panel">
      <div class="flex items-center gap-2">
        <span class="text-lg font-bold text-terminal-accent">F9</span>
        <span class="text-xs text-terminal-dim">深度资料</span>
      </div>
      
      <!-- 代码输入框 -->
      <div class="flex items-center gap-2 flex-1 max-w-md">
        <input
          v-model="inputSymbol"
          type="text"
          placeholder="输入股票代码/拼音/名称"
          class="flex-1 px-3 py-1.5 rounded bg-terminal-bg border border-theme-secondary text-sm text-terminal-primary placeholder-terminal-dim focus:border-terminal-accent focus:outline-none"
          @keyup.enter="handleSearch"
        />
        <button
          class="px-3 py-1.5 rounded bg-terminal-accent/20 text-terminal-accent text-sm hover:bg-terminal-accent/30 transition"
          @click="handleSearch"
        >
          查询
        </button>
      </div>
      
      <!-- 当前股票信息 -->
      <div v-if="stockInfo" class="flex items-center gap-3 text-sm">
        <span class="font-bold text-terminal-primary">{{ stockInfo.name }}</span>
        <span class="text-terminal-dim">{{ stockInfo.symbol }}</span>
        <span :class="priceClass">{{ stockInfo.price }}</span>
        <span :class="changeClass">{{ stockInfo.change }}%</span>
      </div>
    </div>
    
    <!-- 主体区域：左侧导航 + 右侧内容 -->
    <div class="flex-1 flex min-h-0">
      <!-- 左侧导航树 -->
      <div class="w-44 border-r border-theme-secondary bg-terminal-panel overflow-y-auto">
        <div class="py-2">
          <div
            v-for="item in menuItems"
            :key="item.id"
            class="px-3 py-2 text-sm cursor-pointer transition flex items-center gap-2"
            :class="activeTab === item.id ? 'bg-terminal-accent/20 text-terminal-accent border-l-2 border-terminal-accent' : 'text-terminal-secondary hover:bg-theme-hover'"
            @click="activeTab = item.id"
          >
            <span>{{ item.icon }}</span>
            <span>{{ item.name }}</span>
          </div>
        </div>
      </div>
      
      <!-- 右侧内容区 -->
      <div class="flex-1 overflow-y-auto p-4">
        <!-- 公司概况 -->
        <div v-if="activeTab === 'overview'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">公司概况</h2>
          
          <div v-if="loading" class="text-center py-8 text-terminal-dim">
            加载中...
          </div>
          
          <div v-else-if="!stockInfo" class="text-center py-8 text-terminal-dim">
            请输入股票代码查询
          </div>
          
          <div v-else class="space-y-4">
            <!-- 基本信息卡片 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">基本信息</h3>
              <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                  <div class="text-xs text-terminal-dim">股票名称</div>
                  <div class="text-sm text-terminal-primary">{{ stockInfo.name || '--' }}</div>
                </div>
                <div>
                  <div class="text-xs text-terminal-dim">股票代码</div>
                  <div class="text-sm text-terminal-primary">{{ stockInfo.symbol || '--' }}</div>
                </div>
                <div>
                  <div class="text-xs text-terminal-dim">所属行业</div>
                  <div class="text-sm text-terminal-primary">{{ stockInfo.industry || '--' }}</div>
                </div>
                <div>
                  <div class="text-xs text-terminal-dim">上市时间</div>
                  <div class="text-sm text-terminal-primary">{{ stockInfo.listDate || '--' }}</div>
                </div>
                <div>
                  <div class="text-xs text-terminal-dim">总股本</div>
                  <div class="text-sm text-terminal-primary">{{ formatNumber(stockInfo.totalShares) }}</div>
                </div>
                <div>
                  <div class="text-xs text-terminal-dim">流通股本</div>
                  <div class="text-sm text-terminal-primary">{{ formatNumber(stockInfo.floatShares) }}</div>
                </div>
                <div>
                  <div class="text-xs text-terminal-dim">总市值</div>
                  <div class="text-sm text-terminal-primary">{{ formatMoney(stockInfo.totalMarketCap) }}</div>
                </div>
                <div>
                  <div class="text-xs text-terminal-dim">流通市值</div>
                  <div class="text-sm text-terminal-primary">{{ formatMoney(stockInfo.floatMarketCap) }}</div>
                </div>
              </div>
            </div>
            
            <!-- 主营业务 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">主营业务</h3>
              <p class="text-sm text-terminal-secondary leading-relaxed">
                {{ stockInfo.business || '暂无数据' }}
              </p>
            </div>
          </div>
        </div>
        
        <!-- 财务摘要 -->
        <div v-else-if="activeTab === 'finance'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">财务摘要</h2>

          <LoadingSpinner v-if="financialLoading" text="加载财务数据..." />

          <ErrorDisplay
            v-else-if="financialError"
            :error="financialError"
            :retry="fetchFinancialData"
          />

          <div v-else-if="financialData && financialData.latest" class="space-y-4">
            <!-- 关键指标卡片 -->
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <InfoCard
                title="ROE (净资产收益率)"
                :value="financialData.latest['净资产收益率(%)']"
                unit="%"
                format="number"
              />
              <InfoCard
                title="EPS (每股收益)"
                :value="financialData.latest['摊薄每股收益(元)']"
                unit="元"
                format="number"
              />
              <InfoCard
                title="营收增长率"
                :value="financialData.latest['主营业务收入增长率(%)']"
                unit="%"
                format="number"
              />
              <InfoCard
                title="净利润增长率"
                :value="financialData.latest['净利润增长率(%)']"
                unit="%"
                format="number"
              />
            </div>

            <!-- 趋势图表 -->
            <div v-if="financialData.trend && financialData.trend.length > 0" class="space-y-3">
              <h3 class="text-sm font-bold text-terminal-primary">关键指标趋势（近8个季度）</h3>
              <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3">
                  <TrendChart
                    :data="getTrendChartData('摊薄每股收益(元)')"
                    title="每股收益 (EPS)"
                    type="line"
                  />
                </div>
                <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3">
                  <TrendChart
                    :data="getTrendChartData('净资产收益率(%)')"
                    title="ROE (%)"
                    type="line"
                  />
                </div>
                <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3">
                  <TrendChart
                    :data="getTrendChartData('主营业务收入增长率(%)')"
                    title="营收增长率 (%)"
                    type="bar"
                  />
                </div>
                <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3">
                  <TrendChart
                    :data="getTrendChartData('净利润增长率(%)')"
                    title="净利润增长率 (%)"
                    type="bar"
                  />
                </div>
              </div>
            </div>

            <!-- 完整指标表格 -->
            <div>
              <h3 class="text-sm font-bold text-terminal-primary mb-3">完整财务指标</h3>
              <DataTable
                :columns="tableColumns"
                :data="financialData.indicators"
              />
            </div>
          </div>

          <div v-else class="text-center py-8 text-terminal-dim">
            请输入股票代码查询财务数据
          </div>
        </div>
        
        <!-- 盈利预测 -->
        <div v-else-if="activeTab === 'forecast'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">盈利预测</h2>
          
          <div v-if="forecastLoading" class="text-center py-8 text-terminal-dim">
            加载中...
          </div>
          
          <div v-else-if="forecastError" class="text-center py-8 text-red-400">
            {{ forecastError }}
          </div>
          
          <div v-else-if="!forecastData" class="text-center py-8 text-terminal-dim">
            请先查询股票代码
          </div>
          
          <div v-else class="space-y-4">
            <!-- EPS预测表 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">EPS预测（每股收益）</h3>
              <div v-if="forecastData.eps_forecast && forecastData.eps_forecast.length > 0" class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead>
                    <tr class="border-b border-theme-secondary">
                      <th class="text-left py-2 px-3 text-terminal-dim font-normal">年份</th>
                      <th class="text-right py-2 px-3 text-terminal-dim font-normal">最小值</th>
                      <th class="text-right py-2 px-3 text-terminal-dim font-normal">平均值</th>
                      <th class="text-right py-2 px-3 text-terminal-dim font-normal">最大值</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(item, idx) in forecastData.eps_forecast" :key="idx" class="border-b border-theme-secondary/50 hover:bg-theme-hover">
                      <td class="py-2 px-3 text-terminal-primary">{{ item['年度'] || item['年份'] || '--' }}</td>
                      <td class="py-2 px-3 text-right text-terminal-secondary">{{ item['最小值'] || item['预测最小值'] || '--' }}</td>
                      <td class="py-2 px-3 text-right text-terminal-accent font-medium">{{ item['均值'] || item['预测均值'] || '--' }}</td>
                      <td class="py-2 px-3 text-right text-terminal-secondary">{{ item['最大值'] || item['预测最大值'] || '--' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-else class="text-center py-4 text-terminal-dim">暂无EPS预测数据</div>
            </div>
            
            <!-- 机构预测详表 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">机构预测详表</h3>
              <div v-if="forecastData.institutions && forecastData.institutions.length > 0" class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead>
                    <tr class="border-b border-theme-secondary">
                      <th class="text-left py-2 px-3 text-terminal-dim font-normal">机构名称</th>
                      <th class="text-left py-2 px-3 text-terminal-dim font-normal">研究员</th>
                      <th class="text-right py-2 px-3 text-terminal-dim font-normal">报告日期</th>
                      <th class="text-right py-2 px-3 text-terminal-dim font-normal">2026EPS</th>
                      <th class="text-right py-2 px-3 text-terminal-dim font-normal">2027EPS</th>
                      <th class="text-right py-2 px-3 text-terminal-dim font-normal">2028EPS</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(item, idx) in forecastData.institutions.slice(0, 20)" :key="idx" class="border-b border-theme-secondary/50 hover:bg-theme-hover">
                      <td class="py-2 px-3 text-terminal-primary">{{ item['机构名称'] || '--' }}</td>
                      <td class="py-2 px-3 text-terminal-secondary">{{ item['研究员'] || '--' }}</td>
                      <td class="py-2 px-3 text-right text-terminal-secondary">{{ item['报告日期'] || '--' }}</td>
                      <td class="py-2 px-3 text-right text-terminal-accent font-medium">{{ item['预测年报每股收益2026预测'] || '--' }}</td>
                      <td class="py-2 px-3 text-right text-terminal-secondary">{{ item['预测年报每股收益2027预测'] || '--' }}</td>
                      <td class="py-2 px-3 text-right text-terminal-secondary">{{ item['预测年报每股收益2028预测'] || '--' }}</td>
                    </tr>
                  </tbody>
                </table>
                <div v-if="forecastData.institutions.length > 20" class="text-center py-2 text-terminal-dim text-xs">
                  显示前20条，共 {{ forecastData.institutions.length }} 条记录
                </div>
              </div>
              <div v-else class="text-center py-4 text-terminal-dim">暂无机构预测数据</div>
            </div>
          </div>
        </div>
        
        <!-- 机构持股 -->
        <div v-else-if="activeTab === 'institution'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">机构持股</h2>
          
          <div v-if="institutionLoading" class="text-center py-8 text-terminal-dim">
            加载中...
          </div>
          
          <div v-else-if="institutionError" class="text-center py-8 text-red-400">
            {{ institutionError }}
          </div>
          
          <div v-else-if="!institutionData" class="text-center py-8 text-terminal-dim">
            请输入股票代码查询
          </div>
          
          <div v-else class="space-y-4">
            <!-- 汇总卡片 -->
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
                <div class="text-xs text-terminal-dim mb-1">当前季度</div>
                <div class="text-lg font-bold text-terminal-primary">{{ institutionData.quarter || '--' }}</div>
              </div>
              <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
                <div class="text-xs text-terminal-dim mb-1">机构数量</div>
                <div class="text-lg font-bold text-terminal-accent">{{ institutionData.current?.length || 0 }}</div>
              </div>
              <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
                <div class="text-xs text-terminal-dim mb-1">总持股比例</div>
                <div class="text-lg font-bold text-terminal-primary">
                  {{ institutionData.trend?.length > 0 ? (institutionData.trend[institutionData.trend.length - 1]?.total_pct || 0).toFixed(2) + '%' : '--' }}
                </div>
              </div>
              <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
                <div class="text-xs text-terminal-dim mb-1">趋势变化</div>
                <div class="text-lg font-bold" :class="institutionTrendClass">
                  {{ institutionTrendText }}
                </div>
              </div>
            </div>
            
            <!-- 饼图：前10大机构持股分布 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">前10大机构持股分布</h3>
              <div ref="institutionPieChart" class="w-full h-64"></div>
            </div>
            
            <!-- 持股明细表格 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">持股明细</h3>
              <div class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead>
                    <tr class="border-b border-theme-secondary">
                      <th class="text-left py-2 px-3 text-terminal-dim font-normal">序号</th>
                      <th class="text-left py-2 px-3 text-terminal-dim font-normal">机构名称</th>
                      <th class="text-right py-2 px-3 text-terminal-dim font-normal">持股数量(股)</th>
                      <th class="text-right py-2 px-3 text-terminal-dim font-normal">持股比例(%)</th>
                      <th class="text-right py-2 px-3 text-terminal-dim font-normal">较上期变化</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(holder, index) in topInstitutionHolders" :key="index" class="border-b border-theme-secondary/50 hover:bg-theme-hover">
                      <td class="py-2 px-3 text-terminal-secondary">{{ index + 1 }}</td>
                      <td class="py-2 px-3 text-terminal-primary">{{ holder['股东名称'] || holder['机构名称'] || '--' }}</td>
                      <td class="py-2 px-3 text-right text-terminal-secondary">{{ formatHolderShares(holder['持股数量']) }}</td>
                      <td class="py-2 px-3 text-right text-terminal-secondary">{{ formatHolderPct(holder['持股比例']) }}</td>
                      <td class="py-2 px-3 text-right" :class="getChangeClass(holder['增减'])">{{ holder['增减'] || '--' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            
            <!-- 趋势折线图 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">近8季度机构持股趋势</h3>
              <div ref="institutionTrendChart" class="w-full h-64"></div>
            </div>
          </div>
        </div>
        
        <!-- 股东研究 -->
        <div v-else-if="activeTab === 'shareholder'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">股东研究</h2>
          
          <div v-if="shareholderLoading" class="text-center py-8 text-terminal-dim">
            加载中...
          </div>
          
          <div v-else-if="shareholderError" class="text-center py-8 text-red-400">
            {{ shareholderError }}
          </div>
          
          <div v-else-if="!shareholderData" class="text-center py-8 text-terminal-dim">
            请先查询股票代码
          </div>
          
          <div v-else class="space-y-4">
            <!-- Top 10 流通股东 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">
                Top 10 流通股东
                <span v-if="shareholderData.circulateHolders?.date" class="text-xs text-terminal-dim ml-2">
                  ({{ shareholderData.circulateHolders.date }})
                </span>
              </h3>
              <div class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead>
                    <tr class="border-b border-theme-secondary text-terminal-dim">
                      <th class="py-2 px-3 text-left">排名</th>
                      <th class="py-2 px-3 text-left">股东名称</th>
                      <th class="py-2 px-3 text-right">持股数量</th>
                      <th class="py-2 px-3 text-right">占流通股比例</th>
                      <th class="py-2 px-3 text-left">股本性质</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr 
                      v-for="(holder, idx) in shareholderData.circulateHolders?.holders" 
                      :key="idx"
                      class="border-b border-theme-secondary/50 hover:bg-theme-hover"
                    >
                      <td class="py-2 px-3 text-terminal-dim">{{ idx + 1 }}</td>
                      <td class="py-2 px-3 text-terminal-primary">{{ holder['股东名称'] }}</td>
                      <td class="py-2 px-3 text-right text-terminal-secondary">{{ formatNumber(holder['持股数量']) }}</td>
                      <td class="py-2 px-3 text-right text-terminal-accent">{{ holder['占流通股比例'] }}%</td>
                      <td class="py-2 px-3 text-terminal-dim">{{ holder['股本性质'] }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            
            <!-- 股本变动记录 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">股本变动记录（最近365天）</h3>
              <div v-if="!shareholderData.shareChanges?.length" class="text-center py-4 text-terminal-dim">
                暂无股本变动记录
              </div>
              <div v-else class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead>
                    <tr class="border-b border-theme-secondary text-terminal-dim">
                      <th class="py-2 px-3 text-left">变动日期</th>
                      <th class="py-2 px-3 text-left">变动原因</th>
                      <th class="py-2 px-3 text-right">总股本</th>
                      <th class="py-2 px-3 text-right">已流通股份</th>
                      <th class="py-2 px-3 text-right">流通受限股份</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr 
                      v-for="(change, idx) in shareholderData.shareChanges" 
                      :key="idx"
                      class="border-b border-theme-secondary/50 hover:bg-theme-hover"
                    >
                      <td class="py-2 px-3 text-terminal-primary">{{ change.date }}</td>
                      <td class="py-2 px-3 text-terminal-secondary">{{ change.reason }}</td>
                      <td class="py-2 px-3 text-right text-terminal-dim">{{ formatNumber(change.totalShares) }}</td>
                      <td class="py-2 px-3 text-right text-terminal-dim">{{ formatNumber(change.circulateShares) }}</td>
                      <td class="py-2 px-3 text-right text-terminal-dim">{{ formatNumber(change.restrictedShares) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            
            <!-- 股东增减持记录 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">重要股东增减持</h3>
              <div v-if="!shareholderData.holderChanges?.length" class="text-center py-4 text-terminal-dim">
                暂无增减持记录
              </div>
              <div v-else class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead>
                    <tr class="border-b border-theme-secondary text-terminal-dim">
                      <th class="py-2 px-3 text-left">公告日期</th>
                      <th class="py-2 px-3 text-left">变动股东</th>
                      <th class="py-2 px-3 text-right">变动数量</th>
                      <th class="py-2 px-3 text-right">交易均价</th>
                      <th class="py-2 px-3 text-right">剩余股份</th>
                      <th class="py-2 px-3 text-left">变动途径</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr 
                      v-for="(change, idx) in shareholderData.holderChanges" 
                      :key="idx"
                      class="border-b border-theme-secondary/50 hover:bg-theme-hover"
                      :class="{
                        'bg-red-500/10': change.changeAmount && change.changeAmount.includes('减持'),
                        'bg-green-500/10': change.changeAmount && change.changeAmount.includes('增持')
                      }"
                    >
                      <td class="py-2 px-3 text-terminal-primary">{{ change.date }}</td>
                      <td class="py-2 px-3 text-terminal-secondary">{{ change.holder }}</td>
                      <td 
                        class="py-2 px-3 text-right font-medium"
                        :class="{
                          'text-red-400': change.changeAmount && change.changeAmount.includes('减持'),
                          'text-green-400': change.changeAmount && change.changeAmount.includes('增持')
                        }"
                      >
                        {{ change.changeAmount }}
                      </td>
                      <td class="py-2 px-3 text-right text-terminal-dim">{{ change.avgPrice }}</td>
                      <td class="py-2 px-3 text-right text-terminal-dim">{{ change.remainingShares }}</td>
                      <td class="py-2 px-3 text-terminal-dim">{{ change.channel }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 公司公告 -->
        <div v-else-if="activeTab === 'announcement'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">公司公告</h2>
          
          <div v-if="announcementsLoading" class="text-center py-8 text-terminal-dim">
            加载中...
          </div>
          
          <div v-else-if="announcementsError" class="text-center py-8 text-red-400">
            {{ announcementsError }}
          </div>
          
          <div v-else-if="!announcementsData" class="text-center py-8 text-terminal-dim">
            请输入股票代码查询
          </div>
          
          <div v-else class="space-y-4">
            <!-- 公告统计 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <div class="flex items-center justify-between">
                <div class="text-sm text-terminal-dim">
                  共 <span class="text-terminal-accent font-bold">{{ announcementsData.total }}</span> 条公告
                </div>
                <div class="text-xs text-terminal-dim">
                  最近30天数据
                </div>
              </div>
            </div>
            
            <!-- 公告列表 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary">
              <div v-if="!announcementsData.announcements?.length" class="text-center py-8 text-terminal-dim">
                暂无公告数据
              </div>
              <div v-else class="divide-y divide-theme-secondary">
                <div 
                  v-for="(item, idx) in announcementsData.announcements" 
                  :key="idx"
                  class="p-4 hover:bg-theme-hover cursor-pointer transition"
                  @click="openAnnouncement(item.url)"
                >
                  <div class="flex items-start justify-between gap-4">
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2 mb-1">
                        <span 
                          class="px-2 py-0.5 rounded text-xs"
                          :class="getAnnouncementTypeClass(item.type)"
                        >
                          {{ item.type || '公告' }}
                        </span>
                        <span class="text-xs text-terminal-dim">{{ item.date }}</span>
                      </div>
                      <div class="text-sm text-terminal-primary truncate">
                        {{ item.title || '无标题' }}
                      </div>
                    </div>
                    <div class="flex-shrink-0">
                      <svg class="w-4 h-4 text-terminal-dim" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- 分页 -->
            <div v-if="announcementsData.total > announcementsPageSize" class="flex items-center justify-center gap-2">
              <button
                class="px-3 py-1.5 rounded text-sm transition"
                :class="announcementsPage <= 1 ? 'text-terminal-dim cursor-not-allowed' : 'text-terminal-primary hover:bg-theme-hover'"
                :disabled="announcementsPage <= 1"
                @click="fetchAnnouncementsData(announcementsPage - 1)"
              >
                上一页
              </button>
              <span class="text-sm text-terminal-dim">
                第 {{ announcementsPage }} / {{ Math.ceil(announcementsData.total / announcementsPageSize) }} 页
              </span>
              <button
                class="px-3 py-1.5 rounded text-sm transition"
                :class="announcementsPage >= Math.ceil(announcementsData.total / announcementsPageSize) ? 'text-terminal-dim cursor-not-allowed' : 'text-terminal-primary hover:bg-theme-hover'"
                :disabled="announcementsPage >= Math.ceil(announcementsData.total / announcementsPageSize)"
                @click="fetchAnnouncementsData(announcementsPage + 1)"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
        
        <!-- 同业比较 -->
        <div v-else-if="activeTab === 'peer'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">同业比较</h2>

          <div v-if="peersLoading" class="text-center py-8 text-terminal-dim">
            加载中...
          </div>

          <div v-else-if="peersError" class="text-center py-8 text-red-400">
            {{ peersError }}
          </div>

          <div v-else-if="!peersData" class="text-center py-8 text-terminal-dim">
            请输入股票代码查询同业比较数据
          </div>

          <div v-else class="space-y-4">
            <!-- 行业信息 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <div class="text-xs text-terminal-dim mb-1">所属行业</div>
              <div class="text-lg font-bold text-terminal-accent">{{ peersData.industry || '--' }}</div>
            </div>

            <!-- 同业对比表格 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">同业对比</h3>
              <div v-if="!peersData.peers?.length" class="text-center py-4 text-terminal-dim">
                暂无同业数据
              </div>
              <div v-else class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead>
                    <tr class="border-b border-theme-secondary">
                      <th class="text-left py-2 px-3 text-terminal-dim font-normal">股票代码</th>
                      <th class="text-left py-2 px-3 text-terminal-dim font-normal">股票名称</th>
                      <th class="text-right py-2 px-3 text-terminal-dim font-normal">ROE(%)</th>
                      <th class="text-right py-2 px-3 text-terminal-dim font-normal">PE</th>
                      <th class="text-right py-2 px-3 text-terminal-dim font-normal">PB</th>
                      <th class="text-right py-2 px-3 text-terminal-dim font-normal">营收增长(%)</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(peer, idx) in peersData.peers"
                      :key="peer.symbol"
                      class="border-b border-theme-secondary/50 hover:bg-theme-hover"
                      :class="{ 'bg-terminal-accent/10': peer.symbol === inputSymbol }"
                    >
                      <td class="py-2 px-3 text-terminal-secondary">{{ peer.symbol }}</td>
                      <td class="py-2 px-3 text-terminal-primary font-medium">{{ peer.name }}</td>
                      <td class="py-2 px-3 text-right" :class="getMetricClass(peer.roe, 'roe')">
                        {{ formatMetric(peer.roe) }}
                      </td>
                      <td class="py-2 px-3 text-right" :class="getMetricClass(peer.pe, 'pe')">
                        {{ formatMetric(peer.pe) }}
                      </td>
                      <td class="py-2 px-3 text-right" :class="getMetricClass(peer.pb, 'pb')">
                        {{ formatMetric(peer.pb) }}
                      </td>
                      <td class="py-2 px-3 text-right" :class="getMetricClass(peer.revenue_growth, 'growth')">
                        {{ formatMetric(peer.revenue_growth) }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- 雷达图 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">当前股票 vs 行业平均</h3>
              <div ref="peersRadarChart" class="w-full h-80"></div>
            </div>
          </div>
        </div>
        
        <!-- 融资融券 -->
        <div v-else-if="activeTab === 'margin'" class="space-y-4">
          <h2 class="text-lg font-bold text-terminal-accent">融资融券</h2>

          <div v-if="marginLoading" class="text-center py-8 text-terminal-dim">
            加载中...
          </div>

          <div v-else-if="marginError" class="text-center py-8 text-terminal-dim">
            {{ marginError }}
          </div>

          <div v-else-if="!marginData" class="text-center py-8 text-terminal-dim">
            请输入股票代码查询融资融券数据
          </div>

          <div v-else class="space-y-4">
            <!-- 当前融资融券数据卡片 -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <!-- 融资余额 -->
              <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
                <h3 class="text-sm font-bold text-terminal-primary mb-3">融资余额</h3>
                <div class="space-y-2">
                  <div>
                    <div class="text-xs text-terminal-dim">融资余额</div>
                    <div class="text-xl font-bold text-bullish">
                      {{ formatMoney(marginData.current.financing_balance * 10000) }}
                    </div>
                  </div>
                  <div class="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <div class="text-terminal-dim">融资买入</div>
                      <div class="text-bullish">{{ formatMoney(marginData.current.financing_buy * 10000) }}</div>
                    </div>
                    <div>
                      <div class="text-terminal-dim">融资偿还</div>
                      <div class="text-bearish">{{ formatMoney(marginData.current.financing_repay * 10000) }}</div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 融券余额 -->
              <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
                <h3 class="text-sm font-bold text-terminal-primary mb-3">融券余额</h3>
                <div class="space-y-2">
                  <div>
                    <div class="text-xs text-terminal-dim">融券余额</div>
                    <div class="text-xl font-bold text-bearish">
                      {{ formatMoney(marginData.current.lending_balance * 10000) }}
                    </div>
                  </div>
                  <div class="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <div class="text-terminal-dim">融券卖出</div>
                      <div class="text-bearish">{{ formatVolume(marginData.current.lending_sell) }}</div>
                    </div>
                    <div>
                      <div class="text-terminal-dim">融券偿还</div>
                      <div class="text-bullish">{{ formatVolume(marginData.current.lending_repay) }}</div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 融资融券余额 -->
              <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
                <h3 class="text-sm font-bold text-terminal-primary mb-3">融资融券余额</h3>
                <div class="space-y-2">
                  <div>
                    <div class="text-xs text-terminal-dim">总余额</div>
                    <div class="text-xl font-bold text-terminal-accent">
                      {{ formatMoney(marginData.current.total_balance * 10000) }}
                    </div>
                  </div>
                  <div class="text-xs text-terminal-dim">
                    更新日期: {{ marginData.current.date }}
                  </div>
                </div>
              </div>
            </div>

            <!-- 30天趋势图 -->
            <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">30日融资融券趋势</h3>
              <div ref="marginChartRef" style="height: 400px;"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { apiFetch } from '../utils/api.js'
import * as echarts from 'echarts'
import LoadingSpinner from './f9/LoadingSpinner.vue'
import ErrorDisplay from './f9/ErrorDisplay.vue'
import InfoCard from './f9/InfoCard.vue'
import DataTable from './f9/DataTable.vue'
import TrendChart from './f9/TrendChart.vue'

const props = defineProps({
  symbol: { type: String, default: '' }
})

const inputSymbol = ref(props.symbol)
const activeTab = ref('overview')
const loading = ref(false)
const stockInfo = ref(null)

// Helper: strip sh/sz prefix for F9 API calls (F9 API expects bare symbol like "600519")
function getBareSymbol(symbol) {
  if (!symbol) return ''
  return symbol.replace(/^(sh|sz)/i, '')
}

const shareholderData = ref(null)
const shareholderLoading = ref(false)
const shareholderError = ref(null)

// 融资融券数据
const marginData = ref(null)
const marginLoading = ref(false)
const marginError = ref(null)
const marginChartRef = ref(null)
let marginChart = null

// 机构持股数据
const institutionData = ref(null)
const institutionLoading = ref(false)
const institutionError = ref('')
const institutionPieChart = ref(null)
const institutionTrendChart = ref(null)
let pieChartInstance = null
let trendChartInstance = null

const financialData = ref(null)
const financialLoading = ref(false)
const financialError = ref('')

// 盈利预测数据
const forecastData = ref(null)
const forecastLoading = ref(false)
const forecastError = ref(null)

// 同业比较数据
const peersData = ref(null)
const peersLoading = ref(false)
const peersError = ref(null)
const peersRadarChart = ref(null)
let radarChartInstance = null

// 公司公告数据
const announcementsData = ref(null)
const announcementsLoading = ref(false)
const announcementsError = ref(null)
const announcementsPage = ref(1)
const announcementsPageSize = ref(20)

const menuItems = [
  { id: 'overview', name: '公司概况', icon: '🏢' },
  { id: 'finance', name: '财务摘要', icon: '📊' },
  { id: 'forecast', name: '盈利预测', icon: '📈' },
  { id: 'institution', name: '机构持股', icon: '🏛️' },
  { id: 'shareholder', name: '股东研究', icon: '👥' },
  { id: 'announcement', name: '公司公告', icon: '📢' },
  { id: 'peer', name: '同业比较', icon: '📋' },
  { id: 'margin', name: '融资融券', icon: '💹' },
]

const priceClass = computed(() => {
  if (!stockInfo.value) return ''
  return stockInfo.value.change >= 0 ? 'text-bullish' : 'text-bearish'
})

const changeClass = computed(() => {
  if (!stockInfo.value) return ''
  return stockInfo.value.change >= 0 ? 'text-bullish' : 'text-bearish'
})

async function handleSearch() {
  if (!inputSymbol.value) return
  loading.value = true
  
  // 确保 symbol 格式正确（添加 sh/sz 前缀）
  let symbolToQuery = inputSymbol.value
  if (!symbolToQuery.startsWith('sh') && !symbolToQuery.startsWith('sz')) {
    // 根据股票代码第一位判断交易所
    const firstChar = symbolToQuery.charAt(0)
    if (firstChar === '6') {
      symbolToQuery = 'sh' + symbolToQuery
    } else if (firstChar === '0' || firstChar === '3') {
      symbolToQuery = 'sz' + symbolToQuery
    }
  }
  
  try {
    const data = await apiFetch(`/api/v1/stocks/quote?symbol=${symbolToQuery}`, { timeoutMs: 10000 })
    if (data && data.name) {
      stockInfo.value = {
        symbol: inputSymbol.value,
        name: data.name || inputSymbol.value,
        price: data.price || 0,
        change: data.change_pct || 0,
        industry: data.industry || '--',
        totalShares: data.totalShares,
        floatShares: data.floatShares,
        totalMarketCap: data.totalMarketCap,
        floatMarketCap: data.floatMarketCap,
        listDate: data.listDate,
        business: data.business || '暂无主营业务数据',
      }
    } else {
      // API 返回空数据时，使用演示数据但保持 inputSymbol 不变
      stockInfo.value = {
        symbol: inputSymbol.value,
        name: '演示股票',
        price: 10.50,
        change: 2.35,
        industry: '计算机软件',
        totalShares: 1000000000,
        floatShares: 800000000,
        totalMarketCap: 10500000000,
        floatMarketCap: 8400000000,
        listDate: '2020-01-01',
        business: '公司主要从事人工智能、大数据、云计算等前沿技术的研发与应用，为客户提供智能化的解决方案。',
      }
    }
  } catch (e) {
    console.error('[StockDetail] Search error:', e)
    stockInfo.value = {
      symbol: inputSymbol.value,
      name: '演示股票',
      price: 10.50,
      change: 2.35,
      industry: '计算机软件',
      totalShares: 1000000000,
      floatShares: 800000000,
      totalMarketCap: 10500000000,
      floatMarketCap: 8400000000,
      listDate: '2020-01-01',
      business: '公司主要从事人工智能、大数据、云计算等前沿技术的研发与应用，为客户提供智能化的解决方案。',
    }
  } finally {
    loading.value = false
  }
}

async function fetchShareholderData() {
  if (!inputSymbol.value) return
  shareholderLoading.value = true
  shareholderError.value = null
  try {
    const bareSymbol = getBareSymbol(inputSymbol.value)
    const data = await apiFetch(`/api/v1/f9/${bareSymbol}/shareholder`, { timeoutMs: 30000 })
    if (data && (data.circulateHolders || data.shareChanges || data.holderChanges)) {
      shareholderData.value = data
    } else {
      shareholderError.value = '获取股东数据失败'
    }
  } catch (e) {
    console.error('[StockDetail] Shareholder fetch error:', e)
    shareholderError.value = e.message || '网络请求失败'
  } finally {
    shareholderLoading.value = false
  }
}

async function fetchMarginData(symbol) {
  if (!symbol) return
  marginLoading.value = true
  marginError.value = null
  try {
    const bareSymbol = getBareSymbol(symbol)
    const data = await apiFetch(`/api/v1/f9/${bareSymbol}/margin`, { timeoutMs: 30000 })
    if (data && data.current) {
      marginData.value = data
    } else {
      marginError.value = '暂无融资融券数据'
    }
  } catch (e) {
    console.error('[StockDetail] Margin data fetch error:', e)
    marginError.value = e.message || '获取融资融券数据失败'
  } finally {
    marginLoading.value = false
  }
}

async function fetchFinancialData() {
  if (!inputSymbol.value) return
  financialLoading.value = true
  financialError.value = ''
  try {
    const bareSymbol = getBareSymbol(inputSymbol.value)
    const data = await apiFetch(`/api/v1/f9/${bareSymbol}/financial`, { timeoutMs: 30000 })
    if (data && data.indicators && data.indicators.length > 0) {
      financialData.value = data
    } else {
      financialError.value = '暂无财务数据'
    }
  } catch (e) {
    console.error('[StockDetail] Financial data fetch error:', e)
    financialError.value = '加载财务数据失败，请稍后重试'
  } finally {
    financialLoading.value = false
  }
}

async function fetchForecastData(symbol) {
  if (!symbol) return
  forecastLoading.value = true
  forecastError.value = null
  try {
    const bareSymbol = getBareSymbol(symbol)
    const data = await apiFetch(`/api/v1/f9/${bareSymbol}/forecast`, { timeoutMs: 30000 })
    if (data && ((data.eps_forecast && data.eps_forecast.length > 0) || (data.institutions && data.institutions.length > 0))) {
      forecastData.value = data
    } else {
      forecastError.value = '暂无盈利预测数据'
    }
  } catch (e) {
    console.error('[StockDetail] Forecast error:', e)
    forecastError.value = e.message || '网络请求失败'
  } finally {
    forecastLoading.value = false
  }
}

async function fetchPeersData(symbol) {
  if (!symbol) return
  peersLoading.value = true
  peersError.value = null
  try {
    const bareSymbol = getBareSymbol(symbol)
    const data = await apiFetch(`/api/v1/f9/${bareSymbol}/peers`, { timeoutMs: 30000 })
    if (data && data.peers && data.peers.length > 0) {
      peersData.value = data
      await nextTick()
      renderPeersRadarChart()
    } else {
      peersError.value = '暂无同业比较数据'
    }
  } catch (e) {
    console.error('[StockDetail] Peers error:', e)
    peersError.value = e.message || '网络请求失败'
  } finally {
    peersLoading.value = false
  }
}

function formatMetric(value) {
  if (value === null || value === undefined) return '--'
  return value.toFixed(2)
}

function getMetricClass(value, type) {
  if (value === null || value === undefined) return 'text-terminal-dim'
  
  if (type === 'growth') {
    return value >= 0 ? 'text-bullish' : 'text-bearish'
  }
  
  if (type === 'pe') {
    if (value > 0 && value < 20) return 'text-bullish'
    if (value >= 20 && value < 40) return 'text-yellow-400'
    return 'text-bearish'
  }
  
  if (type === 'roe') {
    if (value >= 15) return 'text-bullish'
    if (value >= 8) return 'text-yellow-400'
    return 'text-bearish'
  }
  
  return 'text-terminal-secondary'
}

function renderPeersRadarChart() {
  if (!peersRadarChart.value || !peersData.value?.peers) return
  
  if (radarChartInstance) {
    radarChartInstance.dispose()
  }
  
  radarChartInstance = echarts.init(peersRadarChart.value)
  
  const peers = peersData.value.peers
  const currentStock = peers.find(p => p.symbol === inputSymbol.value)
  
  if (!currentStock) {
    return
  }
  
  const validPeers = peers.filter(p => 
    p.roe !== null && p.pe !== null && p.pb !== null && p.revenue_growth !== null
  )
  
  const avgRoe = validPeers.reduce((sum, p) => sum + p.roe, 0) / validPeers.length
  const avgPe = validPeers.reduce((sum, p) => sum + p.pe, 0) / validPeers.length
  const avgPb = validPeers.reduce((sum, p) => sum + p.pb, 0) / validPeers.length
  const avgGrowth = validPeers.reduce((sum, p) => sum + p.revenue_growth, 0) / validPeers.length
  
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: '#3b82f6',
      textStyle: { color: '#e2e8f0' }
    },
    legend: {
      data: ['当前股票', '行业平均'],
      textStyle: { color: '#94a3b8' },
      top: 10
    },
    radar: {
      indicator: [
        { name: 'ROE', max: Math.max(currentStock.roe || 0, avgRoe) * 1.2 },
        { name: 'PE', max: Math.max(currentStock.pe || 0, avgPe) * 1.2 },
        { name: 'PB', max: Math.max(currentStock.pb || 0, avgPb) * 1.2 },
        { name: '营收增长', max: Math.max(Math.abs(currentStock.revenue_growth || 0), Math.abs(avgGrowth)) * 1.2 }
      ],
      center: ['50%', '55%'],
      radius: '65%',
      axisName: {
        color: '#94a3b8',
        fontSize: 12
      },
      splitLine: {
        lineStyle: { color: '#334155' }
      },
      splitArea: {
        areaStyle: { color: ['rgba(59, 130, 246, 0.05)', 'rgba(59, 130, 246, 0.1)'] }
      },
      axisLine: {
        lineStyle: { color: '#475569' }
      }
    },
    series: [{
      type: 'radar',
      data: [
        {
          value: [
            currentStock.roe || 0,
            currentStock.pe || 0,
            currentStock.pb || 0,
            currentStock.revenue_growth || 0
          ],
          name: '当前股票',
          lineStyle: { color: '#3b82f6', width: 2 },
          areaStyle: { color: 'rgba(59, 130, 246, 0.3)' },
          itemStyle: { color: '#3b82f6' }
        },
        {
          value: [avgRoe, avgPe, avgPb, avgGrowth],
          name: '行业平均',
          lineStyle: { color: '#10b981', width: 2, type: 'dashed' },
          areaStyle: { color: 'rgba(16, 185, 129, 0.2)' },
          itemStyle: { color: '#10b981' }
        }
      ]
    }]
  }
  
  radarChartInstance.setOption(option)
}

async function fetchAnnouncementsData(page = 1) {
  if (!inputSymbol.value) return
  announcementsLoading.value = true
  announcementsError.value = null
  announcementsPage.value = page
  try {
    const bareSymbol = getBareSymbol(inputSymbol.value)
    const data = await apiFetch(`/api/v1/f9/${bareSymbol}/announcements?page=${page}&page_size=${announcementsPageSize.value}`, { timeoutMs: 30000 })
    if (data && data.announcements) {
      announcementsData.value = data
    } else {
      announcementsError.value = '获取公告数据失败'
    }
  } catch (e) {
    console.error('[StockDetail] Announcements fetch error:', e)
    announcementsError.value = e.message || '网络请求失败'
  } finally {
    announcementsLoading.value = false
  }
}

function getAnnouncementTypeClass(type) {
  if (!type) return 'bg-gray-500/20 text-gray-400'
  const t = type.toLowerCase()
  if (t.includes('业绩') || t.includes('财报')) {
    return 'bg-blue-500/20 text-blue-400'
  }
  if (t.includes('重大') || t.includes('重要')) {
    return 'bg-red-500/20 text-red-400'
  }
  if (t.includes('分红') || t.includes('派息')) {
    return 'bg-green-500/20 text-green-400'
  }
  if (t.includes('增发') || t.includes('配股')) {
    return 'bg-yellow-500/20 text-yellow-400'
  }
  if (t.includes('减持') || t.includes('增持')) {
    return 'bg-purple-500/20 text-purple-400'
  }
  return 'bg-gray-500/20 text-gray-400'
}

function openAnnouncement(url) {
  if (url && url !== '--' && url !== 'nan') {
    window.open(url, '_blank')
  }
}

function formatNumber(num) {
  if (!num) return '--'
  if (num >= 1e8) return (num / 1e8).toFixed(2) + '亿'
  if (num >= 1e4) return (num / 1e4).toFixed(2) + '万'
  return num.toString()
}

function formatMoney(num) {
  if (!num) return '--'
  if (num >= 1e12) return (num / 1e12).toFixed(2) + '万亿'
  if (num >= 1e8) return (num / 1e8).toFixed(2) + '亿'
  if (num >= 1e4) return (num / 1e4).toFixed(2) + '万'
  return num.toString()
}

function formatVolume(num) {
  if (!num) return '--'
  if (num >= 1e8) return (num / 1e8).toFixed(2) + '亿股'
  if (num >= 1e4) return (num / 1e4).toFixed(2) + '万股'
  return num.toString() + '股'
}

function renderMarginChart() {
  if (!marginChartRef.value || !marginData.value) return

  if (marginChart) {
    marginChart.dispose()
  }

  marginChart = echarts.init(marginChartRef.value)

  const trend = marginData.value.trend || []
  const dates = trend.map(d => d.date)
  const financingBalances = trend.map(d => d.financing_balance)
  const lendingBalances = trend.map(d => d.lending_balance)
  const totalBalances = trend.map(d => d.total_balance)

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: '#3b82f6',
      textStyle: {
        color: '#e2e8f0'
      }
    },
    legend: {
      data: ['融资余额', '融券余额', '总余额'],
      textStyle: {
        color: '#94a3b8'
      },
      top: 10
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: {
        lineStyle: {
          color: '#475569'
        }
      },
      axisLabel: {
        color: '#94a3b8',
        rotate: 45
      }
    },
    yAxis: {
      type: 'value',
      axisLine: {
        lineStyle: {
          color: '#475569'
        }
      },
      axisLabel: {
        color: '#94a3b8',
        formatter: function(value) {
          if (value >= 10000) {
            return (value / 10000).toFixed(0) + '万'
          }
          return value
        }
      },
      splitLine: {
        lineStyle: {
          color: '#334155'
        }
      }
    },
    series: [
      {
        name: '融资余额',
        type: 'bar',
        data: financingBalances,
        itemStyle: {
          color: '#ef4444'
        }
      },
      {
        name: '融券余额',
        type: 'bar',
        data: lendingBalances,
        itemStyle: {
          color: '#22c55e'
        }
      },
      {
        name: '总余额',
        type: 'line',
        data: totalBalances,
        smooth: true,
        lineStyle: {
          color: '#3b82f6',
          width: 2
        },
        itemStyle: {
          color: '#3b82f6'
        },
        symbol: 'circle',
        symbolSize: 6
      }
    ]
  }

  marginChart.setOption(option)
}

function getTrendChartData(metric) {
  if (!financialData.value || !financialData.value.trend) return []
  return financialData.value.trend
    .filter(item => item[metric] != null)
    .reverse()
    .map(item => ({
      date: item['日期'] || '',
      value: item[metric]
    }))
}

const tableColumns = [
  { key: '日期', label: '日期', format: 'date' },
  { key: '摊薄每股收益(元)', label: '每股收益', format: 'number' },
  { key: '净资产收益率(%)', label: 'ROE', format: 'percentage' },
  { key: '销售毛利率(%)', label: '毛利率', format: 'percentage' },
  { key: '销售净利率(%)', label: '净利率', format: 'percentage' },
  { key: '主营业务收入增长率(%)', label: '营收增长', format: 'percentage' },
  { key: '净利润增长率(%)', label: '利润增长', format: 'percentage' },
  { key: '每股净资产_调整后(元)', label: '每股净资产', format: 'number' },
  { key: '流动比率', label: '流动比率', format: 'number' },
  { key: '资产负债率(%)', label: '资产负债率', format: 'percentage' }
]

function getRatingClass(rating) {
  if (!rating) return 'text-terminal-dim'
  const r = rating.toLowerCase()
  if (r.includes('买入') || r.includes('增持') || r.includes('推荐')) {
    return 'bg-green-500/20 text-green-400'
  }
  if (r.includes('卖出') || r.includes('减持')) {
    return 'bg-red-500/20 text-red-400'
  }
  if (r.includes('中性') || r.includes('持有')) {
    return 'bg-yellow-500/20 text-yellow-400'
  }
  return 'text-terminal-dim'
}

// 监听 props.symbol 变化
watch(() => props.symbol, (newSymbol) => {
  if (newSymbol) {
    inputSymbol.value = newSymbol
    handleSearch()
  }
}, { immediate: true })

// 监听 activeTab 变化，加载各 tab 数据
watch(activeTab, (newTab) => {
  if (!inputSymbol.value) return
  
  if (newTab === 'finance' && !financialData.value) {
    fetchFinancialData()
  }
  if (newTab === 'shareholder' && !shareholderData.value) {
    fetchShareholderData()
  }
  if (newTab === 'margin' && !marginData.value) {
    fetchMarginData(inputSymbol.value)
  }
  if (newTab === 'institution' && !institutionData.value) {
    fetchInstitutionData()
  }
  if (newTab === 'forecast' && !forecastData.value) {
    fetchForecastData(inputSymbol.value)
  }
  if (newTab === 'peer' && !peersData.value) {
    fetchPeersData(inputSymbol.value)
  }
  if (newTab === 'announcement' && !announcementsData.value) {
    fetchAnnouncementsData()
  }
})

// 监听 marginData 变化，渲染图表
watch(marginData, () => {
  nextTick(() => {
    renderMarginChart()
  })
})

// 获取机构持股数据
async function fetchInstitutionData() {
  if (!inputSymbol.value) return
  
  institutionLoading.value = true
  institutionError.value = ''
  
  try {
    const bareSymbol = getBareSymbol(inputSymbol.value)
    const data = await apiFetch(`/api/v1/f9/${bareSymbol}/institution`, { timeoutMs: 30000 })
    if (data && ((data.current && data.current.length > 0) || (data.trend && data.trend.length > 0))) {
      institutionData.value = data
      
      // 渲染图表
      await nextTick()
      renderInstitutionCharts()
    } else {
      institutionError.value = '暂无机构持股数据'
    }
  } catch (e) {
    console.error('[StockDetail] Institution fetch error:', e)
    institutionError.value = `获取数据失败: ${e.message || '未知错误'}`
  } finally {
    institutionLoading.value = false
  }
}

// 计算前10大机构
const topInstitutionHolders = computed(() => {
  if (!institutionData.value?.current) return []
  return institutionData.value.current.slice(0, 10)
})

// 计算趋势变化
const institutionTrendClass = computed(() => {
  if (!institutionData.value?.trend || institutionData.value.trend.length < 2) return 'text-terminal-dim'
  const trend = institutionData.value.trend
  const last = trend[trend.length - 1]?.total_pct || 0
  const prev = trend[trend.length - 2]?.total_pct || 0
  return last >= prev ? 'text-bullish' : 'text-bearish'
})

const institutionTrendText = computed(() => {
  if (!institutionData.value?.trend || institutionData.value.trend.length < 2) return '--'
  const trend = institutionData.value.trend
  const last = trend[trend.length - 1]?.total_pct || 0
  const prev = trend[trend.length - 2]?.total_pct || 0
  const diff = last - prev
  return diff >= 0 ? `+${diff.toFixed(2)}%` : `${diff.toFixed(2)}%`
})

// 渲染机构持股图表
function renderInstitutionCharts() {
  renderInstitutionPieChart()
  renderInstitutionTrendChart()
}

// 渲染饼图
function renderInstitutionPieChart() {
  if (!institutionPieChart.value || !institutionData.value?.current) return
  
  if (pieChartInstance) {
    pieChartInstance.dispose()
  }
  
  pieChartInstance = echarts.init(institutionPieChart.value)
  
  const holders = institutionData.value.current.slice(0, 10)
  const pieData = holders.map(h => ({
    name: h['股东名称'] || h['机构名称'] || '未知',
    value: parseFloat(h['持股比例']) || 0
  }))
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}% ({d}%)'
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 10,
      top: 20,
      bottom: 20,
      textStyle: {
        color: '#9ca3af',
        fontSize: 11
      }
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['40%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 4,
        borderColor: '#1f2937',
        borderWidth: 2
      },
      label: {
        show: false
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 12,
          fontWeight: 'bold',
          color: '#f3f4f6'
        }
      },
      labelLine: {
        show: false
      },
      data: pieData
    }],
    color: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1']
  }
  
  pieChartInstance.setOption(option)
}

// 渲染趋势图
function renderInstitutionTrendChart() {
  if (!institutionTrendChart.value || !institutionData.value?.trend) return
  
  if (trendChartInstance) {
    trendChartInstance.dispose()
  }
  
  trendChartInstance = echarts.init(institutionTrendChart.value)
  
  const trend = institutionData.value.trend
  const quarters = trend.map(t => `${t.year}Q${t.quarter_num}`)
  const counts = trend.map(t => t.count)
  const pcts = trend.map(t => t.total_pct)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      }
    },
    legend: {
      data: ['机构数量', '持股比例(%)'],
      textStyle: {
        color: '#9ca3af'
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: quarters,
      axisLabel: {
        color: '#9ca3af',
        fontSize: 11
      },
      axisLine: {
        lineStyle: {
          color: '#374151'
        }
      }
    },
    yAxis: [
      {
        type: 'value',
        name: '机构数量',
        axisLabel: {
          color: '#9ca3af'
        },
        axisLine: {
          lineStyle: {
            color: '#374151'
          }
        },
        splitLine: {
          lineStyle: {
            color: '#374151',
            type: 'dashed'
          }
        }
      },
      {
        type: 'value',
        name: '持股比例(%)',
        axisLabel: {
          color: '#9ca3af'
        },
        axisLine: {
          lineStyle: {
            color: '#374151'
          }
        },
        splitLine: {
          show: false
        }
      }
    ],
    series: [
      {
        name: '机构数量',
        type: 'bar',
        data: counts,
        itemStyle: {
          color: '#3b82f6'
        }
      },
      {
        name: '持股比例(%)',
        type: 'line',
        yAxisIndex: 1,
        data: pcts,
        smooth: true,
        lineStyle: {
          color: '#10b981',
          width: 2
        },
        itemStyle: {
          color: '#10b981'
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(16, 185, 129, 0.3)' },
              { offset: 1, color: 'rgba(16, 185, 129, 0.05)' }
            ]
          }
        }
      }
    ]
  }
  
  trendChartInstance.setOption(option)
}

// 格式化持股数量
function formatHolderShares(num) {
  if (!num) return '--'
  const n = parseFloat(num)
  if (isNaN(n)) return num
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(0)
}

// 格式化持股比例
function formatHolderPct(pct) {
  if (!pct) return '--'
  const n = parseFloat(pct)
  if (isNaN(n)) return pct
  return n.toFixed(2) + '%'
}

// 获取变化样式
function getChangeClass(change) {
  if (!change) return 'text-terminal-dim'
  const str = String(change)
  if (str.includes('新进') || str.includes('增')) return 'text-bullish'
  if (str.includes('减') || str.includes('不变')) return 'text-bearish'
  return 'text-terminal-dim'
}

// 窗口大小变化时重绘图表
onMounted(() => {
  window.addEventListener('resize', () => {
    pieChartInstance?.resize()
    trendChartInstance?.resize()
    radarChartInstance?.resize()
  })
})
</script>
