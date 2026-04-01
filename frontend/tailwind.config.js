/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: '#0a0e17',
          panel: '#111827',
          accent: '#00ff88',
          dim: '#6b7280'
        },
        // 专业金融色调：涨跌颜色更克制、有层次
        // 上涨：深红系（银行/债券/专业面板）
        bullish: {
          DEFAULT: '#ef232a',
          light:   '#f87171',  // 浅色标签
          dark:    '#b91c1c',  // 深色强调
          bg:      'rgba(239,35,42,0.10)',  // 背景
          border:  'rgba(239,35,42,0.30)',  // 边框
        },
        // 下跌：深绿系
        bearish: {
          DEFAULT: '#14b143',
          light:   '#4ade80',
          dark:    '#166534',
          bg:      'rgba(20,177,67,0.10)',
          border:  'rgba(20,177,67,0.30)',
        },
      }
    },
  },
  plugins: [],
}
