const { chromium } = require('playwright');
const { savePromemoria } = require('./db');

async function estraiPromemoria(codiceScuola, username, password) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log("1. Navigando alla pagina di login...");
    await page.goto("https://www.portaleargo.it/argoweb/famiglia/");
    await page.waitForLoadState("networkidle");
    console.log("Pagina di login caricata");

    console.log("2. Compilando il form di login...");
    await page.fill('input[name="famiglia_customer_code"]', codiceScuola);
    await page.fill('input[name="username"]', username);
    await page.fill('input[name="password"]', password);
    console.log("Form compilato");

    console.log("3. Cliccando il bottone Entra...");
    await page.click('button#accediBtn');
    await page.waitForLoadState("networkidle");
    console.log("Login effettuato");

    // Aspetta un po' dopo il login
    console.log("Attendo il completamento del login...");
    await page.waitForTimeout(5000);

    // Verifica se siamo loggati
    if (page.url() === "https://www.portaleargo.it/argoweb/famiglia/") {
      console.log("Sembra che il login non sia andato a buon fine");
      await page.screenshot({ path: "login_failed.png" });
      throw new Error("Login fallito");
    }

    console.log("4. Cercando la sezione Servizi Classe...");
    // Cerca il div dell'accordion
    const accordionSelector = 'div.btl-accordionItem[title="Servizi Classe"]';
    const accordionHeadSelector = 'div.btl-accordionItem-head[aria-label="Servizi Classe"]';
    
    try {
      console.log("Attendo che l'accordion sia visibile...");
      await page.waitForSelector(accordionSelector, { timeout: 10000 });
      console.log("Accordion trovato");
      
      // Clicca sulla testa dell'accordion per espanderlo
      console.log("Clicco per espandere la sezione...");
      await page.click(accordionHeadSelector);
      console.log("Sezione espansa");
      
      // Aspetta che il menu si espanda
      await page.waitForTimeout(2000);
      
      // Ora cerca il pulsante Promemoria
      console.log("5. Cercando il pulsante Promemoria...");
      const promemoriaSelector = 'span.btl-button[title="Promemoria per Classe"]';
      await page.waitForSelector(promemoriaSelector, { timeout: 5000 });
      console.log("Pulsante Promemoria trovato");
      
      // Clicca sul pulsante
      console.log("Cliccando sul pulsante Promemoria...");
      await page.click(promemoriaSelector);
      console.log("Cliccato sul pulsante Promemoria");
      
      // Aspetta che il contenuto venga caricato
      console.log("Attendo il caricamento del contenuto...");
      await page.waitForTimeout(3000);
      
      console.log("6. Cercando la tabella dei promemoria...");
      // Prova diversi selettori per la tabella
      const tableSelectors = [
        'table.btl-table',
        'table',
        'div[class*="table"]',
        'div.btl-table'
      ];

      let tableFound = false;
      for (const selector of tableSelectors) {
        try {
          console.log(`Provo il selettore tabella: ${selector}`);
          await page.waitForSelector(selector, { timeout: 5000 });
          console.log(`Tabella trovata con selettore: ${selector}`);
          tableFound = true;
          break;
        } catch (e) {
          console.log(`Selettore tabella ${selector} non trovato: ${e.message}`);
          continue;
        }
      }

      if (!tableFound) {
        console.log("Nessun selettore della tabella ha funzionato");
        await page.screenshot({ path: "table_not_found.png" });
        throw new Error("Tabella non trovata");
      }

      console.log("7. Estraendo i promemoria...");
      const promemoria = [];
      
      // Prova a trovare tutte le righe della tabella
      const rows = await page.locator('table tr, div.btl-table tr').all();
      console.log(`Trovate ${rows.length} righe nella tabella`);
      
      for (let i = 1; i < rows.length; i++) { // Salta l'header
        const row = rows[i];
        const cells = await row.locator('td').all();
        
        if (cells.length >= 3) {
          const data = await cells[0].innerText();
          const materia = await cells[1].innerText();
          const descrizione = await cells[2].innerText();

          const dataClean = data.trim();
          const materiaClean = materia.trim();
          const descrizioneClean = descrizione.trim();

          // Filtro: escludi righe non rilevanti
          if (
            (!dataClean && !materiaClean && !descrizioneClean) ||
            dataClean.startsWith("Alunno:") ||
            dataClean.startsWith("Classe:") ||
            dataClean.includes("Informiamo gli utenti")
          ) {
            continue;
          }

          promemoria.push({
            data: dataClean,
            materia: materiaClean,
            descrizione: descrizioneClean
          });
        }
      }

      console.log(`Estratti ${promemoria.length} promemoria`);
      await savePromemoria(promemoria);
      console.log("Promemoria salvati nel database");

      return {
        promemoria: promemoria,
        message: 'Promemoria salvati nel database'
      };

    } catch (e) {
      console.error(`Errore durante l'espansione del menu: ${e.message}`);
      await page.screenshot({ path: "menu_error.png" });
      throw new Error("Errore durante l'espansione del menu");
    }

  } catch (e) {
    console.error(`Errore durante l'estrazione: ${e.message}`);
    await page.screenshot({ path: "error.png" });
    console.log("Screenshot salvato come error.png");
    throw e;
  } finally {
    await browser.close();
  }
}

