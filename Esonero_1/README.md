# Web Extraction Engine & Parser Evaluation

Un'architettura a microservizi pensata per estrarre in markdown, sgrezzare da artefatti DOM e valutare il testo di grandi portali documentali (Wikipedia). Progettato con lo scopo di affinare dataset testuali puliti di altissima qualità da passare poi ad algoritmi di intelligenza artificiale (LLM / RAG).

## Requisiti di Sistema
- **Docker** e **Docker Compose** installati sulla macchina target.
- Nessuna dipendenza Python locale è richiesta, i container isolano l'intero kernel.

## Struttura della Piattaforma
- `/backend`: Motore logico (Porta 8003). Scritto in FastAPI, implementa uno scraper browser-based (`Crawl4AI` su Playwright) potenziato con un pulitore DOM Regex-JavaScript, e include un motore di valutazione matematica di somiglianza testuale ad altissime performance basate su codice C (`Levenshtein`, `rouge-score`).
- `/frontend`: Dashboard UI (Porta 8080). Un'interfaccia single-page minimale e moderna costruita ad-hoc con Tailwind CSS e template rendering Jinja2 nativo.
- `/gs_data`: Contiene il dizionario del proprio *Gold Standard* in JSON usato come ancoraggio di riferimento.

## Avvio del Sistema

L'infrastruttura è completamente "dockerizzata", pertanto i comandi di interazione dal terminale sono universali e agnostici rispetto al sistema operativo.

### Linux / MacOS / Windows (WSL o PowerShell)

1. Apri un terminale nella cartella principale del progetto ed esegui la build dell'ecosistema:
```bash
docker compose up -d --build
```
> **Nota Iniziale**: Il primo avvio può risultare macchinoso (può richiedere fino a 5 minuti) in quanto il container backend è istruito per scaricare da zero Chromium e tutte le librerie ML dedicate, compilandole nel proprio kernel.

2. **Accesso alla Webapp:** Una volta ristabilito il prompt ed elaborata la build, il sito sarà istantaneamente reattivo sul proprio browser locale:
👉 **[http://localhost:8080](http://localhost:8080)**

### Spegnimento
Al termine del test, per abbattere l'infrastruttura inibendo tutti i container e le reti dedicate:
```bash
docker compose down
```

## Strumenti ed Export integrati
Nella Web App sviluppata, per ogni URL processato, è possibile ammirare la formattazione pulita side-by-side e l'interrogazione istantanea per 8 diverse metriche logiche:
* **Core Token NLP**: F1-Score, Precision, Recall
* **Similarità Complessa**: Jaccard Index (3-grammi caratteriali), Rouge-L
* **Error Cost & Leakage**: Word Error Rate (WER), Character Error Rate (CER), Tag Leakage

Sempre per mezzo della UI è consentito scompattare questi dati e avviare un download in locale (`.html` grezzo e `.md` definitivo) preformattati.
