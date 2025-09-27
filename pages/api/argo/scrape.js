const { supabase } = require('../../../lib/supabase');
const { estraiPromemoriaConCredenziali } = require('../../../lib/scraper');

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ message: 'Method not allowed' });
  }

  try {
    const { user_id } = req.body;
    
    if (!user_id) {
      return res.status(400).json({ error: 'user_id mancante' });
    }

    const { data, error } = await supabase
      .from('argo_credentials')
      .select('*')
      .eq('user_id', user_id);

    if (error) {
      console.error('Errore Supabase:', error);
      return res.status(500).json({ error: 'Errore nel recupero delle credenziali' });
    }

    if (!data || data.length === 0) {
      return res.status(404).json({ error: 'Credenziali non trovate' });
    }

    const cred = data[0];
    const { codice_scuola, username, password } = cred;

    const result = await estraiPromemoriaConCredenziali(codice_scuola, username, password);
    
    res.status(200).json({ result });
  } catch (error) {
    console.error('Errore in /api/argo/scrape:', error);
    res.status(500).json({ error: error.message });
  }
}