/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: ['class', '[data-theme="dark"]', '[data-theme="black"]', '[data-theme="wind"]'],
  theme: {
    extend: {
      colors: {
        // ============================================
        // 主题感知颜色 - 使用 CSS 变量
        // ============================================
        theme: {
          // 背景
          bg: {
            primary: 'var(--bg-primary)',
            secondary: 'var(--bg-secondary)',
            tertiary: 'var(--bg-tertiary)',
            hover: 'var(--bg-hover)',
            active: 'var(--bg-active)',
          },
          // 文字
          text: {
            primary: 'var(--text-primary)',
            secondary: 'var(--text-secondary)',
            tertiary: 'var(--text-tertiary)',
            muted: 'var(--text-muted)',
          },
          // 边框
          border: {
            primary: 'var(--border-primary)',
            secondary: 'var(--border-secondary)',
            hover: 'var(--border-hover)',
          },
          // 强调色
          accent: {
            DEFAULT: 'var(--accent-primary)',
            secondary: 'var(--accent-secondary)',
            bg: 'var(--accent-bg)',
            border: 'var(--accent-border)',
          },
          // 面板
          panel: {
            DEFAULT: 'var(--panel-bg)',
            elevated: 'var(--panel-bg-elevated)',
            hover: 'var(--panel-bg-hover)',
          },
          // 涨跌
          bullish: {
            DEFAULT: 'var(--bullish)',
            light: 'var(--bullish-light)',
            bg: 'var(--bullish-bg)',
            border: 'var(--bullish-border)',
          },
          bearish: {
            DEFAULT: 'var(--bearish)',
            light: 'var(--bearish-light)',
            bg: 'var(--bearish-bg)',
            border: 'var(--bearish-border)',
          },
          // 状态
          status: {
            live: 'var(--status-live)',
            warning: 'var(--status-warning)',
            error: 'var(--status-error)',
            info: 'var(--status-info)',
            success: 'var(--status-success)',
          },
          // 图表
          chart: {
            grid: 'var(--chart-grid)',
            text: 'var(--chart-text)',
            line: 'var(--chart-line)',
            area: 'var(--chart-area)',
          },
        },
        
        // ============================================
        // 保留原有 terminal 颜色（向后兼容）
        // ============================================
        terminal: {
          bg: 'var(--bg-primary)',
          panel: 'var(--panel-bg)',
          accent: 'var(--accent-primary)',
          dim: 'var(--text-tertiary)'
        },
        
        // ============================================
        // 专业金融色调（向后兼容）
        // ============================================
        bullish: {
          DEFAULT: 'var(--bullish)',
          light: 'var(--bullish-light)',
          dark: '#b91c1c',
          bg: 'var(--bullish-bg)',
          border: 'var(--bullish-border)',
        },
        bearish: {
          DEFAULT: 'var(--bearish)',
          light: 'var(--bearish-light)',
          dark: '#166534',
          bg: 'var(--bearish-bg)',
          border: 'var(--bearish-border)',
        },
      },
      
      // 阴影
      boxShadow: {
        'theme-sm': 'var(--shadow-sm)',
        'theme-md': 'var(--shadow-md)',
        'theme-lg': 'var(--shadow-lg)',
      },
      
      // 背景色快捷访问
      backgroundColor: {
        'theme-primary': 'var(--bg-primary)',
        'theme-secondary': 'var(--bg-secondary)',
        'theme-panel': 'var(--panel-bg)',
      },
      
      // 文字色快捷访问
      textColor: {
        'theme-primary': 'var(--text-primary)',
        'theme-secondary': 'var(--text-secondary)',
        'theme-tertiary': 'var(--text-tertiary)',
      },
      
      // 边框色快捷访问
      borderColor: {
        'theme': 'var(--border-primary)',
        'theme-secondary': 'var(--border-secondary)',
      },
      
      // 圆角系统 - 万德规范
      borderRadius: {
        'sm': 'var(--radius-sm)',    // 4px PC默认
        'md': 'var(--radius-md)',    // 4px
        'lg': 'var(--radius-lg)',    // 8px 移动端
        'xl': 'var(--radius-xl)',    // 8px
      }
    },
  },
  plugins: [],
}
