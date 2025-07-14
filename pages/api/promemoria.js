const { estraiPromemoria } = require('../../lib/scraper');

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ message: 'Method not allowed' });
  }

  try {
    // Qui dovresti passare le credenziali come parametri o environment variables
    const codiceScuola = process.env.CODICE_SCUOLA;
    const username = process.env.USERNAME;
    const password = process.env.PASSWORD;

    if (!codiceScuola || !username || !password) {
      return res.status(400).json({
        status: 'error',
        message: 'Credenziali mancanti nelle variabili d\'ambiente'
      });
    }

    const dati = await estraiPromemoria(codiceScuola, username, password);
    
    res.status(200).json({
      status: 'success',
      data: dati
    });
  } catch (error) {
    console.error('Errore in /api/promemoria:', error);
    res.status(500).json({
      status: 'error',
      message: error.message
    });
  }
}