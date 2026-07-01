# Guida integrazione backend UpNext

Questo file riassume le cose importanti da sapere per usare questo backend dentro una propria app client, per esempio un'app iOS, Android o web.

Il backend attuale e' una API Python/FastAPI, anche se il `README.md` storico parla ancora di Next.js. Il codice da considerare come riferimento e' dentro `backend/`.

## Panoramica

Il backend espone API per:

- registrare utenti, fare login e gestire sessioni JWT;
- salvare credenziali Argo per ogni utente;
- avviare lo scraping di Argo con Playwright;
- leggere promemoria/verifiche salvate;
- leggere gli stessi dati in formato evento calendario;
- accedere a una dashboard admin protetta da Basic Auth.

Il server gira di default sulla porta `2367` nel Dockerfile e nel `docker-compose.yml`.

Esempio base URL locale:

```text
http://localhost:2367
```

Esempio base URL produzione:

```text
https://tuo-dominio.it
```

Nel client non hardcodare gli endpoint uno per uno: salva una sola `BACKEND_BASE_URL` e componi i path API.

## Stack tecnico

- Python 3
- FastAPI
- Uvicorn
- PostgreSQL
- SQLAlchemy e psycopg2
- JWT con `python-jose`
- bcrypt/passlib per password
- Playwright per scraping Argo
- Docker basato su immagine Playwright Python

Le dipendenze Python sono in:

```text
backend/requirements.txt
```

## Variabili ambiente obbligatorie

Il backend legge la configurazione da variabili ambiente o da `backend/.env`.

Variabili necessarie:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE
JWT_SECRET_KEY=una_stringa_lunga_random
ARGO_CREDENTIALS_KEY=chiave_fernet_base64_opzionale_ma_raccomandata
```

Variabili opzionali:

```env
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
ADMIN_DASHBOARD_USERNAME=admin
ADMIN_DASHBOARD_PASSWORD=password_sicura
DEBUG_SCRAPER=false
```

Note importanti:

- `DATABASE_URL` deve puntare a un PostgreSQL con schema `auth` e tabella `auth.users`.
- `JWT_SECRET_KEY` deve restare segreta e uguale tra riavvii, altrimenti i token gia' emessi non saranno piu' validi.
- `ARGO_CREDENTIALS_KEY` serve per cifrare/decifrare le password Argo salvate. In produzione va sempre impostata e conservata con cura.
- Non mettere mai queste variabili dentro l'app client.

## Database richiesto

Il backend si aspetta una tabella utenti compatibile con Supabase:

```text
auth.users
```

Campi usati dal backend:

- `id`
- `email`
- `encrypted_password`
- `created_at`
- `updated_at`
- `email_confirmed_at`
- `last_sign_in_at`

All'avvio il backend crea, se mancanti, alcune tabelle nello schema `public`:

- `public.promemoria`
- `public.argo_credentials`
- `public.user_profiles`
- `public.refresh_token_state`
- `public.password_reset_tokens`

La tabella `auth.users` non viene creata automaticamente: deve gia' esistere.

## Avvio locale

Da `Api_next.js/backend`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --host 0.0.0.0 --port 2367 --reload
```

Verifica che il server risponda:

```bash
curl http://localhost:2367/health
```

Risposta attesa:

```json
{
  "status": "ok",
  "version": "3.0.0"
}
```

Per controllare configurazione e database puoi usare:

```bash
cd backend
python check.py
```

## Avvio con Docker

Da `Api_next.js`:

```bash
docker compose up --build
```

Il servizio espone:

```text
http://localhost:2367
```

Il compose legge le variabili da:

```text
backend/.env
```

## Rotte principali

Tutte le rotte principali esistono anche con prefisso legacy `/api`.

Esempi equivalenti:

```text
/auth/login
/api/auth/login

/argo/scrape
/api/argo/scrape

/promemoria
/api/promemoria
```

Per nuove app conviene usare i path senza `/api`.

## Autenticazione

Il backend usa JWT:

- `access_token`: token breve, usato nelle richieste autenticate;
- `refresh_token`: token lungo, usato per ottenere un nuovo access token.

Le richieste protette devono includere:

```http
Authorization: Bearer ACCESS_TOKEN
```

### Registrazione

```http
POST /auth/register
Content-Type: application/json
```

Body:

```json
{
  "email": "utente@example.com",
  "password": "password",
  "name": "Nome Utente"
}
```

Risposta:

```json
{
  "id": "uuid",
  "email": "utente@example.com",
  "name": "Nome Utente",
  "created_at": "2026-06-02T10:00:00Z",
  "email_confirmed_at": null,
  "last_sign_in_at": null
}
```

### Login

```http
POST /auth/login
Content-Type: application/json
```

Body:

```json
{
  "email": "utente@example.com",
  "password": "password"
}
```

Risposta:

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

Salva `access_token` e `refresh_token` in storage sicuro. Su iOS usa Keychain, non `UserDefaults`, per i token.

### Utente corrente

```http
GET /auth/me
Authorization: Bearer ACCESS_TOKEN
```

