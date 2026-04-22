"""
Percorso relativo: backend/src/server.py
Corso: Laboratorio di ingegneria informatica
Corso di Laurea: Ingegneria informatica e automatica
Ateneo: Sapienza Università di Roma
Data: Aprile 2026
Autori: Matricole 2114420, 2115153, 2056502

Descrizione:
Questo modulo costituisce l'entry point principale del backend, implementando
un'API RESTful ad alte prestazioni basata su FastAPI. Gestisce l'orchestrazione
dei vari parser di dominio, l'accesso ai dataset di ground truth (Gold Standard)
e l'esecuzione dinamica delle pipeline di valutazione metrica. Include meccanismi
di fallback per la gestione dei percorsi in ambienti containerizzati e di sviluppo locale.
"""

import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from urllib.parse import urlparse, unquote

# --- PATH DISCOVERY ---
# Identificazione dinamica della root del progetto per garantire la portabilità
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOMAINS_PATH = os.path.join(BASE_DIR, "domains.json")
GS_DATA_DIR = os.path.join(BASE_DIR, "gs_data")

# Meccanismo di fallback: risoluzione pervasiva dei path per garantire il funzionamento
# anche qualora il backend venga avviato isolatamente al di fuori dell'orchestrazione Docker (docker-compose).
if not os.path.exists(DOMAINS_PATH):
    DOMAINS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "domains.json")
if not os.path.exists(GS_DATA_DIR):
    GS_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gs_data")

# --- IMPORTAZIONE MODULI INTERNI ---
# Importazione dei parser specializzati e del modulo di valutazione.
from src.parsers.wikipedia_parser import WikipediaParser
from src.parsers.nobel_parser import NobelParser
from src.parsers.romatoday_parser import RomaTodayParser
from src.parsers.governo_parser import GovernoParser
from src.evaluator.metrics import token_level_eval

# --- INIZIALIZZAZIONE APPLICAZIONE ---
app = FastAPI(
    title="Esonero 1 - Web Parsing API",
    description="API for parsing and evaluating web content from supported domains."
)

# --- REGISTRO DEI PARSER ---
# Dizionario di mapping che associa le varianti dei domini supportati alle rispettive
# istanze dei parser. Implementa un pattern Factory/Strategy semplificato.
PARSERS = {
    "en.wikipedia.org": WikipediaParser(),
    "wikipedia.org": WikipediaParser(),
    "www.wikipedia.org": WikipediaParser(),
   # "www.nobelprize.org": NobelParser(),
    #"nobelprize.org": NobelParser(),
    "www.romatoday.it": RomaTodayParser(),
    "romatoday.it": RomaTodayParser(),
    "www.governo.it": GovernoParser(),
    "governo.it": GovernoParser()
}

# --- DEFINIZIONE SCHEMI PYDANTIC ---

class ParseRequest(BaseModel):
    """Schema per la richiesta di parsing testuale."""
    url: str
    html_text: str | None = None # Opzionale: se fornito, bypassa la rete.

class EvaluationRequest(BaseModel):
    """Schema per la richiesta di valutazione metrica."""
    parsed_text: str
    gold_text: str


# --- ENDPOINT API ---

