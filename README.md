# UpNext API

Backend FastAPI per autenticazione, promemoria e integrazione Argo Famiglia.
Il codice eseguibile è in `backend/`; il vecchio client Next.js non fa parte di questo checkout.

## Avvio locale

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# modifica DATABASE_URL, JWT_SECRET_KEY e ARGO_CREDENTIALS_KEY
uvicorn main:app --host 0.0.0.0 --port 2367 --reload
```

Verifica:

```bash
curl http://localhost:2367/health
```

## Docker Compose

Imposta `POSTGRES_PASSWORD` nell'ambiente e avvia:

```bash
POSTGRES_PASSWORD='una-password-locale' docker compose up --build
```

Il servizio è disponibile su `http://localhost:2367`. Il database crea automaticamente il contratto minimo `auth.users` e le tabelle operative mancanti.

## Autenticazione

```bash
curl -X POST http://localhost:2367/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"utente@example.com","password":"password-sicura","name":"Mario"}'

curl -X POST http://localhost:2367/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"utente@example.com","password":"password-sicura"}'
```

Usa il valore `access_token` restituito dal login:

```bash
curl http://localhost:2367/auth/me \
  -H 'Authorization: Bearer ACCESS_TOKEN'
```

Sono disponibili anche `/auth/refresh`, `/auth/logout`, `PATCH /auth/me`, `DELETE /auth/me`, `/auth/forgot-password` e `/auth/reset-password`.

## Argo

Le credenziali sono sempre associate all’utente del JWT; eventuali `user_id` inviati dal client vengono ignorati.

```bash
curl -X POST http://localhost:2367/argo/credentials \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"codice_scuola":"SC123","username":"utente-argo","password":"password-argo"}'

curl -X POST http://localhost:2367/argo/scrape \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{}'

curl -X POST http://localhost:2367/argo/teachers \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{}'
```

Altri endpoint: `GET/DELETE /argo/credentials`, `GET /argo/credentials/details` e `GET /argo/debug/verifiche`. Le password Argo sono cifrate a riposo e non vengono mai restituite dalle API o dalla dashboard admin.

## Promemoria e compatibilità

- `GET /promemoria`
- `GET /promemoria/calendar`
- tutte le rotte principali sono disponibili anche con prefisso legacy `/api`;
- `GET /admin/users` e `/admin/users.json` usano Basic Auth configurata tramite variabili ambiente;
- le risposte usano `401`, `404`, `422`, `503` e `504` per i casi previsti.

La guida dettagliata è in [`BACKEND_INTEGRATION_GUIDE.md`](BACKEND_INTEGRATION_GUIDE.md).
