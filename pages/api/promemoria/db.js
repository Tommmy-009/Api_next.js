const { getPromemoria } = require('../../../lib/db');
const cache = require('../../../lib/cache');

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ message: 'Method not allowed' });
  }

  try {
    // Cache per letture DB
    const cacheKey = 'promemoria_db_read';
    const cachedData = cache.get(cacheKey);

    if (cachedData) {
      return res.status(200).json({
        status: 'success',
        data: cachedData,
        cached: true
      });
    }

    // Se non in cache, leggi dal DB
    const promemoria = await getPromemoria();

    // Cache per 5 minuti (letture più frequenti)
    cache.set(cacheKey, promemoria, 5 * 60 * 1000);

    res.status(200).json({
      status: 'success',
      data: promemoria,
      cached: false
    });
  } catch (error) {
    console.error('Errore in /api/promemoria/db:', error);
    res.status(500).json({
      status: 'error',
      message: error.message
    });
  }
}