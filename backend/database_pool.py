"""
database.py — Connessione e pool di connessioni PostgreSQL
"""
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from config.settings import settings

# Pool di connessioni: min 1, max 10 connessioni simultanee
_pool: ThreadedConnectionPool | None = None


def get_pool() -> ThreadedConnectionPool:
    """Crea (o restituisce) il pool di connessioni."""
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=settings.database_url,
        )
    return _pool


def _acquire_healthy_connection(pool: ThreadedConnectionPool):
    """
    Ottiene una connessione viva dal pool.
    Se la connessione è stantia/rotta, la scarta e riprova.
    """
    last_error = None

    for _ in range(2):
        conn = pool.getconn()
        try:
            # ping minimale per evitare connessioni stale dal pool
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            # SELECT 1 apre una transazione quando autocommit e` False:
            # chiudila subito per consegnare una connessione pulita.
            conn.rollback()
            return conn
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
            last_error = exc
            try:
                pool.putconn(conn, close=True)
            except Exception:
                pass

    if last_error:
        raise last_error
    raise psycopg2.OperationalError("Impossibile ottenere una connessione valida dal pool.")


@contextmanager
def get_db():
    """
    Context manager che fornisce una connessione dal pool.
    La connessione viene restituita al pool alla fine del blocco.
    Usa RealDictCursor per ottenere righe come dizionari.
    """
    pool = get_pool()
    conn = _acquire_healthy_connection(pool)
    try:
        conn.autocommit = False
        yield conn
        conn.commit()
    except Exception:
        if conn and conn.closed == 0:
            try:
                conn.rollback()
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                pass
        raise
    finally:
        # Se la connessione e` gia` chiusa, scartala dal pool.
        should_close = bool(conn is None or conn.closed != 0)
        pool.putconn(conn, close=should_close)


def get_cursor(conn):
    """Restituisce un cursore che mappa le righe in dizionari."""
    return conn.cursor(cursor_factory=RealDictCursor)
