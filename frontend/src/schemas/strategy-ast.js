/**
 * Strategy AST Schema Definition
 * 
 * Defines JSON AST structure for visual strategy builder.
 * Supports Top 5 strategies: MA Cross, MACD, RSI, Bollinger, Volume
 */

// ── Strategy Types ────────────────────────────────────────────────────────────

/**
 * @typedef {'strategy'} StrategyType
 */
export const STRATEGY_TYPES = {
  STRATEGY: 'strategy',
}

/**
 * @typedef {'indicator_crossover' | 'indicator_threshold' | 'price_comparison' | 'volume_comparison'} ConditionType
 */
export const CONDITION_TYPES = {
  INDICATOR_CROSSOVER: 'indicator_crossover',    // MA cross, MACD cross
  INDICATOR_THRESHOLD: 'indicator_threshold',    // RSI threshold, Bollinger band
  PRICE_COMPARISON: 'price_comparison',          // Price vs MA
  VOLUME_COMPARISON: 'volume_comparison',        // Volume surge
}

/**
 * @typedef {'MA' | 'MACD' | 'RSI' | 'BOLL' | 'VOLUME'} IndicatorType
 */
export const INDICATOR_TYPES = {
  MA: 'MA',
  MACD: 'MACD',
  RSI: 'RSI',
  BOLL: 'BOLL',
  VOLUME: 'VOLUME',
}

/**
 * @typedef {'cross_above' | 'cross_below' | 'above' | 'below'} DirectionType
 */
export const DIRECTION_TYPES = {
  CROSS_ABOVE: 'cross_above',
  CROSS_BELOW: 'cross_below',
  ABOVE: 'above',
  BELOW: 'below',
}

/**
 * @typedef {'buy' | 'sell'} ActionType
 */
export const ACTION_TYPES = {
  BUY: 'buy',
  SELL: 'sell',
}

// ── Strategy Templates (Top 5) ────────────────────────────────────────────────

/**
 * Predefined strategy templates for visual builder
 */
