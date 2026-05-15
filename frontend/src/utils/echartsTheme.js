function getCSSVar(name, fallback) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

export function getDynamicThemeColors() {
  const themeAttr = document.documentElement.getAttribute('data-theme') || 'dark'
  const isLight = themeAttr === 'light'
  
  return {
    isLight,
    bg: getCSSVar('--bg-surface', '#1E1E1E'),
    grid: getCSSVar('--chart-grid', '#1C2333'),
    axisLine: getCSSVar('--border-base', '#30363D'),
    axisLabel: getCSSVar('--chart-text', '#8B949E'),
    splitLine: getCSSVar('--chart-grid', '#1C2333'),
    crosshair: getCSSVar('--chart-crosshair', 'rgba(240,246,252,0.20)'),
    
    tooltipBg: isLight ? 'rgba(255,255,255,0.96)' : 'rgba(13,17,23,0.95)',
    tooltipBorder: getCSSVar('--border-base', '#30363D'),
    tooltipText: getCSSVar('--text-primary', '#F0F6FC'),
    
    bull: getCSSVar('--color-bull', '#E63946'),
    bullLight: getCSSVar('--color-bull-light', '#FF6B6B'),
    bear: getCSSVar('--color-bear', '#1A936F'),
    bearLight: getCSSVar('--color-bear-light', '#5CD899'),
    
    primary: getCSSVar('--color-primary', '#0F52BA'),
    primaryBg: getCSSVar('--color-primary-bg', 'rgba(15,82,186,0.10)'),
    
    ma5: '#F5A623',
    ma10: '#0F52BA',
    ma20: '#A855F7',
    ma60: '#EC4899',
    
    dif: '#60a5fa',
    dea: '#f87171',
    macdUp: getCSSVar('--color-bull', '#E63946'),
    macdDown: getCSSVar('--color-bear', '#1A936F'),
    
    volUp: getCSSVar('--color-bull', '#E63946'),
    volDown: getCSSVar('--color-bear', '#1A936F'),
    
    overlay: '#f97316',
    oi: '#f59e0b',
    deltaOiUp: getCSSVar('--color-bull', '#E63946'),
    deltaOiDown: getCSSVar('--color-bear', '#1A936F'),
    deltaOiFlat: '#6b7280',
  }
}

export function buildDynamicEChartsTheme() {
  const colors = getDynamicThemeColors()
  
  return {
    backgroundColor: 'transparent',
    
    textStyle: {
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
      fontSize: 10,
      color: colors.axisLabel
    },
    
    categoryAxis: {
      axisLine: { show: true, lineStyle: { color: colors.axisLine, width: 1 } },
      axisTick: { show: false },
      axisLabel: { show: true, color: colors.axisLabel, fontSize: 10, margin: 8 },
      splitLine: { show: true, lineStyle: { color: colors.splitLine, type: 'dashed', width: 0.5 } },
      splitArea: { show: false }
    },
    
    valueAxis: {
      axisLine: { show: true, lineStyle: { color: colors.axisLine, width: 1 } },
      axisTick: { show: false },
      axisLabel: { show: true, color: colors.axisLabel, fontSize: 10, margin: 8 },
      splitLine: { show: true, lineStyle: { color: colors.splitLine, type: 'dashed', width: 0.5 } },
      splitArea: { show: false }
    },
    
    tooltip: {
      backgroundColor: colors.tooltipBg,
      borderColor: colors.tooltipBorder,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: colors.tooltipText, fontSize: 11, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' },
      extraCssText: 'backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); border-radius: 6px;',
      axisPointer: {
        type: 'cross',
        crossStyle: { color: colors.crosshair, type: 'dashed', width: 0.5 },
        lineStyle: { color: colors.crosshair, type: 'dashed', width: 0.5 }
      }
    },
    
    dataZoom: {
      backgroundColor: 'transparent',
      dataBackgroundColor: `rgba(${colors.isLight ? '0,0,0' : '39,39,42'}, 0.3)`,
      fillerColor: colors.primaryBg,
      handleColor: colors.primary,
      handleSize: '80%',
      textStyle: { color: colors.axisLabel, fontSize: 9 },
      borderColor: colors.axisLine,
      borderWidth: 0.5
    },
    
    candlestick: {
      itemStyle: {
        color: colors.bull,
        color0: colors.bear,
        borderColor: colors.bull,
        borderColor0: colors.bear,
        borderWidth: 1
      }
    },
    
    line: { symbol: 'none', lineStyle: { width: 1 } },
    bar: { itemStyle: { barBorderWidth: 0 }, barMaxWidth: 8 },
    
    grid: {
      left: 55, right: 8, top: 10, bottom: 30,
      containLabel: false,
      backgroundColor: 'transparent',
      borderColor: 'transparent',
      borderWidth: 0
    }
  }
}

