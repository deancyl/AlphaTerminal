/**
 * Strategy Parser - Parse IndicatorStrategy DSL annotations
 * 
 * Supported annotations:
 * - @name Strategy name
 * - @description Strategy description
 * - @param param_name type default_value description
 * - @strategy key value (e.g., stopLossPct 2)
 */

/**
 * Parse strategy code annotations
 * @param {string} code - Strategy code with annotations
 * @returns {Object} Parsed metadata { name, description, parameters, strategySettings }
 */
export function parseAnnotations(code) {
  if (!code || typeof code !== 'string') {
    return { name: '', description: '', parameters: {}, strategySettings: {} }
  }

  const lines = code.split('\n')
  const result = {
    name: '',
    description: '',
    parameters: {},
    strategySettings: {
      stopLossPct: 2.0,
      takeProfitPct: 6.0,
      entryPct: 1.0,
      trailingEnabled: false,
      trailingStopPct: 0.0,
      trailingActivationPct: 0.0,
      tradeDirection: 'both'
    }
  }

  // Regex patterns
  const namePattern = /^#\s*@name\s+(.+)$/
  const descPattern = /^#\s*@description\s+(.+)$/
  const paramPattern = /^#\s*@param\s+(\w+)\s+(\w+)\s+(\S+)\s+(.+)$/
  const strategyPattern = /^#\s*@strategy\s+(\w+)\s+(.+)$/

  for (const line of lines) {
    const trimmed = line.trim()

    // Parse @name
    const nameMatch = trimmed.match(namePattern)
    if (nameMatch) {
      result.name = nameMatch[1].trim()
      continue
    }

    // Parse @description
    const descMatch = trimmed.match(descPattern)
    if (descMatch) {
      result.description = descMatch[1].trim()
      continue
    }

    // Parse @param
    const paramMatch = trimmed.match(paramPattern)
    if (paramMatch) {
      const [, paramName, paramType, defaultValue, paramDesc] = paramMatch
      result.parameters[paramName.trim()] = {
        type: paramType.trim(),
        default: parseParamValue(defaultValue.trim(), paramType.trim()),
        description: paramDesc.trim()
      }
      continue
    }

    // Parse @strategy
    const strategyMatch = trimmed.match(strategyPattern)
    if (strategyMatch) {
      const [, key, value] = strategyMatch
      const settingKey = key.trim()
      const settingValue = value.trim()

      // Map strategy settings
      if (settingKey === 'stopLossPct') {
        result.strategySettings.stopLossPct = parseFloat(settingValue) || 2.0
      } else if (settingKey === 'takeProfitPct') {
        result.strategySettings.takeProfitPct = parseFloat(settingValue) || 6.0
      } else if (settingKey === 'entryPct') {
        result.strategySettings.entryPct = parseFloat(settingValue) || 1.0
      } else if (settingKey === 'trailingEnabled') {
        result.strategySettings.trailingEnabled = settingValue.toLowerCase() === 'true'
      } else if (settingKey === 'trailingStopPct') {
        result.strategySettings.trailingStopPct = parseFloat(settingValue) || 0.0
      } else if (settingKey === 'trailingActivationPct') {
        result.strategySettings.trailingActivationPct = parseFloat(settingValue) || 0.0
      } else if (settingKey === 'tradeDirection') {
        result.strategySettings.tradeDirection = settingValue.toLowerCase()
      }
    }
  }

  return result
}

/**
 * Parse parameter value based on type
 * @param {string} value - String value
 * @param {string} type - Parameter type (int, float, bool, str)
 * @returns {*} Parsed value
 */
function parseParamValue(value, type) {
  if (type === 'int') {
    return parseInt(value, 10) || 0
  } else if (type === 'float') {
    return parseFloat(value) || 0.0
  } else if (type === 'bool') {
    return value.toLowerCase() === 'true'
  }
  return value
}

/**
 * Inject parameters into strategy code
 * Replaces ${param_name} placeholders with actual values
 * @param {string} code - Strategy code
 * @param {Object} params - Parameter values { param_name: value }
 * @returns {string} Code with injected parameters
 */
export function injectParameters(code, params) {
  if (!code || !params || typeof params !== 'object') {
    return code || ''
  }

  let result = code

  // Replace ${param_name} placeholders
  for (const [key, value] of Object.entries(params)) {
    const placeholder = `\${${key}}`
    result = result.split(placeholder).join(String(value))
  }

  return result
}

/**
 * Validate strategy code
 * @param {string} code - Strategy code
 * @returns {Object} { valid: boolean, errors: string[] }
 */
export function validateStrategy(code) {
  const errors = []

  if (!code || typeof code !== 'string') {
    return { valid: false, errors: ['策略代码不能为空'] }
  }

  // Check for forbidden patterns (security)
  const forbiddenPatterns = [
    'import os',
    'import sys',
    'import subprocess',
    'import multiprocessing',
    'import threading',
    'import socket',
    'import urllib',
    'import http',
    'import requests',
    'eval(',
    'exec(',
    'open(',
    'file(',
    '__import__',
    'compile(',
    'getattr(',
    'setattr(',
    'delattr('
  ]

  for (const pattern of forbiddenPatterns) {
    if (code.includes(pattern)) {
      errors.push(`代码包含禁止的模式: ${pattern}`)
    }
  }

  // Check for required output variable
  if (!code.includes('output')) {
    errors.push('代码必须定义 output 变量')
  }

  // Check for required annotations
  const metadata = parseAnnotations(code)
  if (!metadata.name) {
    errors.push('缺少 @name 注解')
  }

  // Check for signals in output
  if (code.includes('output') && !code.includes('signals')) {
    errors.push('output 必须包含 signals 字段')
  }

  return {
    valid: errors.length === 0,
    errors
  }
}

/**
 * Extract parameter definitions from code
 * @param {string} code - Strategy code
 * @returns {Array} Array of parameter definitions [{ name, type, default, description }]
 */
export function extractParameters(code) {
  const metadata = parseAnnotations(code)
  return Object.entries(metadata.parameters).map(([name, def]) => ({
    name,
    type: def.type,
    default: def.default,
    description: def.description
  }))
}

/**
 * Generate parameter form schema from code
 * @param {string} code - Strategy code
 * @returns {Array} Form schema for UI rendering
 */
export function generateParamSchema(code) {
  const params = extractParameters(code)
  return params.map(p => ({
    key: p.name,
    label: p.description || p.name,
    type: p.type === 'int' ? 'number' : p.type === 'float' ? 'number' : p.type === 'bool' ? 'checkbox' : 'text',
    default: p.default,
    step: p.type === 'float' ? '0.1' : undefined,
    min: p.type === 'int' ? 1 : p.type === 'float' ? 0 : undefined
  }))
}
