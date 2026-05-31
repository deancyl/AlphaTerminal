/**
 * Phase 5: Data Aggregation and Analysis
 * Aggregates all Phase results and generates comprehensive statistics.
 */

import { test, expect } from '@playwright/test';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Constants
const THRESHOLD_TOTAL_TIME = 1000;
const THRESHOLD_API_TIME = 500;
const THRESHOLD_LOAD_TIME = 1000;
const THRESHOLD_RENDER_TIME = 500;
const THRESHOLD_WS_TIME = 1000;

const RESULTS_DIR = join(__dirname, '.');
const OUTPUT_FILE = join(RESULTS_DIR, 'performance-test-results.json');

function loadPhaseResults(phase) {
  const filePath = join(RESULTS_DIR, 'performance-' + phase + '-results.json');
  const alternatePath = join(__dirname, '../performance-' + phase + '-results.json');
  
  if (existsSync(filePath)) {
    return JSON.parse(readFileSync(filePath, 'utf-8'));
  } else if (existsSync(alternatePath)) {
    return JSON.parse(readFileSync(alternatePath, 'utf-8'));
  }
  
  console.warn('[Phase 5] Results file not found: ' + phase);
  return null;
}

function mergeAllPhaseResults() {
  const phase1 = loadPhaseResults('phase1');
  const phase2 = loadPhaseResults('phase2');
  const phase3 = loadPhaseResults('phase3');
  const phase4 = loadPhaseResults('phase4');
  
  return {
    phase1: phase1 || { tests: [], summary: {} },
    phase2: phase2 || { results: [], summary: {} },
    phase3: phase3 || { pages: [], summary: {} },
    phase4: phase4 || { tabs: [], summary: {} }
  };
}

function calculateTimeMetrics(times) {
  if (times.length === 0) {
    return { min: 0, max: 0, avg: 0, median: 0, p50: 0, p95: 0, p99: 0 };
  }
  
  const sorted = times.slice().sort(function(a, b) { return a - b; });
  const sum = sorted.reduce(function(a, b) { return a + b; }, 0);
  
  function percentile(p) {
    const index = Math.floor(sorted.length * p);
    return sorted[Math.min(index, sorted.length - 1)];
  }
  
  return {
    min: sorted[0],
    max: sorted[sorted.length - 1],
    avg: sum / sorted.length,
    median: sorted[Math.floor(sorted.length / 2)],
    p50: percentile(0.5),
    p95: percentile(0.95),
    p99: percentile(0.99)
  };
}

function analyzeRootCause(page) {
  const reasons = [];
  
  const apiTime = page.apiTime || 0;
  const loadTime = page.loadTime || page.switchTime || 0;
  const renderTime = page.renderTime || 0;
  const wsTime = page.wsTime || 0;
  const totalTime = page.totalTime || 0;
  
  if (apiTime > THRESHOLD_API_TIME) {
    reasons.push('API响应慢(' + apiTime + 'ms): 检查后端缓存和熔断器');
  }
  
  if (loadTime > THRESHOLD_LOAD_TIME) {
    reasons.push('页面加载慢(' + loadTime + 'ms): 检查前端bundle大小和懒加载');
  }
  
  if (renderTime > THRESHOLD_RENDER_TIME) {
    reasons.push('数据渲染慢(' + renderTime + 'ms): 检查ECharts初始化和大数据处理');
  }
  
  if (wsTime > THRESHOLD_WS_TIME) {
    reasons.push('WebSocket慢(' + wsTime + 'ms): 检查网络连接和重连逻辑');
  }
  
  if (totalTime > 5000 && loadTime < totalTime * 0.3) {
    reasons.push('冷启动问题(' + totalTime + 'ms): 首次加载，考虑预加载或预热缓存');
  }
  
  if (reasons.length === 0) {
    reasons.push('总体时间慢(' + totalTime + 'ms): 多因素综合影响，需要进一步分析');
  }
  
  return reasons;
}

