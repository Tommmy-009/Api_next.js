"""
database/db.py — SQLAlchemy engine, session factory, e base dichiarativa
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config.settings import settings

# ── Engine ──────────────────────────────────────────────────────────────────
# pool_pre_ping=True: controlla che la connessione sia viva prima di usarla
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# ── Session factory ──────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# ── Base dichiarativa per i modelli ORM ──────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dependency FastAPI ────────────────────────────────────────────────────────
def get_db():
    """
    Dependency che fornisce una sessione SQLAlchemy per request.
    Chiude la sessione alla fine del ciclo request/response.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