Risposta:

```json
{
  "id": "uuid",
  "email": "utente@example.com",
  "name": "Nome Utente",
  "created_at": "2026-06-02T10:00:00Z",
  "email_confirmed_at": null,
  "last_sign_in_at": null
}
```

### Aggiornamento profilo

```http
PATCH /auth/me
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json
```

Body, con almeno un campo:

```json
{
  "name": "Nuovo Nome",
  "email": "nuova@example.com",
  "password": "nuova_password"
}
```

### Refresh token

```http
POST /auth/refresh
Content-Type: application/json
```

Body:

```json
{
  "refresh_token": "eyJ..."
}
```

Risposta:

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

Quando una richiesta torna `401`, il client dovrebbe provare una volta a fare refresh e poi ripetere la richiesta originale. Se anche il refresh fallisce, bisogna fare logout locale.

### Logout

```http
POST /auth/logout
Authorization: Bearer ACCESS_TOKEN
```

Risposta:

```text
204 No Content
```

Il logout invalida i refresh token emessi prima del logout.

## Credenziali Argo

Le credenziali Argo sono sempre associate all'utente autenticato. Il client non deve inviare `user_id` per salvarle: il backend lo ricava dal token.

### Salvare o aggiornare credenziali

```http
POST /argo/credentials
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json
```

Body:

```json
{
  "codice_scuola": "SC12345",
  "username": "nomeutente",
  "password": "password_argo"
}
```

Risposta:

```json
{
  "success": true,
  "configured": true
}
```

### Verificare se sono configurate

```http
GET /argo/credentials
Authorization: Bearer ACCESS_TOKEN
```

Risposta:

```json
{
  "configured": true
}
```

### Leggere dettagli senza password

```http
GET /argo/credentials/details
Authorization: Bearer ACCESS_TOKEN
```

Risposta:

```json
{
  "configured": true,
  "codice_scuola": "SC12345",
  "username": "nomeutente"
}
```

### Eliminare credenziali

```http
DELETE /argo/credentials
Authorization: Bearer ACCESS_TOKEN
```

Risposta:

```text
204 No Content
```

## Scraping Argo

Lo scraping richiede:

1. utente autenticato;
2. credenziali Argo gia' salvate;
3. Playwright disponibile nel runtime.

Endpoint:

```http
POST /argo/scrape
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json
```

Per sincronizzare i docenti usa l'endpoint dedicato:

```http
POST /argo/teachers
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json
```

La risposta contiene `teachers` e `result`, con elementi nel formato
`{"name": "Nome Cognome", "subject": "Materia"}`. L'endpoint legge la pagina
“Servizi Classe → Docenti Classe”.

Body consigliato:

```json
{}
```

Il backend accetta anche questo formato per compatibilita' con client vecchi:

```json
{
  "user_id": "uuid"
}
```

Il valore `user_id` nel body viene ignorato: conta sempre l'utente dentro il JWT.

Risposta:

```json
{
  "promemoria": [
    {
      "data": "21/05/2026",
      "materia": "Matematica",
      "descrizione": "Verifica sulle equazioni"
    }
  ],
  "result": [
    {
      "data": "21/05/2026",
      "materia": "Matematica",
      "descrizione": "Verifica sulle equazioni"
    }
  ],
  "count": 1,
  "scraped": 1,
  "inserted": 1,
  "duplicates": 0,
  "message": "Scraped: 1, inserted: 1, duplicates: 0"
}
```

Note client:

- imposta timeout almeno a `120` secondi;
- mostra uno stato di caricamento chiaro;
- gestisci `404` come "credenziali Argo non configurate";
- gestisci `504` come "scraping troppo lento, riprova";
- non chiamare lo scraping a ogni apertura schermata: e' una chiamata pesante.

## Promemoria salvati

Per leggere le verifiche gia' salvate:

```http
GET /promemoria
Authorization: Bearer ACCESS_TOKEN
```

Risposta:

```json
{
  "status": "success",
  "data": [
    {
      "data": "21/05/2026",
      "materia": "Matematica",
      "descrizione": "Verifica sulle equazioni"
    }
  ],
  "cached": false
}
```

Questa risposta puo' essere cachata dal backend per 5 minuti.

## Eventi calendario

Per ottenere i promemoria in formato calendario:

```http
GET /promemoria/calendar
Authorization: Bearer ACCESS_TOKEN
```

Risposta:

```json
{
  "status": "success",
  "data": [
    {
      "id": "promemoria_Matematica_20260521",
      "title": "Verifica: Matematica",
      "description": "Verifica sulle equazioni",
      "start": "2026-05-21T00:00:00+00:00",
      "end": "2026-05-21T00:00:00+00:00",
      "color": "#FF5733",
      "all_day": true
    }
  ]
}
```

Attenzione: nel JSON il campo e' `all_day`, non `allDay`, perche' arriva dal modello Pydantic Python.

## Errori da gestire nel client

Formato tipico errore FastAPI:

```json
{
  "detail": "Messaggio errore"
}
```

