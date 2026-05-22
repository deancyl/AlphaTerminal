/**
 * Options Glossary Data
 * 
 * Plain-language explanations for options terminology
 * Designed for non-professional users
 */

export const optionsGlossary = {
  delta: {
    term: 'Delta (德尔塔)',
    shortExplanation: '期权价格随股价变化的幅度',
    detailedExplanation: 'Delta 告诉你股价每涨1元，期权价格大概涨多少。看涨期权Delta在0-1之间，看跌期权在-1到0之间。',
    practicalTip: 'Delta接近1说明期权走势和股价很像，接近0说明期权对股价变化不敏感。',
    colorContext: 'neutral'
  },
  
  gamma: {
    term: 'Gamma (伽马)',
    shortExplanation: 'Delta的变化速度',
    detailedExplanation: 'Gamma衡量Delta的稳定性。Gamma高说明Delta变化快，期权价格波动大。',
    practicalTip: 'Gamma在接近行权价时最大，这时期权价格变化最剧烈。',
    colorContext: 'warning'
  },
  
  theta: {
    term: 'Theta (西塔)',
    shortExplanation: '时间流逝对期权价格的影响',
    detailedExplanation: 'Theta是每天因时间流逝损失的期权价值。期权越接近到期日，时间价值流失越快。',
    practicalTip: 'Theta通常是负数，表示每天损失的价值。买期权要注意时间成本！',
    colorContext: 'danger'
  },
  
  vega: {
    term: 'Vega (维加)',
    shortExplanation: '期权价格对波动率变化的敏感度',
    detailedExplanation: 'Vega告诉你波动率每变化1%，期权价格变化多少。波动率上升，期权价格通常上涨。',
    practicalTip: 'Vega高说明期权价格对市场恐慌/乐观情绪敏感。',
    colorContext: 'neutral'
  },
  
  iv: {
    term: 'IV (隐含波动率)',
    shortExplanation: '市场对未来价格波动的预期',
    detailedExplanation: 'IV反映市场对未来30天股价波动的预期。IV高说明市场预期大波动，IV低说明预期平稳。',
    practicalTip: 'IV高时买期权贵，IV低时买期权便宜。',
    colorContext: 'warning'
  },
  
  pcr: {
    term: 'PCR (看跌看涨比率)',
    shortExplanation: '看跌期权与看涨期权成交量的比值',
    detailedExplanation: 'PCR = 看跌期权成交量 / 看涨期权成交量。PCR<0.8说明市场乐观，PCR>1.2说明市场悲观。',
    practicalTip: '极端PCR可能是反向指标：极度悲观时可能是买入机会。',
    colorContext: 'sentiment'
  },
  
  atm: {
    term: 'ATM (平值)',
    shortExplanation: '行权价接近当前股价',
    detailedExplanation: 'ATM期权的行权价和当前股价差不多，这类期权流动性最好。',
    practicalTip: 'ATM期权适合新手，价格适中，流动性好。',
    colorContext: 'highlight'
  },
  
  otm: {
    term: 'OTM (虚值)',
    shortExplanation: '行权价远离当前股价',
    detailedExplanation: 'OTM看涨期权的行权价高于现价，OTM看跌期权的行权价低于现价。',
    practicalTip: 'OTM期权便宜但可能一文不值，适合高风险投机。',
    colorContext: 'muted'
  },
  
  itm: {
    term: 'ITM (实值)',
    shortExplanation: '行权价对持有者有利',
    detailedExplanation: 'ITM看涨期权的行权价低于现价，ITM看跌期权的行权价高于现价。',
    practicalTip: 'ITM期权有内在价值，但价格也更高。',
    colorContext: 'success'
  },
  
  strike: {
    term: 'Strike (行权价)',
    shortExplanation: '期权到期时可以买入/卖出股票的价格',
    detailedExplanation: '行权价是期权合约约定的买卖价格。看涨期权可以在行权价买入股票，看跌期权可以在行权价卖出股票。',
    practicalTip: '选择行权价要考虑你的预期和风险承受能力。',
    colorContext: 'neutral'
  },
  
  call: {
    term: 'Call (看涨期权)',
    shortExplanation: '有权在到期日以行权价买入股票',
    detailedExplanation: '买入看涨期权 = 买入股票的"优惠券"。股价涨过行权价就赚钱。',
    practicalTip: '看涨期权适合看多后市，风险有限（期权费），收益无限。',
    colorContext: 'bullish'
  },
  
  put: {
    term: 'Put (看跌期权)',
    shortExplanation: '有权在到期日以行权价卖出股票',
    detailedExplanation: '买入看跌期权 = 买入股票的"保险"。股价跌破行权价就赚钱。',
    practicalTip: '看跌期权适合看空后市或对冲持仓风险。',
    colorContext: 'bearish'
  },
  
  openInterest: {
    term: 'Open Interest (持仓量)',
    shortExplanation: '市场上未平仓的期权合约数量',
    detailedExplanation: '持仓量高说明这个期权很受欢迎，流动性好。持仓量低可能买卖困难。',
    practicalTip: '选择持仓量高的期权，买卖价差小，成交快。',
    colorContext: 'volume'
  }
}

export const pcrInterpretations = [
  { range: [0, 0.6], label: '极度乐观', color: 'bullish', tip: '市场情绪非常乐观，注意反向风险' },
  { range: [0.6, 0.8], label: '乐观情绪', color: 'bullish', tip: '市场偏向看涨' },
  { range: [0.8, 1.2], label: '市场中性', color: 'neutral', tip: '市场情绪平衡' },
  { range: [1.2, 1.5], label: '悲观情绪', color: 'bearish', tip: '市场偏向看跌' },
  { range: [1.5, Infinity], label: '极度悲观', color: 'bearish', tip: '市场情绪非常悲观，可能是买入机会' }
]

export const ivSmileShapes = [
  { shape: 'smile', label: '微笑型', description: '两端IV高，中间低。市场预期两端价格波动大。' },
  { shape: 'skew', label: '偏斜型', description: '一侧IV明显高于另一侧。市场预期单方向风险。' },
  { shape: 'flat', label: '平坦型', description: 'IV曲线较平。市场预期波动均匀分布。' }
]