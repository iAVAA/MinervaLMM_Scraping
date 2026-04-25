# ==============================================================================
# Percorso relativo: frontend/Dockerfile
# Corso: Laboratorio di ingegneria informatica
# Corso di Laurea: Ingegneria informatica e automatica
# Ateneo: Sapienza Università di Roma
# Data: Aprile 2026
# Autori: Matricole 2114420, 2115153, 2056502
#
# Descrizione:
# Questo Dockerfile definisce l'ambiente containerizzato per il servizio frontend.
# Configura un'immagine leggera basata su Python 3.10 slim, gestisce l'installazione
# delle dipendenze e predispone l'avvio del server ASGI Uvicorn per esporre
# l'interfaccia utente basata su FastAPI e Jinja2 sulla porta 8004.
# ==============================================================================

# Immagine di base ufficiale di Python, versione minimale (slim) per ridurre l'impronta
# di memoria e accelerare i tempi di build e deployment.
FROM python:3.10-slim

# Definizione della directory di lavoro principale all'interno del container.
WORKDIR /app

# Copia del file contenente le librerie necessarie (es. FastAPI, httpx, jinja2) 
# nell'ambiente isolato del container.
COPY requirements.txt .

# Installazione delle dipendenze Python. Il flag --no-cache-dir è utilizzato 
# per prevenire il salvataggio dei pacchetti scaricati, ottimizzando le dimensioni finali dell'immagine.
RUN pip install --no-cache-dir -r requirements.txt

# Modifica della directory di lavoro alla cartella specifica del frontend 
# da cui verrà eseguito il server.
WORKDIR /app/frontend

# Comando di entrypoint del container: avvia il server web ASGI Uvicorn.
# L'host "0.0.0.0" garantisce che il servizio sia accessibile dall'esterno del container
# (es. dalla rete Docker interna o dall'host) esponendo il servizio sulla porta 8004.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8004"]