async function estraiPromemoriaConCredenziali(codiceScuola, username, password) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    await page.goto("https://www.portaleargo.it/argoweb/famiglia/");
    await page.waitForLoadState("networkidle");
    await page.fill('input[name="famiglia_customer_code"]', codiceScuola);
    await page.fill('input[name="username"]', username);
    await page.fill('input[name="password"]', password);
    await page.click('button#accediBtn');
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(5000);

    if (page.url() === "https://www.portaleargo.it/argoweb/famiglia/") {
      return [];
    }

    const accordionSelector = 'div.btl-accordionItem[title="Servizi Classe"]';
    const accordionHeadSelector = 'div.btl-accordionItem-head[aria-label="Servizi Classe"]';
    
    try {
      await page.waitForSelector(accordionSelector, { timeout: 10000 });
      await page.click(accordionHeadSelector);
      await page.waitForTimeout(2000);
      
      const promemoriaSelector = 'span.btl-button[title="Promemoria per Classe"]';
      await page.waitForSelector(promemoriaSelector, { timeout: 5000 });
      await page.click(promemoriaSelector);
      await page.waitForTimeout(3000);
      
      const tableSelectors = [
        'table.btl-table',
        'table',
        'div[class*="table"]',
        'div.btl-table'
      ];

      let tableFound = false;
      for (const selector of tableSelectors) {
        try {
          await page.waitForSelector(selector, { timeout: 5000 });
          tableFound = true;
          break;
        } catch (e) {
          continue;
        }
      }

      if (!tableFound) {
        return [];
      }

      const promemoria = [];
      const rows = await page.locator('table tr, div.btl-table tr').all();
      
      for (let i = 1; i < rows.length; i++) {
        const row = rows[i];
        const cells = await row.locator('td').all();
        
        if (cells.length >= 3) {
          const data = await cells[0].innerText();
          const materia = await cells[1].innerText();
          const descrizione = await cells[2].innerText();

          const dataClean = data.trim();
          const materiaClean = materia.trim();
          const descrizioneClean = descrizione.trim();

          if (
            (!dataClean && !materiaClean && !descrizioneClean) ||
            dataClean.startsWith("Alunno:") ||
            dataClean.startsWith("Classe:") ||
            dataClean.includes("Informiamo gli utenti")
          ) {
            continue;
          }

          promemoria.push({
            data: dataClean,
            materia: materiaClean,
            descrizione: descrizioneClean
          });
        }
      }

      return promemoria;

    } catch (e) {
      return [];
    }

  } catch (e) {
    return [];
  } finally {
    await browser.close();
  }
}

module.exports = {
  estraiPromemoria,
  estraiPromemoriaConCredenziali
};