# Minerva LLM & Web Scraping - Assignment 1

A microservices-based system built with **FastAPI** and **Docker** for automated web scraping, parsing, and evaluation of extracted content.

The project extracts structured information from domain-specific websites, compares it against a **Gold Standard**, and computes multiple **NLP evaluation metrics** to assess extraction quality.

---

## Overview

The system is containerized using `Docker Compose` and consists of two main services:

### Backend (Port 8003)

A REST API built with **FastAPI** responsible for:

- managing domain-specific parsers
- performing web scraping and content parsing
- loading local Gold Standard datasets
- computing NLP evaluation metrics
- supporting asynchronous batch execution across entire domains

### Frontend (Port 8004)

A web interface built with **FastAPI + Jinja2** that:

- consumes backend APIs
- provides an intuitive interface for interacting with the system
- visualizes parsing and evaluation workflows

---

## Features

### Domain-Specific Parsing (Factory / Strategy Pattern)

Supported domains include:

- **Wikipedia**
- **Nobel Prize**
- **RomaToday**
- **Italian Government**

### NLP Evaluation Metrics

The system evaluates extraction quality through:

- **Precision / Recall / F1-score**
- **ROUGE-L**
- **Levenshtein Distance (CER / WER)**
- **Jaccard Index**
- **Leakage Analysis**

### Asynchronous Batch Evaluation

- processing of entire domain datasets
- automated aggregation of evaluation metrics
- scalable execution pipeline

### Development Hot Reload

- live code updates through Docker volumes
- automatic backend and frontend refresh during development

---

## Tech Stack

### Backend & Web Frameworks
- **Python 3**
- **FastAPI**
- **Uvicorn**
- **Jinja2**

### Web Scraping & Parsing
- **Crawl4AI**
- **Playwright**
- **BeautifulSoup4**
- **HTML2Text**

### NLP & Evaluation
- **Levenshtein**
- **rouge-score**

### Infrastructure
- **Docker**
- **Docker Compose**

---

## Project Architecture

The application follows a **microservices architecture**, separating business logic and user interaction into independent services:

- **Backend Service** → scraping, parsing, NLP evaluation
- **Frontend Service** → UI layer and API consumption

This design improves **modularity**, **maintainability**, and **scalability**.

---

## Getting Started

Clone the repository and start the containers:

```bash
docker-compose up --build
```

Once started:

- **Backend API** → `http://localhost:8003`
- **Frontend UI** → `http://localhost:8004`

---

## Development

The project supports **hot reload** during development, allowing code changes to be reflected automatically without rebuilding containers.

```bash
docker-compose up
```

---

## License

This project is distributed under the **MIT License**. See the [LICENSE](LICENSE) file for more information.
