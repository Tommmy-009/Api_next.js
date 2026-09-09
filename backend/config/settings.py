"""
config/settings.py — Impostazioni centralizzate da variabili d'ambiente
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PostgreSQL
    database_url: str

    # JWT
    jwt_secret_key: str
    argo_credentials_key: str | None = None
    admin_dashboard_username: str | None = None
    admin_dashboard_password: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    argo_scrape_timeout_seconds: int = 120
    cors_origins: str = "*"
    debug_scraper: bool = False

    model_config = SettingsConfigDict(
        # Support both `uvicorn main:app` from backend/ and repository-root tools.
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
