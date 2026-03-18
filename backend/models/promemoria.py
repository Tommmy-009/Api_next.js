"""
models/promemoria.py — Modelli Pydantic per promemoria e calendario
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PromemoriaItem(BaseModel):
    data: str          # "21/05/2024"
    materia: str
    descrizione: str


class CalendarEvent(BaseModel):
    id: str
    title: str
    description: str
    start: str         # ISO 8601
    end: str           # ISO 8601
    color: str = "#FF5733"
    all_day: bool = True


class ScrapeRequest(BaseModel):
    user_id: Optional[str] = None


class ScrapeResponse(BaseModel):
    promemoria: list[PromemoriaItem]
    result: list[PromemoriaItem]
    count: int
    scraped: int
    inserted: int
    duplicates: int
    message: str


class PromemoriaListResponse(BaseModel):
    status: str = "success"
    data: list[PromemoriaItem]
    cached: bool = False


class CalendarResponse(BaseModel):
    status: str = "success"
    data: list[CalendarEvent]
