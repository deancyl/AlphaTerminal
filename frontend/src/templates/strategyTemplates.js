/**
 * Strategy Templates - Pre-built IndicatorStrategy templates
 */

export const STRATEGY_TEMPLATES = {
  ma_cross: {
    id: 'ma_cross',
    name: '均线金叉',
    nameEn: 'MA Cross',
    icon: '📈',
    category: 'trend',
    market: ['AStock', 'USStock', 'Crypto', 'Forex'],
    description: '短期均线上穿长期均线时买入，下穿时卖出',
    params: {
      fast_period: { type: 'int', default: 5, description: '短期均线周期' },
      slow_period: { type: 'int', default: 20, description: '长期均线周期' }
    },
    riskSettings: {
      stopLossPct: 2.0,
      takeProfitPct: 6.0
    },
    code: `# @name 均线金叉策略
# @description 短期均线上穿长期均线时买入，下穿时卖出
# @param fast_period int 5 短期均线周期
# @param slow_period int 20 长期均线周期
# @strategy stopLossPct 2
# @strategy takeProfitPct 6

ma_fast = df['close'].rolling(fast_period).mean()
ma_slow = df['close'].rolling(slow_period).mean()
buy = (ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))
sell = (ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))
output = {
    'indicators': {'ma_fast': ma_fast, 'ma_slow': ma_slow},
    'signals': {'buy': buy, 'sell': sell}
}`
  },

  rsi_oversold: {
    id: 'rsi_oversold',
    name: 'RSI 超卖',
    nameEn: 'RSI Oversold',
    icon: '📊',
    category: 'mean_reversion',
    market: ['AStock', 'USStock', 'Crypto', 'Forex'],
    description: 'RSI低于超卖值时买入，高于超买值时卖出',
    params: {
      rsi_period: { type: 'int', default: 14, description: 'RSI周期' },
      rsi_buy: { type: 'float', default: 30, description: '超卖阈值' },
      rsi_sell: { type: 'float', default: 70, description: '超买阈值' }
    },
    riskSettings: {
      stopLossPct: 3.0,
      takeProfitPct: 8.0
    },
    code: `# @name RSI 超买超卖策略
# @description RSI低于超卖值时买入，高于超买值时卖出
# @param rsi_period int 14 RSI周期
# @param rsi_buy float 30 超卖阈值
# @param rsi_sell float 70 超买阈值
# @strategy stopLossPct 3
# @strategy takeProfitPct 8

delta = df['close'].diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
avg_gain = gain.rolling(window=rsi_period).mean()
avg_loss = loss.rolling(window=rsi_period).mean()
rs = avg_gain / avg_loss
rsi = 100 - (100 / (1 + rs))
buy = rsi < rsi_buy
sell = rsi > rsi_sell
output = {
    'indicators': {'rsi': rsi},
    'signals': {'buy': buy, 'sell': sell}
}`
  },

  bollinger_bands: {
    id: 'bollinger_bands',
    name: '布林带回归',
    nameEn: 'Bollinger Bands',
    icon: '📉',
    category: 'mean_reversion',
    market: ['AStock', 'USStock', 'Crypto', 'Forex'],
    description: '价格触及布林带下轨时买入，上轨时卖出',
    params: {
      bb_period: { type: 'int', default: 20, description: '布林带周期' },
      bb_std: { type: 'float', default: 2.0, description: '标准差倍数' }
    },
    riskSettings: {
      stopLossPct: 2.0,
      takeProfitPct: 5.0
    },
    code: `# @name 布林带均值回归策略
# @description 价格触及布林带下轨时买入，上轨时卖出
# @param bb_period int 20 布林带周期
# @param bb_std float 2 布林带标准差倍数
# @strategy stopLossPct 2
# @strategy takeProfitPct 5

middle = df['close'].rolling(bb_period).mean()
std = df['close'].rolling(bb_period).std()
upper = middle + bb_std * std
lower = middle - bb_std * std
buy = (df['close'] < lower) & (df['close'].shift(1) >= lower.shift(1))
sell = (df['close'] > upper) & (df['close'].shift(1) <= upper.shift(1))
output = {
    'indicators': {'upper': upper, 'middle': middle, 'lower': lower},
    'signals': {'buy': buy, 'sell': sell}
}`
  },

  macd_cross: {
    id: 'macd_cross',
    name: 'MACD 金叉',
    nameEn: 'MACD Cross',
    icon: '⚡',
    category: 'trend',
    market: ['AStock', 'USStock', 'Crypto', 'Forex'],
    description: 'DIF上穿DEA买入，下穿卖出',
    params: {
      macd_fast: { type: 'int', default: 12, description: '快线周期' },
      macd_slow: { type: 'int', default: 26, description: '慢线周期' },
      macd_signal: { type: 'int', default: 9, description: '信号线周期' }
    },
    riskSettings: {
      stopLossPct: 2.0,
      takeProfitPct: 6.0
    },
    code: `# @name MACD 金叉死叉策略
# @description DIF上穿DEA买入，下穿卖出
# @param macd_fast int 12 快线周期
# @param macd_slow int 26 慢线周期
# @param macd_signal int 9 信号线周期
# @strategy stopLossPct 2
# @strategy takeProfitPct 6

ema_fast = df['close'].ewm(span=macd_fast, adjust=False).mean()
ema_slow = df['close'].ewm(span=macd_slow, adjust=False).mean()
dif = ema_fast - ema_slow
dea = dif.ewm(span=macd_signal, adjust=False).mean()
histogram = (dif - dea) * 2
buy = (dif > dea) & (dif.shift(1) <= dea.shift(1))
sell = (dif < dea) & (dif.shift(1) >= dea.shift(1))
output = {
    'indicators': {'dif': dif, 'dea': dea, 'histogram': histogram},
    'signals': {'buy': buy, 'sell': sell}
}`
  },

  kdj_cross: {
    id: 'kdj_cross',
    name: 'KDJ 金叉',
    nameEn: 'KDJ Cross',
    icon: '🎯',
    category: 'oscillator',
    market: ['AStock', 'USStock'],
    description: 'K线上穿D线买入，下穿卖出',
    params: {
      kdj_n: { type: 'int', default: 9, description: 'KDJ周期' },
      kdj_m1: { type: 'int', default: 3, description: 'K值平滑' },
      kdj_m2: { type: 'int', default: 3, description: 'D值平滑' }
    },
    riskSettings: {
      stopLossPct: 2.5,
      takeProfitPct: 7.0
    },
    code: `# @name KDJ 金叉死叉策略
# @description K线上穿D线买入，下穿卖出
# @param kdj_n int 9 KDJ周期
# @param kdj_m1 int 3 K值平滑周期
# @param kdj_m2 int 3 D值平滑周期
# @strategy stopLossPct 2.5
# @strategy takeProfitPct 7

lowest_low = df['low'].rolling(window=kdj_n).min()
highest_high = df['high'].rolling(window=kdj_n).max()
rsv = (df['close'] - lowest_low) / (highest_high - lowest_low) * 100
k = rsv.ewm(com=kdj_m1-1, adjust=False).mean()
d = k.ewm(com=kdj_m2-1, adjust=False).mean()
j = 3 * k - 2 * d
buy = (k > d) & (k.shift(1) <= d.shift(1)) & (k < 30)
sell = (k < d) & (k.shift(1) >= d.shift(1)) & (k > 70)
output = {
    'indicators': {'k': k, 'd': d, 'j': j},
    'signals': {'buy': buy, 'sell': sell}
}`
  },

  dual_thrust: {
    id: 'dual_thrust',
    name: 'Dual Thrust',
    nameEn: 'Dual Thrust',
    icon: '🚀',
    category: 'breakout',
    market: ['AStock', 'USStock', 'Futures'],
    description: '价格突破区间时入场，经典日内突破策略',
    params: {
      dt_period: { type: 'int', default: 4, description: '回溯周期' },
      dt_k1: { type: 'float', default: 0.5, description: '上轨系数' },
      dt_k2: { type: 'float', default: 0.5, description: '下轨系数' }
    },
    riskSettings: {
      stopLossPct: 1.5,
      takeProfitPct: 3.0
    },
    code: `# @name Dual Thrust 突破策略
# @description 价格突破区间时入场
# @param dt_period int 4 回溯周期
# @param dt_k1 float 0.5 上轨系数
# @param dt_k2 float 0.5 下轨系数
# @strategy stopLossPct 1.5
# @strategy takeProfitPct 3

hh = df['high'].rolling(window=dt_period).max()
ll = df['low'].rolling(window=dt_period).min()
hc = df['close'].rolling(window=dt_period).max()
lc = df['close'].rolling(window=dt_period).min()
range_val = max(hh - ll, hc - lc)
upper = df['open'] + dt_k1 * range_val
lower = df['open'] - dt_k2 * range_val
buy = df['close'] > upper.shift(1)
sell = df['close'] < lower.shift(1)
output = {
    'indicators': {'upper': upper, 'lower': lower, 'range': range_val},
    'signals': {'buy': buy, 'sell': sell}
}`
  }
}

export const TEMPLATE_CATEGORIES = {
  trend: { name: '趋势跟踪', icon: '📈' },
  mean_reversion: { name: '均值回归', icon: '📊' },
  oscillator: { name: '震荡指标', icon: '🎯' },
  breakout: { name: '突破策略', icon: '🚀' }
}

export const MARKET_OPTIONS = [
  { value: 'AStock', label: 'A股', icon: '🇨🇳' },
  { value: 'USStock', label: '美股', icon: '🇺🇸' },
  { value: 'Crypto', label: '加密货币', icon: '₿' },
  { value: 'Forex', label: '外汇', icon: '💱' },
  { value: 'Futures', label: '期货', icon: '📈' }
]

export function getTemplateById(id) {
  return STRATEGY_TEMPLATES[id] || null
}

export function getTemplatesByCategory(category) {
  return Object.values(STRATEGY_TEMPLATES).filter(t => t.category === category)
}

export function getTemplatesByMarket(market) {
  return Object.values(STRATEGY_TEMPLATES).filter(t => t.market.includes(market))
}
