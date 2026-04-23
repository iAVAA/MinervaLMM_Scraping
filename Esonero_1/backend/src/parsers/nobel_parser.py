"""
Percorso relativo: backend/src/nobel_parser.py
Corso: Laboratorio di ingegneria informatica
Corso di Laurea: Ingegneria informatica e automatica
Ateneo: Sapienza Università di Roma
Data: Aprile 2026
Autori: Matricole 2114420, 2115153, 2056502

Descrizione:
Questo modulo definisce la classe `NobelParser`, un estrattore asincrono
ottimizzato per l'acquisizione dei contenuti dal sito nobelprize.org.
Il parser utilizza `crawl4ai` per aggirare in modo proattivo i banner dei cookie
(OneTrust) tramite iniezioni JavaScript e applica una pipeline di espressioni
regolari per isolare e pulire il testo informativo rimuovendo metadati,
policy sulla privacy e pattern di disturbo strutturale.
"""

import asyncio
import re
from urllib.parse import urlparse, unquote
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

class NobelParser:
    """
    Parser ottimizzato specificamente per il dominio NobelPrize.org.
    L'architettura centralizza la logica di estrazione e pulizia direttamente
    all'interno di Crawl4Ai tramite selettori CSS nativi e iniezioni JS, 
    eliminando la dipendenza da parser HTML esterni come BeautifulSoup.
    """ 
    def __init__(self):
        """
        Inizializza l'ambiente di scraping asincrono. Configura le dimensioni
        della viewport del browser headless e definisce le logiche di bypass
        dei cookie e la selezione dei target CSS.
        """
        # Configurazione del browser headless per emulare un display desktop standard
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080
        )
        
        # Script JavaScript iniettato a runtime per l'accettazione automatica dei
        # banner dei cookie (piattaforma OneTrust) e la gestione delle overlay.
        # Viene forzato un ritardo asincrono per consentire le animazioni di chiusura.
        self.js_cleanup_script = """
        const acceptCookies = () => {
            const acceptBtn = document.querySelector('#onetrust-accept-btn-handler') || 
                              document.querySelector('.ot-sdk-container button');
            if (acceptBtn && acceptBtn.click) acceptBtn.click();
        };
        
        return new Promise(resolve => {
            acceptCookies();
            setTimeout(resolve, 2000); // Attesa per la chiusura delle animazioni degli overlay
        });
        """
        
        # Parametrizzazione avanzata dell'esecuzione del crawler per l'estrazione
        # diretta del core content tramite selettori CSS e l'esclusione di tag rumorosi.
        self.crawler_config = CrawlerRunConfig(
            js_code=self.js_cleanup_script,
            wait_for="css:.page-content, main#content, article", 
            word_count_threshold=1,
            exclude_external_links=True,
            remove_overlay_elements=True,
            
            # Strategia di estrazione mirata: delimita il parsing ai soli container
            # principali, sostituendo le vecchie euristiche di filtraggio manuale.
            css_selector=".page-content, main#content, article",
            
            # Blacklist dei tag HTML da omettere preventivamente dalla generazione del Markdown
            excluded_tags=[
                "script", "style", "nav", "footer", "aside", "header", 
                "form", "img", "picture", "source", "figure", "noscript", 
                "video", "iframe", "button", "input"
            ]
        )

    async def parse(self, url: str, html_text: str = None) -> dict:
        """
        Avvia il processo di scraping e parsing per una specifica pagina del premio Nobel.

        Args:
            url (str): L'URL completo della pagina da elaborare.
            html_text (str, optional): Stringa HTML prelevata esternamente. Se presente,
                                       il crawling di rete viene bypassato a favore del processing locale.

        Returns:
            dict: Un dizionario strutturato contenente dominio, titolo ricavato,
                  sorgente HTML e il testo Markdown post-processato.

        Raises:
            Exception: Segnala un fallimento critico del processo di crawling.
        """
        domain = urlparse(url).netloc
        
        # Composizione dell'URI di esecuzione: abilita il rendering locale tramite protocollo "raw:"
        # qualora l'HTML sia già disponibile in memoria, garantendo la medesima pipeline configurata.
        run_url = f"raw:{html_text}" if html_text else url

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=run_url, config=self.crawler_config)
            
            # Strategia di Fallback: se i selettori CSS restrittivi falliscono 
            # (es. su layout legacy o pagine atipiche), si ritenta l'estrazione sull'intero body.
            if not result.success:
                fallback_config = self.crawler_config.clone()
                fallback_config.css_selector = None # Disabilita il vincolo di selezione
                fallback_config.wait_for = None
                result = await crawler.arun(url=run_url, config=fallback_config)

            if not result.success:
                raise Exception(f"NobelPrize crawl failed: {result.error_message}")

            # --- Inizio Pipeline di Pulizia Post-Parsing (Basata su RegEx) ---
            # Il testo estratto subisce trasformazioni per omogeneizzare la formattazione
            # e rimuovere residui di navigazione non filtrati a livello DOM.
            clean_text = result.markdown
            
            # Eliminazione di artefatti Markdown (immagini rotte, link testuali e ancore)
            clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', clean_text)
            clean_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean_text)
            clean_text = re.sub(r'<(https?://[^>]+)>', '', clean_text)
            clean_text = re.sub(r'https?://\S+|www\.\S+', '', clean_text, flags=re.IGNORECASE)
            
            # Normalizzazione di caratteri speciali e indicatori di formattazione
            clean_text = clean_text.replace('_', ' ')
            clean_text = re.sub(r'(?i)\bTranslation\b', ' ', clean_text)
            clean_text = re.sub(r'[<>]', ' ', clean_text)
            clean_text = re.sub(r'^\s*>\s*', ' ', clean_text, flags=re.MULTILINE)
            
            # Dizionario di pattern regex per intercettare e rimuovere disclaimer di privacy,
            # utility di navigazione e moduli di consenso cookie sfuggiti al blocco iniziale.
            noise_patterns = [
                r'(?i)Skip to content',
                r'(?i)Go to the top of the page',
                r'(?i)Back to top',
                r'(?i)Navigate to:',
                r'(?i)By clicking.*?cookie list',
                r'(?i)Privacy Preference Center',
                r'(?i)Targeting Cookies.*?advertising',
                r'(?i)Performance Cookies.*?performance',
                r'(?i)Strictly Necessary Cookies.*?information',
                r'(?i)Functional Cookies.*?properly',
                r'(?i)manage consent preferences',
                r'(?i)cookie list'
            ]
            for pattern in noise_patterns:
                clean_text = re.sub(pattern, ' ', clean_text, flags=re.DOTALL)
            
            # Appiattimento della struttura e sanificazione di parentesi non necessarie
            clean_text = clean_text.replace('\n', ' ').replace('\r', ' ')
            clean_text = re.sub(r'#+\s?', '', clean_text)
            clean_text = re.sub(r'\[\s*\]|\(\s*\)|\{\s*\}', ' ', clean_text)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
            # Rimozione puntuale di rinvii a documentazione esterna o formati file
            clean_text = re.sub(r'\[\s*\d+[\s\d\-\,]*\]', ' ', clean_text)
            clean_text = re.sub(r'\[\s*(PDF|DOC|XLS|ZIP)\s*\]', ' ', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            # Inferenza semantica del titolo basata sulla tokenizzazione dell'URL
            # Agisce da fallback garantito per il tagging del record di output
            path_parts = [p for p in urlparse(url).path.split('/') if p]
            if path_parts:
                title_text = path_parts[-1].replace("-", " ").title()
                if (title_text in ["Summary", "Facts"]) and len(path_parts) >= 3:
                     title_text = path_parts[-2].replace("-", " ").title()
            else:
                title_text = "Nobel Prize"

            return {
                "url": url,
                "domain": domain,
                "title": title_text,
                "html_text": result.html,
                "parsed_text": clean_text
            }