function calculateStatistics(allResults) {
  const stats = {
    pages: {},
    overall: {
      totalTests: 0, passedTests: 0, failedTests: 0,
      avgTotalTime: 0, avgApiTime: 0, avgLoadTime: 0, avgRenderTime: 0, avgWsTime: 0
    },
    distribution: { p50: 0, p95: 0, p99: 0 },
    slowPages: [],
    phases: {
      phase1: { total: 0, passed: 0, failed: 0 },
      phase2: { total: 0, passed: 0, failed: 0 },
      phase3: { total: 0, passed: 0, failed: 0 },
      phase4: { total: 0, passed: 0, failed: 0 }
    }
  };
  
  const allTimes = [];
  const allApiTimes = [];
  const allLoadTimes = [];
  const allRenderTimes = [];
  
  // Phase 1
  if (allResults.phase1 && allResults.phase1.tests) {
    allResults.phase1.tests.forEach(function(test) {
      const pageId = (test.name || '').toLowerCase().replace(/\s+/g, '-') || 'unknown';
      const success = test.success !== false;
      
      stats.phases.phase1.total++;
      if (success) stats.phases.phase1.passed++;
      else stats.phases.phase1.failed++;
      
      const loadTime = test.loadTimeMs || 0;
      const responseTime = test.responseTimeMs || 0;
      const wsTime = test.connectionTimeMs || 0;
      
      if (loadTime > 0) allLoadTimes.push(loadTime);
      if (responseTime > 0) allApiTimes.push(responseTime);
      if (wsTime > 0) { allTimes.push(wsTime); allApiTimes.push(wsTime); }
      
      stats.pages['phase1-' + pageId] = {
        pageId: pageId, phase: 'phase1', name: test.name, success: success,
        loadTime: loadTime, apiTime: responseTime, wsTime: wsTime,
        totalTime: Math.max(loadTime, responseTime, wsTime)
      };
    });
  }
  
  // Phase 2
  if (allResults.phase2 && allResults.phase2.results) {
    allResults.phase2.results.forEach(function(result) {
      const pageId = result.pageId || 'unknown';
      const success = result.status === 'pass';
      
      stats.phases.phase2.total++;
      if (success) stats.phases.phase2.passed++;
      else stats.phases.phase2.failed++;
      
      const iterations = result.iterations || [];
      const totalTime = result.metrics && result.metrics.totalTime || 0;
      const renderTime = result.metrics && result.metrics.dataRenderTime || 0;
      const loadTime = result.metrics && result.metrics.pageLoadTime && result.metrics.pageLoadTime.loadComplete || 0;
      
      if (totalTime > 0) allTimes.push(totalTime);
      if (renderTime > 0) allRenderTimes.push(renderTime);
      if (loadTime > 0) allLoadTimes.push(loadTime);
      
      stats.pages['phase2-' + pageId] = {
        pageId: pageId, phase: 'phase2', description: result.description, success: success,
        totalTime: totalTime, renderTime: renderTime, loadTime: loadTime,
        iterations: iterations.length, threshold: result.threshold
      };
    });
  }
  
  // Phase 3
  if (allResults.phase3 && allResults.phase3.pages) {
    allResults.phase3.pages.forEach(function(page) {
      const pageId = page.pageId || 'unknown';
      const success = page.status === 'pass';
      
      stats.phases.phase3.total++;
      if (success) stats.phases.phase3.passed++;
      else stats.phases.phase3.failed++;
      
      const medianLoadTime = page.medianLoadTime || 0;
      const apiResults = page.apiResults || [];
      let apiTime = 0;
      if (apiResults.length > 0) {
        apiTime = apiResults.reduce(function(sum, r) { return sum + (r.responseTime || 0); }, 0) / apiResults.length;
      }
      
      if (medianLoadTime > 0) allTimes.push(medianLoadTime);
      if (apiTime > 0) allApiTimes.push(apiTime);
      
      stats.pages['phase3-' + pageId] = {
        pageId: pageId, phase: 'phase3', name: page.pageName, success: success,
        loadTime: medianLoadTime, apiTime: apiTime, totalTime: medianLoadTime,
        iterations: page.iterations ? page.iterations.length : 0
      };
    });
  }
  
  // Phase 4
  if (allResults.phase4 && allResults.phase4.tabs) {
    allResults.phase4.tabs.forEach(function(tab) {
      const tabId = (tab.tabId || '').toLowerCase().replace(/\s+/g, '-') || 'unknown';
      const success = tab.status === 'success';
      const failed = tab.status === 'error';
      const skipped = tab.status === 'skipped';
      
      if (!skipped) {
        stats.phases.phase4.total++;
        if (success) stats.phases.phase4.passed++;
        else stats.phases.phase4.failed++;
      }
      
      const switchTime = tab.switchTime || 0;
      if (switchTime > 0) { allTimes.push(switchTime); allRenderTimes.push(switchTime); }
      
      stats.pages['phase4-' + tabId] = {
        pageId: tabId, phase: 'phase4', name: tab.tabId, success: success,
        failed: failed, skipped: skipped, switchTime: switchTime, totalTime: switchTime,
        error: tab.error || null
      };
    });
  }
  
  // Calculate overall stats
  stats.overall.totalTests = stats.phases.phase1.total + stats.phases.phase2.total + stats.phases.phase3.total + stats.phases.phase4.total;
  stats.overall.passedTests = stats.phases.phase1.passed + stats.phases.phase2.passed + stats.phases.phase3.passed + stats.phases.phase4.passed;
  stats.overall.failedTests = stats.phases.phase1.failed + stats.phases.phase2.failed + stats.phases.phase3.failed + stats.phases.phase4.failed;
  
  const timeMetrics = calculateTimeMetrics(allTimes);
  const apiMetrics = calculateTimeMetrics(allApiTimes);
  const loadMetrics = calculateTimeMetrics(allLoadTimes);
  const renderMetrics = calculateTimeMetrics(allRenderTimes);
  
  stats.overall.avgTotalTime = timeMetrics.avg;
  stats.overall.avgApiTime = apiMetrics.avg;
  stats.overall.avgLoadTime = loadMetrics.avg;
  stats.overall.avgRenderTime = renderMetrics.avg;
  
  stats.distribution.p50 = timeMetrics.p50 || 0;
  stats.distribution.p95 = timeMetrics.p95 || 0;
  stats.distribution.p99 = timeMetrics.p99 || 0;
  
  // Identify slow pages
  Object.keys(stats.pages).forEach(function(key) {
    const page = stats.pages[key];
    const totalTime = page.totalTime || 0;
    
    if (totalTime > THRESHOLD_TOTAL_TIME) {
      stats.slowPages.push({
        pageId: page.pageId, phase: page.phase,
        name: page.name || page.description || page.pageId,
        totalTime: totalTime, excessMs: totalTime - THRESHOLD_TOTAL_TIME,
        rootCause: analyzeRootCause(page),
        priority: totalTime > 2000 ? 'P0' : totalTime > 1500 ? 'P1' : 'P2'
      });
    }
  });
  
  stats.slowPages.sort(function(a, b) { return b.totalTime - a.totalTime; });
  return stats;
}

