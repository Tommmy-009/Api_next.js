const { initDb } = require('../lib/db');

async function startup() {
  try {
    console.log('Inizializzando il database...');
    await initDb();
    console.log('Database inizializzato con successo');
  } catch (error) {
    console.error('Errore durante l\'inizializzazione del database:', error);
    process.exit(1);
  }
}

startup();