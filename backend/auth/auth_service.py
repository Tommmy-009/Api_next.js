"""
auth/auth_service.py — Business logic: login, get_current_user, refresh
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from models.user import (
    User,
    TokenResponse,
    UserResponse,
    RefreshResponse,
    RegisterRequest,
    GenericSuccessResponse,
    UpdateMeRequest,
)
from auth.password import verify_password, hash_password
from auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
)

logger = logging.getLogger(__name__)


# ── Login ─────────────────────────────────────────────────────────────────────

def login_user(email: str, password: str, db: Session) -> TokenResponse:
    """
    Autentica l'utente:
    1. Cerca l'utente per email in auth.users
    2. Verifica la password con bcrypt
    3. Genera e restituisce access_token + refresh_token

    Raises:
        HTTPException 401: se email non esiste o password errata
                           (messaggio generico per sicurezza)
    """
    # 1. Query — recupera solo le colonne necessarie
    user: User | None = (
        db.query(User)
        .filter(User.email == email.lower().strip())
        .first()
    )

    # 2. Verifica — messaggio identico per email inesistente e password sbagliata
    #    (anti user-enumeration)
    if user is None or not user.encrypted_password:
        _raise_invalid_credentials()

    if not verify_password(password, user.encrypted_password):
        _raise_invalid_credentials()

    # 3. Genera token
    user_id = str(user.id)
    access_token, expires_in = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


# ── /me ───────────────────────────────────────────────────────────────────────

def get_current_user(user_id: str, db: Session) -> UserResponse:
    """
    Restituisce i dati dell'utente dato il suo UUID.

    Raises:
        HTTPException 404: se l'utente non esiste
    """
    user: User | None = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )

    return _to_user_response(user, db)


# ── Refresh ───────────────────────────────────────────────────────────────────

def refresh_tokens(refresh_token: str, db: Session) -> RefreshResponse:
    """
    Verifica un refresh token e genera un nuovo access token.

    Raises:
        HTTPException 401: se il refresh token non è valido o l'utente non esiste
    """
    from jose import JWTError

    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_issued_at = _token_datetime(payload.get("iat"))
    if _is_refresh_revoked(user_id, token_issued_at, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revocato",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Controlla che l'utente esista ancora
    user: User | None = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente non trovato",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, expires_in = create_access_token(user_id)

    return RefreshResponse(
        access_token=access_token,
        expires_in=expires_in,
    )


# ── Register ──────────────────────────────────────────────────────────────────

def register_user(body: RegisterRequest, db: Session) -> UserResponse:
    email = body.email.lower().strip()
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email già registrata",
        )

    new_user = User(
        email=email,
        encrypted_password=hash_password(body.password),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(new_user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email già registrata",
        )

    if body.name is not None:
        _upsert_profile_name(str(new_user.id), body.name, db)

    db.commit()
    db.refresh(new_user)
    return _to_user_response(new_user, db)


# ── Logout ────────────────────────────────────────────────────────────────────

def logout_user(user_id: str, db: Session) -> None:
    _upsert_refresh_token_state(user_id, db)
    db.commit()


# ── Delete account ────────────────────────────────────────────────────────────

def delete_account(user_id: str, db: Session) -> None:
    user: User | None = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )

    _delete_user_rows("public.password_reset_tokens", user_id, db)
    _delete_user_rows("public.refresh_token_state", user_id, db)
    _delete_user_rows("public.user_profiles", user_id, db)
    _delete_user_rows("public.argo_credentials", user_id, db)
    _delete_user_rows("public.promemoria", user_id, db)

    db.delete(user)
    db.commit()


# ── Password reset ────────────────────────────────────────────────────────────

def forgot_password(email: str, db: Session) -> GenericSuccessResponse:
    normalized_email = email.lower().strip()
    user: User | None = db.query(User).filter(User.email == normalized_email).first()

    if user is not None:
        reset_token = secrets.token_urlsafe(32)
        token_hash = _sha256(reset_token)

        db.execute(
            text(
                """
                INSERT INTO public.password_reset_tokens (user_id, token_hash, expires_at)
                VALUES (:user_id, :token_hash, :expires_at)
                """
            ),
            {
                "user_id": str(user.id),
                "token_hash": token_hash,
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            },
        )
        db.commit()
        logger.info("Password reset requested for an existing account")

    return GenericSuccessResponse(message="Se l'email esiste, riceverai istruzioni per il reset")


def reset_password(reset_token: str, new_password: str, db: Session) -> GenericSuccessResponse:
    token_hash = _sha256(reset_token)
    token_row = db.execute(
        text(
            """
            SELECT id, user_id
            FROM public.password_reset_tokens
            WHERE token_hash = :token_hash
              AND used_at IS NULL
              AND expires_at > NOW()
            LIMIT 1
            """
        ),
        {"token_hash": token_hash},
    ).first()

    if token_row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token di reset non valido o scaduto",
        )

    token_data = token_row._mapping
    user: User | None = db.query(User).filter(User.id == token_data["user_id"]).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )

    user.encrypted_password = hash_password(new_password)
    user.updated_at = datetime.now(timezone.utc)

    db.execute(
        text(
            """
            UPDATE public.password_reset_tokens
            SET used_at = NOW()
            WHERE id = :token_id
            """
        ),
        {"token_id": token_data["id"]},
    )
    _upsert_refresh_token_state(str(user.id), db)
    db.commit()

    return GenericSuccessResponse(message="Password aggiornata con successo")


# ── Update profile ────────────────────────────────────────────────────────────

def update_me(user_id: str, body: UpdateMeRequest, db: Session) -> UserResponse:
    user: User | None = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )

    if body.email is not None:
        normalized_email = body.email.lower().strip()
        conflict_user = (
            db.query(User)
            .filter(User.email == normalized_email, User.id != user_id)
            .first()
        )
        if conflict_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email già in uso",
            )
        user.email = normalized_email

    if body.password is not None:
        user.encrypted_password = hash_password(body.password)
        _upsert_refresh_token_state(user_id, db)

    if body.name is not None:
        _upsert_profile_name(user_id, body.name, db)

    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return _to_user_response(user, db)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _raise_invalid_credentials():
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenziali non valide",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _get_profile_name(user_id: str, db: Session) -> str | None:
    try:
        row = db.execute(
            text("SELECT name FROM public.user_profiles WHERE user_id = :user_id LIMIT 1"),
            {"user_id": user_id},
        ).first()
    except Exception as exc:
        if _is_missing_relation(exc, "public.user_profiles") or _is_permission_denied(exc):
            db.rollback()
            logger.warning(
                "Lettura public.user_profiles non disponibile (tabella assente o permessi insufficienti): ritorno name=None"
            )
            return None
        raise

    if row is None:
        return None
    return row._mapping["name"]


def _to_user_response(user: User, db: Session) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        name=_get_profile_name(str(user.id), db),
        created_at=user.created_at,
        email_confirmed_at=user.email_confirmed_at,
        last_sign_in_at=user.last_sign_in_at,
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _token_datetime(value) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token iat non valido",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _is_refresh_revoked(user_id: str, token_issued_at: datetime, db: Session) -> bool:
    try:
        row = db.execute(
            text(
                """
                SELECT revoked_after
                FROM public.refresh_token_state
                WHERE user_id = :user_id
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        ).first()
    except Exception as exc:
        if _is_missing_relation(exc, "public.refresh_token_state"):
            db.rollback()
            logger.warning("Tabella public.refresh_token_state non trovata: revoca refresh disattivata")
            return False
        raise

    if row is None or row._mapping["revoked_after"] is None:
        return False

    revoked_after = row._mapping["revoked_after"]
    if revoked_after.tzinfo is None:
        revoked_after = revoked_after.replace(tzinfo=timezone.utc)
    return token_issued_at <= revoked_after.astimezone(timezone.utc)


