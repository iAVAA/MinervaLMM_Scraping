from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json
import os
from src.parsers.wikipedia_parser import WikipediaParser
from src.parsers.nobel_parser import NobelParser
from src.evaluator.metrics import token_level_eval
from urllib.parse import urlparse, unquote

app = FastAPI(title="Esonero 1 Backend")
wiki_parser = WikipediaParser()
nobel_parser = NobelParser()

class EvaluationRequest(BaseModel):
    parsed_text: str
    gold_text: str

@app.get("/domains")
def get_domains():
    try:
        with open("../domains.json", "r") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/parse")
async def parse_url(url: str):
    domain = urlparse(url).netloc
    
    if domain == "en.wikipedia.org":
        try:
            return await wiki_parser.parse(url)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    elif domain == "www.nobelprize.org" or domain == "nobelprize.org":
        try:
            return await nobel_parser.parse(url)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail=f"Parser for domain {domain} not implemented yet.")

@app.get("/gold_standard")
def get_gold_standard(url: str):
    domain = urlparse(url).netloc
    gs_path = f"../gs_data/{domain}.json"
    if not os.path.exists(gs_path):
        raise HTTPException(status_code=404, detail="Gold standard file not found for this domain.")
    
    try:
        url_decoded = unquote(url)
        with open(gs_path, "r") as f:
            gs_list = json.load(f)
            for item in gs_list:
                if unquote(item["url"]) == url_decoded:
                    return item
            raise HTTPException(status_code=404, detail="URL not found in gold standard.")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Error decoding gold standard JSON.")

@app.get("/full_gold_standard")
def get_full_gold_standard(domain: str):
    gs_path = f"../gs_data/{domain}.json"
    if not os.path.exists(gs_path):
        raise HTTPException(status_code=404, detail="Gold standard file not found for this domain.")
    
    try:
        with open(gs_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evaluate")
def evaluate(req: EvaluationRequest):
    metrics = token_level_eval(req.parsed_text, req.gold_text)
    return metrics

@app.get("/full_gs_eval")
async def full_gs_eval(domain: str):
    gs_path = f"../gs_data/{domain}.json"
    if not os.path.exists(gs_path):
        raise HTTPException(status_code=404, detail="Gold standard file not found.")
    
    with open(gs_path, "r") as f:
        gs_list = json.load(f)
    
    if not gs_list:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "jaccard": 0.0, "cer": 0.0, "wer": 0.0, "rouge_l": 0.0, "leakage": 0.0}
    
    total_metrics = {"precision": 0.0, "recall": 0.0, "f1": 0.0, "jaccard": 0.0, "cer": 0.0, "wer": 0.0, "rouge_l": 0.0, "leakage": 0.0}
    
    for item in gs_list:
        url = item["url"]
        gold_text = item["gold_text"]
        
        if domain == "en.wikipedia.org":
            parsed_data = await wiki_parser.parse(url)
            parsed_text = parsed_data["parsed_text"]
            metrics = token_level_eval(parsed_text, gold_text)
            
            for k in total_metrics.keys():
                total_metrics[k] += metrics[k]
        elif domain == "www.nobelprize.org" or domain == "nobelprize.org":
            parsed_data = await nobel_parser.parse(url)
            parsed_text = parsed_data["parsed_text"]
            metrics = token_level_eval(parsed_text, gold_text)
            
            for k in total_metrics.keys():
                total_metrics[k] += metrics[k]
            
    count = len(gs_list)
    return {k: v / count for k, v in total_metrics.items()}