function generateRecommendations(stats) {
  const recommendations = [];
  
  const p0SlowPages = stats.slowPages.filter(function(p) { return p.priority === 'P0'; });
  if (p0SlowPages.length > 0) {
    recommendations.push({
      priority: 'P0', category: '性能',
      issue: p0SlowPages.length + '个页面总时间超过2秒',
      pages: p0SlowPages.map(function(p) { return p.pageId; }),
      recommendation: '优先优化这些页面的加载性能，检查API响应、前端bundle大小、ECharts初始化'
    });
  }
  
  const p1SlowPages = stats.slowPages.filter(function(p) { return p.priority === 'P1'; });
  if (p1SlowPages.length > 0) {
    recommendations.push({
      priority: 'P1', category: '性能',
      issue: p1SlowPages.length + '个页面总时间在1.5-2秒之间',
      pages: p1SlowPages.map(function(p) { return p.pageId; }),
      recommendation: '考虑懒加载、代码分割、预加载等优化手段'
    });
  }
  
  if (stats.overall.avgApiTime > THRESHOLD_API_TIME) {
    recommendations.push({
      priority: 'P1', category: 'API',
      issue: '平均API响应时间' + Math.round(stats.overall.avgApiTime) + 'ms超过阈值' + THRESHOLD_API_TIME + 'ms',
      recommendation: '检查后端缓存配置、熔断器状态、数据库查询优化'
    });
  }
  
  if (stats.overall.avgLoadTime > THRESHOLD_LOAD_TIME) {
    recommendations.push({
      priority: 'P1', category: '加载',
      issue: '平均页面加载时间' + Math.round(stats.overall.avgLoadTime) + 'ms超过阈值' + THRESHOLD_LOAD_TIME + 'ms',
      recommendation: '检查前端bundle大小、懒加载配置、资源压缩'
    });
  }
  
  if (stats.distribution.p99 > 2000) {
    recommendations.push({
      priority: 'P2', category: '稳定性',
      issue: 'P99延迟' + Math.round(stats.distribution.p99) + 'ms过高',
      recommendation: '优化长尾请求，考虑超时重试、降级策略'
    });
  }
  
  const successRate = stats.overall.totalTests > 0 ? (stats.overall.passedTests / stats.overall.totalTests) * 100 : 0;
  if (successRate < 95) {
    recommendations.push({
      priority: 'P0', category: '稳定性',
      issue: '测试成功率' + successRate.toFixed(2) + '%低于95%',
      recommendation: '优先修复失败的测试用例，确保基础功能正常'
    });
  }
  
  return recommendations;
}

