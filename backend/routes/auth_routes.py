"""
routes/auth_routes.py — Router FastAPI per tutti gli endpoint di autenticazione
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError

from database.db import get_db
from models.user import (
    LoginRequest,
    TokenResponse,
    UserResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    GenericSuccessResponse,
    UpdateMeRequest,
)
from auth.auth_service import (
    login_user,
    get_current_user,
    refresh_tokens,
    register_user,
    forgot_password,
    reset_password,
    logout_user,
    update_me,
)
from auth.jwt_handler import get_user_id_from_token

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer_scheme = HTTPBearer()


# ── Dependency — estrae e valida il JWT dall'header Authorization ─────────────

def _get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """
    Legge 'Authorization: Bearer <token>' e restituisce il user_id.
    Lancia HTTP 401 se il token è assente, scaduto o non valido.
    """
    try:
        return get_user_id_from_token(credentials.credentials, expected_type="access")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login con email e password",
    description=(
        "Verifica le credenziali contro `auth.users` "
        "e restituisce `access_token` + `refresh_token`."
    ),
)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    **Esempio richiesta:**
    ```json
    { "email": "user@example.com", "password": "secret" }
    ```
    """
    return login_user(body.email, body.password, db)


# ── POST /auth/refresh ────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Rinnova l'access token tramite refresh token",
    description="Restituisce un nuovo access token validando il refresh token.",
)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    """
    **Esempio richiesta:**
    ```json
    {
      "refresh_token": "eyJ..."
    }
    ```
    """
    return refresh_tokens(body.refresh_token, db)


# ── POST /auth/register ───────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registra un nuovo utente",
)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    return register_user(body, db)


# ── POST /auth/forgot-password ────────────────────────────────────────────────

@router.post(
    "/forgot-password",
    response_model=GenericSuccessResponse,
    summary="Avvia il reset password",
)
def forgot_password_endpoint(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    return forgot_password(body.email, db)


# ── POST /auth/reset-password ─────────────────────────────────────────────────

@router.post(
    "/reset-password",
    response_model=GenericSuccessResponse,
    summary="Completa il reset password",
)
def reset_password_endpoint(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    return reset_password(body.reset_token, body.new_password, db)


# ── POST /auth/logout ─────────────────────────────────────────────────────────

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Invalida il refresh token lato server",
)
def logout(
    user_id: str = Depends(_get_current_user_id),
    db: Session = Depends(get_db),
):
    logout_user(user_id, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Dati dell'utente autenticato",
)
def me(
    user_id: str = Depends(_get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Richiede header `Authorization: Bearer <access_token>`.
    """
    return get_current_user(user_id, db)


# ── PATCH /auth/me ────────────────────────────────────────────────────────────

@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Aggiorna il profilo dell'utente autenticato",
)
def patch_me(
    body: UpdateMeRequest,
    user_id: str = Depends(_get_current_user_id),
    db: Session = Depends(get_db),
):
    return update_me(user_id, body, db)