@app.get("/domains", summary="List supported domains")
def get_domains():
    """
    Recupera l'elenco dei domini attualmente supportati dal sistema leggendo 
    il file di configurazione 'domains.json'.

    Returns:
        list: Lista di domini (stringhe).
        
    Raises:
        HTTPException (500): In caso di errore nella lettura del file.
    """
    try:
        with open(DOMAINS_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/parse", summary="Parse a URL")
async def parse_url(url: str):
    """
    Analizza un URL fornito, instrada la richiesta al parser associato al dominio
    ed estrae le informazioni strutturate.

    Args:
        url (str): L'URL della risorsa web da analizzare.

    Returns:
        dict: Il payload estratto dal parser contenente testo pulito e metadati.
        
    Raises:
        HTTPException (400): Se il dominio non è registrato tra quelli supportati.
        HTTPException (500): Se il processo di parsing fallisce internamente.
    """
    domain = urlparse(url).netloc
    parser = PARSERS.get(domain)
    
    if not parser:
        raise HTTPException(
            status_code=400, 
            detail=f"No parser implemented for domain: {domain}"
        )
    
    
    try:
        return await parser.parse(url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing error: {str(e)}")

@app.post("/parse", summary="Parse a URL with optional HTML text")
async def post_parse_url(req: ParseRequest):
    """
    Alternativa in POST dell'endpoint di parsing. Permette l'iniezione diretta 
    del sorgente HTML tramite body request, utile per processare dataset in cache.

    Args:
        req (ParseRequest): Payload contenente l'URL e opzionalmente l'HTML raw.

    Returns:
        dict: Payload dei dati estratti.
    """
    domain = urlparse(req.url).netloc
    parser = PARSERS.get(domain)
    
    if not parser:
        raise HTTPException(
            status_code=400, 
            detail=f"No parser implemented for domain: {domain}"
        )
    
    try:
        # Passaggio dell'HTML raw al parser per evitare richieste di rete superflue
        return await parser.parse(req.url, html_text=req.html_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing error: {str(e)}")

@app.get("/gold_standard", summary="Get GS for a specific URL")
def get_gold_standard(url: str):
    """
    Ricerca ed estrae i dati di riferimento (Gold Standard) specifici per un URL
    dal filesystem locale.

    Args:
        url (str): URL della pagina da cercare nel dataset.

    Returns:
        dict: Il record associato all'URL richiesto.
        
    Raises:
        HTTPException (404): Se l'URL o il dataset per il dominio non esistono.
        HTTPException (500): Errore critico in fase di lettura dati.
    """
    domain = urlparse(url).netloc
    
    # Euristiche per la localizzazione del file GS associato al dominio
    possible_files = [f"{domain}.json"]
    if domain.startswith("www."): possible_files.append(f"{domain[4:]}.json")
    else: possible_files.append(f"www.{domain}.json")
    if domain == "wikipedia.org": possible_files.append("en.wikipedia.org.json")
    
    gs_path = None
    for f_name in possible_files:
        test_path = os.path.join(GS_DATA_DIR, f_name)
        if os.path.exists(test_path):
            gs_path = test_path
            break
    
    if not gs_path:
        raise HTTPException(status_code=404, detail=f"No GS data found for domain: {domain}")
    
    try:
        url_decoded = unquote(url)
        with open(gs_path, "r", encoding="utf-8") as f:
            gs_list = json.load(f)
            # Scansione lineare alla ricerca della singola entità
            for item in gs_list:
                if unquote(item["url"]) == url_decoded:
                    return item
            raise HTTPException(status_code=404, detail="URL not found in gold standard.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading GS data: {str(e)}")

@app.get("/full_gold_standard", summary="Get all GS for a domain")
def get_full_gold_standard(domain: str):
    """
    Restituisce l'intero dataset di Ground Truth (Gold Standard) relativo 
    a un dominio specifico.

    Args:
        domain (str): Il nome del dominio (es. "www.governo.it").

    Returns:
        dict: Dizionario con chiave 'gold_standard' contenente la lista dei record.
    """
    possible_files = [f"{domain}.json"]
    if domain.startswith("www."): possible_files.append(f"{domain[4:]}.json")
    else: possible_files.append(f"www.{domain}.json")
    if domain == "wikipedia.org": possible_files.append("en.wikipedia.org.json")

    gs_path = None
    for f_name in possible_files:
        test_path = os.path.join(GS_DATA_DIR, f_name)
        if os.path.exists(test_path):
            gs_path = test_path
            break
            
    if not gs_path:
        raise HTTPException(status_code=404, detail=f"Gold standard file for {domain} not found.")
    
    try:
        with open(gs_path, "r", encoding="utf-8") as f:
            return {"gold_standard": json.load(f)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evaluate", summary="Evaluate text against gold standard")
def evaluate(req: EvaluationRequest):
    """
    Calcola le metriche di valutazione testuale (Precision, Recall, F1, ROUGE, ecc.) 
    confrontando dinamicamente due porzioni di testo fornite.

    Args:
        req (EvaluationRequest): Payload contenente il testo estratto e il testo Gold Standard.

    Returns:
        dict: Risultati partizionati in "token_level_eval" e "x_eval" (metriche avanzate).
    """
    metrics = token_level_eval(req.parsed_text, req.gold_text)
    return {
        "token_level_eval": {
            "precision": metrics.pop("precision"),
            "recall": metrics.pop("recall"),
            "f1": metrics.pop("f1")
        },
        "x_eval": metrics
    }

@app.get("/full_gs_eval", summary="Run full domain evaluation")
async def full_gs_eval(domain: str):
    """
    Innesca un'esecuzione batch automatizzata: valuta la qualità estrattiva del parser
    applicandolo in sequenza su tutti gli URL presenti nel Gold Standard di un dominio,
    restituendo le metriche medie aggregate sull'intero dataset.

    Args:
        domain (str): Il dominio target su cui condurre il test massivo.

    Returns:
        dict: Statistiche medie riassuntive sull'intero corpus (Precision, F1, Jaccard, ecc.).
    """
    # Identificazione del path corretto per il file GS
    possible_files = [f"{domain}.json"]
    if domain.startswith("www."): possible_files.append(f"{domain[4:]}.json")
    else: possible_files.append(f"www.{domain}.json")
    if domain == "wikipedia.org": possible_files.append("en.wikipedia.org.json")

    gs_path = None
    for f_name in possible_files:
        test_path = os.path.join(GS_DATA_DIR, f_name)
        if os.path.exists(test_path):
            gs_path = test_path
            break

    if not gs_path:
        raise HTTPException(status_code=404, detail="Gold standard file not found.")
    
    parser = PARSERS.get(domain)
    if not parser:
        raise HTTPException(status_code=400, detail=f"Domain {domain} not supported for evaluation.")

    try:
        with open(gs_path, "r", encoding="utf-8") as f:
            gs_list = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading GS: {str(e)}")
    
    # Se la lista è vuota, restituisce valori a zero per evitare eccezioni di divisione.
    if not gs_list:
        return {
            "token_level_eval": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
            "x_eval": {k: 0.0 for k in ["jaccard", "cer", "wer", "rouge_l", "leakage"]}
        }
    
    # Inizializzazione degli accumulatori per il calcolo della media aritmetica
    metrics_sum = {k: 0.0 for k in ["precision", "recall", "f1", "jaccard", "cer", "wer", "rouge_l", "leakage"]}
    
    for item in gs_list:
        url = item["url"]
        gold_text = item["gold_text"]
        
        try:
            # Sfrutta l'HTML in cache (se disponibile) per massimizzare le performance di test
            parsed_data = await parser.parse(url, html_text=item.get("html_text"))
            metrics = token_level_eval(parsed_data["parsed_text"], gold_text)
            
            # Somma incrementale delle metriche correnti
            for k in metrics_sum:
                metrics_sum[k] += metrics[k]
        except Exception:
            # Fallback passivo: in una build di produzione qui andrebbe un logging su file (es. logger.warning).
            # Ignoriamo il record fallito per non interrompere il job massivo.
            continue
            
    count = len(gs_list)
    # Calcolo delle medie pesate sul totale dei documenti del Gold Standard
    avg_metrics = {k: v / count for k, v in metrics_sum.items()}
    
    return {
        "token_level_eval": {
            "precision": avg_metrics.pop("precision"),
            "recall": avg_metrics.pop("recall"),
            "f1": avg_metrics.pop("f1")
        },
        "x_eval": avg_metrics
    }