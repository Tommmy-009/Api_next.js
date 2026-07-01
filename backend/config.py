"""
config.py — Impostazioni centralizzate lette da variabili d'ambiente / .env
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Singleton importabile ovunque
settings = Settings()
