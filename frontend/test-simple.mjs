import { spawn } from 'child_process';

// Use curl to test specific paths
const tests = [
  { name: 'Home Page', path: '/' },
  { name: 'Admin Panel', path: '/#admin' },
  { name: 'Macro Dashboard', path: '/#macro' },
  { name: 'Multi-Asset Matrix', path: '/#multi-asset-matrix' },
];

async function testPage(name, path) {
  return new Promise((resolve) => {
    console.log(`\nTesting: ${name} (${path})`);
    
    const curl = spawn('curl', ['-s', '-o', `/tmp/test-${name.replace(/ /g, '-')}.html`, '-w', '%{http_code}', `http://localhost:60100${path}`]);
    
    let output = '';
    curl.stdout.on('data', (data) => { output += data; });
    curl.stderr.on('data', (data) => { console.error('stderr:', data); });
    curl.on('close', (code) => {
      const statusCode = output.trim();
      console.log(`  Status Code: ${statusCode}`);
      resolve({ name, path, statusCode: parseInt(statusCode) });
    });
  });
}

// Test all pages
const results = await Promise.all(tests.map(t => testPage(t.name, t.path)));

console.log('\n=== SUMMARY ===');
results.forEach(r => {
  console.log(`${r.name}: ${r.statusCode === 200 ? '✅ OK' : '❌ ' + r.statusCode}`);
});

// Check specific API endpoints
console.log('\n=== API ENDPOINTS ===');
const apiTests = [
  '/api/v1/macro/overview',
  '/api/v1/market/overview',
  '/api/v1/forex/spot',
  '/api/v1/admin/tokens/summary',
];

for (const api of apiTests) {
  const result = await new Promise((resolve) => {
    const curl = spawn('curl', ['-s', '-w', '\n%{http_code}', `http://localhost:60100${api}`]);
    let output = '';
    curl.stdout.on('data', (data) => { output += data; });
    curl.on('close', () => {
      const lines = output.trim().split('\n');
      const body = lines.slice(0, -1).join('\n');
      const code = lines[lines.length - 1];
      
      try {
        const json = JSON.parse(body);
        console.log(`${api}: HTTP ${code} - API code: ${json.code}`);
        resolve({ api, httpCode: parseInt(code), apiCode: json.code });
      } catch (e) {
        console.log(`${api}: HTTP ${code} - Invalid JSON`);
        resolve({ api, httpCode: parseInt(code), apiCode: null });
      }
    });
  });
}
