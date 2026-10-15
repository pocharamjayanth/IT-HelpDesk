const http = require('http');

function testTriage(title, description) {
  return new Promise((resolve, reject) => {
    const req = http.request('http://127.0.0.1:8000/api/triage', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(JSON.parse(data)));
    });
    req.on('error', reject);
    req.write(JSON.stringify({ title, description }));
    req.end();
  });
}

async function run() {
  console.log('🧪 Testing Hybrid AI Triage Engine...\n');

  const test1 = await testTriage("GlobalProtect error", "VPN connection hangs at 74% with tunnel failure");
  console.log('Test 1 (Network):', test1.suggested_category, '| Confidence:', test1.confidence_score, '| Engine:', test1.engine);

  const test2 = await testTriage("Need Figma access", "Please grant design workspace license");
  console.log('Test 2 (Software):', test2.suggested_category, '| Confidence:', test2.confidence_score, '| Engine:', test2.engine);

  const test3 = await testTriage("General query", "How do I request a new desk monitor?");
  console.log('Test 3 (Fallback):', test3.suggested_category, '| Confidence:', test3.confidence_score, '| Engine:', test3.engine);
}

run();