export const MARKET_COLORS = {
  UP: '#ef4444',
  DOWN: '#10b981',
  FLAT: '#71717a',
  MA5: '#ffffff',
  MA10: '#fbbf24',
  MA20: '#c084fc',
  MA60: '#22d3ee',
  DIF: '#60a5fa',
  DEA: '#f87171',
  MACD_UP: '#ef4444',
  MACD_DOWN: '#10b981',
  VOL_UP: '#ef4444',
  VOL_DOWN: '#10b981',
  OVERLAY: '#f97316',
  OI: '#f59e0b',
  DELTA_OI_UP: '#ef4444',
  DELTA_OI_DOWN: '#10b981',
  DELTA_OI_FLAT: '#6b7280'
}

export function getDynamicMarketColors() {
  const colors = getDynamicThemeColors()
  return {
    UP: colors.bull,
    DOWN: colors.bear,
    FLAT: '#71717a',
    MA5: colors.ma5,
    MA10: colors.ma10,
    MA20: colors.ma20,
    MA60: colors.ma60,
    DIF: colors.dif,
    DEA: colors.dea,
    MACD_UP: colors.macdUp,
    MACD_DOWN: colors.macdDown,
    VOL_UP: colors.volUp,
    VOL_DOWN: colors.volDown,
    OVERLAY: colors.overlay,
    OI: colors.oi,
    DELTA_OI_UP: colors.deltaOiUp,
    DELTA_OI_DOWN: colors.deltaOiDown,
    DELTA_OI_FLAT: colors.deltaOiFlat
  }
}

export const CHART_COLORS = {
  GRID: '#27272a',
  AXIS_LINE: '#27272a',
  AXIS_LABEL: '#71717a',
  SPLIT_LINE: '#27272a',
  TOOLTIP_BG: 'rgba(18, 18, 18, 0.92)',
  TOOLTIP_BORDER: '#3f3f46',
  TOOLTIP_TEXT: '#e4e4e7',
  CROSSHAIR: '#52525b'
}

export function getDynamicChartColors() {
  const colors = getDynamicThemeColors()
  return {
    GRID: colors.grid,
    AXIS_LINE: colors.axisLine,
    AXIS_LABEL: colors.axisLabel,
    SPLIT_LINE: colors.splitLine,
    TOOLTIP_BG: colors.tooltipBg,
    TOOLTIP_BORDER: colors.tooltipBorder,
    TOOLTIP_TEXT: colors.tooltipText,
    CROSSHAIR: colors.crosshair
  }
}

