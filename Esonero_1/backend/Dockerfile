FROM python:3.10-slim

# Installa librerie di sistema necessarie per playwright e networking
RUN apt-get update && apt-get install -y \
    wget gnupg \
    libnss3 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
RUN playwright install-deps

WORKDIR /app/backend

# In fase di esecuzione (docker-compose) il codice in /app/backend verrà sovrascritto dal volume mount
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8003"]