def _is_missing_relation(exc: Exception, relation_name: str) -> bool:
    msg = str(exc).lower()
    return "does not exist" in msg and relation_name.lower() in msg


def _is_permission_denied(exc: Exception) -> bool:
    return "permission denied" in str(exc).lower()


def _upsert_refresh_token_state(user_id: str, db: Session) -> None:
    try:
        db.execute(
            text(
                """
                INSERT INTO public.refresh_token_state (user_id, revoked_after)
                VALUES (:user_id, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    revoked_after = EXCLUDED.revoked_after
                """
            ),
            {"user_id": user_id},
        )
    except Exception as exc:
        if _is_missing_relation(exc, "public.refresh_token_state") or _is_permission_denied(exc):
            db.rollback()
            logger.warning(
                "Scrittura public.refresh_token_state non disponibile (tabella assente o permessi insufficienti): revoca refresh disattivata"
            )
            return
        raise


def _upsert_profile_name(user_id: str, name: str, db: Session) -> None:
    try:
        db.execute(
            text(
                """
                INSERT INTO public.user_profiles (user_id, name, updated_at)
                VALUES (:user_id, :name, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    updated_at = NOW()
                """
            ),
            {"user_id": user_id, "name": name},
        )
    except Exception as exc:
        if _is_missing_relation(exc, "public.user_profiles") or _is_permission_denied(exc):
            db.rollback()
            logger.warning(
                "Scrittura public.user_profiles non disponibile (tabella assente o permessi insufficienti): aggiornamento nome disattivato"
            )
            return
        raise


def _delete_user_rows(table_name: str, user_id: str, db: Session) -> None:
    try:
        with db.begin_nested():
            db.execute(
                text(f"DELETE FROM {table_name} WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
    except Exception as exc:
        if _is_missing_relation(exc, table_name) or _is_permission_denied(exc):
            logger.warning(
                "Cancellazione %s non disponibile (tabella assente o permessi insufficienti): salto",
                table_name,
            )
            return
        raise