function generateReport(allResults, stats) {
  const now = new Date().toISOString();
  
  return {
    testDate: now,
    version: 'v0.6.220',
    summary: {
      totalTests: stats.overall.totalTests,
      passedTests: stats.overall.passedTests,
      failedTests: stats.overall.failedTests,
      successRate: stats.overall.totalTests > 0 ? ((stats.overall.passedTests / stats.overall.totalTests) * 100).toFixed(2) + '%' : '0%',
      averageTimes: {
        total: Math.round(stats.overall.avgTotalTime),
        api: Math.round(stats.overall.avgApiTime),
        load: Math.round(stats.overall.avgLoadTime),
        render: Math.round(stats.overall.avgRenderTime)
      },
      distribution: {
        p50: Math.round(stats.distribution.p50),
        p95: Math.round(stats.distribution.p95),
        p99: Math.round(stats.distribution.p99)
      }
    },
    phases: {
      phase1: { name: '基础连通性', total: stats.phases.phase1.total, passed: stats.phases.phase1.passed, failed: stats.phases.phase1.failed },
      phase2: { name: '核心页面', total: stats.phases.phase2.total, passed: stats.phases.phase2.passed, failed: stats.phases.phase2.failed },
      phase3: { name: 'AI功能', total: stats.phases.phase3.total, passed: stats.phases.phase3.passed, failed: stats.phases.phase3.failed },
      phase4: { name: '系统管理', total: stats.phases.phase4.total, passed: stats.phases.phase4.passed, failed: stats.phases.phase4.failed }
    },
    slowPages: stats.slowPages,
    pages: stats.pages,
    recommendations: generateRecommendations(stats),
    nextSteps: [
      '优化慢页面（优先处理P0级别）',
      '检查API响应时间是否在阈值内',
      '验证WebSocket连接稳定性',
      '测试页面加载性能（bundle大小、懒加载）',
      '测试数据渲染性能（ECharts初始化、大数据处理）'
    ]
  };
}

