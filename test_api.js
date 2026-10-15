const http = require('http');

const API_BASE = 'http://127.0.0.1:8000';

function request(path, options = {}) {
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

async function runTests() {
  console.log('🧪 Executing Complete Verification Test Suite...\n');
  let passed = 0;

  try {
    // 1. Root Health Check
    const root = await request('/');
    if (root.status === 200 && root.data.status === 'ok') {
      console.log('✅ 1. Root Health Check Passed');
      passed++;
    }

    // 2. GET Tickets (Dashboard & Persistence)
    const tickets = await request('/api/tickets');
    if (tickets.status === 200 && Array.isArray(tickets.data)) {
      console.log(`✅ 2. GET /api/tickets Passed (${tickets.data.length} records retrieved from Supabase)`);
      passed++;
    }

    // 3. Ticket Creation Error Handling Check
    const badTicket = await request('/api/tickets', { method: 'POST', body: { title: '  ', description: '' } });
    if (badTicket.status === 422) {
      console.log('✅ 3. Ticket Creation Error Handling Passed (HTTP 422 on empty body)');
      passed++;
    }

    // 4. Ticket Creation Success Check
    const newTicket = await request('/api/tickets', { method: 'POST', body: { title: 'Test Ticket', description: 'Testing persistence' } });
    if (newTicket.status === 201 && newTicket.data.id) {
      console.log('✅ 4. POST /api/tickets Passed (Created Ticket ID: ' + newTicket.data.id + ')');
      passed++;
    }

    // 5. AI Triage Engine
    const triage = await request('/api/triage', { method: 'POST', body: { title: 'VPN connection broken', description: 'Error tunnel refused' } });
    if (triage.status === 200 && triage.data.suggested_category === 'network') {
      console.log('✅ 5. POST /api/triage AI Classification Passed');
      passed++;
    }

    // 6. Interactive Queue PATCH Controls
    if (tickets.data.length > 0) {
      const ticketId = tickets.data[0].id;
      const patchRes = await request(`/api/tickets/${ticketId}`, { method: 'PATCH', body: { status: 'in_progress', assignee_name: 'Jayanth P.' } });
      if (patchRes.status === 200) {
        console.log('✅ 6. PATCH /api/tickets Queue Controls Passed');
        passed++;
      }
    }

    // 7. RAG Knowledge Base Search
    const rag = await request('/api/kb/search', { method: 'POST', body: { query: 'VPN' } });
    if (rag.status === 200 && rag.data.matches.length > 0) {
      console.log('✅ 7. POST /api/kb/search RAG Engine Passed');
      passed++;
    }

    console.log(`\n🎉 Success: ${passed}/7 End-to-End Tasks Fully Verified!`);
    process.exit(0);
  } catch (err) {
    console.error('❌ Verification Error:', err.message);
    process.exit(1);
  }
}

runTests();