export const STRATEGY_TEMPLATES = {
  MA_CROSS: {
    id: 'ma_cross',
    name: 'MA金叉策略',
    icon: '📈',
    description: '快均线上穿慢均线买入，下穿卖出',
    category: 'trend',
    conditions: [
      {
        type: CONDITION_TYPES.INDICATOR_CROSSOVER,
        indicator: INDICATOR_TYPES.MA,
        params: { fast_period: 5, slow_period: 20 },
        direction: DIRECTION_TYPES.CROSS_ABOVE,
      },
    ],
    actions: [
      { type: ACTION_TYPES.BUY, quantity: 100 },
      { type: ACTION_TYPES.SELL, signal: DIRECTION_TYPES.CROSS_BELOW },
    ],
    defaultParams: {
      fast_period: { type: 'number', default: 5, min: 2, max: 60, label: '快线周期' },
      slow_period: { type: 'number', default: 20, min: 5, max: 250, label: '慢线周期' },
    },
  },

  MACD_CROSS: {
    id: 'macd_cross',
    name: 'MACD交叉策略',
    icon: '📊',
    description: 'DIF上穿DEA买入，下穿卖出',
    category: 'trend',
    conditions: [
      {
        type: CONDITION_TYPES.INDICATOR_CROSSOVER,
        indicator: INDICATOR_TYPES.MACD,
        params: { fast_period: 12, slow_period: 26, signal_period: 9 },
        direction: DIRECTION_TYPES.CROSS_ABOVE,
      },
    ],
    actions: [
      { type: ACTION_TYPES.BUY, quantity: 100 },
      { type: ACTION_TYPES.SELL, signal: DIRECTION_TYPES.CROSS_BELOW },
    ],
    defaultParams: {
      fast_period: { type: 'number', default: 12, min: 5, max: 30, label: '快线周期' },
      slow_period: { type: 'number', default: 26, min: 10, max: 60, label: '慢线周期' },
      signal_period: { type: 'number', default: 9, min: 3, max: 20, label: '信号线周期' },
    },
  },

  RSI_OVERSOLD: {
    id: 'rsi_oversold',
    name: 'RSI超卖策略',
    icon: '📉',
    description: 'RSI低于超卖线买入，高于超买线卖出',
    category: 'oscillator',
    conditions: [
      {
        type: CONDITION_TYPES.INDICATOR_THRESHOLD,
        indicator: INDICATOR_TYPES.RSI,
        params: { period: 14 },
        threshold: 30,
        direction: DIRECTION_TYPES.BELOW,  // RSI < 30 = oversold
      },
    ],
    actions: [
      { type: ACTION_TYPES.BUY, quantity: 100 },
      { 
        type: ACTION_TYPES.SELL, 
        signal: { indicator: INDICATOR_TYPES.RSI, threshold: 70, direction: DIRECTION_TYPES.ABOVE }
      },
    ],
    defaultParams: {
      period: { type: 'number', default: 14, min: 5, max: 30, label: 'RSI周期' },
      oversold: { type: 'number', default: 30, min: 10, max: 40, label: '超卖线' },
      overbought: { type: 'number', default: 70, min: 60, max: 90, label: '超买线' },
    },
  },

  BOLL_BREAK: {
    id: 'boll_break',
    name: '布林带突破策略',
    icon: '📏',
    description: '价格突破下轨买入，突破上轨卖出',
    category: 'volatility',
    conditions: [
      {
        type: CONDITION_TYPES.INDICATOR_THRESHOLD,
        indicator: INDICATOR_TYPES.BOLL,
        params: { period: 20, std_dev: 2 },
        band: 'lower',
        direction: DIRECTION_TYPES.BELOW,  // Price < lower band
      },
    ],
    actions: [
      { type: ACTION_TYPES.BUY, quantity: 100 },
      { 
        type: ACTION_TYPES.SELL, 
        signal: { indicator: INDICATOR_TYPES.BOLL, band: 'upper', direction: DIRECTION_TYPES.ABOVE }
      },
    ],
    defaultParams: {
      period: { type: 'number', default: 20, min: 5, max: 60, label: '周期' },
      std_dev: { type: 'number', default: 2, min: 1, max: 3, step: 0.5, label: '标准差倍数' },
    },
  },

  VOLUME_SURGE: {
    id: 'volume_surge',
    name: '放量突破策略',
    icon: '📦',
    description: '成交量放大超过均量2倍时买入',
    category: 'volume',
    conditions: [
      {
        type: CONDITION_TYPES.VOLUME_COMPARISON,
        indicator: INDICATOR_TYPES.VOLUME,
        params: { period: 20 },
        multiplier: 2.0,
        direction: DIRECTION_TYPES.ABOVE,  // Volume > 2x average
      },
    ],
    actions: [
      { type: ACTION_TYPES.BUY, quantity: 100 },
    ],
    defaultParams: {
      period: { type: 'number', default: 20, min: 5, max: 60, label: '均量周期' },
      multiplier: { type: 'number', default: 2.0, min: 1.5, max: 5, step: 0.5, label: '放量倍数' },
    },
  },
}

// ── Strategy AST Schema ───────────────────────────────────────────────────────

/**
 * @typedef {Object} StrategyCondition
 * @property {ConditionType} type - Condition type
 * @property {IndicatorType} indicator - Indicator type
 * @property {Object} params - Indicator parameters
 * @property {DirectionType} direction - Direction (cross_above, cross_below, above, below)
 * @property {number} [threshold] - Threshold value (for RSI, etc.)
 * @property {string} [band] - Band type (for Bollinger: 'upper', 'lower', 'middle')
 * @property {number} [multiplier] - Multiplier (for volume surge)
 */

/**
 * @typedef {Object} StrategyAction
 * @property {ActionType} type - Action type (buy, sell)
 * @property {number} [quantity] - Quantity to trade
 * @property {string|Object} [signal] - Signal condition for sell
 */

