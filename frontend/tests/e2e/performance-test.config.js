/**
 * AlphaTerminal 性能测试配置
 * 
 * 测试策略:
 * - 缓存: 冷缓存（每次测试前清除localStorage）
 * - 成功标准: 所有数据渲染完成（包含ECharts图表）
 * - 重复次数: 3次取中位数
 * - 测试数据: 动态选择
 */

export const config = {
  // 项目配置
  baseUrl: 'http://localhost:60100',
  backendUrl: 'http://localhost:8002',
  wsUrl: 'ws://localhost:8002/ws/market',
  
  // 测试策略
  testStrategy: {
    cacheStrategy: 'cold',           // 冷缓存
    successCriteria: 'all-data-rendered',  // 所有数据渲染完成
    repeatability: 'median-of-3',    // 3次取中位数
    dataSelection: 'dynamic'         // 动态选择
  },
  
  // 性能阈值（毫秒）
  thresholds: {
    apiResponse: 1000,      // API响应时间 < 1s
    pageLoad: 3000,         // 页面加载时间 < 3s
    dataRender: 1000,       // 数据渲染时间 < 1s
    totalTime: 1000,        // 总时间（用户视角）< 1s
    
    // Core Web Vitals
    lcp: 2500,              // Largest Contentful Paint < 2.5s
    fid: 100,               // First Input Delay < 100ms
    cls: 0.1                // Cumulative Layout Shift < 0.1
  },
  
  // 测试页面配置
  pages: [
    // 核心页面（P0）
    { id: 'stock', route: '#view=stock', priority: 'P0', module: 'market' },
    { id: 'portfolio', route: '#view=portfolio', priority: 'P0', module: 'portfolio' },
    { id: 'fund', route: '#view=fund', priority: 'P0', module: 'fund' },
    { id: 'bond', route: '#view=bond', priority: 'P0', module: 'bond' },
    { id: 'futures', route: '#view=futures', priority: 'P0', module: 'futures' },
    { id: 'forex', route: '#view=forex', priority: 'P0', module: 'forex' },
    { id: 'macro', route: '#view=macro', priority: 'P0', module: 'macro' },
    
    // AI功能（P1）
    { id: 'strategy-center', route: '#view=strategy-center', priority: 'P1', module: 'ai' },
    { id: 'factor-sandbox', route: '#view=factor-sandbox', priority: 'P1', module: 'ai' },
    { id: 'market-radar', route: '#view=market-radar', priority: 'P1', module: 'ai' },
    { id: 'timemachine', route: '#view=timemachine', priority: 'P1', module: 'ai' },
    { id: 'multi-asset-matrix', route: '#view=multi-asset-matrix', priority: 'P1', module: 'ai' },
    { id: 'walk-forward', route: '#view=walk-forward', priority: 'P1', module: 'ai' },
    
    // 其他页面（P2）
    { id: 'options', route: '#view=options', priority: 'P2', module: 'options' },
    { id: 'global-index', route: '#view=global-index', priority: 'P2', module: 'market' },
    { id: 'research', route: '#view=research', priority: 'P2', module: 'research' },
    { id: 'admin', route: '#view=admin', priority: 'P2', module: 'system' }
  ],
  
  // 管理面板标签（单独测试）
  adminTabs: [
    // 系统与基础设施
    'monitor', 'watchdog', 'logs', 'database', 'layout',
    // 数据引擎
    'sources', 'scheduler', 'cache', 'ratelimit', 'data_gaps',
    // 智能引擎
    'llm', 'tokens', 'cost-attribution', 'agent_tokens', 'mcp',
    // 业务控制
    'backtest', 'performance'
  ],
  
  // 超时配置
  timeout: {
    navigation: 10000,      // 页面导航超时 10s
    dataLoad: 5000,         // 数据加载超时 5s
    apiResponse: 30000      // API响应超时 30s（akshare可能慢）
  }
}

export default config
