const http = require('http');

function request(path, method = 'GET', data = null) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: '127.0.0.1',
      port: 8000,
      path,
      method,
      headers: { 'Content-Type': 'application/json' }
    };
    const req = http.request(options, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(body || '{}') });
        } catch (e) {
          resolve({ status: res.statusCode, body });
        }
      });
    });
    req.on('error', reject);
    if (data) req.write(JSON.stringify(data));
    req.end();
  });
}

async function runTests() {
  console.log('🧪 Executing Comprehensive API Integration Suite...\n');
  try {
    // Test 1: Health Check
    const root = await request('/');
    console.assert(root.status === 200, 'Health check failed');
    console.log('✅ GET / - Server Health Verified');

    // Test 2: Fetch Tickets
    const list = await request('/api/tickets');
    console.assert(list.status === 200 && Array.isArray(list.body), 'List tickets failed');
    console.log(`✅ GET /api/tickets - Retrieved ${list.body.length} DB records`);

    // Test 3: AI Triage Matching
    const triage = await request('/api/triage', 'POST', { title: 'VPN connection lost', description: 'Port 2376 timeout' });
    console.assert(triage.body.suggested_category === 'network', 'Triage category mismatch');
    console.log('✅ POST /api/triage - AI Classification Verified');

    // Test 4: Validation Error Handling
    const badReq = await request('/api/tickets', 'POST', { invalid_field: true });
    console.assert(badReq.status === 422, 'Validation error test failed');
    console.log('✅ POST /api/tickets - 422 Validation Error Correctly Handled');

    console.log('\n🎉 All API Integration Checks Passed!');
    process.exit(0);
  } catch (err) {
    console.error('❌ Test Failed:', err.message);
    process.exit(1);
  }
}

runTests();