const http = require('http');

function postTicket(title, description) {
  return new Promise((resolve, reject) => {
    const req = http.request('http://127.0.0.1:8000/api/tickets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ status: res.statusCode, data: JSON.parse(data) }));
    });
    req.on('error', reject);
    req.write(JSON.stringify({ title, description, category: 'network', priority: 'high' }));
    req.end();
  });
}

function getTickets() {
  return new Promise((resolve, reject) => {
    http.get('http://127.0.0.1:8000/api/tickets', (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ status: res.statusCode, data: JSON.parse(data) }));
    }).on('error', reject);
  });
}

async function runTest() {
  console.log('🧪 Testing Live Supabase Persistence...\n');

  const testTitle = `Persistence Test ${Date.now()}`;
  console.log(`1. Creating ticket: "${testTitle}"...`);
  const created = await postTicket(testTitle, 'Testing live PostgreSQL persistence via Supabase.');
  
  if (created.status === 201 && created.data.id) {
    console.log(`✅ Ticket created successfully! Assigned ID: ${created.data.id}`);
  } else {
    console.error('❌ Failed to insert ticket into Supabase:', created);
    return;
  }

  console.log('\n2. Fetching tickets from Supabase database...');
  const fetched = await getTickets();
  const match = fetched.data.find(t => t.id === created.data.id);

  if (match) {
    console.log(`🎉 Persistence Confirmed! Found ticket "${match.title}" in Supabase query.`);
  } else {
    console.error('❌ Ticket created but not found in query results.');
  }
}

runTest();