/**
 * ECharts TradingView-style Dark Theme Configuration
 * Professional financial terminal chart styling
 */

export const ECHARTS_DARK_THEME = {
  backgroundColor: 'transparent',
  
  textStyle: {
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    fontSize: 10,
    color: '#71717a'
  },
  
  title: {
    textStyle: {
      color: '#a1a1aa',
      fontSize: 12,
      fontWeight: 'normal'
    },
    subtextStyle: {
      color: '#71717a',
      fontSize: 10
    }
  },
  
  legend: {
    textStyle: {
      color: '#a1a1aa',
      fontSize: 10
    },
    pageTextStyle: {
      color: '#71717a'
    },
    pageIconColor: '#71717a',
    pageIconInactiveColor: '#3f3f46'
  },
  
  categoryAxis: {
    axisLine: {
      show: true,
      lineStyle: {
        color: '#27272a',
        width: 1
      }
    },
    axisTick: {
      show: false
    },
    axisLabel: {
      show: true,
      color: '#71717a',
      fontSize: 10,
      margin: 8
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: '#27272a',
        type: 'dashed',
        width: 0.5
      }
    },
    splitArea: {
      show: false
    }
  },
  
  valueAxis: {
    axisLine: {
      show: true,
      lineStyle: {
        color: '#27272a',
        width: 1
      }
    },
    axisTick: {
      show: false
    },
    axisLabel: {
      show: true,
      color: '#71717a',
      fontSize: 10,
      margin: 8
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: '#27272a',
        type: 'dashed',
        width: 0.5
      }
    },
    splitArea: {
      show: false
    }
  },
  
  logAxis: {
    axisLine: {
      lineStyle: {
        color: '#27272a'
      }
    },
    axisLabel: {
      color: '#71717a',
      fontSize: 10
    },
    splitLine: {
      lineStyle: {
        color: '#27272a',
        type: 'dashed'
      }
    }
  },
  
  timeAxis: {
    axisLine: {
      lineStyle: {
        color: '#27272a'
      }
    },
    axisLabel: {
      color: '#71717a',
      fontSize: 10
    },
    splitLine: {
      lineStyle: {
        color: '#27272a',
        type: 'dashed'
      }
    }
  },
  
  tooltip: {
    backgroundColor: 'rgba(18, 18, 18, 0.92)',
    borderColor: '#3f3f46',
    borderWidth: 1,
    padding: [8, 12],
    textStyle: {
      color: '#e4e4e7',
      fontSize: 11,
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace'
    },
    extraCssText: 'backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); border-radius: 6px;',
    axisPointer: {
      type: 'cross',
      crossStyle: {
        color: '#52525b',
        type: 'dashed',
        width: 0.5
      },
      lineStyle: {
        color: '#52525b',
        type: 'dashed',
        width: 0.5
      }
    }
  },
  
  dataZoom: {
    backgroundColor: 'transparent',
    dataBackgroundColor: 'rgba(39, 39, 42, 0.3)',
    fillerColor: 'rgba(59, 130, 246, 0.08)',
    handleColor: '#3b82f6',
    handleSize: '80%',
    textStyle: {
      color: '#71717a',
      fontSize: 9
    },
    borderColor: '#27272a',
    borderWidth: 0.5
  },
  
  candlestick: {
    itemStyle: {
      color: '#ef4444',
      color0: '#10b981',
      borderColor: '#ef4444',
      borderColor0: '#10b981',
      borderWidth: 1
    }
  },
  
  line: {
    symbol: 'none',
    lineStyle: {
      width: 1
    }
  },
  
  bar: {
    itemStyle: {
      barBorderWidth: 0
    },
    barMaxWidth: 8
  },
  
  grid: {
    left: 55,
    right: 8,
    top: 10,
    bottom: 30,
    containLabel: false,
    backgroundColor: 'transparent',
    borderColor: 'transparent',
    borderWidth: 0
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

export function buildTooltipFormatter(params, options = {}) {
  const { showVolume = true, showOverlay = true } = options
  
  if (!Array.isArray(params) || !params.length) return ''
  
  const kp = params.find(p => p.seriesType === 'candlestick')
  if (!kp || !kp.data) return ''
  
  const [o, c, l, hi] = kp.data
  const isUp = c >= o
  const color = isUp ? MARKET_COLORS.UP : MARKET_COLORS.DOWN
  const sign = isUp ? '+' : ''
  const chgPct = o > 0 ? ((c - o) / o * 100).toFixed(2) : '0.00'
  const chgAbs = (c - o).toFixed(2)
  
  let html = `<div style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 11px;">`
  html += `<div style="color: #a1a1aa; font-size: 10px; margin-bottom: 4px;">${kp.axisValue}</div>`
  html += `<table style="width: 100%; border-collapse: collapse;">`
  html += `<tr><td style="color: #71717a; padding: 1px 4px;">开</td><td style="color: ${color}; text-align: right; padding: 1px 4px;">${o?.toFixed(2)}</td></tr>`
  html += `<tr><td style="color: #71717a; padding: 1px 4px;">收</td><td style="color: ${color}; text-align: right; padding: 1px 4px;">${c?.toFixed(2)}</td></tr>`
  html += `<tr><td style="color: #71717a; padding: 1px 4px;">涨跌</td><td style="color: ${color}; text-align: right; padding: 1px 4px;">${sign}${chgAbs} (${sign}${chgPct}%)</td></tr>`
  html += `<tr><td style="color: #71717a; padding: 1px 4px;">低</td><td style="color: #a1a1aa; text-align: right; padding: 1px 4px;">${l?.toFixed(2)}</td></tr>`
  html += `<tr><td style="color: #71717a; padding: 1px 4px;">高</td><td style="color: #a1a1aa; text-align: right; padding: 1px 4px;">${hi?.toFixed(2)}</td></tr>`
  
  if (showVolume) {
    const volParam = params.find(p => p.seriesName === 'VOL')
    if (volParam?.value) {
      const vol = volParam.value
      const volStr = vol >= 1e8 ? (vol / 1e8).toFixed(2) + '亿' : vol >= 1e4 ? (vol / 1e4).toFixed(0) + '万' : vol.toLocaleString()
      html += `<tr><td style="color: #71717a; padding: 1px 4px;">量</td><td style="color: #a1a1aa; text-align: right; padding: 1px 4px;">${volStr}</td></tr>`
    }
  }
  
  if (showOverlay) {
    const ovParams = params.filter(p => p.seriesType === 'line' && p.seriesName === '对比')
    ovParams.forEach(p => {
      const rawVal = p.value?.[1]
      if (rawVal != null) {
        html += `<tr><td style="color: #71717a; padding: 1px 4px;">对比</td><td style="color: ${MARKET_COLORS.OVERLAY}; text-align: right; padding: 1px 4px;">${rawVal?.toFixed(4)}</td></tr>`
      }
    })
  }
  
  html += `</table></div>`
  return html
}

export function buildAxisOptions(gridIndex, options = {}) {
  const {
    showLabel = true,
    showSplitLine = true,
    position = 'left',
    color = CHART_COLORS.AXIS_LABEL,
    fontSize = 10,
    formatter
  } = options
  
  return {
    type: 'value',
    gridIndex,
    position,
    scale: true,
    axisLine: {
      show: true,
      lineStyle: {
        color: CHART_COLORS.AXIS_LINE,
        width: 1
      }
    },
    axisTick: {
      show: false
    },
    axisLabel: {
      show: showLabel,
      color,
      fontSize,
      margin: 8,
      formatter
    },
    splitLine: {
      show: showSplitLine,
      lineStyle: {
        color: CHART_COLORS.SPLIT_LINE,
        type: 'dashed',
        width: 0.5
      }
    },
    splitArea: {
      show: false
    }
  }
}

export function buildGridOptions(options = {}) {
  const {
    top = 10,
    height = '65%',
    left = 55,
    right = 8
  } = options
  
  return {
    top,
    height,
    left,
    right,
    containLabel: false,
    backgroundColor: 'transparent',
    borderColor: 'transparent',
    borderWidth: 0
  }
}

export function buildDataZoomOptions(xAxisIndices) {
  return [
    {
      type: 'inside',
      xAxisIndex: xAxisIndices,
      start: 70,
      end: 100
    },
    {
      type: 'slider',
      xAxisIndex: xAxisIndices,
      bottom: 0,
      height: 16,
      borderColor: '#27272a',
      fillerColor: 'rgba(59, 130, 246, 0.08)',
      handleStyle: {
        color: '#3b82f6'
      },
      textStyle: {
        color: '#71717a',
        fontSize: 9
      },
      dataBackground: {
        lineStyle: {
          color: '#3f3f46'
        },
        areaStyle: {
          color: 'rgba(39, 39, 42, 0.3)'
        }
      },
      selectedDataBackground: {
        lineStyle: {
          color: '#3b82f6'
        },
        areaStyle: {
          color: 'rgba(59, 130, 246, 0.1)'
        }
      }
    }
  ]
}