/**
 * @typedef {Object} StrategyAST
 * @property {StrategyType} type - AST type (always 'strategy')
 * @property {string} name - Strategy name
 * @property {string} [description] - Strategy description
 * @property {StrategyCondition[]} conditions - Entry conditions
 * @property {StrategyAction[]} actions - Trade actions
 * @property {Object} [riskManagement] - Risk management settings
 * @property {number} [riskManagement.stopLossPct] - Stop loss percentage
 * @property {number} [riskManagement.takeProfitPct] - Take profit percentage
 */

/**
 * Create a new strategy AST from template
 * @param {string} templateId - Template ID
 * @param {Object} params - Custom parameters
 * @returns {StrategyAST}
 */
export function createStrategyFromTemplate(templateId, params = {}) {
  const template = STRATEGY_TEMPLATES[templateId]
  if (!template) {
    throw new Error(`Unknown template: ${templateId}`)
  }

  // Deep clone the template
  const ast = JSON.parse(JSON.stringify({
    type: STRATEGY_TYPES.STRATEGY,
    name: template.name,
    description: template.description,
    conditions: template.conditions,
    actions: template.actions,
  }))

  // Apply custom parameters to conditions
  if (params && ast.conditions.length > 0) {
    const condition = ast.conditions[0]
    Object.keys(params).forEach(key => {
      if (condition.params && key in condition.params) {
        condition.params[key] = params[key]
      }
      if (key === 'threshold') {
        condition.threshold = params[key]
      }
      if (key === 'multiplier') {
        condition.multiplier = params[key]
      }
    })
  }

  return ast
}

/**
 * Validate strategy AST
 * @param {StrategyAST} ast - Strategy AST to validate
 * @returns {{ valid: boolean, errors: string[] }}
 */
export function validateStrategyAST(ast) {
  const errors = []

  if (!ast || typeof ast !== 'object') {
    errors.push('Strategy AST must be an object')
    return { valid: false, errors }
  }

  if (ast.type !== STRATEGY_TYPES.STRATEGY) {
    errors.push(`Invalid strategy type: ${ast.type}`)
  }

  if (!ast.name || typeof ast.name !== 'string') {
    errors.push('Strategy name is required')
  }

  if (!Array.isArray(ast.conditions) || ast.conditions.length === 0) {
    errors.push('At least one condition is required')
  } else {
    ast.conditions.forEach((cond, idx) => {
      if (!Object.values(CONDITION_TYPES).includes(cond.type)) {
        errors.push(`Condition ${idx}: invalid type "${cond.type}"`)
      }
      if (!Object.values(INDICATOR_TYPES).includes(cond.indicator)) {
        errors.push(`Condition ${idx}: invalid indicator "${cond.indicator}"`)
      }
      if (!Object.values(DIRECTION_TYPES).includes(cond.direction)) {
        errors.push(`Condition ${idx}: invalid direction "${cond.direction}"`)
      }
    })
  }

  if (!Array.isArray(ast.actions) || ast.actions.length === 0) {
    errors.push('At least one action is required')
  } else {
    ast.actions.forEach((action, idx) => {
      if (!Object.values(ACTION_TYPES).includes(action.type)) {
        errors.push(`Action ${idx}: invalid type "${action.type}"`)
      }
    })
  }

  return {
    valid: errors.length === 0,
    errors,
  }
}

/**
 * Get all available strategy templates
 * @returns {Array<{id: string, name: string, icon: string, description: string, category: string}>}
 */
export function getAvailableTemplates() {
  return Object.values(STRATEGY_TEMPLATES).map(t => ({
    id: t.id,
    name: t.name,
    icon: t.icon,
    description: t.description,
    category: t.category,
  }))
}

/**
 * Get template by ID
 * @param {string} templateId
 * @returns {Object|null}
 */
export function getTemplateById(templateId) {
  return STRATEGY_TEMPLATES[templateId] || null
}

export default {
  STRATEGY_TYPES,
  CONDITION_TYPES,
  INDICATOR_TYPES,
  DIRECTION_TYPES,
  ACTION_TYPES,
  STRATEGY_TEMPLATES,
  createStrategyFromTemplate,
  validateStrategyAST,
  getAvailableTemplates,
  getTemplateById,
}
