"""
auth/password.py — Verifica password bcrypt
"""
import bcrypt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica una password in chiaro contro un hash bcrypt.
    Compatibile con i prefissi $2a$ (Supabase/PostgreSQL) e $2b$ (python-bcrypt).

    Args:
        plain_password:  Password inviata dall'utente in chiaro
        hashed_password: Hash bcrypt salvato in auth.users.encrypted_password

    Returns:
        True se la password è corretta, False altrimenti.
        Non lancia mai eccezioni — restituisce False in caso di errore.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def hash_password(plain_password: str) -> str:
    """
    Genera un hash bcrypt per una nuova password.
    Usato solo in fase di registrazione.

    Returns:
        Stringa hash bcrypt (prefisso $2b$).
    """
    salt = bcrypt.gensalt(rounds=10)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")
