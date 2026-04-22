"""
Percorso relativo: backend/src/wikipedia_parser.py
Corso: Laboratorio di ingegneria informatica
Corso di Laurea: Ingegneria informatica e automatica
Ateneo: Sapienza Università di Roma
Data: Aprile 2026
Autori: Matricole 2114420, 2115153, 2056502

Descrizione:
Questo modulo definisce la classe `WikipediaParser`, un estrattore asincrono
ottimizzato per l'acquisizione e la pulizia del contenuto testuale dalle voci di Wikipedia.
Implementa una logica di web scraping a due livelli: una pulizia preventiva del DOM 
tramite JavaScript per rimuovere elementi strutturali irrilevanti (infobox, note, 
pannelli di navigazione) e una rigorosa post-elaborazione del formato Markdown
basata su espressioni regolari per massimizzare la pulizia del testo estratto.
"""

import asyncio
import json
import re
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

class WikipediaParser:
    """
    Parser specializzato per l'estrazione di testo puro dalle pagine del dominio wikipedia.org.
    La classe incapsula le logiche di rendering headless e le regole euristiche per 
    isolare il solo contenuto enciclopedico utile, scartando metadati, riferimenti e artefatti.
    """

    def __init__(self):
        """
        Inizializza l'ambiente di scraping, impostando la risoluzione del browser
        headless e definendo gli script JavaScript per la manipolazione del DOM.
        """
        # Configurazione standard del browser headless
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080
        )
        
        # Script JavaScript per la pulizia del DOM prima del rendering.
        # Rimuove sistematicamente classi e ID associati a elementi non prettamente testuali
        # come box informativi, tabelle, indicatori di coordinate, e banner di avviso.
        self.js_cleanup_script = """
        const selectors = [
            '.infobox', '.reference', '.navbox', '.reflist', '.metadata', '.sistersitebox', 
            '.mw-editsection', '#siteNotice', '#mw-head', '#mw-panel', '#footer', '.printfooter',
            '.thumb', '.thumbcaption', 'figure', 'figcaption', '.magnify', '.gallery', '.mw-file-description',
            '.toc', '.ambox', '.noprint', '.mw-empty-elt', '.dmbox', '.box-Multiple_issues', '.hatnote',
            '.shortdescription', '.coordinates', 'table', 'sup', '.IPA', '.unicode', '.citation',
            'ol.references', '.references', '.mw-indicators', '#coordinates',
            'form', 'input', 'button', 'textarea', 'select',
            '.infobox-caption', '.wp-caption-text', 'caption',
            '.catlinks', '#catlinks', '.mw-authority-control', '.asst-links'
        ];
        document.querySelectorAll(selectors.join(', ')).forEach(el => el.remove());

        // Identifica e rimuove le sezioni finali tipiche di Wikipedia ("Voci correlate", 
        // "Bibliografia", ecc.) e tutto il contenuto successivo ad esse.
        const endSectionIds = ['See_also', 'References', 'Bibliography', 'External_links', 'Further_reading', 'Notes', 'Citations', 'Authority_control', 'Categories'];
        endSectionIds.forEach(id => {
            const span = document.getElementById(id);
            if (span) {
                let heading = span.closest('h2, h3');
                if (heading) {
                    let next = heading.nextElementSibling;
                    while(next) {
                        let toRemove = next;
                        next = next.nextElementSibling;
                        toRemove.remove();
                    }
                    heading.remove();
                }
            }
        });
        """
        
        # Configurazione dell'esecuzione del crawler: targetizza il contenitore principale
        # del testo enciclopedico ignorando preventivamente i tag semantici non utili.
        self.crawler_config = CrawlerRunConfig(
            css_selector="#mw-content-text",
            excluded_tags=["nav", "footer", "aside", "header", "form", "script", "style"],
            js_code=self.js_cleanup_script,
            word_count_threshold=1,
            exclude_external_links=False
        )

    async def parse(self, url: str, html_text: str = None) -> dict:
        """
        Esegue il fetch, l'estrazione e la sanitizzazione di una pagina Wikipedia.

        Args:
            url (str): L'URL della pagina Wikipedia da elaborare.
            html_text (str, optional): Sorgente HTML raw (se disponibile, evita il fetch di rete).

        Returns:
            dict: Dizionario strutturato con l'URL, il dominio, il titolo dedotto, 
                  l'HTML elaborato e il testo normalizzato.

        Raises:
            ValueError: Se il dominio fornito non appartiene a wikipedia.org.
            Exception: Se il processo di crawling fallisce.
        """
        domain = urlparse(url).netloc
        
        # Validazione di sicurezza del dominio in ingresso
        if not domain.endswith("wikipedia.org"):
            raise ValueError("Questo parser supporta solo il dominio wikipedia.org")

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            run_url = f"raw:{html_text}" if html_text else url
            result = await crawler.arun(url=run_url, config=self.crawler_config)
            
            # Gestione degli errori a livello di framework di crawling
            if not result.success:
                raise Exception(f"Crawl failed: {result.error_message}")
                
            raw_md = result.markdown
            
            # Troncamento basato su testo: secondo livello di sicurezza per eliminare 
            # eventuali appendici rimaste nel Markdown dopo la pulizia JS.
            end_sections = [
                'See also', 'References', 'External links', 'Further reading',
                'Bibliography', 'Notes', 'Citations', 'Sources', 'Works cited', 
                'General references', 'Notes and references', 'Authority control', 'Categories'
            ]
            for section in end_sections:
                pattern = r'(?mi)^#{2,5}\s*' + re.escape(section) + r'\b.*$'
                match = re.search(pattern, raw_md)
                if match:
                    raw_md = raw_md[:match.start()]
            
            # Cleanup iniziale del markdown
            clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', raw_md) # Rimozione immagini
            clean_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean_text) # Appiattimento link testuali
            clean_text = re.sub(r'\[\d+\]', ' ', clean_text) # Eliminazione citazioni numeriche stile [1]
            clean_text = re.sub(r'#+\s?', ' ', clean_text) # Eliminazione dei token di intestazione markdown (#)
            clean_text = clean_text.replace('\n', ' ').replace('\r', ' ') # Linearizzazione su singola riga
            
            # Pulizia reiterata per parentesi rotonde e quadre vuote o contenenti solo punteggiatura residua
            for _ in range(2):
                clean_text = re.sub(r'\(\s*[;,\s]*\)', ' ', clean_text)
                clean_text = re.sub(r'\[\s*[;,\s]*\]', ' ', clean_text)
            
            # Rimozione di artefatti testuali comuni e URL espliciti nel testo
            clean_text = re.sub(r'(?i)edit|citation needed|Jump up to', ' ', clean_text)
            clean_text = re.sub(r'https?://\S+|www\.\S+', ' ', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'\{\{[^}]+\}\}', ' ', clean_text) # Rimuove template mediawiki sfuggiti
            
            # Normalizzazione punteggiatura ripetuta dovuta alle rimozioni precedenti
            clean_text = re.sub(r'(?:[\*\.]\s*){3,}', ' ', clean_text)
            
            # --- CLEANUP REDUNDANCIES ---
            # Gestisce anomalie sui link annidati, es: The Swan's Way "Swan's Way (footpath)") 
            # rimuovendo ripetizioni tautologiche lasciate dai parser.
            clean_text = re.sub(r'["\']([^"\']+)["\']\s*\(\1[^)]*\)', r'\1', clean_text)
            clean_text = re.sub(r'([^ ]+)\s*\(\1[^)]*\)', r'\1', clean_text)
            
            # --- REFINED TRAILING TRASH REMOVAL ---
            # Rimuove liste puntate spurie alla fine del documento (solitamente rimaste da menu 
            # di navigazione o "Voci correlate" non identificate correttamente).
            clean_text = re.sub(r'(?:\s*\*\s*[^#\*]{2,40}){2,}\.?$', '', clean_text).strip()
            
            # Rimuove classici blocchi informativi tra parentesi alla fine del testo
            clean_text = re.sub(r'\s*\([^)]*(?:link|map|archive|original|reference)[^)]*\)\.?$', '', clean_text, flags=re.IGNORECASE)
            
            # Correzione delle virgolette multiple ed escape non necessari
            clean_text = clean_text.replace('""', ' ')
            clean_text = re.sub(r'\\([()])', r'\1', clean_text)
            clean_text = clean_text.replace('\\', '')
            clean_text = re.sub(r'\[\s*(?:PDF|DOC|XLS|ZIP)\s*\]', ' ', clean_text, flags=re.IGNORECASE)
            
            # Normalizzazione finale degli spazi bianchi
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            # Estrazione del titolo direttamente dalla sintassi dell'URL
            path_end = urlparse(url).path.split('/')[-1]
            title_text = unquote(path_end).replace("_", " ")

            return {
                "url": url,
                "domain": domain,
                "title": title_text,
                "html_text": result.html,
                "parsed_text": clean_text
            }