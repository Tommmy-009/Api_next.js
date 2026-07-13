"""
main.py — Entry point UpNext API v3 (struttura production)
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── Routers ──────────────────────────────────────────────────────────────────
from routes.auth_routes import router as auth_router
from promemoria.router import router as promemoria_router
from scraper.router import router as argo_router
from admin.router import router as admin_router

# ── Startup utilities ─────────────────────────────────────────────────────────
from database.db import engine
from database.db import Base  # noqa: F401 — needed for metadata
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
    Crea le tabelle necessarie senza dipendere da Supabase/auth.users
    """
    with engine.connect() as conn:

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.promemoria (
                id SERIAL PRIMARY KEY,
                user_id UUID,
                data TEXT,
                materia TEXT,
                descrizione TEXT,
                scraped_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.argo_credentials (
                id SERIAL PRIMARY KEY,
                user_id UUID UNIQUE,
                codice_scuola TEXT NOT NULL,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.user_profiles (
                user_id UUID PRIMARY KEY,
                name TEXT,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.refresh_token_state (
                user_id UUID PRIMARY KEY,
                revoked_after TIMESTAMPTZ
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id UUID,
                token_hash TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                used_at TIMESTAMPTZ,
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

            # Hardening schema legacy
            conn.execute(text("""
                CREATE SEQUENCE IF NOT EXISTS public.promemoria_id_seq
            """))

            conn.execute(text("""
                ALTER TABLE public.promemoria
                ALTER COLUMN id
                SET DEFAULT nextval('public.promemoria_id_seq')
            """))

            conn.execute(text("""
                ALTER SEQUENCE public.promemoria_id_seq
                OWNED BY public.promemoria.id
            """))

            conn.execute(text("""
                SELECT setval(
                    'public.promemoria_id_seq',
                    GREATEST(
                        COALESCE(
                            (SELECT MAX(id) FROM public.promemoria),
                            0
                        ) + 1,
                        1
                    ),
                    false
                )
            """))

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
                        UNIQUE (
                            user_id,
                            data,
                            materia,
                            descrizione
                        );
                    END IF;
                END $$;
            """))

        except SQLAlchemyError as exc:
            conn.rollback()

            logger.warning(
                "Schema hardening skipped: %s",
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
        "- /auth → login, refresh, /me\n"
        "- /promemoria → lista e calendario\n"
        "- /argo → scraper portaleargo.it\n"
    ),
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(auth_router)

app.include_router(
    promemoria_router,
    prefix="/promemoria",
    tags=["Promemoria"]
)

app.include_router(
    argo_router,
    prefix="/argo",
    tags=["Argo Scraper"]
)

app.include_router(admin_router)

# Compatibilità retroattiva

app.include_router(auth_router, prefix="/api")

app.include_router(
    promemoria_router,
    prefix="/api/promemoria",
    tags=["Promemoria"]
)

app.include_router(
    argo_router,
    prefix="/api/argo",
    tags=["Argo Scraper"]
)

app.include_router(admin_router, prefix="/api")


@app.get("/health", tags=["Utility"])
def health():
    return {
        "status": "ok",
        "version": "3.0.0"
    }
