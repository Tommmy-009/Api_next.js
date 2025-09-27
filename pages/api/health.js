const cache = require('../../lib/cache');

export default function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ message: 'Method not allowed' });
  }

  // Keep-alive endpoint ottimizzato per Fly.io
  res.status(200).json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    memory: process.memoryUsage(),
    cache: {
      size: cache.size(),
      uptime: process.uptime()
    }
  });
}