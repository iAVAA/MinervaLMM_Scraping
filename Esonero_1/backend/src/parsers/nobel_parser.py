import asyncio
import re
from urllib.parse import urlparse, unquote
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

class NobelParser:
    """
    Parser ottimizzato per NobelPrize.org.
    Centralizza la logica di pulizia su Crawl4Ai eliminando la necessità di BeautifulSoup.
    """ 
    def __init__(self):
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080
        )
        
        # Script JS minimale per gestire esclusivamente le interazioni (cookie/overlay)
        # La pulizia dei contenuti è ora delegata ai selettori nativi di Crawl4Ai
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
        
        self.crawler_config = CrawlerRunConfig(
            js_code=self.js_cleanup_script,
            wait_for="css:.page-content, main#content, article", 
            word_count_threshold=1,
            exclude_external_links=True,
            remove_overlay_elements=True,
            
            # Strategia di estrazione: puntiamo direttamente al contenuto core.
            # Questo sostituisce il filtraggio manuale che facevi con BeautifulSoup.
            css_selector=".page-content, main#content, article",
            
            # Rimuoviamo i tag che generano rumore nel Markdown
            excluded_tags=[
                "script", "style", "nav", "footer", "aside", "header", 
                "form", "img", "picture", "source", "figure", "noscript", 
                "video", "iframe", "button", "input"
            ],
            
            # Parametri per un markdown più pulito
            ignore_links=True,
            exclude_external_images=True
        )

    async def parse(self, url: str, html_text: str = None) -> dict:
        domain = urlparse(url).netloc
        
        # Se abbiamo html_text, usiamo il prefisso "raw:", altrimenti usiamo l'URL.
        # Crawl4Ai applicherà la stessa configurazione di estrazione in entrambi i casi.
        run_url = f"raw:{html_text}" if html_text else url

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=run_url, config=self.crawler_config)
            
            # Gestione fallback se il selettore principale non viene trovato (es. pagine speciali)
            if not result.success:
                fallback_config = self.crawler_config.clone()
                fallback_config.css_selector = None # Estrai tutto il body se il selettore fallisce
                fallback_config.wait_for = None
                result = await crawler.arun(url=run_url, config=fallback_config)

            if not result.success:
                raise Exception(f"NobelPrize crawl failed: {result.error_message}")

            # --- Pulizia Post-Parsing (Regex) ---
            # Manteniamo la tua logica di pulizia del testo per massimizzare la leggibilità
            clean_text = result.markdown
            
            # Rimozione di immagini residue, link e pattern di disturbo
            clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', clean_text)
            clean_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean_text)
            clean_text = re.sub(r'<(https?://[^>]+)>', '', clean_text)
            clean_text = re.sub(r'https?://\S+|www\.\S+', '', clean_text, flags=re.IGNORECASE)
            
            clean_text = clean_text.replace('_', ' ')
            clean_text = re.sub(r'(?i)\bTranslation\b', ' ', clean_text)
            clean_text = re.sub(r'[<>]', ' ', clean_text)
            clean_text = re.sub(r'^\s*>\s*', ' ', clean_text, flags=re.MULTILINE)
            
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
            
            # Normalizzazione spazi e rimozione formattazione Markdown pesante
            clean_text = clean_text.replace('\n', ' ').replace('\r', ' ')
            clean_text = re.sub(r'#+\s?', '', clean_text)
            clean_text = re.sub(r'\[\s*\]|\(\s*\)|\{\s*\}', ' ', clean_text)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
            # Rimozione citazioni e riferimenti a documenti
            clean_text = re.sub(r'\[\s*\d+[\s\d\-\,]*\]', ' ', clean_text)
            clean_text = re.sub(r'\[\s*(PDF|DOC|XLS|ZIP)\s*\]', ' ', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            # Estrazione del titolo dall'URL come fallback logico
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

# Esempio di utilizzo:
async def main():
    parser = NobelParser()
    # Esempio con URL live
    # data = await parser.parse("https://www.nobelprize.org/prizes/physics/1921/einstein/facts/")
    # print(data["parsed_text"])
    pass

if __name__ == "__main__":
    asyncio.run(main())