export function buildTooltipFormatter(params, options = {}) {
  const { showVolume = true, showOverlay = true } = options
  const colors = getDynamicThemeColors()
  
  if (!Array.isArray(params) || !params.length) return ''
  
  const kp = params.find(p => p.seriesType === 'candlestick')
  if (!kp || !kp.data) return ''
  
  const [o, c, l, hi] = kp.data
  const isUp = c >= o
  const color = isUp ? colors.bull : colors.bear
  const sign = isUp ? '+' : ''
  const chgPct = o > 0 ? ((c - o) / o * 100).toFixed(2) : '0.00'
  const chgAbs = (c - o).toFixed(2)
  
  let html = `<div style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 11px;">`
  html += `<div style="color: ${colors.axisLabel}; font-size: 10px; margin-bottom: 4px;">${kp.axisValue}</div>`
  html += `<table style="width: 100%; border-collapse: collapse;">`
  html += `<tr><td style="color: ${colors.axisLabel}; padding: 1px 4px;">开</td><td style="color: ${color}; text-align: right; padding: 1px 4px;">${o?.toFixed(2)}</td></tr>`
  html += `<tr><td style="color: ${colors.axisLabel}; padding: 1px 4px;">收</td><td style="color: ${color}; text-align: right; padding: 1px 4px;">${c?.toFixed(2)}</td></tr>`
  html += `<tr><td style="color: ${colors.axisLabel}; padding: 1px 4px;">涨跌</td><td style="color: ${color}; text-align: right; padding: 1px 4px;">${sign}${chgAbs} (${sign}${chgPct}%)</td></tr>`
  html += `<tr><td style="color: ${colors.axisLabel}; padding: 1px 4px;">低</td><td style="color: ${colors.tooltipText}; text-align: right; padding: 1px 4px;">${l?.toFixed(2)}</td></tr>`
  html += `<tr><td style="color: ${colors.axisLabel}; padding: 1px 4px;">高</td><td style="color: ${colors.tooltipText}; text-align: right; padding: 1px 4px;">${hi?.toFixed(2)}</td></tr>`
  
  if (showVolume) {
    const volParam = params.find(p => p.seriesName === 'VOL')
    if (volParam?.value) {
      const vol = volParam.value
      const volStr = vol >= 1e8 ? (vol / 1e8).toFixed(2) + '亿' : vol >= 1e4 ? (vol / 1e4).toFixed(0) + '万' : vol.toLocaleString()
      html += `<tr><td style="color: ${colors.axisLabel}; padding: 1px 4px;">量</td><td style="color: ${colors.tooltipText}; text-align: right; padding: 1px 4px;">${volStr}</td></tr>`
    }
  }
  
  if (showOverlay) {
    const ovParams = params.filter(p => p.seriesType === 'line' && p.seriesName === '对比')
    ovParams.forEach(p => {
      const rawVal = p.value?.[1]
      if (rawVal != null) {
        html += `<tr><td style="color: ${colors.axisLabel}; padding: 1px 4px;">对比</td><td style="color: ${colors.overlay}; text-align: right; padding: 1px 4px;">${rawVal?.toFixed(4)}</td></tr>`
      }
    })
  }
  
  html += `</table></div>`
  return html
}

export function buildAxisOptions(gridIndex, options = {}) {
  const colors = getDynamicChartColors()
  const { showLabel = true, showSplitLine = true, position = 'left', fontSize = 10, formatter } = options
  
  return {
    type: 'value',
    gridIndex,
    position,
    scale: true,
    axisLine: { show: true, lineStyle: { color: colors.AXIS_LINE, width: 1 } },
    axisTick: { show: false },
    axisLabel: { show: showLabel, color: colors.AXIS_LABEL, fontSize, margin: 8, formatter },
    splitLine: { show: showSplitLine, lineStyle: { color: colors.SPLIT_LINE, type: 'dashed', width: 0.5 } },
    splitArea: { show: false }
  }
}

export function buildGridOptions(options = {}) {
  const { top = 10, height = '65%', left = 55, right = 8 } = options
  
  return {
    top, height, left, right,
    containLabel: false,
    backgroundColor: 'transparent',
    borderColor: 'transparent',
    borderWidth: 0
  }
}

export function buildDataZoomOptions(xAxisIndices) {
  const colors = getDynamicThemeColors()
  
  return [
    { type: 'inside', xAxisIndex: xAxisIndices, start: 70, end: 100 },
    {
      type: 'slider',
      xAxisIndex: xAxisIndices,
      bottom: 0,
      height: 16,
      borderColor: colors.axisLine,
      fillerColor: colors.primaryBg,
      handleStyle: { color: colors.primary },
      textStyle: { color: colors.axisLabel, fontSize: 9 },
      dataBackground: {
        lineStyle: { color: colors.tooltipBorder },
        areaStyle: { color: `rgba(${colors.isLight ? '0,0,0' : '39,39,42'}, 0.3)` }
      },
      selectedDataBackground: {
        lineStyle: { color: colors.primary },
        areaStyle: { color: colors.primaryBg }
      }
    }
  ]
}