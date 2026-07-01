# Backend UpNext - Documentazione d'uso

Questa cartella contiene il backend Python/FastAPI del progetto.
La documentazione di integrazione completa è disponibile nel file principale:

- `../BACKEND_INTEGRATION_GUIDE.md`

## Panoramica

Il backend offre:
- autenticazione JWT con login, refresh, logout e profilo utente;
- salvataggio credenziali Argo per singolo utente;
- scraping di Argo con Playwright e memorizzazione dei promemoria;
- lettura promemoria da database;
- esportazione dei promemoria in formato calendario;
- dashboard admin protetta da Basic Auth.

## Avvio locale

1. Posizionati nella cartella `backend`:

```bash
cd /Users/tommasobrugnera/Developer/UPNEXT\ CON\ BACKEND/Api_next.js/backend
```

2. Crea l'ambiente virtuale e installa le dipendenze:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Installa Playwright:

```bash
python -m playwright install chromium
```

4. Avvia il server:

```bash
uvicorn main:app --host 0.0.0.0 --port 2367 --reload
```

5. Verifica che il backend risponda:

```bash
curl http://localhost:2367/health
```

## Variabili d'ambiente principali

Il backend legge la configurazione da `backend/.env` oppure da variabili ambiente:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE
JWT_SECRET_KEY=una_stringa_lunga_random
ARGO_CREDENTIALS_KEY=chiave_per_la_cifra_opzionale_ma_raccomandata
```

Opzionali:

```env
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
ADMIN_DASHBOARD_USERNAME=admin
ADMIN_DASHBOARD_PASSWORD=password_sicura
DEBUG_SCRAPER=false
```

## Endpoints principali

Tutte le rotte sono disponibili anche con il prefisso legacy `/api`.

### Autenticazione

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `PATCH /auth/me`

### Argo / scraping

- `POST /argo/credentials`
- `GET /argo/credentials`
- `GET /argo/credentials/details`
- `DELETE /argo/credentials`
- `POST /argo/scrape`
- `GET /argo/debug/verifiche`

### Promemoria

- `GET /promemoria`
- `GET /promemoria/calendar`

### Admin

- `GET /admin` (protetto da Basic Auth)

## Note importanti

- Il backend richiede un database PostgreSQL con schema `auth` e tabella `auth.users` già esistente.
- All'avvio vengono create automaticamente le seguenti tabelle nel schema `public` se mancanti:
  - `public.promemoria`
  - `public.argo_credentials`
  - `public.user_profiles`
  - `public.refresh_token_state`
  - `public.password_reset_tokens`
- Le richieste protette richiedono header:

```http
Authorization: Bearer ACCESS_TOKEN
```

- Il token `access_token` ha durata breve, il `refresh_token` serve per rinnovo.

## Documentazione completa

Per dettagli di request/response, flussi d'uso e gestione degli errori, leggi il file:

- `BACKEND_INTEGRATION_GUIDE.md`