test.describe('Phase 5: Data Aggregation and Analysis', function() {
  
  test('should aggregate all phase results and generate statistics', async function() {
    console.log('[Phase 5] Loading all phase results...');
    const allResults = mergeAllPhaseResults();
    
    expect(Object.keys(allResults).length).toBeGreaterThan(0);
    console.log('[Phase 5] Loaded phases:', Object.keys(allResults));
    
    console.log('[Phase 5] Calculating statistics...');
    const stats = calculateStatistics(allResults);
    
    expect(stats).toHaveProperty('overall');
    expect(stats).toHaveProperty('distribution');
    expect(stats).toHaveProperty('slowPages');
    expect(stats).toHaveProperty('pages');
    
    console.log('[Phase 5] Overall statistics:', {
      totalTests: stats.overall.totalTests,
      passedTests: stats.overall.passedTests,
      failedTests: stats.overall.failedTests,
      avgTotalTime: Math.round(stats.overall.avgTotalTime),
      p50: Math.round(stats.distribution.p50),
      p95: Math.round(stats.distribution.p95),
      p99: Math.round(stats.distribution.p99)
    });
    
    console.log('[Phase 5] Generating report...');
    const report = generateReport(allResults, stats);
    
    expect(report).toHaveProperty('testDate');
    expect(report).toHaveProperty('version');
    expect(report).toHaveProperty('summary');
    expect(report).toHaveProperty('phases');
    expect(report).toHaveProperty('slowPages');
    expect(report).toHaveProperty('recommendations');
    
    console.log('[Phase 5] Saving report to:', OUTPUT_FILE);
    
    const dir = dirname(OUTPUT_FILE);
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }
    
    writeFileSync(OUTPUT_FILE, JSON.stringify(report, null, 2), 'utf-8');
    console.log('[Phase 5] Report saved successfully');
    
    expect(existsSync(OUTPUT_FILE)).toBe(true);
  });
  
  test('should identify slow pages correctly', async function() {
    const allResults = mergeAllPhaseResults();
    const stats = calculateStatistics(allResults);
    
    console.log('[Phase 5] Found ' + stats.slowPages.length + ' slow pages (>' + THRESHOLD_TOTAL_TIME + 'ms)');
    
    if (stats.slowPages.length > 0) {
      console.log('\n[Phase 5] Slow Pages Analysis:');
      stats.slowPages.forEach(function(page) {
        console.log('  - [' + page.priority + '] ' + page.pageId + ' (' + page.phase + '): ' + page.totalTime + 'ms');
        console.log('    Excess: +' + page.excessMs + 'ms');
        page.rootCause.forEach(function(reason) {
          console.log('    - ' + reason);
        });
      });
    }
    
    expect(Array.isArray(stats.slowPages)).toBe(true);
    
    stats.slowPages.forEach(function(page) {
      expect(['P0', 'P1', 'P2']).toContain(page.priority);
      expect(page.totalTime).toBeGreaterThan(THRESHOLD_TOTAL_TIME);
      expect(page.rootCause).toBeDefined();
      expect(Array.isArray(page.rootCause)).toBe(true);
      expect(page.rootCause.length).toBeGreaterThan(0);
    });
  });
  
  test('should calculate distribution percentiles correctly', async function() {
    const allResults = mergeAllPhaseResults();
    const stats = calculateStatistics(allResults);
    
    expect(stats.distribution.p50).toBeLessThanOrEqual(stats.distribution.p95);
    expect(stats.distribution.p95).toBeLessThanOrEqual(stats.distribution.p99);
    
    console.log('[Phase 5] Distribution percentiles:', {
      p50: Math.round(stats.distribution.p50),
      p95: Math.round(stats.distribution.p95),
      p99: Math.round(stats.distribution.p99)
    });
    
    expect(stats.distribution.p50).toBeLessThan(5000);
  });
  
  test('should generate actionable recommendations', async function() {
    const allResults = mergeAllPhaseResults();
    const stats = calculateStatistics(allResults);
    const report = generateReport(allResults, stats);
    
    console.log('[Phase 5] Generated ' + report.recommendations.length + ' recommendations');
    
    report.recommendations.forEach(function(rec) {
      expect(rec).toHaveProperty('priority');
      expect(['P0', 'P1', 'P2', 'P3']).toContain(rec.priority);
      expect(rec).toHaveProperty('category');
      expect(rec).toHaveProperty('issue');
      expect(rec).toHaveProperty('recommendation');
    });
    
    console.log('\n[Phase 5] Recommendations:');
    report.recommendations.forEach(function(rec) {
      console.log('  - [' + rec.priority + '] ' + rec.category + ': ' + rec.issue);
      console.log('    Recommendation: ' + rec.recommendation);
    });
  });
  
  test('should handle missing phase results gracefully', async function() {
    const partialResults = {
      phase1: { tests: [{ name: 'test', success: true, loadTimeMs: 100 }], summary: {} },
      phase2: null, phase3: null, phase4: null
    };
    
    const stats = calculateStatistics(partialResults);
    
    expect(stats.phases.phase1.total).toBe(1);
    expect(stats.phases.phase2.total).toBe(0);
    expect(stats.phases.phase3.total).toBe(0);
    expect(stats.phases.phase4.total).toBe(0);
    
    expect(stats.overall.totalTests).toBe(1);
    expect(stats.overall.passedTests).toBe(1);
  });
});
