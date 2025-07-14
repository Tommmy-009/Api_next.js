const Database = require('sqlite3').Database;
const path = require('path');

const dbPath = path.join(process.cwd(), 'promemoria.db');

function initDb() {
  return new Promise((resolve, reject) => {
    const db = new Database(dbPath, (err) => {
      if (err) {
        reject(err);
        return;
      }
      
      db.run(`CREATE TABLE IF NOT EXISTS promemoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        materia TEXT,
        descrizione TEXT
      )`, (err) => {
        if (err) {
          reject(err);
          return;
        }
        db.close();
        resolve();
      });
    });
  });
}

function savePromemoria(promemoria) {
  return new Promise((resolve, reject) => {
    const db = new Database(dbPath, (err) => {
      if (err) {
        reject(err);
        return;
      }
      
      db.run('DELETE FROM promemoria', (err) => {
        if (err) {
          reject(err);
          return;
        }
        
        const stmt = db.prepare('INSERT INTO promemoria (data, materia, descrizione) VALUES (?, ?, ?)');
        
        promemoria.forEach(p => {
          stmt.run(p.data, p.materia, p.descrizione);
        });
        
        stmt.finalize((err) => {
          if (err) {
            reject(err);
            return;
          }
          db.close();
          resolve("Promemoria salvati nel database");
        });
      });
    });
  });
}

function getPromemoria() {
  return new Promise((resolve, reject) => {
    const db = new Database(dbPath, (err) => {
      if (err) {
        reject(err);
        return;
      }
      
      db.all('SELECT data, materia, descrizione FROM promemoria', (err, rows) => {
        if (err) {
          reject(err);
          return;
        }
        
        const promemoria = rows.map(row => ({
          data: row.data,
          materia: row.materia,
          descrizione: row.descrizione
        }));
        
        db.close();
        resolve(promemoria);
      });
    });
  });
}

function getCalendarEvents() {
  return new Promise(async (resolve, reject) => {
    try {
      const promemoria = await getPromemoria();
      const events = [];
      
      for (const p of promemoria) {
        try {
          // Converti la data nel formato italiano (es: "21/05/2024") in Date
          const [day, month, year] = p.data.split('/');
          const data = new Date(year, month - 1, day);
          
          // Crea un evento per il calendario
          const event = {
            id: `promemoria_${p.materia}_${data.getFullYear()}${(data.getMonth() + 1).toString().padStart(2, '0')}${data.getDate().toString().padStart(2, '0')}`,
            title: `Verifica: ${p.materia}`,
            description: p.descrizione,
            start: data.toISOString(),
            end: data.toISOString(),
            color: '#FF5733',
            allDay: true
          };
          events.push(event);
        } catch (e) {
          console.error(`Errore nel convertire la data ${p.data}:`, e);
          continue;
        }
      }
      
      resolve(events);
    } catch (error) {
      reject(error);
    }
  });
}

module.exports = {
  initDb,
  savePromemoria,
  getPromemoria,
  getCalendarEvents
};