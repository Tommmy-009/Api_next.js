"""
models/argo.py — Schemas Pydantic per gestione credenziali Argo
"""
from typing import Annotated

from pydantic import BaseModel, StringConstraints

NonEmptyTrimmed = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ArgoCredentialsUpsertRequest(BaseModel):
    codice_scuola: NonEmptyTrimmed
    username: NonEmptyTrimmed
    password: NonEmptyTrimmed


class ArgoCredentialsUpsertResponse(BaseModel):
    success: bool
    configured: bool


class ArgoCredentialsConfiguredResponse(BaseModel):
    configured: bool


class ArgoCredentialsDetailsResponse(BaseModel):
    configured: bool
    codice_scuola: str | None = None
    username: str | None = None


class ArgoTeacherItem(BaseModel):
    name: str
    subject: str | None = None


class ArgoTeachersScrapeResponse(BaseModel):
    teachers: list[ArgoTeacherItem]
    result: list[ArgoTeacherItem]
    count: int
