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
    """Genera un hash bcrypt."""
    hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=10))
    return hashed.decode()


def _verify_password(plain: str, hashed: str) -> bool:
    """Verifica una password contro un hash bcrypt."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# --------------------------------------------------------------------------- #
#  Service functions
# --------------------------------------------------------------------------- #

def login_user(email: str, password: str) -> TokenResponse:
    """
    Cerca l'utente per email nella tabella users,
    verifica la password e restituisce i token.
    """
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute(
                """
                SELECT id, encrypted_password
                FROM users
                WHERE email = %s
                LIMIT 1
                """,
                (email.lower().strip(),),
            )
            row = cur.fetchone()

    if row is None or not _verify_password(password, row["encrypted_password"] or ""):
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
    Registra un nuovo utente nella tabella users locale.
    """
    email = email.lower().strip()
    hashed = _hash_password(password)
    new_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with get_db() as conn:
        with get_cursor(conn) as cur:

            # Controlla email già esistente
            cur.execute(
                "SELECT id FROM users WHERE email = %s LIMIT 1",
                (email,),
            )

            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email già registrata",
                )

            # Inserisce nuovo utente
            cur.execute(
                """
                INSERT INTO users (
                    id,
                    email,
                    encrypted_password,
                    created_at,
                    updated_at,
                    email_confirmed_at,
                    last_sign_in_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(new_id),
                    email,
                    hashed,
                    now,
                    now,
                    now,
                    now,
                ),
            )

        conn.commit()

    access_token, expires_in = create_access_token(new_id)
    refresh_token = create_refresh_token(new_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


def refresh_access_token(refresh_token: str) -> TokenResponse:
    """Genera un nuovo access token da refresh token."""
    from jose import JWTError

    try:
        user_id = get_user_id_from_token(
            refresh_token,
            expected_type="refresh"
        )

    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verifica esistenza utente
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute(
                "SELECT id FROM users WHERE id = %s LIMIT 1",
                (user_id,),
            )

            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Utente non trovato",
                )

    access_token, expires_in = create_access_token(user_id)
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
                SELECT
                    id,
                    email,
                    created_at,
                    updated_at,
                    email_confirmed_at,
                    last_sign_in_at
                FROM users
                WHERE id = %s
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