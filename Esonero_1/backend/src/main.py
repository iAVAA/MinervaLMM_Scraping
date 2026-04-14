import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from urllib.parse import urlparse, unquote

# Path Discovery
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOMAINS_PATH = os.path.join(BASE_DIR, "domains.json")
GS_DATA_DIR = os.path.join(BASE_DIR, "gs_data")

# Fallback for localized runs of backend separately
if not os.path.exists(DOMAINS_PATH):
    DOMAINS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "domains.json")
if not os.path.exists(GS_DATA_DIR):
    GS_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gs_data")

# Import parsers
from src.parsers.wikipedia_parser import WikipediaParser
from src.parsers.nobel_parser import NobelParser
from src.parsers.romatoday_parser import RomaTodayParser
from src.parsers.governo_parser import GovernoParser
from src.evaluator.metrics import token_level_eval

# Initialize FastAPI app
app = FastAPI(
    title="Esonero 1 - Web Parsing API",
    description="API for parsing and evaluating web content from supported domains."
)

# Parser Registry
PARSERS = {
    "en.wikipedia.org": WikipediaParser(),
    "www.nobelprize.org": NobelParser(),
    "nobelprize.org": NobelParser(),
    "www.romatoday.it": RomaTodayParser(),
    "www.governo.it": GovernoParser()
}

class EvaluationRequest(BaseModel):
    parsed_text: str
    gold_text: str

@app.get("/domains", summary="List supported domains")
def get_domains():
    """Returns the list of domains currently supported by the system."""
    try:
        with open(DOMAINS_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/parse", summary="Parse a URL")
async def parse_url(url: str):
    """
    Parses the provided URL using the appropriate domain-specific parser.
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

@app.get("/gold_standard", summary="Get GS for a specific URL")
def get_gold_standard(url: str):
    """Retrieves the gold standard data for a specific URL from local storage."""
    domain = urlparse(url).netloc
    gs_path = os.path.join(GS_DATA_DIR, f"{domain}.json")
    
    if not os.path.exists(gs_path):
        raise HTTPException(status_code=404, detail=f"No GS data found for domain: {domain}")
    
    try:
        url_decoded = unquote(url)
        with open(gs_path, "r", encoding="utf-8") as f:
            gs_list = json.load(f)
            for item in gs_list:
                if unquote(item["url"]) == url_decoded:
                    return item
            raise HTTPException(status_code=404, detail="URL not found in gold standard.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading GS data: {str(e)}")

@app.get("/full_gold_standard", summary="Get all GS for a domain")
def get_full_gold_standard(domain: str):
    """Returns the full gold standard list for a given domain."""
    gs_path = os.path.join(GS_DATA_DIR, f"{domain}.json")
    
    if not os.path.exists(gs_path):
        raise HTTPException(status_code=404, detail=f"Gold standard file for {domain} not found.")
    
    try:
        with open(gs_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evaluate", summary="Evaluate text against gold standard")
def evaluate(req: EvaluationRequest):
    """Calculates evaluation metrics between parsed text and gold standard text."""
    return token_level_eval(req.parsed_text, req.gold_text)

@app.get("/full_gs_eval", summary="Run full domain evaluation")
async def full_gs_eval(domain: str):
    """
    Performs an automated evaluation of the parser across all URLs in the 
    gold standard for a specific domain.
    """
    gs_path = os.path.join(GS_DATA_DIR, f"{domain}.json")
    if not os.path.exists(gs_path):
        raise HTTPException(status_code=404, detail="Gold standard file not found.")
    
    parser = PARSERS.get(domain)
    if not parser:
        raise HTTPException(status_code=400, detail=f"Domain {domain} not supported for evaluation.")

    try:
        with open(gs_path, "r", encoding="utf-8") as f:
            gs_list = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading GS: {str(e)}")
    
    if not gs_list:
        return {k: 0.0 for k in ["precision", "recall", "f1", "jaccard", "cer", "wer", "rouge_l", "leakage"]}
    
    metrics_sum = {k: 0.0 for k in ["precision", "recall", "f1", "jaccard", "cer", "wer", "rouge_l", "leakage"]}
    
    for item in gs_list:
        url = item["url"]
        gold_text = item["gold_text"]
        
        try:
            parsed_data = await parser.parse(url)
            metrics = token_level_eval(parsed_data["parsed_text"], gold_text)
            for k in metrics_sum:
                metrics_sum[k] += metrics[k]
        except Exception:
            # Skip failed URLs but log them in a real app
            continue
            
    count = len(gs_list)
    return {k: v / count for k, v in metrics_sum.items()}
