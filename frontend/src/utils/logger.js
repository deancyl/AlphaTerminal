// Logger utility for AlphaTerminal
// In production, logs are suppressed. In development, they are shown.

const isDev = import.meta.env.DEV || import.meta.env.MODE === 'development'

export const logger = {
  log: (...args) => {
    if (isDev) console.log(...args)
  },
  debug: (...args) => {
    if (isDev) console.debug(...args)
  },
  warn: (...args) => {
    if (isDev) console.warn(...args)
  },
  error: (...args) => {
    console.error(...args)
  },
  info: (...args) => {
    if (isDev) console.info(...args)
  }
}

export default logger