"""
Percorso relativo: backend/src/governo_parser.py
Corso: Laboratorio di ingegneria informatica
Corso di Laurea: Ingegneria informatica e automatica
Ateneo: Sapienza Università di Roma
Data: Aprile 2026
Autori: Matricole 2114420, 2115153, 2056502

Descrizione:
Questo modulo implementa la classe `GovernoParser`, un componente specializzato 
nell'estrazione e pulizia del contenuto testuale dalle pagine del dominio istituzionale 
"governo.it". Utilizza `crawl4ai` in modalità asincrona per renderizzare la pagina, 
eseguire script di pulizia DOM lato client e post-processare il markdown risultante 
tramite espressioni regolari, al fine di isolare il contenuto informativo primario.
"""

import asyncio
import re
from urllib.parse import urlparse, unquote
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig


class GovernoParser:
    """
    Parser dedicato per il dominio istituzionale governo.it.
    Gestisce la configurazione del browser headless, la rimozione degli elementi
    di layout (header, footer, menu) tramite iniezione JavaScript e la pulizia avanzata
    del testo estratto.
    """

    def __init__(self):
        """
        Inizializza le configurazioni del parser, inclusi i parametri del browser,
        lo script di pulizia DOM e le regole di esecuzione del crawler.
        """
        # Configurazione del browser headless per il rendering della pagina
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080
        )

        # Script JavaScript iniettato prima dell'estrazione per rimuovere elementi di "rumore"
        # visivo e strutturale (es. menu di navigazione, footer, form, breadcrumb e script).
        self.js_cleanup_script = """
        const selectors = [
            'nav', 'header', 'footer', 'aside',
            '.breadcrumb', '.pagination', '.pager',
            '.region-header', '.region-footer', '.region-sidebar-first', '.region-sidebar-second',
            '#block-governo-branding', '#block-governo-main-menu', '#block-governo-footer',
            '.social-share', '.share_buttons',
            '.field--name-field-tags', '.field--name-field-categoria',
            '.views-exposed-form', 'form',
            '.back-to-top', '#back-to-top',
            '.alert', '.messages',
            'figure', 'figcaption', '.media', '.field--type-image',
            '.tabs', '.local-tasks',
            '#toolbar-administration',
            'script', 'style', 'noscript',
            '.div_lingue'
        ];
        document.querySelectorAll(selectors.join(', ')).forEach(el => el.remove());
        """

        # Configurazione del crawler: definisce il selettore principale, i tag da ignorare
        # a livello di parser HTML e inietta lo script di pulizia JS.
        self.crawler_config = CrawlerRunConfig(
            css_selector="#main",
            excluded_tags=["nav", "footer", "aside", "header", "form", "script", "style"],
            js_code=self.js_cleanup_script,
            word_count_threshold=1,
            exclude_external_links=False
        )

    async def parse(self, url: str, html_text: str = None) -> dict:
        """
        Analizza ed estrae i dati dalla pagina web specificata.

        Args:
            url (str): L'URL della pagina web da analizzare.
            html_text (str, optional): Testo HTML pre-scaricato. Se fornito, evita la fetch di rete.

        Returns:
            dict: Dizionario contenente URL, dominio, titolo estratto, HTML raw e testo pulito in formato Markdown.

        Raises:
            ValueError: Se il dominio dell'URL non corrisponde a 'www.governo.it' o 'governo.it'.
        """
        domain = urlparse(url).netloc
        
        # Validazione rigorosa del dominio per prevenire esecuzioni su target non supportati
        if domain not in ["www.governo.it", "governo.it"]:
            raise ValueError("Questo parser supporta solo il dominio www.governo.it o governo.it")

        # Inizializzazione asincrona del web crawler
        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            # Se è fornito un HTML raw, bypassa il caricamento di rete usando lo schema 'raw:'
            run_url = f"raw:{html_text}" if html_text else url
            result = await crawler.arun(url=run_url, config=self.crawler_config)
            raw_md = result.markdown

            # Inizio pipeline di pulizia basata su Regex
            clean_text = raw_md

            # Rimozione boilerplates testuali specifici del sito governativo
            clean_text = re.sub(r'Vai al Contenuto.*?(?=\n|$)', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'Raggiungi il piè di pagina.*?(?=\n|$)', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'Seguici su:\s*(?:Facebook|Twitter|Instagram|YouTube|Linkedin\s*)+', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'Follow us:\s*(?:Facebook|Twitter|Instagram|YouTube|Linkedin\s*)+', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'(?:Home|Homepage)\s*[›»>]\s*[^\n]*?(?=\n|$)', '', clean_text, flags=re.IGNORECASE)
            
            # Sanitizzazione costrutti Markdown e link
            clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', clean_text) # Rimuove le immagini Markdown
            clean_text = re.sub(r'\[([^\]]*)\]\([^\)]+\)', r'\1', clean_text) # Converte i link nel solo testo dell'anchor
            clean_text = re.sub(r'\[\d+\]', '', clean_text) # Rimuove i riferimenti a note stile wiki [1], [2]
            clean_text = re.sub(r'https?://\S+|www\.\S+', '', clean_text, flags=re.IGNORECASE) # Rimuove URL espliciti

            # Pulizia di artefatti sintattici residui e formattazione superflua
            clean_text = re.sub(r'\(\s*\)|\{\s*\}', '', clean_text) # Parentesi vuote
            clean_text = re.sub(r'\{\{[^}]+\}\}', '', clean_text) # Placeholder template
            clean_text = re.sub(r'\\([^\s])', r'\1', clean_text) # Rimuove escape backslash
            clean_text = re.sub(r'""([^"]+)""', r'\1', clean_text) # Doppi apici ridondanti
            clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip() # Normalizzazione delle spaziature verticali

            # Derivazione euristica del titolo tramite l'ultimo segmento del path dell'URL
            path_end = urlparse(url).path.rstrip("/").split('/')[-1]
            title_text = unquote(path_end).replace("-", " ").replace("_", " ")

            # Costruzione payload di output
            return {
                "url": url,
                "domain": domain,
                "title": title_text,
                "html_text": result.html,
                "parsed_text": clean_text
            }