"""
auth/login.py — Logica di business per login, register, refresh e /me
"""
import uuid
from datetime import datetime, timezone

import bcrypt
from fastapi import HTTPException, status

from database import get_db, get_cursor
from auth.jwt import (
    create_access_token,
    create_refresh_token,
    get_user_id_from_token,
)
from models.user import TokenResponse, UserResponse


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #

def _hash_password(plain: str) -> str:
    """Genera un hash bcrypt compatibile con il formato $2a$ di Supabase."""
    hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=10))
    # python-bcrypt usa $2b$; Supabase/PostgreSQL usa $2a$ — entrambi verificabili
    return hashed.decode()


def _verify_password(plain: str, hashed: str) -> bool:
    """Verifica una password contro un hash bcrypt ($2a$ o $2b$)."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# --------------------------------------------------------------------------- #
#  Service functions
# --------------------------------------------------------------------------- #

def login_user(email: str, password: str) -> TokenResponse:
    """
    Cerca l'utente per email in auth.users, verifica la password,
    e restituisce access + refresh token.
    """
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute(
                """
                SELECT id, encrypted_password
                FROM auth.users
                WHERE email = %s
                  AND deleted_at IS NULL
                LIMIT 1
                """,
                (email.lower().strip(),),
            )
            row = cur.fetchone()

    if row is None or not _verify_password(password, row["encrypted_password"] or ""):
        # Messaggio generico per non rivelare l'esistenza dell'account
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, expires_in = create_access_token(row["id"])
    refresh_token = create_refresh_token(row["id"])
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


def register_user(email: str, password: str) -> TokenResponse:
    """
    Registra un nuovo utente in auth.users senza modificare lo schema.
    Campi obbligatori non-nullable in Supabase: id, instance_id, aud, role, email,
    encrypted_password, created_at, updated_at, email_change_token_new, confirmation_token,
    recovery_token, email_change_token_current, raw_app_meta_data, raw_user_meta_data.
    """
    email = email.lower().strip()
    hashed = _hash_password(password)
    new_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with get_db() as conn:
        with get_cursor(conn) as cur:
            # Controlla se l'email è già registrata
            cur.execute(
                "SELECT id FROM auth.users WHERE email = %s LIMIT 1",
                (email,),
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email già registrata",
                )

            cur.execute(
                """
                INSERT INTO auth.users (
                    id,
                    instance_id,
                    aud,
                    role,
                    email,
                    encrypted_password,
                    email_confirmed_at,
                    created_at,
                    updated_at,
                    confirmation_token,
                    recovery_token,
                    email_change_token_new,
                    email_change_token_current,
                    raw_app_meta_data,
                    raw_user_meta_data
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb
                )
                """,
                (
                    str(new_id),
                    "00000000-0000-0000-0000-000000000000",  # default instance_id
                    "authenticated",
                    "authenticated",
                    email,
                    hashed,
                    now,          # email_confirmed_at (auto-confermiamo per app mobile)
                    now,          # created_at
                    now,          # updated_at
                    "",           # confirmation_token
                    "",           # recovery_token
                    "",           # email_change_token_new
                    "",           # email_change_token_current
                    '{"provider": "email", "providers": ["email"]}',
                    "{}",
                ),
            )

    access_token, expires_in = create_access_token(new_id)
    refresh_token = create_refresh_token(new_id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


def refresh_access_token(refresh_token: str) -> TokenResponse:
    """Genera un nuovo access token verificando un refresh token valido."""
    from jose import JWTError

    try:
        user_id = get_user_id_from_token(refresh_token, expected_type="refresh")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verifica che l'utente esista ancora
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute(
                "SELECT id FROM auth.users WHERE id = %s AND deleted_at IS NULL LIMIT 1",
                (user_id,),
            )
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Utente non trovato",
                )

    access_token, expires_in = create_access_token(user_id)
    # Ruota anche il refresh token per maggiore sicurezza
    new_refresh_token = create_refresh_token(user_id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=expires_in,
    )


def get_current_user(user_id: str) -> UserResponse:
    """Restituisce i dati dell'utente autenticato."""
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute(
                """
                SELECT id, email, created_at, updated_at,
                       email_confirmed_at, last_sign_in_at
                FROM auth.users
                WHERE id = %s
                  AND deleted_at IS NULL
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )

    return UserResponse(**dict(row))
