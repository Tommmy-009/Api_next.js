"""
models/user.py — Modello SQLAlchemy users locale
             + Modelli Pydantic per request/response API
"""

from sqlalchemy import Column, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from database.db import Base

from pydantic import BaseModel, EmailStr, field_validator, model_validator

from typing import Optional
from datetime import datetime

import uuid


# ── ORM Model ────────────────────────────────────────────────────────────────

class User(Base):
    """
    Modello utenti Supabase/PostgreSQL.
    La tabella reale vive nello schema auth.
    """

    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email              = Column(Text, unique=True, nullable=False, index=True)
    encrypted_password = Column(Text, nullable=True)

    created_at         = Column(DateTime(timezone=True), nullable=True)
    updated_at         = Column(DateTime(timezone=True), nullable=True)

    email_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    last_sign_in_at    = Column(DateTime(timezone=True), nullable=True)


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("La password non può essere vuota")
        return v


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def register_password_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("La password non può essere vuota")
        return v

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None

        name = v.strip()
        return name or None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def reset_password_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("La password non può essere vuota")

        return v


class UpdateMeRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None

    @field_validator("name")
    @classmethod
    def update_name_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None

        name = v.strip()
        return name or None

    @field_validator("password")
    @classmethod
    def update_password_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None

        if not v.strip():
            raise ValueError("La password non può essere vuota")

        return v

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.name is None and self.email is None and self.password is None:
            raise ValueError("Fornisci almeno un campo da aggiornare")

        return self


class GenericSuccessResponse(BaseModel):
    success: bool = True
    message: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str

    name: Optional[str] = None

    created_at: Optional[datetime] = None
    email_confirmed_at: Optional[datetime] = None
    last_sign_in_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }
