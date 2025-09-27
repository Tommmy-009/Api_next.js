# API Argo Famiglia - Next.js

API per estrarre i promemoria da Argo Famiglia, convertita da Python/Flask a Next.js.

## Caratteristiche

- ✅ API REST completa con tutti gli endpoint originali
- ✅ Scraping automatico con Playwright
- ✅ Database SQLite per la persistenza
- ✅ Integrazione con Supabase per le credenziali
- ✅ Eventi calendario formattati
- ✅ Pronto per il deployment su Render
- ✅ Containerizzato con Docker

## Struttura del Progetto

```
├── lib/
│   ├── db.js              # Gestione database SQLite
│   ├── scraper.js         # Logica di scraping Playwright
│   └── supabase.js        # Client Supabase
├── pages/
│   ├── api/
│   │   ├── health.js      # Health check
│   │   ├── index.js       # Root endpoint
│   │   ├── promemoria.js  # Estrai promemoria principale
│   │   ├── promemoria/
│   │   │   ├── db.js      # Promemoria da database
│   │   │   └── calendar.js # Eventi calendario
│   │   └── argo/
│   │       └── scrape.js  # Scraping con credenziali Supabase
│   └── index.js           # Homepage con documentazione
├── scripts/
│   └── startup.js         # Script di inizializzazione
├── Dockerfile             # Container Docker
├── render.yaml            # Configurazione Render
└── package.json           # Dipendenze Node.js
```

## Installazione Locale

1. **Clona il repository**

```bash
git clone <repository-url>
cd api-argo-famiglia-nextjs
```

2. **Installa le dipendenze**

```bash
npm install
```

3. **Installa i browser Playwright**

```bash
npx playwright install chromium
```

4. **Configura le variabili d'ambiente**

```bash
cp .env.example .env.local
# Modifica .env.local con le tue credenziali
```

5. **Avvia in modalità sviluppo**

```bash
npm run dev
```

## Deployment su Render

### Metodo 1: Automatic Deploy (Raccomandato)

