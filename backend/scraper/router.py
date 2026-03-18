"""
scraper/router.py — Endpoint POST /argo/scrape
Richiede JWT. Legge le credenziali Argo dal DB, lancia lo scraper,
salva i risultati in public.promemoria (replace) e li restituisce.
"""
import logging
import os
import hashlib
from base64 import urlsafe_b64encode
from concurrent.futures import ThreadPoolExecutor
import psycopg2
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from database_pool import get_db, get_cursor
from config.settings import settings
from auth.jwt_handler import get_user_id_from_token
from scraper.argo import estrai_promemoria_con_credenziali
from models.promemoria import ScrapeRequest, ScrapeResponse, PromemoriaItem
from models.argo import (
    ArgoCredentialsConfiguredResponse,
    ArgoCredentialsDetailsResponse,
    ArgoCredentialsUpsertRequest,
    ArgoCredentialsUpsertResponse,
)

logger = logging.getLogger(__name__)

DEBUG_SCRAPER = os.getenv("DEBUG_SCRAPER", "false").lower() == "true"
router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)

# Executor per girare il sync Playwright in un thread separato
_executor = ThreadPoolExecutor(max_workers=3)


def _get_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Bearer mancante o non valido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return get_user_id_from_token(credentials.credentials, expected_type="access")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


def _get_argo_cipher():
    try:
        from cryptography.fernet import Fernet
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cifratura credenziali Argo non disponibile lato server.",
        ) from exc

    secret = settings.argo_credentials_key or settings.jwt_secret_key
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configurazione server incompleta per cifratura credenziali Argo.",
        )

    key = urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _encrypt_argo_password(raw_password: str) -> str:
    cipher = _get_argo_cipher()
    return cipher.encrypt(raw_password.encode("utf-8")).decode("utf-8")


def _decrypt_argo_password(stored_password: str) -> str:
    cipher = _get_argo_cipher()
    try:
        return cipher.decrypt(stored_password.encode("utf-8")).decode("utf-8")
    except Exception:
        # Compatibilità retroattiva: credenziali legacy salvate in chiaro.
        if stored_password.startswith("gAAAA"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Formato credenziali Argo non valido.",
            )
        return stored_password


@router.post(
    "/scrape",
    response_model=ScrapeResponse,
    summary="Scrape Argo e salva i promemoria",
    description=(
        "Recupera le credenziali Argo dalla tabella `argo_credentials`, "
        "lancia Playwright headless su portaleargo.it, estrae i promemoria "
        "e li salva (replace) in `public.promemoria`."
    ),
)
def scrape_argo(
    body: ScrapeRequest,
    caller_user_id: str = Depends(_get_user_id),
):
    """
    Richiede `Authorization: Bearer <access_token>`.
    Lo scrape viene sempre eseguito per l'utente autenticato.
    Il `user_id` nel body è opzionale ed è accettato solo se coincide.
    """
    # Sicurezza: lo scrape avviene sempre e solo per l'utente autenticato.
    # Se un client legacy invia un user_id diverso, rifiutiamo la richiesta.
    if body.user_id is not None and body.user_id != caller_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Non puoi fare scrape per altri utenti",
        )
    effective_user_id = caller_user_id

    # 1. Recupera credenziali Argo dal DB
    try:
        with get_db() as conn:
            with get_cursor(conn) as cur:
                cur.execute(
                    """
                    SELECT codice_scuola, username, password
                    FROM public.argo_credentials
                    WHERE user_id = %s
                    LIMIT 1
                    """,
                    (effective_user_id,),
                )
                cred = cur.fetchone()
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporaneamente non disponibile. Riprova tra poco.",
        )

    if not cred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credenziali Argo non trovate. Usa POST /argo/credentials per salvarle.",
        )

    # 2. Lancia lo scraper in un thread separato (Playwright è sync)
    logger.info(f"Avvio scrape per user_id={effective_user_id}")
    future = _executor.submit(
        estrai_promemoria_con_credenziali,
        cred["codice_scuola"],
        cred["username"],
        _decrypt_argo_password(cred["password"]),
    )
    try:
        risultati: list[dict] = future.result(timeout=120)  # max 2 minuti
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout durante lo scraping di Argo (>120s)",
        )
    except Exception as e:
        logger.error(f"Errore scraper: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore durante lo scraping: {str(e)}",
        )

    # 3. Salva i risultati con protezione conflitti a livello DB
    scraped_count = len(risultati)
    inserted_count = 0
    duplicate_count = 0

    try:
        with get_db() as conn:
            with get_cursor(conn) as cur:
                for r in risultati:
                    if DEBUG_SCRAPER:
                        print("SCRAPER DEBUG:")
                        print(f"User: {effective_user_id}")
                        print(f"Date: {r['data']}")
                        print(f"Subject: {r['materia']}")
                        print(f"Description: {r['descrizione']}")
                        print(f"SCRAPER DEBUG:\nAttempting insert → {r['data']} {r['materia']}")

                    cur.execute(
                        """
                        INSERT INTO public.promemoria (user_id, data, materia, descrizione)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (effective_user_id, r["data"], r["materia"], r["descrizione"]),
                    )
                    if cur.rowcount == 1:
                        inserted_count += 1
                        if DEBUG_SCRAPER:
                            print("SCRAPER DEBUG:\nInsert completed.")
                    else:
                        duplicate_count += 1
                        if DEBUG_SCRAPER:
                            print("SCRAPER DEBUG:\nDuplicate detected, skipping.")
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporaneamente non disponibile durante il salvataggio.",
        )

    logger.info(
        "Salvataggio scrape completato per user_id=%s: scraped=%d inserted=%d duplicates=%d",
        effective_user_id,
        scraped_count,
        inserted_count,
        duplicate_count,
    )
    
    message = (
        f"Scraped: {scraped_count}, inserted: {inserted_count}, duplicates: {duplicate_count}"
    )

    return ScrapeResponse(
        promemoria=[PromemoriaItem(**r) for r in risultati],
        result=[PromemoriaItem(**r) for r in risultati],
        count=inserted_count,
        scraped=scraped_count,
        inserted=inserted_count,
        duplicates=duplicate_count,
        message=message,
    )


@router.post(
    "/credentials",
    response_model=ArgoCredentialsUpsertResponse,
    status_code=status.HTTP_200_OK,
    summary="Crea o aggiorna le credenziali Argo dell'utente",
)
def save_argo_credentials(
    body: ArgoCredentialsUpsertRequest,
    user_id: str = Depends(_get_user_id),
):
    """
    Salva (o aggiorna) le credenziali Argo per l'utente autenticato.
    Usa `upsert` per non duplicare le righe.
    """
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO public.argo_credentials (user_id, codice_scuola, username, password)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    codice_scuola = EXCLUDED.codice_scuola,
                    username      = EXCLUDED.username,
                    password      = EXCLUDED.password
                """,
                (
                    user_id,
                    body.codice_scuola,
                    body.username,
                    _encrypt_argo_password(body.password),
                ),
            )

    return ArgoCredentialsUpsertResponse(success=True, configured=True)


