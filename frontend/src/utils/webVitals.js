import { onLCP, onCLS, onFCP, onTTFB, onINP } from 'web-vitals'

const vitals = {
  fcp: null,
  lcp: null,
  cls: null,
  inp: null,
  ttfb: null
}

function getRating(name, value) {
  const thresholds = {
    FCP: [1800, 3000],
    LCP: [2500, 4000],
    CLS: [0.1, 0.25],
    INP: [200, 500],
    TTFB: [800, 1800]
  }
  
  const [good, poor] = thresholds[name] || [0, Infinity]
  
  if (value <= good) return 'good'
  if (value <= poor) return 'needs-improvement'
  return 'poor'
}

function sendToAnalytics(metric) {
  if (navigator.sendBeacon) {
    const url = '/api/v1/admin/web-vitals'
    const data = JSON.stringify({
      name: metric.name,
      value: metric.value,
      rating: metric.rating,
      timestamp: metric.timestamp,
      page: window.location.pathname
    })
    navigator.sendBeacon(url, data)
  }
}

function logMetric(metric) {
  const emoji = metric.rating === 'good' ? '✅' : 
                metric.rating === 'needs-improvement' ? '⚠️' : '❌'
  console.log(`${emoji} ${metric.name}: ${metric.value}ms (${metric.rating})`)
}

export function initWebVitals(sendAnalytics = true) {
  onFCP((metric) => {
    vitals.fcp = {
      name: 'FCP',
      value: metric.value,
      rating: getRating('FCP', metric.value),
      timestamp: Date.now()
    }
    logMetric(vitals.fcp)
    if (sendAnalytics) sendToAnalytics(vitals.fcp)
  })
  
  onLCP((metric) => {
    vitals.lcp = {
      name: 'LCP',
      value: metric.value,
      rating: getRating('LCP', metric.value),
      timestamp: Date.now()
    }
    logMetric(vitals.lcp)
    if (sendAnalytics) sendToAnalytics(vitals.lcp)
  })
  
  onCLS((metric) => {
    vitals.cls = {
      name: 'CLS',
      value: metric.value,
      rating: getRating('CLS', metric.value),
      timestamp: Date.now()
    }
    logMetric(vitals.cls)
    if (sendAnalytics) sendToAnalytics(vitals.cls)
  })
  
  onINP((metric) => {
    vitals.inp = {
      name: 'INP',
      value: metric.value,
      rating: getRating('INP', metric.value),
      timestamp: Date.now()
    }
    logMetric(vitals.inp)
    if (sendAnalytics) sendToAnalytics(vitals.inp)
  })
  
  onTTFB((metric) => {
    vitals.ttfb = {
      name: 'TTFB',
      value: metric.value,
      rating: getRating('TTFB', metric.value),
      timestamp: Date.now()
    }
    logMetric(vitals.ttfb)
    if (sendAnalytics) sendToAnalytics(vitals.ttfb)
  })
}

export function getWebVitals() {
  return vitals
}

export function getWebVitalsSummary() {
  const metrics = Object.entries(vitals)
    .filter(([_, m]) => m !== null)
    .map(([name, metric]) => {
      if (!metric) return ''
      const emoji = metric.rating === 'good' ? '✅' : 
                    metric.rating === 'needs-improvement' ? '⚠️' : '❌'
      return `${emoji} ${name.toUpperCase()}: ${metric.value}ms`
    })
    .join('\n')
  
  return metrics || 'Web Vitals not yet collected'
}

export function hasPoorVitals() {
  return Object.values(vitals)
    .filter(m => m !== null)
    .some(m => m?.rating === 'poor')
}
