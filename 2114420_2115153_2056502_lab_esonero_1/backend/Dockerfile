# ==============================================================================
# Percorso relativo: backend/Dockerfile
# Corso: Laboratorio di ingegneria informatica
# Corso di Laurea: Ingegneria informatica e automatica
# Ateneo: Sapienza Università di Roma
# Data: Aprile 2026
# Autori: Matricole 2114420, 2115153, 2056502
#
# Descrizione:
# Questo Dockerfile definisce l'immagine container per il servizio backend.
# Configura un ambiente runtime basato su Python 3.10, installando in modo
# ottimizzato le dipendenze di sistema necessarie per il funzionamento dei
# browser headless (tramite Playwright, richiesto dal framework Crawl4AI).
# Infine, espone l'API RESTful gestita da FastAPI/Uvicorn.
# ==============================================================================

# Immagine di base ufficiale di Python, versione minimale (slim) per ridurre l'impronta di memoria
FROM python:3.10-slim

# Aggiornamento dei repository OS e installazione dei pacchetti di sistema richiesti.
# Vengono inclusi i core grafici (libnss3, libgbm1, ecc.) fondamentali per
# permettere a Playwright di eseguire Chromium in modalità headless all'interno del container.
# Il flag --no-install-recommends e la rimozione finale delle cache di apt-get mantengono l'immagine leggera.
RUN apt-get update && apt-get install -y \
    wget gnupg \
    libnss3 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Definizione della directory di lavoro root del container
WORKDIR /app

# Copia del file contenente le dipendenze Python e successiva installazione.
# L'opzione --no-cache-dir previene la memorizzazione locale dei pacchetti scaricati, ottimizzando le dimensioni.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Inizializzazione di Playwright: scarica esclusivamente il binario per Chromium (ignorando WebKit/Firefox)
RUN playwright install chromium

# Risoluzione dinamica e installazione di eventuali dipendenze OS di basso livello 
# mancanti specifiche per la versione di Playwright correntemente installata
RUN playwright install-deps

# Impostazione del working directory specifico per l'esecuzione del codice backend
WORKDIR /app/backend

# Comando di entrypoint del container: avvia il server ASGI Uvicorn.
# Nota architettonica: in fase di sviluppo/esecuzione tramite docker-compose, 
# la directory /app/backend viene generalmente mappata su un volume locale,
# sovrascrivendo i file per abilitare l'hot-reloading senza dover ricostruire l'immagine.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8003"]