"""
auth/jwt_handler.py — Creazione e decodifica di JWT (access + refresh token)
"""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from jose import JWTError, jwt

from config.settings import settings

TokenType = Literal["access", "refresh"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: str) -> tuple[str, int]:
    """
    Crea un JWT di tipo 'access'.

    Returns:
        (token_string, expires_in_seconds)
    """
    expires_in = settings.access_token_expire_minutes * 60
    expire     = _utc_now() + timedelta(seconds=expires_in)

    payload = {
        "sub":  user_id,
        "type": "access",
        "exp":  expire,
        "iat":  _utc_now(),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_in


def create_refresh_token(user_id: str) -> str:
    """
    Crea un JWT di tipo 'refresh' a lunga scadenza.

    Returns:
        token_string
    """
    expire = _utc_now() + timedelta(days=settings.refresh_token_expire_days)

    payload = {
        "sub":  user_id,
        "type": "refresh",
        "exp":  expire,
        "iat":  _utc_now(),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str, expected_type: TokenType) -> dict:
    """
    Decodifica e valida un JWT.

    Raises:
        JWTError: se il token è scaduto, non valido, o del tipo errato.
    """
    payload: dict = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    if payload.get("type") != expected_type:
        raise JWTError(
            f"Token type mismatch: expected '{expected_type}', "
            f"got '{payload.get('type')}'"
        )

    return payload


def get_user_id_from_token(token: str, expected_type: TokenType = "access") -> str:
    """
    Estrae il 'sub' (user_id) da un token valido.

    Raises:
        JWTError: se il token non è valido.
    """
    payload = decode_token(token, expected_type)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise JWTError("Token missing 'sub' claim")
    try:
        return str(UUID(user_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise JWTError("Token subject non valido") from exc
