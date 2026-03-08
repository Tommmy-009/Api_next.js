# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — UpNext FastAPI Backend
# Usa l'immagine ufficiale Playwright per avere Chromium già disponibile
# ─────────────────────────────────────────────────────────────────────────────
FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy

WORKDIR /app

# Copia prima i requirements per sfruttare il layer cache di Docker
COPY backend/requirements.txt .

# Installa le dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Installa solo Chromium (già incluso nell'immagine base, questo lo aggiorna se serve)
RUN playwright install chromium

# Copia il codice del backend
COPY backend/ .

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]