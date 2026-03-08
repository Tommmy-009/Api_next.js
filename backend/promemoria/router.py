"""
promemoria/router.py — Endpoints GET /promemoria e GET /promemoria/calendar
"""
import logging
from datetime import datetime, timezone
from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, status

from database_pool import get_db, get_cursor
from models.promemoria import PromemoriaItem, CalendarEvent, PromemoriaListResponse, CalendarResponse
from auth.jwt_handler import get_user_id_from_token
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache TTL: 5 minuti per le letture dal DB
_cache: TTLCache = TTLCache(maxsize=128, ttl=300)

bearer_scheme = HTTPBearer()


def _get_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    try:
        return get_user_id_from_token(credentials.credentials, expected_type="access")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


def _date_to_iso(data_str: str) -> str:
    """
    Converte data italiana "DD/MM/YYYY" → ISO 8601 "YYYY-MM-DDT00:00:00Z".
    Restituisce stringa vuota in caso di errore.
    """
    try:
        day, month, year = data_str.split("/")
        dt = datetime(int(year), int(month), int(day), tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return ""


@router.get("", response_model=PromemoriaListResponse, summary="Lista promemoria dell'utente")
def get_promemoria(user_id: str = Depends(_get_user_id)):
    """
    Restituisce i promemoria salvati per l'utente autenticato.
    La risposta è cachata per 5 minuti per utente.
    """
    cache_key = f"promemoria:{user_id}"

    if cache_key in _cache:
        return PromemoriaListResponse(data=_cache[cache_key], cached=True)

    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute(
                """
                SELECT data, materia, descrizione
                FROM public.promemoria
                WHERE user_id = %s
                ORDER BY scraped_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()

    items = [PromemoriaItem(**dict(r)) for r in rows]
    _cache[cache_key] = items
    return PromemoriaListResponse(data=items, cached=False)


@router.get("/calendar", response_model=CalendarResponse, summary="Promemoria in formato calendario")
def get_calendar(user_id: str = Depends(_get_user_id)):
    """
    Restituisce gli eventi calendario derivati dai promemoria dell'utente.
    Stessa logica di getCalendarEvents() dal db.js originale.
    """
    cache_key = f"calendar:{user_id}"

    if cache_key in _cache:
        return CalendarResponse(data=_cache[cache_key])

    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute(
                "SELECT data, materia, descrizione FROM public.promemoria WHERE user_id = %s",
                (user_id,),
            )
            rows = cur.fetchall()

    events: list[CalendarEvent] = []
    for row in rows:
        iso = _date_to_iso(row["data"])
        if not iso:
            logger.warning(f"Data non parsabile: {row['data']}")
            continue

        events.append(
            CalendarEvent(
                id=f"promemoria_{row['materia']}_{iso[:10].replace('-', '')}",
                title=f"Verifica: {row['materia']}",
                description=row["descrizione"],
                start=iso,
                end=iso,
                color="#FF5733",
                all_day=True,
            )
        )

    _cache[cache_key] = events
    return CalendarResponse(data=events)
