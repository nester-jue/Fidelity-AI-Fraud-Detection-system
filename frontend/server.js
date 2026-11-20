// Lightweight frontend server using Node.js standard library (ES Module compatible)
import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = 5174;
const HOST = '0.0.0.0';
const FRONTEND_DIR = __dirname;
const INDEX_PATH = path.join(FRONTEND_DIR, 'index.html');
const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8010';

// API path prefixes proxied to the FastAPI backend
const API_PREFIXES = [
  '/api', '/auth', '/claims', '/fraud', '/investigations', '/dashboard',
  '/audit-logs', '/customers', '/policies', '/notifications', '/users',
  '/departmental', '/forensics', '/ocr', '/compliance-reports', '/management-reports', '/health',
];

async function proxyToBackend(req, res, body) {
  const url = BACKEND_URL + req.url;
  try {
    const upstream = await fetch(url, {
      method: req.method,
      headers: {
        ...(req.headers.host ? { 'Host': req.headers.host } : {}),
        ...(req.headers['content-type'] ? { 'Content-Type': req.headers['content-type'] } : {}),
        ...(req.headers.authorization ? { 'Authorization': req.headers.authorization } : {}),
      },
      body: ['GET', 'HEAD', 'DELETE'].includes(req.method) ? undefined : body,
    });
    const buffer = Buffer.from(await upstream.arrayBuffer());
    res.writeHead(upstream.status, {
      'Content-Type': upstream.headers.get('content-type') || 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'no-store',
    });
    res.end(buffer);
  } catch (e) {
    res.writeHead(502, { 'Content-Type': 'text/plain' });
    res.end(`Backend unavailable at ${BACKEND_URL}: ${e.message}`);
  }
}

const server = http.createServer(async (req, res) => {
  const isApi = API_PREFIXES.some((p) => req.url === p || req.url.startsWith(p + '/'));
  if (isApi) {
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => proxyToBackend(req, res, Buffer.concat(chunks)));
    return;
  }

  // Normalize request url
  let reqPath = req.url.split('?')[0];
  let filePath = path.join(FRONTEND_DIR, reqPath);

  // Default to index.html for root or SPA paths
  if (reqPath === '/' || !fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
    filePath = INDEX_PATH;
  }

  const ext = path.extname(filePath).toLowerCase();
  const mimeTypes = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.jsx': 'application/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
  };

  const contentType = mimeTypes[ext] || 'application/octet-stream';

  fs.readFile(filePath, (err, content) => {
    if (err) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end(`Server Error: ${err.message}`);
      return;
    }
    res.writeHead(200, {
      'Content-Type': contentType,
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'no-cache',
    });
    res.end(content);
  });
});

server.listen(PORT, HOST, () => {
  console.log(`==================================================================`);
  console.log(`  FIDELITY LIFE ASSURANCE - FRONTEND DASHBOARD RUNNING`);
  console.log(`  URL: http://localhost:${PORT}`);
  console.log(`  Connected Backend API: http://localhost:8010`);
  console.log(`==================================================================`);
});