Codici importanti:

- `400`: richiesta non valida;
- `401`: token assente, scaduto o non valido;
- `404`: risorsa mancante, per esempio credenziali Argo non salvate;
- `409`: email gia' registrata;
- `422`: validazione body fallita;
- `500`: errore interno;
- `503`: database temporaneamente non disponibile;
- `504`: timeout scraping.

## Flusso consigliato per una app

1. All'avvio leggi token da storage sicuro.
2. Se hai un access token, chiama `GET /auth/me`.
3. Se torna `401`, chiama `POST /auth/refresh`.
4. Se il refresh riesce, aggiorna access token e continua.
5. Se il refresh fallisce, cancella sessione locale e mostra login.
6. Dopo login, salva `access_token`, `refresh_token` e dati utente.
7. Prima dello scraping controlla `GET /argo/credentials`.
8. Se non configurate, mostra form credenziali Argo.
9. Se configurate, chiama `POST /argo/scrape`.
10. Per schermate calendario/lista usa `GET /promemoria` o `GET /promemoria/calendar`.

## Esempio Swift minimo

Configurazione:

```swift
struct APIConfig {
    static let backendBaseURL = "https://tuo-dominio.it"
}
```

Login:

```swift
struct LoginBody: Encodable {
    let email: String
    let password: String
}

struct TokenResponse: Decodable {
    let access_token: String
    let refresh_token: String
    let token_type: String
    let expires_in: Int
}

func login(email: String, password: String) async throws -> TokenResponse {
    let url = URL(string: APIConfig.backendBaseURL + "/auth/login")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.httpBody = try JSONEncoder().encode(LoginBody(email: email, password: password))

    let (data, response) = try await URLSession.shared.data(for: request)
    guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
        throw URLError(.badServerResponse)
    }
    return try JSONDecoder().decode(TokenResponse.self, from: data)
}
```

Richiesta autenticata:

```swift
func authenticatedRequest(path: String, accessToken: String) throws -> URLRequest {
    let url = URL(string: APIConfig.backendBaseURL + path)!
    var request = URLRequest(url: url)
    request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
    return request
}
```

Scraping:

```swift
func scrape(accessToken: String) async throws -> Data {
    let url = URL(string: APIConfig.backendBaseURL + "/argo/scrape")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.timeoutInterval = 120
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
    request.httpBody = Data("{}".utf8)

    let (data, response) = try await URLSession.shared.data(for: request)
    guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
        throw URLError(.badServerResponse)
    }
    return data
}
```

## Dashboard admin

Endpoint:

```text
GET /admin
```

Richiede Basic Auth con:

```env
ADMIN_DASHBOARD_USERNAME=...
ADMIN_DASHBOARD_PASSWORD=...
```

Non abilitarla pubblicamente senza credenziali robuste. La dashboard mostra anche dati sensibili, incluse credenziali Argo decifrate.

## Checklist produzione

- Usa HTTPS.
- Imposta `JWT_SECRET_KEY` forte e stabile.
- Imposta `ARGO_CREDENTIALS_KEY` forte e stabile.
- Non committare `.env`.
- Restringi CORS in `backend/main.py` se il client e' web.
- Configura backup PostgreSQL.
- Verifica che Playwright/Chromium funzioni nel provider scelto.
- Imposta timeout lato client di almeno 120 secondi per `/argo/scrape`.
- Logga gli errori server, ma non stampare password o token.
- Proteggi o disabilita la dashboard admin se non serve.

## File importanti

- `backend/main.py`: entry point FastAPI e registrazione router.
- `backend/routes/auth_routes.py`: endpoint autenticazione.
- `backend/auth/auth_service.py`: logica login, register, refresh, logout.
- `backend/auth/jwt_handler.py`: creazione e validazione JWT.
- `backend/scraper/router.py`: credenziali Argo e scraping.
- `backend/scraper/argo.py`: automazione Playwright.
- `backend/scraper/credentials_crypto.py`: cifratura password Argo.
- `backend/promemoria/router.py`: lettura promemoria e calendario.
- `backend/models/`: schemi request/response.
- `backend/database/db.py`: connessione SQLAlchemy.
- `backend/database_pool.py`: pool psycopg2 per query operative.
- `Dockerfile`: immagine di produzione.
- `docker-compose.yml`: avvio locale containerizzato.

## Compatibilita' con l'app iOS esistente

Nel progetto iOS attuale la base URL viene letta da:

```text
APIKeys.plist -> BACKEND_BASE_URL
```

Il valore di default nel codice e':

```text
https://upnext.home-servis.nl
```

Le chiamate esistenti usano gia':

- `/auth/login`
- `/auth/register`
- `/auth/me`
- `/auth/refresh`
- `/auth/logout`
- `/argo/credentials`
- `/argo/credentials/details`
- `/argo/scrape`

Quindi, per puntare l'app a un nuovo backend, normalmente basta cambiare `BACKEND_BASE_URL` e assicurarsi che il database e le variabili ambiente del server siano configurati correttamente.
