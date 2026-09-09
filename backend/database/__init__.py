"""Legacy psycopg2 helpers kept for compatibility with older integrations."""

from database_pool import get_cursor, get_db

__all__ = ["get_db", "get_cursor"]
