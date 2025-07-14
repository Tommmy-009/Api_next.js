const { getPromemoria } = require('../../../lib/db');

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ message: 'Method not allowed' });
  }

  try {
    const promemoria = await getPromemoria();
    
    res.status(200).json({
      status: 'success',
      data: promemoria
    });
  } catch (error) {
    console.error('Errore in /api/promemoria/db:', error);
    res.status(500).json({
      status: 'error',
      message: error.message
    });
  }
}