1. **Connetti il repository GitHub a Render**

   - Vai su [Render Dashboard](https://dashboard.render.com/)
   - Clicca "New" → "Web Service"
   - Connetti il tuo repository GitHub

2. **Configura il servizio**

   - **Name**: `api-argo-famiglia-nextjs`
   - **Environment**: `Node`
   - **Build Command**: `npm install && npm run build`
   - **Start Command**: `npm start`
   - **Plan**: Free (o il piano che preferisci)

3. **Imposta le variabili d'ambiente**
   Nel dashboard di Render, vai su "Environment" e aggiungi:

   ```
   NODE_ENV=production
   PORT=3000
   PLAYWRIGHT_BROWSERS_PATH=/usr/bin/chromium-browser
   PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
   ```

   Se usi credenziali hardcoded (non raccomandato), aggiungi anche:

   ```
   CODICE_SCUOLA=your_school_code
   USERNAME=your_username
   PASSWORD=your_password
   ```

4. **Deploy**
   - Clicca "Create Web Service"
   - Render farà automaticamente il build e deploy

### Metodo 2: Docker Deploy

1. **Crea il servizio Docker su Render**

   - Scegli "Docker" come environment
   - **Dockerfile Path**: `./Dockerfile`
   - **Docker Build Context**: `./`

2. **Stesse variabili d'ambiente del metodo 1**

### Metodo 3: Manual Deploy con render.yaml

1. **Usa il file render.yaml**
   Il file `render.yaml` nella root contiene già tutta la configurazione

2. **Connetti e deploy**
   Render rileverà automaticamente il file e configurerà il servizio

## Endpoints API

### GET /api/health

Health check del servizio

```json
{
  "status": "ok",
  "timestamp": "2024-01-01T12:00:00.000Z"
}
```

### GET /api/promemoria

Estrai promemoria da Argo (richiede credenziali in env)

```json
{
  "status": "success",
  "data": {
    "promemoria": [...],
    "message": "Promemoria salvati nel database"
  }
}
```

### GET /api/promemoria/db

Ottieni promemoria dal database locale

```json
{
  "status": "success",
  "data": [
    {
      "data": "01/01/2024",
      "materia": "Matematica",
      "descrizione": "Compito in classe"
    }
  ]
}
```

### GET /api/promemoria/calendar

Ottieni eventi formattati per calendario

```json
{
  "status": "success",
  "data": [
    {
      "id": "promemoria_Matematica_20240101",
      "title": "Verifica: Matematica",
      "description": "Compito in classe",
      "start": "2024-01-01T00:00:00.000Z",
      "end": "2024-01-01T00:00:00.000Z",
      "color": "#FF5733",
      "allDay": true
    }
  ]
}
```

### POST /api/argo/scrape

Scraping con credenziali da Supabase

```json
// Request
{
  "user_id": "user123"
}

// Response
{
  "result": [
    {
      "data": "01/01/2024",
      "materia": "Matematica",
      "descrizione": "Compito in classe"
    }
  ]
}
```

## Integrazione con Swift

### Esempio di chiamata da Swift

```swift
import Foundation

class ArgoAPI {
    static let shared = ArgoAPI()
    private let baseURL = "https://your-render-app.onrender.com"

    func getPromemoria() async throws -> [Promemoria] {
        guard let url = URL(string: "\(baseURL)/api/promemoria/db") else {
            throw URLError(.badURL)
        }

        let (data, _) = try await URLSession.shared.data(from: url)
        let response = try JSONDecoder().decode(PromemoriaResponse.self, from: data)

        if response.status == "success" {
            return response.data
        } else {
            throw APIError.serverError(response.message ?? "Unknown error")
        }
    }

    func scrapeWithCredentials(userId: String) async throws -> [Promemoria] {
        guard let url = URL(string: "\(baseURL)/api/argo/scrape") else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let requestBody = ["user_id": userId]
        request.httpBody = try JSONEncoder().encode(requestBody)

        let (data, _) = try await URLSession.shared.data(for: request)
        let response = try JSONDecoder().decode(ScrapeResponse.self, from: data)

        return response.result
    }
}

struct Promemoria: Codable {
    let data: String
    let materia: String
    let descrizione: String
}

struct PromemoriaResponse: Codable {
    let status: String
    let data: [Promemoria]
    let message: String?
}

struct ScrapeResponse: Codable {
    let result: [Promemoria]
}

enum APIError: Error {
    case serverError(String)
}
```

## Configurazione Supabase

Per usare l'endpoint `/api/argo/scrape`, assicurati di avere una tabella `argo_credentials` in Supabase:

```sql
CREATE TABLE argo_credentials (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    codice_scuola TEXT NOT NULL,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Monitoraggio e Logging

- I log sono visibili nel dashboard di Render
- Gli screenshot di debug vengono salvati in caso di errore
- Health check disponibile su `/api/health`

## Troubleshooting

### Errori comuni su Render:

1. **Playwright non trova il browser**

   - Assicurati che `PLAYWRIGHT_BROWSERS_PATH` sia impostato
   - Usa il Dockerfile per installazioni più robuste

2. **Database non inizializzato**

   - Il database SQLite viene creato automaticamente
   - I file persistono tra i riavvii su Render

3. **Timeout durante lo scraping**
   - Render Free ha timeout di 30 secondi per le richieste
   - Considera l'upgrade a un piano pagato per timeout più lunghi

## Sicurezza

- Le credenziali sono gestite tramite variabili d'ambiente
- L'integrazione Supabase permette credenziali per utente
- SSL/TLS automatico su Render
- Rate limiting configurabile

## Performance

- Next.js API Routes ottimizzate
- Database SQLite leggero
- Caching automatico di Next.js
- Supporto per multiple istanze su Render

## Contribuire

1. Fork il repository
2. Crea un branch per la tua feature
3. Commit le modifiche
4. Push al branch
5. Apri una Pull Request
# Myplanck_api_next
# Api_next.js
