# Minerva LLM & Web Scraping - Esonero 1

Sistema a microservizi basato su **FastAPI** e **Docker** per scraping, parsing e valutazione automatica di contenuti web.

Il progetto estrae dati da domini specifici, li confronta con un **Gold Standard** e calcola metriche NLP per valutarne la qualità.

---

## Architettura

Il sistema è containerizzato tramite `docker-compose` ed è composto da due componenti principali:

### Backend (porta 8003)
API REST sviluppata in FastAPI che:
- gestisce i parser per dominio
- esegue scraping e parsing dei contenuti
- carica il Gold Standard locale
- calcola metriche di valutazione NLP
- supporta esecuzioni batch asincrone su interi domini

### Frontend (porta 8004)
Interfaccia web basata su FastAPI + Jinja2 che:
- consuma le API del backend
- permette l’interazione con il sistema in modo semplice e intuitivo

---

## Funzionalità

- **Parsing per dominio (Factory/Strategy pattern)**
  - Wikipedia
  - Nobel Prize
  - RomaToday
  - Governo italiano

- **Valutazione NLP**
  - Precision / Recall / F1-score
  - ROUGE-L
  - Levenshtein distance (CER/WER)
  - Jaccard index
  - Leakage analysis

- **Batch evaluation asincrona**
  - elaborazione di interi dataset per dominio
  - aggregazione automatica delle metriche

- **Hot-reload in sviluppo**
  - aggiornamento live del codice tramite volumi Docker
  - refresh automatico di API e template

---

## Stack tecnologico

- Python 3
- FastAPI, Uvicorn, Jinja2
- Crawl4AI, Playwright, BeautifulSoup4, HTML2Text
- Levenshtein, rouge-score
- Docker, Docker Compose

---

## Avvio del progetto

Clona il repository e avvia i container:

```bash
docker-compose up --build
```
