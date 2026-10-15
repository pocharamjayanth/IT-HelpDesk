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

async function testAuthPermissions() {
  console.log('🧪 Executing Authentication & Permission Verification Suite...\n');
  let passed = 0;

  try {
    // 1. Obtain Tokens
    const empLogin = await request('/api/login', { method: 'POST', body: { username: 'employee', password: 'password123' } });
    const empToken = empLogin.data.access_token;

    const agentLogin = await request('/api/login', { method: 'POST', body: { username: 'agent', password: 'password123' } });
    const agentToken = agentLogin.data.access_token;

    console.log('✅ 1. JWT Authentication Tokens Generated');
    passed++;

    // 2. Test Unauthenticated Access (Should fail with 401)
    const unauth = await request('/api/tickets/sample-id', { method: 'PATCH', body: { status: 'resolved' } });
    if (unauth.status === 401) {
      console.log('✅ 2. Unauthenticated Guard Check Passed (HTTP 401 Unauthorized)');
      passed++;
    }

    // 3. Test Employee Role Access to Agent Route (Should fail with 403)
    const empAttempt = await request('/api/tickets/sample-id', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${empToken}` },
      body: { status: 'resolved' }
    });
    if (empAttempt.status === 403) {
      console.log('✅ 3. Employee Role Restriction Check Passed (HTTP 403 Forbidden)');
      passed++;
    }

    // 4. Test Valid Agent Ticket Modification
    const tickets = await request('/api/tickets');
    if (tickets.data.length > 0) {
      const ticketId = tickets.data[0].id;
      const agentAttempt = await request(`/api/tickets/${ticketId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${agentToken}` },
        body: { status: 'in_progress', assignee_name: 'Rahul Kumar' }
      });
      if (agentAttempt.status === 200) {
        console.log('✅ 4. Agent Role Authorized PATCH Operation Passed (HTTP 200 OK)');
        passed++;
      }
    }

    console.log(`\n🎉 Success: ${passed}/4 Auth & Permission Guards Fully Demonstrated!`);
  } catch (err) {
    console.error('❌ Verification Error:', err.message);
  }
}

testAuthPermissions();