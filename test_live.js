const http = require('http');

const API_BASE = process.env.API_URL || 'http://127.0.0.1:8000';

function httpRequest(path, options = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, API_BASE);
    const reqOptions = {
      method: options.method || 'GET',
      headers: options.headers || { 'Content-Type': 'application/json' },
    };

    const req = http.request(url, reqOptions, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = data ? JSON.parse(data) : {};
          resolve({ status: res.statusCode, data: json });
        } catch (e) {
          resolve({ status: res.statusCode, data });
        }
      });
    });

    req.on('error', reject);
    if (options.body) req.write(JSON.stringify(options.body));
    req.end();
  });
}

async function runLiveVerification() {
  console.log(`🚀 Starting Live Database & Deployment Verification against: ${API_BASE}\n`);
  let passed = 0;
  let total = 5;

  try {
    // 1. Health & System Probe Check
    const health = await httpRequest('/healthz');
    if (health.status === 200 && health.data.status === 'healthy') {
      console.log('✅ 1. System Liveness Check Passed (/healthz)');
      passed++;
    } else {
      console.error('❌ 1. Liveness check failed:', health);
    }

    // 2. Authentication Login Check
    const login = await httpRequest('/api/login', {
      method: 'POST',
      body: { username: 'agent', password: 'password123' }
    });
    if (login.status === 200 && login.data.access_token) {
      console.log('✅ 2. JWT Authentication & Login Check Passed');
      passed++;
    } else {
      console.error('❌ 2. Login failed:', login);
    }
    const token = login.data.access_token;

    // 3. Live Supabase Database Read Check
    const ticketsRead = await httpRequest('/api/tickets');
    if (ticketsRead.status === 200 && Array.isArray(ticketsRead.data)) {
      console.log(`✅ 3. Live Supabase Read Persistence Passed (${ticketsRead.data.length} records retrieved)`);
      passed++;
    } else {
      console.error('❌ 3. Database read failed:', ticketsRead);
    }

    // 4. Live Supabase Database Write Check (Authenticated)
    const ticketWrite = await httpRequest('/api/tickets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: { title: 'Live Verification Ticket', description: 'Testing Supabase write persistence in production environment.' }
    });
    if (ticketWrite.status === 201 && ticketWrite.data.id) {
      console.log(`✅ 4. Live Supabase Write Persistence Passed (Created ID: ${ticketWrite.data.id})`);
      passed++;
    } else {
      console.error('❌ 4. Database write failed:', ticketWrite);
    }

    // 5. Semantic RAG Search Engine Check
    const ragSearch = await httpRequest('/api/kb/search', {
      method: 'POST',
      body: { query: 'Wi-Fi connection' }
    });
    if (ragSearch.status === 200 && ragSearch.data.engine) {
      console.log(`✅ 5. Semantic RAG Engine Check Passed (Engine: ${ragSearch.data.engine})`);
      passed++;
    } else {
      console.error('❌ 5. RAG search failed:', ragSearch);
    }

    console.log(`\n🎉 Verification Complete: ${passed}/${total} Live Tests Passed Successfully!`);
    process.exit(passed === total ? 0 : 1);
  } catch (err) {
    console.error('❌ Live Verification Error:', err.message);
    process.exit(1);
  }
}

runLiveVerification();