@router.get(
    "/credentials",
    response_model=ArgoCredentialsConfiguredResponse,
    summary="Verifica se le credenziali Argo sono configurate",
)
def get_argo_credentials_status(user_id: str = Depends(_get_user_id)):
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute(
                """
                SELECT 1
                FROM public.argo_credentials
                WHERE user_id = %s
                LIMIT 1
                """,
                (user_id,),
            )
            configured = cur.fetchone() is not None

    return ArgoCredentialsConfiguredResponse(configured=configured)


@router.get(
    "/credentials/details",
    response_model=ArgoCredentialsDetailsResponse,
    summary="Legge i dettagli credenziali Argo (senza password)",
)
def get_argo_credentials_details(user_id: str = Depends(_get_user_id)):
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute(
                """
                SELECT codice_scuola, username
                FROM public.argo_credentials
                WHERE user_id = %s
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()

    if not row:
        return ArgoCredentialsDetailsResponse(configured=False)

    return ArgoCredentialsDetailsResponse(
        configured=True,
        codice_scuola=row["codice_scuola"],
        username=row["username"],
    )


@router.delete(
    "/credentials",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina le credenziali Argo salvate",
)
def delete_argo_credentials(user_id: str = Depends(_get_user_id)):
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute(
                """
                DELETE FROM public.argo_credentials
                WHERE user_id = %s
                """,
                (user_id,),
            )

    return None

@router.get(
    "/debug/verifiche",
    summary="Scrape di debug che non altera il DB",
)
def debug_verifiche(user_id: str = Depends(_get_user_id)):
    """
    Ritorna le verifiche estratte dal portale, quelle a DB e quelle calcolate come nuove, 
    senza salvarle nel database.
    """
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute(
                """
                SELECT codice_scuola, username, password
                FROM public.argo_credentials
                WHERE user_id = %s
                LIMIT 1
                """,
                (user_id,),
            )
            cred = cur.fetchone()

    if not cred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credenziali Argo non trovate.",
        )

    # 2. Scraped tests
    future = _executor.submit(
        estrai_promemoria_con_credenziali,
        cred["codice_scuola"],
        cred["username"],
        _decrypt_argo_password(cred["password"]),
    )
    try:
        scraped_tests = future.result(timeout=120)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 3. DB tests
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute(
                "SELECT data, materia, descrizione FROM public.promemoria WHERE user_id = %s",
                (user_id,)
            )
            db_rows = cur.fetchall()
            db_tests = [{"data": r["data"], "materia": r["materia"], "descrizione": r["descrizione"]} for r in db_rows]

    # 4. New tests logic
    new_tests = []
    for r in scraped_tests:
        exists = any(
            db_t["data"] == r["data"] and db_t["materia"] == r["materia"] and db_t["descrizione"] == r["descrizione"]
            for db_t in db_tests
        )
        if not exists:
            new_tests.append(r)

    return {
        "scraped_tests": scraped_tests,
        "database_tests": db_tests,
        "new_tests": new_tests
    }
