FROM mcr.microsoft.com/playwright/python:v1.62.0-jammy

WORKDIR /app/backend

# Runtime defaults for container logs and Python behavior
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install dependencies first for better Docker layer caching
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Copy backend source code
COPY backend/ /app/backend/

EXPOSE 2367

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "2367"]
