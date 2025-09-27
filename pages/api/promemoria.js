const { estraiPromemoria } = require('../../lib/scraper');
const cache = require('../../lib/cache');

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ message: 'Method not allowed' });
  }

  try {
    const codiceScuola = process.env.CODICE_SCUOLA;
    const username = process.env.USERNAME;
    const password = process.env.PASSWORD;

    if (!codiceScuola || !username || !password) {
      return res.status(400).json({
        status: 'error',
        message: 'Credenziali mancanti nelle variabili d\'ambiente'
      });
    }

    // Chiave cache basata su credenziali
    const cacheKey = `promemoria_${Buffer.from(codiceScuola + username).toString('base64').slice(0, 10)}`;

    // Controlla cache prima
    const cachedData = cache.get(cacheKey);
    if (cachedData) {
      return res.status(200).json({
        status: 'success',
        data: cachedData,
        cached: true,
        cacheInfo: `Cache size: ${cache.size()}`
      });
    }

    // Se non in cache, scrappa
    const dati = await estraiPromemoria(codiceScuola, username, password);

    // Salva in cache per 15 minuti
    cache.set(cacheKey, dati, 15 * 60 * 1000);

    res.status(200).json({
      status: 'success',
      data: dati,
      cached: false
    });
  } catch (error) {
    console.error('Errore in /api/promemoria:', error);
    res.status(500).json({
      status: 'error',
      message: error.message
    });
  }
}