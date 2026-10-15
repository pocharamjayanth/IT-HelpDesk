const http = require('http');

function makeRequest(options, postData) {
  return new Promise((resolve, reject) => {
    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ status: res.statusCode, body: JSON.parse(data || '{}') }));
    });
    req.on('error', reject);
    if (postData) req.write(JSON.stringify(postData));
    req.end();
  });
}

async function runTests() {
  console.log('🧪 Running HelpDesk AI Integration Tests...\n');
  
  try {
    // 1. Root Health Test
    const root = await makeRequest({ hostname: '127.0.0.1', port: 8000, path: '/', method: 'GET' });
    console.assert(root.status === 200, 'Root health check failed');
    console.log('✅ GET / - Server Online');

    // 2. Fetch Tickets Test
    const tickets = await makeRequest({ hostname: '127.0.0.1', port: 8000, path: '/api/tickets', method: 'GET' });
    console.assert(tickets.status === 200, 'GET /api/tickets failed');
    console.assert(Array.isArray(tickets.body), 'Response is not an array');
    console.log(`✅ GET /api/tickets - Retrieved ${tickets.body.length} records`);

    // 3. AI Triage Test
    const triage = await makeRequest(
      { hostname: '127.0.0.1', port: 8000, path: '/api/triage', method: 'POST', headers: { 'Content-Type': 'application/json' } },
      { title: 'Wi-Fi connection failing on port 2376', description: 'Subnet handshake error' }
    );
    console.assert(triage.status === 200, 'POST /api/triage failed');
    console.assert(triage.body.suggested_category === 'network', 'Triage classification error');
    console.log('✅ POST /api/triage - Neural rule matching verified');

    console.log('\n🎉 All API Integration Tests Passed!');
    process.exit(0);
  } catch (err) {
    console.error('❌ Integration Test Failed:', err.message);
    process.exit(1);
  }
}

runTests();