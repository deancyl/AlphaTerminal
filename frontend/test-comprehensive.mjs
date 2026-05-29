// Comprehensive API and Component Test
import { spawn } from 'child_process';

async function curlJson(url) {
  return new Promise((resolve) => {
    const curl = spawn('curl', ['-s', '-w', '\n%{http_code}', url]);
    let output = '';
    curl.stdout.on('data', (data) => { output += data; });
    curl.on('close', () => {
      const lines = output.trim().split('\n');
      const body = lines.slice(0, -1).join('\n');
      const code = parseInt(lines[lines.length - 1]);
      
      try {
        resolve({ httpCode: code, json: JSON.parse(body) });
      } catch (e) {
        resolve({ httpCode: code, json: null, error: e.message });
      }
    });
  });
}

console.log('========================================');
console.log('AlphaTerminal Frontend Comprehensive Test');
console.log('========================================\n');

// Test 1: WebSocket Status (claimed "未连接")
console.log('1. WebSocket Status Test');
const wsStatus = await curlJson('http://localhost:60100/api/v1/streaming/status');
console.log(`   Streaming Status API: HTTP ${wsStatus.httpCode}`);
if (wsStatus.json) {
  console.log(`   Response: code=${wsStatus.json.code}, message=${wsStatus.json.message}`);
} else {
  console.log(`   Response: ${wsStatus.error}`);
}

// Test 2: North Flow (claimed "网络连接失败")
console.log('\n2. North Flow Ranking Test');
const northFlow = await curlJson('http://localhost:60100/api/v1/market/north_flow_ranking');
console.log(`   North Flow API: HTTP ${northFlow.httpCode}`);
if (northFlow.json) {
  console.log(`   Response: code=${northFlow.json.code}, dataSource=${northFlow.json.data?.dataSource?.name}`);
  if (northFlow.json.code === 0) {
    console.log(`   ✅ API returns code 0 (success)`);
  }
}

// Test 3: Macro Dashboard (claimed blank)
console.log('\n3. Macro Dashboard Test');
const macro = await curlJson('http://localhost:60100/api/v1/macro/overview');
console.log(`   Macro Overview API: HTTP ${macro.httpCode}`);
if (macro.json) {
  console.log(`   Response: code=${macro.json.code}, dataKeys=${Object.keys(macro.json.data || {}).join(',')}`);
}

// Test 4: Dashboard Stock
console.log('\n4. Dashboard Stock Test');
const dashboard = await curlJson('http://localhost:60100/api/v1/market/overview');
console.log(`   Market Overview API: HTTP ${dashboard.httpCode}`);
if (dashboard.json) {
  console.log(`   Response: code=${dashboard.json.code}, message=${dashboard.json.message}`);
}

// Test 5: Multi-Asset Matrix
console.log('\n5. Multi-Asset Matrix Test');
const matrix = await curlJson('http://localhost:60100/');
console.log(`   Frontend Page: HTTP ${matrix.httpCode}`);
console.log(`   HTML contains <div id="app">: ${matrix.json ? 'No (HTML)' : 'Yes (check manually)'}`);

// Test 6: Admin Panel 404 errors
console.log('\n6. Admin Panel Endpoints Test');
const adminEndpoints = [
  '/api/v1/admin/tokens/summary',
  '/api/v1/admin/tokens/trend',
  '/api/v1/admin/tokens/recent',
  '/api/v1/admin/models/',
];

for (const endpoint of adminEndpoints) {
  const result = await curlJson(`http://localhost:60100${endpoint}`);
  console.log(`   ${endpoint}: HTTP ${result.httpCode}, API code=${result.json?.code ?? 'N/A'}`);
}

// Test 7: Bond Data Source
console.log('\n7. Bond Module Test');
const bond = await curlJson('http://localhost:60100/api/v1/bond/curve');
console.log(`   Bond Curve API: HTTP ${bond.httpCode}`);
if (bond.json) {
  console.log(`   Response: code=${bond.json.code}, source=${bond.json.data?.source}`);
}

// Test 8: Forex Cross-Rate
console.log('\n8. Forex Cross-Rate Test');
const forex = await curlJson('http://localhost:60100/api/v1/forex/matrix');
console.log(`   Forex Matrix API: HTTP ${forex.httpCode}`);
if (forex.json) {
  console.log(`   Response: code=${forex.json.code}, matrixRows=${forex.json.data?.matrix?.length}`);
}

// Test 9: Futures
console.log('\n9. Futures Test');
const futures = await curlJson('http://localhost:60100/api/v1/futures/main_indexes');
console.log(`   Futures API: HTTP ${futures.httpCode}`);
if (futures.json) {
  console.log(`   Response: code=${futures.json.code}, indexes=${futures.json.data?.length}`);
}

// Test 10: Market Radar
console.log('\n10. Market Radar Test');
const radar = await curlJson('http://localhost:60100/api/v1/market_radar/treemap?level=sector');
console.log(`   Market Radar API: HTTP ${radar.httpCode}`);
if (radar.json) {
  console.log(`   Response: code=${radar.json.code}, data_source=${radar.json.data?.data_source}`);
}

console.log('\n========================================');
console.log('Test Summary');
console.log('========================================');
console.log('All endpoints tested. Check individual results above.');
