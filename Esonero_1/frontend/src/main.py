from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import httpx
import os

app = FastAPI(title="Esonero 1 Frontend")

templates = Jinja2Templates(directory="templates")

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8003")

async def get_all_gs_data(client: httpx.AsyncClient, domains: list):
    all_gs = []
    for domain in domains:
        try:
            resp = await client.get(f"{BACKEND_URL}/full_gold_standard?domain={domain}")
            if resp.status_code == 200:
                all_gs.extend(resp.json())
        except:
            continue
    return all_gs

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    domains_data = {"domains": []}
    gs_list = []
    error = None
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{BACKEND_URL}/domains")
            if resp.status_code == 200:
                domains = resp.json()
                
            try:
                for d in domains.get("domains", []):
                    gs_resp = await client.get(f"{BACKEND_URL}/full_gold_standard?domain={d}")
                    if gs_resp.status_code == 200:
                        gs_list.extend(gs_resp.json())
            except:
                pass

    except Exception as e:
        error = f"Cannot connect to backend: {e}"

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
    parsed_data = None
    metrics = None
    gs_data = None
    error = None
    domains_data = {"domains": []}
    gs_list = []
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{BACKEND_URL}/parse?url={url}")
            if resp.status_code == 200:
                parsed_data = resp.json()
                
                # Check metrics if it is in GS!
                gs_resp = await client.get(f"{BACKEND_URL}/gold_standard?url={url}")
                if gs_resp.status_code == 200:
                    gs_data = gs_resp.json()
                    eval_resp = await client.post(f"{BACKEND_URL}/evaluate", json={
                        "parsed_text": parsed_data["parsed_text"],
                        "gold_text": gs_data["gold_text"]
                    })
                    if eval_resp.status_code == 200:
                        metrics = eval_resp.json()
            else:
                error = resp.json().get("detail", "Error during parsing")

            # Refresh domains and gs_list
            d_resp = await client.get(f"{BACKEND_URL}/domains")
            if d_resp.status_code == 200:
                domains = d_resp.json()
            
            try:
                for d in domains.get("domains", []):
                    gsl_resp = await client.get(f"{BACKEND_URL}/full_gold_standard?domain={d}")
                    if gsl_resp.status_code == 200:
                        gs_list.extend(gsl_resp.json())
            except:
                pass
                
    except Exception as e:
        error = str(e)
        
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
