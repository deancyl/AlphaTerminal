<template>
  <div class="h-full flex flex-col bg-terminal-bg overflow-hidden" role="region" aria-label="ESG评级面板">
    <!-- 顶部标题栏 -->
    <div class="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-theme-secondary">
      <div class="flex items-center gap-3">
        <span class="text-lg font-bold text-terminal-accent" role="heading" aria-level="2">🌱 ESG评级</span>
        <span class="text-xs text-terminal-dim hidden sm:inline">环境·社会·治理</span>
      </div>
      <div class="flex items-center gap-2">
        <span v-if="lastUpdate" class="text-xs text-terminal-dim hidden md:inline" aria-live="polite">
          更新于 {{ formatTime(lastUpdate) }}
        </span>
        <button 
          class="px-4 py-2 rounded-sm text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition disabled:opacity-50"
          style="min-width: 44px; min-height: 44px;"
          @click="refreshCurrentTab"
          :disabled="loading"
          aria-label="刷新当前数据"
          aria-busy="loading"
        >
          {{ loading ? '...' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- Tab导航 - 桌面端 -->
    <div class="flex-shrink-0 border-b border-theme-secondary hidden md:block">
      <div class="flex px-4">
        <button 
          v-for="tab in tabs" 
          :key="tab.key"
          class="px-4 py-2 text-sm font-medium transition-colors relative"
          :class="activeTab === tab.key ? 'text-terminal-accent' : 'text-terminal-dim hover:text-terminal-primary'"
          @click="switchTab(tab.key)"
        >
          {{ tab.label }}
          <span 
            v-if="activeTab === tab.key" 
            class="absolute bottom-0 left-0 right-0 h-0.5 bg-terminal-accent"
          ></span>
        </button>
      </div>
    </div>
    
    <!-- Tab导航 - 移动端滚动 -->
    <div class="flex-shrink-0 md:hidden">
      <MobileScrollableTabs 
        :tabs="tabs"
        v-model="activeTab"
        @update:model-value="switchTab"
      />
    </div>

    <!-- 主内容区域 -->
    <div class="flex-1 overflow-y-auto p-3 md:p-4">
      <!-- Tab 1: ESG评级查询 -->
      <div v-show="activeTab === 'rating'" class="space-y-4">
        <!-- 股票代码输入 -->
        <div class="flex gap-2">
          <input 
            v-model="symbolInput"
            type="text" 
            placeholder="输入股票代码 (如: 600519)"
            class="flex-1 px-3 py-2 bg-terminal-panel border border-theme-secondary rounded-sm text-terminal-primary text-sm focus:outline-none focus:border-terminal-accent"
            style="min-height: 44px;"
            @keyup.enter="searchRating"
          />
          <button 
            class="px-4 py-2 bg-terminal-accent text-white rounded-sm text-sm font-medium hover:bg-terminal-accent/80 transition disabled:opacity-50"
            style="min-width: 44px; min-height: 44px;"
            @click="searchRating"
            :disabled="loading || !symbolInput.trim()"
          >
            查询
          </button>
        </div>

        <!-- 错误提示 -->
        <div v-if="ratingError" class="bg-bearish/10 border border-bearish/30 rounded-lg p-4 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-bearish">⚠️</span>
            <span class="text-sm text-bearish">{{ ratingError }}</span>
          </div>
          <button 
            @click="searchRating" 
            class="px-3 py-1 bg-bearish/20 text-bearish rounded-sm text-xs hover:bg-bearish/30 transition"
          >
            重试
          </button>
        </div>

        <!-- 骨架加载器 -->
        <div v-if="loading && activeTab === 'rating' && !ratingError" class="space-y-3">
          <div v-for="i in 3" :key="i" class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 animate-pulse">
            <div class="h-4 w-24 bg-terminal-bg/50 rounded mb-3"></div>
            <div class="h-3 w-full bg-terminal-bg/50 rounded mb-2"></div>
            <div class="h-3 w-3/4 bg-terminal-bg/50 rounded"></div>
          </div>
        </div>

        <!-- ESG雷达图 -->
        <div v-else-if="ratings.length > 0 && hasEsgScores" class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
          <h3 class="text-sm font-medium text-terminal-primary mb-3">ESG评分雷达图</h3>
          <div ref="radarChartRef" class="h-[180px] sm:h-[200px]"></div>
        </div>

        <!-- 评级结果 -->
        <div v-if="ratings.length > 0" class="space-y-3">
          <div 
            v-for="(rating, index) in ratings" 
            :key="index"
            class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 hover:border-terminal-accent/50 transition-colors"
          >
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm font-bold text-terminal-accent">{{ rating.source }}</span>
              <span class="text-xs text-terminal-dim">{{ rating.date || '--' }}</span>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <div class="text-xs text-terminal-dim mb-1">评级</div>
                <div class="text-lg font-bold text-terminal-primary">{{ rating.rating || '--' }}</div>
              </div>
              <div>
                <div class="text-xs text-terminal-dim mb-1">得分</div>
                <div class="text-lg font-bold text-terminal-primary">{{ rating.score?.toFixed(2) || '--' }}</div>
              </div>
              <div v-if="rating.environment_score">
                <div class="text-xs text-terminal-dim mb-1">环境</div>
                <div class="text-lg font-bold text-green-400">{{ rating.environment_score?.toFixed(2) }}</div>
              </div>
              <div v-if="rating.social_score">
                <div class="text-xs text-terminal-dim mb-1">社会</div>
                <div class="text-lg font-bold text-blue-400">{{ rating.social_score?.toFixed(2) }}</div>
              </div>
              <div v-if="rating.governance_score">
                <div class="text-xs text-terminal-dim mb-1">治理</div>
                <div class="text-lg font-bold text-purple-400">{{ rating.governance_score?.toFixed(2) }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-else-if="!loading && symbolInput && hasSearched && !ratingError" class="text-center py-12 text-terminal-dim">
          <div class="text-4xl mb-2">🔍</div>
          <div class="text-sm">未找到 {{ symbolInput }} 的ESG评级数据</div>
        </div>

        <!-- 初始提示 -->
        <div v-else-if="!hasSearched" class="text-center py-12 text-terminal-dim">
          <div class="text-4xl mb-2">🌱</div>
          <div class="text-sm">输入股票代码查询ESG评级</div>
        </div>
      </div>

      <!-- Tab 2: 碳排放数据 -->
      <div v-show="activeTab === 'carbon'" class="space-y-4">
        <!-- 错误提示 -->
        <div v-if="carbonError" class="bg-bearish/10 border border-bearish/30 rounded-lg p-4 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-bearish">⚠️</span>
            <span class="text-sm text-bearish">{{ carbonError }}</span>
          </div>
          <button 
            @click="fetchCarbonData" 
            class="px-3 py-1 bg-bearish/20 text-bearish rounded-sm text-xs hover:bg-bearish/30 transition"
          >
            重试
          </button>
        </div>

        <!-- 骨架加载器 -->
        <div v-if="loading && activeTab === 'carbon' && !carbonError" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <div v-for="i in 6" :key="i" class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 animate-pulse">
            <div class="h-4 w-20 bg-terminal-bg/50 rounded mb-3"></div>
            <div class="h-6 w-16 bg-terminal-bg/50 rounded mb-2"></div>
            <div class="h-3 w-24 bg-terminal-bg/50 rounded"></div>
          </div>
        </div>

        <!-- 碳交易卡片 -->
        <div v-else-if="carbonData.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <div 
            v-for="(item, index) in carbonData" 
            :key="index"
            class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 hover:border-terminal-accent/50 transition-colors"
          >
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm font-bold text-terminal-accent">{{ item.market }}</span>
              <span class="text-[10px] text-terminal-dim">{{ item.date || '--' }}</span>
            </div>
            <div class="mb-2">
              <div class="text-xs text-terminal-dim mb-1">成交价</div>
              <div class="text-xl font-bold text-terminal-primary">
                {{ item.price?.toFixed(2) || '--' }} <span class="text-xs text-terminal-dim">元/吨</span>
              </div>
            </div>
            <div>
              <div class="text-xs text-terminal-dim mb-1">成交量</div>
              <div class="text-sm text-terminal-dim">{{ formatVolume(item.volume) }}</div>
            </div>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-else-if="!carbonError" class="text-center py-12 text-terminal-dim">
          <div class="text-4xl mb-2">🌍</div>
          <div class="text-sm">暂无碳排放交易数据</div>
        </div>
      </div>

      <!-- Tab 3: ESG排名 -->
      <div v-show="activeTab === 'rank'" class="space-y-4">
        <!-- 错误提示 -->
        <div v-if="rankError" class="bg-bearish/10 border border-bearish/30 rounded-lg p-4 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-bearish">⚠️</span>
            <span class="text-sm text-bearish">{{ rankError }}</span>
          </div>
          <button 
            @click="fetchRankData" 
            class="px-3 py-1 bg-bearish/20 text-bearish rounded-sm text-xs hover:bg-bearish/30 transition"
          >
            重试
          </button>
        </div>

        <!-- 骨架加载器 -->
        <div v-if="loading && activeTab === 'rank' && !rankError" class="space-y-2">
          <div v-for="i in 10" :key="i" class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 animate-pulse">
            <div class="flex items-center justify-between">
              <div class="h-4 w-32 bg-terminal-bg/50 rounded"></div>
              <div class="h-4 w-16 bg-terminal-bg/50 rounded"></div>
            </div>
          </div>
        </div>

        <!-- 排名表格 -->
        <div v-else-if="rankItems.length > 0" class="space-y-3">
          <div class="flex justify-end">
            <button 
              @click="exportCSV" 
              class="px-4 py-2 rounded-sm text-xs border border-theme-secondary text-terminal-dim hover:border-terminal-accent hover:text-terminal-accent transition"
              style="min-width: 44px; min-height: 44px;"
            >
              📥 导出CSV
            </button>
          </div>
          
          <!-- Desktop Table View -->
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary overflow-hidden hidden md:block">
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead class="bg-terminal-bg/50">
                  <tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-terminal-dim">排名</th>
                    <th @click="sortBy('symbol')" class="px-4 py-3 text-left text-xs font-medium text-terminal-dim cursor-pointer hover:text-terminal-accent">
                      股票代码 {{ sortField === 'symbol' ? (sortOrder === 'desc' ? '↓' : '↑') : '' }}
                    </th>
                    <th @click="sortBy('name')" class="px-4 py-3 text-left text-xs font-medium text-terminal-dim cursor-pointer hover:text-terminal-accent">
                      股票名称 {{ sortField === 'name' ? (sortOrder === 'desc' ? '↓' : '↑') : '' }}
                    </th>
                    <th @click="sortBy('rating')" class="px-4 py-3 text-left text-xs font-medium text-terminal-dim cursor-pointer hover:text-terminal-accent">
                      评级 {{ sortField === 'rating' ? (sortOrder === 'desc' ? '↓' : '↑') : '' }}
                    </th>
                    <th @click="sortBy('score')" class="px-4 py-3 text-right text-xs font-medium text-terminal-dim cursor-pointer hover:text-terminal-accent">
                      得分 {{ sortField === 'score' ? (sortOrder === 'desc' ? '↓' : '↑') : '' }}
                    </th>
                    <th @click="sortBy('date')" class="px-4 py-3 text-left text-xs font-medium text-terminal-dim cursor-pointer hover:text-terminal-accent">
                      评级日期 {{ sortField === 'date' ? (sortOrder === 'desc' ? '↓' : '↑') : '' }}
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-theme-secondary">
                  <tr 
                    v-for="(item, index) in rankItems" 
                    :key="index"
                    class="hover:bg-terminal-bg/30 transition-colors"
                  >
                    <td class="px-4 py-3 text-terminal-dim">{{ (page - 1) * pageSize + index + 1 }}</td>
                    <td class="px-4 py-3 font-mono text-terminal-primary">{{ item.symbol }}</td>
                    <td class="px-4 py-3 text-terminal-primary">{{ item.name }}</td>
                    <td class="px-4 py-3">
                      <span class="px-2 py-0.5 rounded text-xs font-medium" :class="getRatingClass(item.rating)">
                        {{ item.rating }}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-right font-mono text-terminal-primary">{{ item.score?.toFixed(2) || '--' }}</td>
                    <td class="px-4 py-3 text-terminal-dim">{{ item.date || '--' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          
          <!-- Mobile Card View -->
          <div class="md:hidden space-y-2">
            <div
              v-for="(item, index) in rankItems"
              :key="index"
              class="bg-terminal-panel rounded-lg border border-theme-secondary p-3"
            >
              <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                  <span class="text-xs text-terminal-dim">#{{ (page - 1) * pageSize + index + 1 }}</span>
                  <span class="font-mono text-sm text-terminal-primary">{{ item.symbol }}</span>
                </div>
                <span class="px-2 py-0.5 rounded text-xs font-medium" :class="getRatingClass(item.rating)">
                  {{ item.rating }}
                </span>
              </div>
              <div class="flex justify-between items-center text-xs">
                <span class="text-terminal-primary">{{ item.name }}</span>
                <span class="font-mono text-terminal-primary">{{ item.score?.toFixed(2) || '--' }}</span>
              </div>
              <div v-if="item.date" class="text-xs text-terminal-dim mt-1">{{ item.date }}</div>
            </div>
          </div>
          
          <!-- 分页控件 -->
          <div class="flex justify-between items-center px-2">
            <button 
              @click="prevPage" 
              :disabled="page <= 1" 
              class="px-4 py-2 rounded-sm text-xs border border-theme-secondary text-terminal-dim hover:border-terminal-accent hover:text-terminal-accent transition disabled:opacity-40 disabled:cursor-not-allowed"
              style="min-width: 44px; min-height: 44px;"
            >
              上一页
            </button>
            <div class="flex items-center gap-2 sm:gap-3">
              <span class="text-xs text-terminal-dim">第 {{ page }} / {{ totalPages }} 页</span>
              <select 
                v-model="pageSize" 
                @change="page = 1; fetchRankData()"
                class="bg-terminal-bg/60 border border-theme-secondary rounded-sm px-2 py-2 text-xs text-terminal-primary focus:outline-none focus:border-terminal-accent"
                style="min-height: 44px;"
              >
                <option :value="10">10条/页</option>
                <option :value="20">20条/页</option>
                <option :value="50">50条/页</option>
              </select>
            </div>
            <button 
              @click="nextPage" 
              :disabled="page >= totalPages"
              class="px-4 py-2 rounded-sm text-xs border border-theme-secondary text-terminal-dim hover:border-terminal-accent hover:text-terminal-accent transition disabled:opacity-40 disabled:cursor-not-allowed"
              style="min-width: 44px; min-height: 44px;"
            >
              下一页
            </button>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-else-if="!rankError" class="text-center py-12 text-terminal-dim">
          <div class="text-4xl mb-2">📊</div>
          <div class="text-sm">暂无ESG排名数据</div>
        </div>
      </div>

      <!-- Tab 4: 历史趋势 -->
      <div v-show="activeTab === 'history'" class="space-y-4">
        <!-- 股票代码输入 -->
        <div class="flex gap-2">
          <input 
            v-model="historySymbol"
            type="text" 
            placeholder="输入股票代码 (如: 600519)"
            class="flex-1 px-3 py-2 bg-terminal-panel border border-theme-secondary rounded-sm text-terminal-primary text-sm focus:outline-none focus:border-terminal-accent"
            style="min-height: 44px;"
            @keyup.enter="fetchHistoryData"
          />
          <button 
            class="px-4 py-2 bg-terminal-accent text-white rounded-sm text-sm font-medium hover:bg-terminal-accent/80 transition disabled:opacity-50"
            style="min-width: 44px; min-height: 44px;"
            @click="fetchHistoryData"
            :disabled="loading || !historySymbol.trim()"
          >
            查询
          </button>
        </div>

        <!-- 错误提示 -->
        <div v-if="historyError" class="bg-bearish/10 border border-bearish/30 rounded-lg p-4 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-bearish">⚠️</span>
            <span class="text-sm text-bearish">{{ historyError }}</span>
          </div>
          <button 
            @click="fetchHistoryData" 
            class="px-3 py-1 bg-bearish/20 text-bearish rounded-sm text-xs hover:bg-bearish/30 transition"
          >
            重试
          </button>
        </div>

        <!-- 历史趋势图表 -->
        <div v-if="historyData.length > 0" class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
          <h3 class="text-sm font-medium text-terminal-primary mb-3">12个月ESG趋势</h3>
          <div ref="historyChartRef" class="h-[250px] sm:h-[300px]"></div>
        </div>

        <!-- 空状态 -->
        <div v-else-if="!loading && !historyError" class="text-center py-12 text-terminal-dim">
          <div class="text-4xl mb-2">📈</div>
          <div class="text-sm">输入股票代码查看12个月ESG历史趋势</div>
        </div>
      </div>

      <!-- Tab 5: 对比分析 -->
      <div v-show="activeTab === 'compare'" class="space-y-4">
        <!-- 股票代码输入 -->
        <div class="space-y-2">
          <div class="flex gap-2">
            <input 
              v-model="compareSymbols"
              type="text" 
              placeholder="输入2-5个股票代码，用逗号分隔 (如: 600519,000858,601318)"
              class="flex-1 px-3 py-2 bg-terminal-panel border border-theme-secondary rounded-sm text-terminal-primary text-sm focus:outline-none focus:border-terminal-accent"
              style="min-height: 44px;"
              @keyup.enter="fetchCompareData"
            />
            <button 
              class="px-4 py-2 bg-terminal-accent text-white rounded-sm text-sm font-medium hover:bg-terminal-accent/80 transition disabled:opacity-50"
              style="min-width: 44px; min-height: 44px;"
              @click="fetchCompareData"
              :disabled="loading || !compareSymbols.trim()"
            >
              对比
            </button>
          </div>
          <div class="text-xs text-terminal-dim">支持2-5个股票代码对比</div>
        </div>

        <!-- 错误提示 -->
        <div v-if="compareError" class="bg-bearish/10 border border-bearish/30 rounded-lg p-4 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-bearish">⚠️</span>
            <span class="text-sm text-bearish">{{ compareError }}</span>
          </div>
          <button 
            @click="fetchCompareData" 
            class="px-3 py-1 bg-bearish/20 text-bearish rounded-sm text-xs hover:bg-bearish/30 transition"
          >
            重试
          </button>
        </div>

        <!-- 对比表格 -->
        <div v-if="compareData.length > 0" class="bg-terminal-panel rounded-lg border border-theme-secondary overflow-hidden">
          <!-- Desktop Table View -->
          <div class="hidden md:block overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-terminal-bg/50">
                <tr>
                  <th class="px-4 py-3 text-left text-xs font-medium text-terminal-dim">股票代码</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-terminal-dim">股票名称</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-terminal-dim">评级</th>
                  <th class="px-4 py-3 text-right text-xs font-medium text-terminal-dim">ESG得分</th>
                  <th class="px-4 py-3 text-right text-xs font-medium text-terminal-dim">环境(E)</th>
                  <th class="px-4 py-3 text-right text-xs font-medium text-terminal-dim">社会(S)</th>
                  <th class="px-4 py-3 text-right text-xs font-medium text-terminal-dim">治理(G)</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-theme-secondary">
                <tr 
                  v-for="(item, index) in compareData" 
                  :key="index"
                  class="hover:bg-terminal-bg/30 transition-colors"
                >
                  <td class="px-4 py-3 font-mono text-terminal-primary">{{ item.symbol }}</td>
                  <td class="px-4 py-3 text-terminal-primary">{{ item.name }}</td>
                  <td class="px-4 py-3">
                    <span class="px-2 py-0.5 rounded text-xs font-medium" :class="getRatingClass(item.rating)">
                      {{ item.rating }}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-right font-mono text-terminal-primary">{{ item.score?.toFixed(2) || '--' }}</td>
                  <td class="px-4 py-3 text-right font-mono text-green-400">{{ item.environment_score?.toFixed(2) || '--' }}</td>
                  <td class="px-4 py-3 text-right font-mono text-blue-400">{{ item.social_score?.toFixed(2) || '--' }}</td>
                  <td class="px-4 py-3 text-right font-mono text-purple-400">{{ item.governance_score?.toFixed(2) || '--' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          
          <!-- Mobile Card View -->
          <div class="md:hidden space-y-2 p-3">
            <div
              v-for="(item, index) in compareData"
              :key="index"
              class="bg-terminal-bg rounded-lg border border-theme-secondary p-3"
            >
              <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                  <span class="font-mono text-sm text-terminal-primary">{{ item.symbol }}</span>
                  <span class="text-terminal-primary text-sm">{{ item.name }}</span>
                </div>
                <span class="px-2 py-0.5 rounded text-xs font-medium" :class="getRatingClass(item.rating)">
                  {{ item.rating }}
                </span>
              </div>
              <div class="grid grid-cols-2 gap-2 text-xs">
                <div class="flex justify-between">
                  <span class="text-terminal-dim">ESG得分</span>
                  <span class="font-mono text-terminal-primary">{{ item.score?.toFixed(2) || '--' }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-terminal-dim">环境(E)</span>
                  <span class="font-mono text-green-400">{{ item.environment_score?.toFixed(2) || '--' }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-terminal-dim">社会(S)</span>
                  <span class="font-mono text-blue-400">{{ item.social_score?.toFixed(2) || '--' }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-terminal-dim">治理(G)</span>
                  <span class="font-mono text-purple-400">{{ item.governance_score?.toFixed(2) || '--' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-else-if="!loading && !compareError" class="text-center py-12 text-terminal-dim">
          <div class="text-4xl mb-2">⚖️</div>
          <div class="text-sm">输入多个股票代码进行ESG对比分析</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { apiFetch } from '../utils/api.js'
import { useApiError } from '../composables/useApiError.js'
import { safeDispose } from '../utils/chartManager.js'
import MobileScrollableTabs from './mobile/MobileScrollableTabs.vue'

const { handleError } = useApiError({ showToast: false })

const tabs = [
  { key: 'rank', label: 'ESG排名' },
  { key: 'rating', label: '评级查询' },
  { key: 'carbon', label: '碳排放' },
  { key: 'history', label: '历史趋势' },
  { key: 'compare', label: '对比分析' },
]

const activeTab = ref('rank')
const loading = ref(false)
const lastUpdate = ref(null)

// ESG评级查询
const symbolInput = ref('')
const hasSearched = ref(false)
const ratings = ref([])
const ratingError = ref(null)
const radarChartRef = ref(null)
let radarChartInstance = null

// 碳排放数据
const carbonData = ref([])
const carbonError = ref(null)

// ESG排名 - 分页和排序
const rankItems = ref([])
const rankError = ref(null)
const page = ref(1)
const pageSize = ref(20)
const totalPages = ref(1)
const sortField = ref('score')
const sortOrder = ref('desc')

// 历史趋势
const historySymbol = ref('')
const historyData = ref([])
const historyError = ref(null)
const historyChartRef = ref(null)
let historyChartInstance = null

// 对比分析
const compareSymbols = ref('')
const compareData = ref([])
const compareError = ref(null)

let _fetchController = null  // AbortController：组件卸载时取消 pending 请求

// 计算是否有ESG分数
const hasEsgScores = computed(() => {
  return ratings.value.some(r => 
    r.environment_score || r.social_score || r.governance_score
  )
})

async function fetchRankData() {
  rankError.value = null
  try {
    // Abort any pending request before starting a new one
    _fetchController?.abort()
    _fetchController = new AbortController()
    const res = await apiFetch(`/api/v1/esg/rank?page=${page.value}&page_size=${pageSize.value}&sort_by=${sortField.value}&sort_order=${sortOrder.value}`, { timeoutMs: 30000, signal: _fetchController.signal })
    if (res?.items) {
      rankItems.value = res.items
      totalPages.value = res.total_pages || Math.ceil((res.total || res.items.length) / pageSize.value)
      lastUpdate.value = new Date().toISOString()
    }
  } catch (e) {
    // Ignore abort errors silently
    if (e.name === 'AbortError' || e.message?.includes('aborted')) return
    const { userMessage } = handleError(e, { context: 'ESG排名' })
    rankError.value = userMessage || '获取ESG排名失败'
  } finally {
    _fetchController = null
  }
}

function prevPage() {
  if (page.value > 1) {
    page.value--
    fetchRankData()
  }
}

function nextPage() {
  if (page.value < totalPages.value) {
    page.value++
    fetchRankData()
  }
}

function sortBy(field) {
  if (sortField.value === field) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortField.value = field
    sortOrder.value = 'desc'
  }
  page.value = 1
  fetchRankData()
}

function exportCSV() {
  if (rankItems.value.length === 0) return
  
  const headers = ['排名', '股票代码', '股票名称', '评级', '得分', '评级日期']
  const rows = rankItems.value.map((item, index) => [
    index + 1 + (page.value - 1) * pageSize.value,
    item.symbol,
    item.name,
    item.rating,
    item.score?.toFixed(2) || '--',
    item.date || '--'
  ])
  
  const csvContent = [headers, ...rows].map(row => row.join(',')).join('\n')
  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `esg_rank_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

async function fetchCarbonData() {
  carbonError.value = null
  try {
    // Abort any pending request before starting a new one
    _fetchController?.abort()
    _fetchController = new AbortController()
    const res = await apiFetch('/api/v1/esg/carbon', { timeoutMs: 30000, signal: _fetchController.signal })
    if (res?.carbon_data) {
      carbonData.value = res.carbon_data
    }
  } catch (e) {
    // Ignore abort errors silently
    if (e.name === 'AbortError' || e.message?.includes('aborted')) return
    const { userMessage } = handleError(e, { context: '碳排放数据' })
    carbonError.value = userMessage || '获取碳排放数据失败'
  } finally {
    _fetchController = null
  }
}

async function searchRating() {
  if (!symbolInput.value.trim()) return
  
  loading.value = true
  hasSearched.value = true
  ratingError.value = null
  
  try {
    // Abort any pending request before starting a new one
    _fetchController?.abort()
    _fetchController = new AbortController()
    const res = await apiFetch(`/api/v1/esg/rating/${symbolInput.value.trim()}`, { timeoutMs: 30000, signal: _fetchController.signal })
    if (res?.ratings) {
      ratings.value = res.ratings
      await nextTick()
      drawRadarChart()
    }
  } catch (e) {
    // Ignore abort errors silently
    if (e.name === 'AbortError' || e.message?.includes('aborted')) return
    const { userMessage } = handleError(e, { context: 'ESG评级' })
    ratingError.value = userMessage || '获取ESG评级失败'
    ratings.value = []
  } finally {
    _fetchController = null
    loading.value = false
  }
}

async function fetchHistoryData() {
  if (!historySymbol.value.trim()) return
  
  historyError.value = null
  loading.value = true
  
  try {
    // Abort any pending request before starting a new one
    _fetchController?.abort()
    _fetchController = new AbortController()
    const res = await apiFetch(`/api/v1/esg/history/${historySymbol.value.trim()}?months=12`, { timeoutMs: 30000, signal: _fetchController.signal })
    if (res?.history) {
      historyData.value = res.history
      await nextTick()
      drawHistoryChart()
    }
  } catch (e) {
    // Ignore abort errors silently
    if (e.name === 'AbortError' || e.message?.includes('aborted')) return
    const { userMessage } = handleError(e, { context: 'ESG历史趋势' })
    historyError.value = userMessage || '获取历史趋势失败'
    historyData.value = []
  } finally {
    _fetchController = null
    loading.value = false
  }
}

function drawHistoryChart() {
  const echarts = window.echarts
  if (!echarts || !historyChartRef.value) return
  
  if (!historyChartInstance) {
    historyChartInstance = echarts.init(historyChartRef.value)
  }
  
  const colors = getChartColors()
  const data = historyData.value
  
  historyChartInstance.setOption({
    tooltip: { 
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    legend: {
      data: ['ESG得分', '环境(E)', '社会(S)', '治理(G)'],
      textStyle: { color: colors.text, fontSize: 11 },
      top: 0
    },
    grid: {
      left: '3%', right: '4%', bottom: '3%', top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: data.map(d => d.date || d.month),
      axisLine: { lineStyle: { color: colors.text + '40' } },
      axisLabel: { color: colors.text, fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      min: 0, max: 100,
      axisLine: { lineStyle: { color: colors.text + '40' } },
      axisLabel: { color: colors.text, fontSize: 10 },
      splitLine: { lineStyle: { color: colors.text + '20' } }
    },
    series: [
      {
        name: 'ESG得分', type: 'line',
        data: data.map(d => d.score),
        lineStyle: { color: colors.primary, width: 2 },
        itemStyle: { color: colors.primary }
      },
      {
        name: '环境(E)', type: 'line',
        data: data.map(d => d.environment_score),
        lineStyle: { color: colors.green, width: 1.5 },
        itemStyle: { color: colors.green }
      },
      {
        name: '社会(S)', type: 'line',
        data: data.map(d => d.social_score),
        lineStyle: { color: colors.blue, width: 1.5 },
        itemStyle: { color: colors.blue }
      },
      {
        name: '治理(G)', type: 'line',
        data: data.map(d => d.governance_score),
        lineStyle: { color: colors.purple, width: 1.5 },
        itemStyle: { color: colors.purple }
      }
    ]
  })
}

async function fetchCompareData() {
  const symbols = compareSymbols.value.split(',').map(s => s.trim()).filter(s => s)
  if (symbols.length < 2 || symbols.length > 5) {
    compareError.value = '请输入2-5个股票代码，用逗号分隔'
    return
  }
  
  compareError.value = null
  loading.value = true
  
  try {
    // Abort any pending request before starting a new one
    _fetchController?.abort()
    _fetchController = new AbortController()
    const res = await apiFetch(`/api/v1/esg/compare?symbols=${symbols.join(',')}`, { timeoutMs: 30000, signal: _fetchController.signal })
    if (res?.comparison) {
      compareData.value = res.comparison
    }
  } catch (e) {
    // Ignore abort errors silently
    if (e.name === 'AbortError' || e.message?.includes('aborted')) return
    const { userMessage } = handleError(e, { context: 'ESG对比分析' })
    compareError.value = userMessage || '获取对比数据失败'
    compareData.value = []
  } finally {
    _fetchController = null
    loading.value = false
  }
}

async function switchTab(tabKey) {
  activeTab.value = tabKey
  
  if (tabKey === 'rank' && rankItems.value.length === 0) {
    loading.value = true
    await fetchRankData()
    loading.value = false
  } else if (tabKey === 'carbon' && carbonData.value.length === 0) {
    loading.value = true
    await fetchCarbonData()
    loading.value = false
  }
}

async function refreshCurrentTab() {
  loading.value = true
  
  if (activeTab.value === 'rank') {
    await fetchRankData()
  } else if (activeTab.value === 'carbon') {
    await fetchCarbonData()
  } else if (activeTab.value === 'rating' && symbolInput.value.trim()) {
    await searchRating()
  } else if (activeTab.value === 'history' && historySymbol.value.trim()) {
    await fetchHistoryData()
  } else if (activeTab.value === 'compare' && compareSymbols.value.trim()) {
    await fetchCompareData()
  }
  
  loading.value = false
}

function getChartColors() {
  return {
    primary: getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#0F52BA',
    text: getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E',
    green: '#51CF66',
    blue: '#4DABF7',
    purple: '#BE4BDB',
  }
}

function drawRadarChart() {
  const echarts = window.echarts
  if (!echarts || !radarChartRef.value) return
  
  const rating = ratings.value.find(r => 
    r.environment_score || r.social_score || r.governance_score
  )
  
  if (!rating) return
  
  if (!radarChartInstance) {
    radarChartInstance = echarts.init(radarChartRef.value)
  }
  
  const colors = getChartColors()
  
  const data = [
    { name: '环境(E)', value: rating.environment_score || 0 },
    { name: '社会(S)', value: rating.social_score || 0 },
    { name: '治理(G)', value: rating.governance_score || 0 },
  ]
  
  radarChartInstance.setOption({
    tooltip: { 
      trigger: 'item',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      textStyle: { color: '#E5E7EB', fontSize: 12 }
    },
    radar: {
      indicator: data.map(d => ({ name: d.name, max: 100 })),
      axisName: { color: colors.text, fontSize: 11 },
      splitLine: { lineStyle: { color: colors.text + '30' } },
      splitArea: { areaStyle: { color: ['rgba(15, 23, 42, 0.2)', 'rgba(15, 23, 42, 0.1)'] } },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    series: [{
      type: 'radar',
      data: [{
        value: data.map(d => d.value),
        name: 'ESG评分',
        areaStyle: { color: colors.primary + '40' },
        lineStyle: { color: colors.primary, width: 2 },
        itemStyle: { color: colors.primary }
      }]
    }]
  })
}

function formatTime(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function formatVolume(val) {
  if (val === null || val === undefined) return '--'
  if (val >= 10000) {
    return (val / 10000).toFixed(2) + '万吨'
  }
  return val.toFixed(2) + '吨'
}

function getRatingClass(rating) {
  if (!rating) return 'bg-terminal-dim/20 text-terminal-dim'
  
  if (rating.includes('AAA') || rating.includes('AA') || rating === 'A') {
    return 'bg-green-500/20 text-green-400'
  }
  if (rating.includes('BBB') || rating.includes('BB') || rating === 'B') {
    return 'bg-blue-500/20 text-blue-400'
  }
  return 'bg-yellow-500/20 text-yellow-400'
}

function handleResize() {
  radarChartInstance?.resize()
  historyChartInstance?.resize()
}

onMounted(async () => {
  loading.value = true
  await fetchRankData()
  loading.value = false
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  _fetchController?.abort()
  _fetchController = null
  safeDispose(radarChartInstance)
  safeDispose(historyChartInstance)
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.bg-terminal-panel {
  background: var(--bg-secondary, #1a1f2e);
}

.bg-terminal-bg {
  background: var(--bg-primary, #0f1419);
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

.border-theme-secondary {
  border-color: var(--border-color, #2d3748);
}

.divide-theme-secondary > * + * {
  border-color: var(--border-color, #2d3748);
}

.text-bearish {
  color: var(--color-down, #FF6B6B);
}

.bg-bearish\/10 {
  background: rgba(255, 107, 107, 0.1);
}

.bg-bearish\/20 {
  background: rgba(255, 107, 107, 0.2);
}

.border-bearish\/30 {
  border-color: rgba(255, 107, 107, 0.3);
}
</style>
