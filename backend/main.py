"""
main.py — Entry point UpNext API v3 (struttura production)
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── Routers ──────────────────────────────────────────────────────────────────
from routes.auth_routes   import router as auth_router
from promemoria.router    import router as promemoria_router
from scraper.router       import router as argo_router

# ── Startup utilities ─────────────────────────────────────────────────────────
from database.db import engine
from database.db import Base          # noqa: F401 — needed for metadata
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Startup: crea le tabelle operative se non esistono ───────────────────────

def _ensure_tables():
    """
    Crea public.promemoria e public.argo_credentials se non esistono.
    Lo schema auth.users NON viene toccato.
    """
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.promemoria (
                id          SERIAL PRIMARY KEY,
                user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
                data        TEXT,
                materia     TEXT,
                descrizione TEXT,
                scraped_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.argo_credentials (
                id            SERIAL PRIMARY KEY,
                user_id       UUID UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
                codice_scuola TEXT NOT NULL,
                username      TEXT NOT NULL,
                password      TEXT NOT NULL,
                created_at    TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.user_profiles (
                user_id    UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
                name       TEXT,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.refresh_token_state (
                user_id       UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
                revoked_after TIMESTAMPTZ
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.password_reset_tokens (
                id         SERIAL PRIMARY KEY,
                user_id    UUID REFERENCES auth.users(id) ON DELETE CASCADE,
                token_hash TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                used_at    TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id
                ON public.password_reset_tokens (user_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at
                ON public.password_reset_tokens (expires_at)
            """))
            # Hardening schema legacy: garantisce autoincrement su id anche su DB già esistenti.
            conn.execute(text("CREATE SEQUENCE IF NOT EXISTS public.promemoria_id_seq"))
            conn.execute(text("""
                ALTER TABLE public.promemoria
                ALTER COLUMN id SET DEFAULT nextval('public.promemoria_id_seq')
            """))
            conn.execute(text("""
                ALTER SEQUENCE public.promemoria_id_seq
                OWNED BY public.promemoria.id
            """))
            conn.execute(text("""
                SELECT setval(
                    'public.promemoria_id_seq',
                    GREATEST(COALESCE((SELECT MAX(id) FROM public.promemoria), 0) + 1, 1),
                    false
                )
            """))
            # Evita duplicati logici nelle verifiche.
            conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'unique_verifica'
                          AND conrelid = 'public.promemoria'::regclass
                    ) THEN
                        ALTER TABLE public.promemoria
                        ADD CONSTRAINT unique_verifica
                        UNIQUE (user_id, data, materia, descrizione);
                    END IF;
                END $$;
            """))
        except SQLAlchemyError as exc:
            conn.rollback()
            logger.warning(
                "Schema hardening skipped (insufficient privileges or legacy ownership): %s",
                exc,
            )
        conn.commit()
    logger.info("Tabelle DB verificate/create")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_tables()
    logger.info("🚀 UpNext API avviata")
    yield
    logger.info("UpNext API fermata")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="UpNext API",
    description=(
        "Backend unico per l'app iOS UpNext.\n\n"
        "- **`/auth`** → login, refresh, /me\n"
        "- **`/promemoria`** → lista e calendario\n"
        "- **`/argo`** → Playwright scraper portaleargo.it\n"
    ),
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # restringi in produzione
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(promemoria_router, prefix="/promemoria", tags=["Promemoria"])
app.include_router(argo_router,       prefix="/argo",       tags=["Argo Scraper"])


@app.get("/health", tags=["Utility"])
def health():
    return {"status": "ok", "version": "3.0.0"}
