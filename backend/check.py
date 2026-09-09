"""
check.py — Script di diagnostica rapida per UpNext FastAPI
Esegui con: python check.py

Verifica:
  1. Lettura del file .env e config
  2. Connessione a PostgreSQL
  3. Lettura tabella auth.users
"""
import sys
from urllib.parse import urlsplit, urlunsplit


def step(n: int, desc: str):
    print(f"\n{'─'*50}")
    print(f"  STEP {n}: {desc}")
    print(f"{'─'*50}")


def ok(msg: str):
    print(f"  ✅  {msg}")


def fail(msg: str, exc: Exception | None = None):
    print(f"  ❌  {msg}")
    if exc:
        print(f"      Dettaglio: {exc}")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Config / .env
# ─────────────────────────────────────────────────────────────────────────────
step(1, "Lettura .env e dipendenze Python")

try:
    from config.settings import settings
    ok(f"Config caricata")
    parsed = urlsplit(settings.database_url)
    safe_host = urlunsplit((parsed.scheme, parsed.hostname or "", parsed.path, "", ""))
    ok(f"DATABASE_URL host = {safe_host}")
    ok(f"JWT_SECRET_KEY presente: {'sì' if settings.jwt_secret_key else 'NO ← problema!'}")
except Exception as e:
    fail("Impossibile caricare config.py / .env", e)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Connessione PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────
step(2, "Connessione a PostgreSQL")

try:
    import psycopg2
    conn = psycopg2.connect(settings.database_url)
    cur = conn.cursor()
    cur.execute("SELECT version();")
    version = cur.fetchone()[0]
    ok(f"Connessione riuscita!")
    ok(f"PostgreSQL: {version[:60]}")
except Exception as e:
    fail("Connessione al database fallita", e)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Lettura auth.users
# ─────────────────────────────────────────────────────────────────────────────
step(3, "Lettura tabella auth.users")

try:
    cur.execute("SELECT COUNT(*) FROM auth.users;")
    count = cur.fetchone()[0]
    ok(f"Tabella auth.users accessibile — {count} utenti trovati")

    # Mostra un utente di esempio (senza password)
    cur.execute("""
        SELECT id, email, created_at, encrypted_password IS NOT NULL AS has_password
        FROM auth.users
        LIMIT 1
    """)
    row = cur.fetchone()
    if row:
        ok(f"Esempio utente:")
        ok(f"  id            = {row[0]}")
        ok(f"  email         = {row[1]}")
        ok(f"  created_at    = {row[2]}")
        ok(f"  has_password  = {row[3]}")
    else:
        print("  ⚠️   La tabella è vuota (nessun utente)")

    # Verifica formato bcrypt
    cur.execute("""
        SELECT encrypted_password
        FROM auth.users
        WHERE encrypted_password IS NOT NULL
        LIMIT 1
    """)
    pw_row = cur.fetchone()
    if pw_row:
        hashed = pw_row[0]
        if hashed.startswith("$2a$") or hashed.startswith("$2b$"):
            ok(f"  Hash bcrypt rilevato: {hashed[:20]}... ← compatibile")
        else:
            print(f"  ⚠️   Hash non bcrypt: {hashed[:20]}... ← verifica manuale necessaria")

except Exception as e:
    fail("Impossibile leggere auth.users", e)
finally:
    cur.close()
    conn.close()

# ─────────────────────────────────────────────────────────────────────────────
# RIEPILOGO
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'═'*50}")
print("  🎉  Tutte e 3 le verifiche passate!")
print("      Il server FastAPI dovrebbe funzionare.")
print(f"{'═'*50}\n")
print("  Prossimo passo → avvia il server:")
print("  uvicorn main:app --reload --port 8000\n")
