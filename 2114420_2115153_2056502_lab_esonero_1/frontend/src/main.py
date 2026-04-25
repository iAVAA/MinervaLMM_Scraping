"""
Percorso relativo: frontend/src/frontend.py
Corso: Laboratorio di ingegneria informatica
Corso di Laurea: Ingegneria informatica e automatica
Ateneo: Sapienza Università di Roma
Data: Aprile 2026
Autori: Matricole 2114420, 2115153, 2056502

Descrizione:
Questo modulo implementa il servizio frontend dell'architettura. Sviluppato
utilizzando FastAPI per la gestione del routing e Jinja2 per il rendering 
dinamico dei template HTML. Agisce da API Gateway client-side, gestendo 
le interazioni dell'utente, orchestrando le chiamate asincrone verso il backend
per i processi di scraping e le valutazioni metriche rispetto al Gold Standard.
"""

from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import httpx
import os

# Inizializzazione dell'applicazione FastAPI dedicata all'interfaccia utente
app = FastAPI(title="Esonero 1 Frontend")

# Configurazione del motore di templating Jinja2 puntando alla directory locale "templates"
templates = Jinja2Templates(directory="templates")

# Risoluzione dinamica dell'URL del backend: 
# Utilizza le variabili d'ambiente per il deployment containerizzato (es. Docker), 
# con fallback su localhost per gli ambienti di sviluppo e testing locale.
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8003")

async def get_all_gs_data(client: httpx.AsyncClient, domains: list):
    """
    Funzione di supporto per aggregare in modo asincrono tutti i dati di Gold Standard
    (GS) disponibili per una lista di domini supportati.
    
    Args:
        client (httpx.AsyncClient): Client HTTP asincrono condiviso.
        domains (list): Lista di domini (stringhe) da interrogare.
        
    Returns:
        list: Lista aggregata di tutti i record Gold Standard trovati.
    """
    all_gs = []
    for domain in domains:
        try:
            # Richiede l'intero corpus GS associato al dominio specifico
            resp = await client.get(f"{BACKEND_URL}/full_gold_standard?domain={domain}")
            if resp.status_code == 200:
                all_gs.extend(resp.json().get("gold_standard", []))
        except:
            # Silenzia le eccezioni di connessione per i singoli domini per 
            # garantire una parziale operatività (graceful degradation).
            continue
    return all_gs

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Endpoint di root (GET).
    Renderizza la pagina principale popolando i menu a tendina con i domini
    supportati e pre-caricando i dati di test (Gold Standard) disponibili nel backend.
    """
    domains_data = {"domains": []}
    gs_list = []
    error = None
    
    try:
        # Inizializza un client asincrono con timeout per prevenire hanging
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Recupera l'elenco dei domini supportati dall'API di backend
            resp = await client.get(f"{BACKEND_URL}/domains")
            if resp.status_code == 200:
                domains = resp.json()
                
            try:
                # Esegue iterativamente il fetch massivo dei GS per ogni dominio
                for d in domains.get("domains", []):
                    gs_resp = await client.get(f"{BACKEND_URL}/full_gold_standard?domain={d}")
                    if gs_resp.status_code == 200:
                        gs_list.extend(gs_resp.json().get("gold_standard", []))
            except:
                pass

    except Exception as e:
        # Intercetta errori critici (es. backend down) propagando un messaggio UI
        error = f"Cannot connect to backend: {e}"

    # Inietta il contesto recuperato all'interno del template index.html
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "domains": domains_data.get("domains", []),
            "error": error,
            "gs_list": gs_list
        }
    )

@app.post("/parse", response_class=HTMLResponse)
async def parse(request: Request, url: str = Form(...)):
    """
    Endpoint di elaborazione principale (POST).
    Riceve un URL in input dall'utente, interroga il backend per eseguire
    il parsing del contenuto e, se presente un Gold Standard associato a tale URL,
    innesca automaticamente la valutazione delle metriche qualitative.
    """
    parsed_data = None
    metrics = None
    gs_data = None
    error = None
    domains_data = {"domains": []}
    gs_list = []
    
    try:
        # Aumentato il timeout a 30s per compensare i tempi fisiologici di crawling/rendering
        async with httpx.AsyncClient(timeout=30.0) as client:
            
            # FASE 1: Ricerca preventiva del Gold Standard.
            # Se disponibile, estrae l'HTML pre-salvato per bypassare il download di rete 
            # nel backend (migliorando determinismo e velocità).
            gs_resp = await client.get(f"{BACKEND_URL}/gold_standard?url={url}")
            if gs_resp.status_code == 200:
                gs_data = gs_resp.json()
            
            # FASE 2: Esecuzione del parsing tramite backend.
            payload = {"url": url}
            if gs_data and gs_data.get("html_text"):
                payload["html_text"] = gs_data["html_text"]
                
            resp = await client.post(f"{BACKEND_URL}/parse", json=payload)
            if resp.status_code == 200:
                parsed_data = resp.json()
                
                # FASE 3: Valutazione metrica (eseguita solo in presenza di Ground Truth).
                if gs_data:
                    eval_resp = await client.post(f"{BACKEND_URL}/evaluate", json={
                        "parsed_text": parsed_data["parsed_text"],
                        "gold_text": gs_data["gold_text"]
                    })
                    if eval_resp.status_code == 200:
                        metrics = eval_resp.json()
            else:
                error = resp.json().get("detail", "Error during parsing")

            # FASE 4: Aggiornamento dello stato dell'interfaccia (re-idratazione del contesto).
            d_resp = await client.get(f"{BACKEND_URL}/domains")
            if d_resp.status_code == 200:
                domains = d_resp.json()
            
            try:
                for d in domains.get("domains", []):
                    gsl_resp = await client.get(f"{BACKEND_URL}/full_gold_standard?domain={d}")
                    if gsl_resp.status_code == 200:
                        gs_list.extend(gsl_resp.json().get("gold_standard", []))
            except:
                pass
                
    except Exception as e:
        error = str(e)
        
    # Renderizza nuovamente la view principale iniettando i risultati e/o le metriche.
    return templates.TemplateResponse(
        request=request,
        name="index.html", 
        context={
            "parsed_data": parsed_data,
            "metrics": metrics,
            "gs_data": gs_data,
            "error": error,
            "domains": domains_data.get("domains", []),
            "gs_list": gs_list
        }
    )