"""
Percorso relativo: backend/src/romatoday_parser.py
Corso: Laboratorio di ingegneria informatica
Corso di Laurea: Ingegneria informatica e automatica
Ateneo: Sapienza Università di Roma
Data: Aprile 2026
Autori: Matricole 2114420, 2115153, 2056502

Descrizione:
Questo modulo implementa la classe `RomaTodayParser`, un estrattore asincrono
specializzato per il recupero di articoli dal dominio "romatoday.it". 
Utilizza una complessa pipeline di pulizia basata su iniezioni JavaScript (per
rimuovere paywall, pubblicità, embed social e sezioni correlate) ed espressioni 
regolari sul Markdown risultante per garantire l'estrazione del solo testo utile.
"""

import re
import html
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

class RomaTodayParser:
    """
    Parser specializzato per le testate del gruppo Citynews (nello specifico RomaToday).
    Gestisce in modo proattivo elementi intrusivi come banner, embed di terze parti,
    e interfacce utente dinamiche.
    """

    def __init__(self):
        """
        Inizializza la configurazione del browser e del crawler, inclusa 
        la definizione di uno script JS molto aggressivo per la pulizia del DOM.
        """
        # Configurazione del browser headless con risoluzione standard
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080
        )

        # Script JS iniettato per rimuovere in modo massivo elementi non testuali:
        # header, footer, pubblicità, sezioni social, player video e articoli correlati.
        self.js_cleanup_script = """
        const selectors = [
            '.u-label-02',
            'footer', 'nav', 'aside',
            '.c-smb', '.o-link-category', '.article-authors', '.article-date',
            '.c-announcement', '.c-social-bar', '.c-related-articles',
            '[class*="share"]', '[class*="adv"]',
            '[class*="banner"]', '[class*="sponsor"]', '[class*="newsletter"]',
            '[class*="cookie"]', '[class*="gdpr"]', '[class*="popup"]',
            'script', 'style', 'noscript', 'iframe', 'form',
            'input', 'button', 'textarea', 'select',
            '.c-recommendation', '.c-trending', '[class*="related"]',
            '[class*="suggest"]', '[class*="taboola"]', '[class*="outbrain"]',
            '.c-stickyplayer', '.slot', '[data-share-btns]', '[data-share-native]',
            '.c-share', '.l-entry__byline', '.l-entry__podcast', '[data-podcast]',
            '.c-tags',
            /* --- ELIMINAZIONE MEDIA E UI DEI PLAYER --- */
            'img', 'video', 'picture', 'figure', 'source', 'audio', 'canvas', 'svg',
            '[data-player]', '[class*="player--"]', '.player--loading',
            /* --- ELIMINAZIONE EMBED SOCIAL (Instagram, Twitter, FB, TikTok) --- */
            '.instagram-media', 'blockquote[class*="instagram"]', 
            '.twitter-tweet', '.fb-post', '.tiktok-embed'
        ];
        document.querySelectorAll(selectors.join(', ')).forEach(el => el.remove());

        // RIMOZIONE SICURA DOSSIER/ARTICOLI CORRELATI
        // Cerca solo i titoli (h2, h3, h4) ignorando i paragrafi (p)
        document.querySelectorAll('.l-entry__body h2, .l-entry__body h3, .l-entry__body h4').forEach(el => {
            const link = el.querySelector('a');
            // Elimina l'elemento SOLO se è composto interamente ed esclusivamente da un link
            if (link && el.textContent.trim() === link.textContent.trim()) {
                el.remove();
            }
        });
        """

        # Configurazione di esecuzione del crawler, che aggira la cache per avere
        # contenuti sempre aggiornati ed esegue il selettore CSS specifico del corpo articolo.
        self.crawler_config = CrawlerRunConfig(
            css_selector=" .u-p-base, .l-entry__header , .c-entry ",
            js_code=self.js_cleanup_script,
            excluded_tags=["nav", "footer", "aside", "form", "script", "style"],
            word_count_threshold=5,
            exclude_external_links=False,
            magic=True,
            cache_mode=CacheMode.BYPASS
        )

    def _extract_meta_from_html(self, raw_html: str) -> tuple[str, str]:
        """
        Estrae titolo e sommario analizzando direttamente l'HTML grezzo tramite espressioni regolari.
        Viene usato come sistema infallibile (fallback) prima dell'elaborazione di crawl4ai.

        Args:
            raw_html (str): Il codice sorgente HTML della pagina.

        Returns:
            tuple[str, str]: Una tupla contenente (titolo, sommario).
        """
        # Estrazione Titolo (Infallibile su h1 RomaToday o og:title)
        title = ""
        title_match = re.search(
            r'<h1[^>]*(?:data-amp=["\']amp-title["\']|class=["\'][^"\']*l-entry__title[^"\']*["\'])[^>]*>(.*?)</h1>',
            raw_html, re.DOTALL | re.IGNORECASE
        )
        if title_match:
            title = re.sub(r'<[^>]+>', '', title_match.group(1))
        else:
            og_match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\'](.*?)["\']', raw_html, re.IGNORECASE)
            if og_match:
                title = og_match.group(1)

        # Estrazione Sommario (Infallibile su p/div abstract o meta description)
        summary = ""
        summary_match = re.search(
            r'<(?:p|div)[^>]*(?:data-amp=["\']amp-abstract["\']|class=["\'][^"\']*l-entry__summary[^"\']*["\'])[^>]*>(.*?)</(?:p|div)>',
            raw_html, re.DOTALL | re.IGNORECASE
        )
        if summary_match:
            summary = re.sub(r'<[^>]+>', '', summary_match.group(1))
        else:
            desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', raw_html, re.IGNORECASE)
            if desc_match:
                summary = desc_match.group(1)

        # Pulizia base metadati estratti
        title = html.unescape(title or "").strip()
        title = re.sub(r'\s+', ' ', title)
        
        summary = html.unescape(summary or "").strip()
        summary = re.sub(r'\s+', ' ', summary)

        return title, summary

    async def parse(self, url: str, html_text: str = None) -> dict:
        """
        Scarica, analizza e pulisce il contenuto di una pagina di RomaToday.

        Args:
            url (str): URL della notizia da estrarre.
            html_text (str, optional): HTML opzionale bypassando la rete (non usato internamente qui se non fornito).

        Returns:
            dict: Struttura dati contenente URL, dominio, titolo, sommario, HTML e testo Markdown pulito.

        Raises:
            ValueError: Se il dominio non corrisponde a RomaToday.
        """
        domain = urlparse(url).netloc
        
        # Validazione del dominio di competenza del parser
        if domain not in ["www.romatoday.it", "romatoday.it"] and not html_text:
            raise ValueError("Questo parser supporta solo il dominio www.romatoday.it")

        # Inizializzazione del crawler asincrono
        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=url, config=self.crawler_config)

            # Estrazione sicura di titolo e sommario
            title, summary = self._extract_meta_from_html(result.html)

            # Fallback del titolo generato dall'URL in assenza di metadati validi
            if not title:
                path_end = urlparse(url).path.rstrip('/').split('/')[-1]
                title = re.sub(r'\.\w+$', '', path_end).replace('-', ' ').capitalize()

            raw_md = result.markdown or ""

            # Pipeline di pulizia del testo markdown: rimuove artefatti, media residui,
            # metadati non rilevanti e stringhe "boilerplate" editoriali.
            clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', raw_md) # Rimuove le immagini Markdown
            clean_text = re.sub(r'\[([^\]]*)\]\([^\)]+\)', r'\1', clean_text)
            clean_text = re.sub(r'\[\d+\]', '', clean_text)
            clean_text = re.sub(r'https?://\S+|www\.\S+', '', clean_text, flags=re.IGNORECASE)

            clean_text = re.sub(r'\(\s*\)|\{\s*\}', '', clean_text)
            clean_text = re.sub(r'\{\{[^}]+\}\}', '', clean_text)
            clean_text = re.sub(r'\\([^\s])', r'\1', clean_text)
            clean_text = re.sub(r'""([^"]+)""', r'\1', clean_text)
            clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()
            
            # Rimuove le linee orizzontali in markdown (es. *** o ---) ma SALVA gli asterischi singoli (*) per le liste
            # clean_text = re.sub(r'(?:---|___|\*\*\*(?!\*))\s*', '', clean_text)
            
            # Rimozione date testuali
            #clean_text = re.sub(
            #     r'\b\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{4}(?:,\s*\d{2}:\d{2})?\b',
            #     '', clean_text, flags=re.IGNORECASE
            #)

            # Rimozione super-aggressiva del footer app (compresi eventuali "_" del markdown)
            #clean_text = re.sub(
            #    r'_?RomaToday è anche su Mobile.*?aggiornato\.?_?', 
            #    '', clean_text, flags=re.IGNORECASE
            #)
            
            # ELIMINAZIONE FANTASMA DEL VIDEO E DI INSTAGRAM testuali residui
            clean_text = re.sub(r'_?Video\s+[a-zA-Z]+Today_?\s*>?\s*', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'>?\s*Visualizza questo post su Instagram.*?\)\s*', '', clean_text, flags=re.IGNORECASE)

            # Elimina la parola isolata "social" rimasta appesa
            clean_text = re.sub(r'\s+social\s+(?=[A-Z])', ' ', clean_text)

            clean_text = re.sub(
                r'_?RomaToday è anche su Mobile.*?aggiornato\.?_?', 
                '', clean_text, flags=re.IGNORECASE
            )
            
            # Rimozione notice abbonati per gli articoli protetti da paywall
            clean_text = re.sub(r'_?Il contenuto è riservato agli abbonati\._?.*', '', clean_text, flags=re.IGNORECASE | re.DOTALL)
            
            # Fallback in caso mancasse la prima frase, taglia dal pulsante "Leggi tutto l'articolo"
            clean_text = re.sub(r'Leggi tutto l\'articolo.*', '', clean_text, flags=re.IGNORECASE | re.DOTALL)
            
            # Nel caso scappasse il minutaggio isolato
            clean_text = re.sub(r'\*?\*?\d+\*?\*?\s+minuti di lettura', '', clean_text, flags=re.IGNORECASE)
            
            #clean_text = html.unescape(clean_text)
            #clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            # RICOSTRUZIONE DEL TESTO FINALE
            

            # Output strutturato
            return {
                "url": url,
                "domain": domain,
                "title": title,
                "summary": summary,
                "html_text": result.html,
                "parsed_text": clean_text
            }