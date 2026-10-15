const http = require('http');

http.get('http://127.0.0.1:8000/', (res) => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    console.log('✅ API Health Check Response:', data);
    process.exit(res.statusCode === 200 ? 0 : 1);
  });
}).on('error', (err) => {
  console.error('❌ API Test Failed:', err.message);
  process.exit(1);
});