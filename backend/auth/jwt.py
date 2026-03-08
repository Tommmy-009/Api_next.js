"""
auth/jwt.py — Creazione e verifica di JWT (access + refresh token)
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from typing import Literal

from jose import JWTError, jwt

from config.settings import settings

TokenType = Literal["access", "refresh"]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: UUID | str) -> tuple[str, int]:
    """
    Crea un JWT di tipo 'access'.
    Restituisce (token, expires_in_seconds).
    """
    expire_seconds = settings.access_token_expire_minutes * 60
    expire = _now_utc() + timedelta(seconds=expire_seconds)

    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": expire,
        "iat": _now_utc(),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expire_seconds


def create_refresh_token(user_id: UUID | str) -> str:
    """
    Crea un JWT di tipo 'refresh' a lunga scadenza.
    """
    expire = _now_utc() + timedelta(days=settings.refresh_token_expire_days)

    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iat": _now_utc(),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: TokenType) -> dict:
    """
    Decodifica e valida un JWT.
    Lancia JWTError se il token non è valido, scaduto, o del tipo sbagliato.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise JWTError(f"Token non valido: {exc}") from exc

    if payload.get("type") != expected_type:
        raise JWTError(f"Tipo di token non valido: atteso '{expected_type}'")

    return payload


def get_user_id_from_token(token: str, expected_type: TokenType = "access") -> str:
    """
    Helper: restituisce il subject (user_id) da un token valido.
    """
    payload = decode_token(token, expected_type)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise JWTError("Token privo di 'sub'")
    return user_id
