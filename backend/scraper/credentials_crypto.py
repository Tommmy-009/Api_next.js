"""
scraper/credentials_crypto.py — cifratura/decifratura credenziali Argo
"""
import hashlib
from base64 import urlsafe_b64encode

from fastapi import HTTPException, status

from config.settings import settings


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


def encrypt_argo_password(raw_password: str) -> str:
    cipher = _get_argo_cipher()
    return cipher.encrypt(raw_password.encode("utf-8")).decode("utf-8")


def decrypt_argo_password(stored_password: str) -> str:
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
