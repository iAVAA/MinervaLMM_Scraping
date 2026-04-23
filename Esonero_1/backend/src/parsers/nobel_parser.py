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
    Parser dedicated to NobelPrize.org.
    """ 
    def __init__(self):
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080
        )
        
        self.js_cleanup_script = """
        const acceptCookies = () => {
            const acceptBtn = document.querySelector('#onetrust-accept-btn-handler') || 
                              document.querySelector('.ot-pc-refusal-link') ||
                              document.querySelector('#onetrust-policy-text');
            if (acceptBtn && acceptBtn.click) acceptBtn.click();
            
            const blockers = [
                '#onetrust-consent-sdk', '.ot-sdk-container', '.onetrust-pc-dark-filter',
                '.cookie-notice', '.ad-slot', '.overlay', '.modal'
            ];
            blockers.forEach(s => {
                const el = document.querySelector(s);
                if (el) {
                    el.style.display = 'none';
                    el.style.visibility = 'hidden';
                    el.remove();
                }
            });
            
            document.body.style.overflow = 'auto';
            document.documentElement.style.overflow = 'auto';
        };

        const cleanupUI = () => {
            const content = document.querySelector('.page-content') || 
                            document.querySelector('article') || 
                            document.querySelector('main#content');
            if (content) {
                const contentHtml = content.innerHTML;
                document.body.innerHTML = '<div class="page-content">' + contentHtml + '</div>';
            }
            
            const noise = [
                '.share-buttons', '.social-links', '.citation-container', 
                '.laureate-nav', '.copyright', 'footer', 'nav', 
                'aside', 'select', 'button', 'form', 'input', 'label',
                '.btn', '.menu', '.navigation', '.skip-link',
                'figcaption', '.figcaption__attribution', '.wp-caption-text',
                '.video-container', '.video-player', '.video-caption', 
                '.video-title', 'iframe', '.wp-block-embed', '.wp-block-video',
                'video', '.smalltext'
            ];
            noise.forEach(s => document.querySelectorAll(s).forEach(el => el.remove()));
        };

        return new Promise(resolve => {
            acceptCookies();
            setTimeout(() => {
                cleanupUI();
                resolve();
            }, 2500);
        });
        """
        
        self.crawler_config = CrawlerRunConfig(
            js_code=self.js_cleanup_script,
            wait_for="css:.page-content", 
            word_count_threshold=1,
            exclude_external_links=True,
            remove_overlay_elements=True,
            excluded_tags=["script", "style", "nav", "footer", "aside", "header", "form"]
        )

    async def parse(self, url: str, html_text: str = None) -> dict:
        domain = urlparse(url).netloc
        
        if html_text:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, 'html.parser')
            for sel in ['script', 'style', '#onetrust-consent-sdk', '.ot-sdk-container', '.cookie-notice', 'nav', 'footer', 'aside', 'img', 'picture', 'source', 'figure', 'noscript', 'video', 'iframe', '.laureate-nav', '.share-buttons', '.citation-container']:
                for el in soup.select(sel):
                    el.decompose()
                    
            content = soup.select_one('.page-content') or soup.find('main', id='content') or soup.select_one('article')
            if content:
                # Wrap it in a clean body
                html_text = f'<html><body><div class="page-content">{content.decode_contents()}</div></body></html>'
            else:
                html_text = str(soup)

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            run_url = f"raw:{html_text}" if html_text else url
            result = await crawler.arun(url=run_url, config=self.crawler_config)
            
            if not result.success:
                fallback_config = self.crawler_config.clone()
                fallback_config.wait_for = None
                result = await crawler.arun(url=run_url, config=fallback_config)

            if not result.success:
                raise Exception(f"NobelPrize crawl failed: {result.error_message}")

            clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', result.markdown)
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
            
            clean_text = clean_text.replace('\n', ' ').replace('\r', ' ')
            clean_text = re.sub(r'#+\s?', '', clean_text)
            clean_text = re.sub(r'\[\s*\]|\(\s*\)|\{\s*\}', ' ', clean_text)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
            clean_text = re.sub(r'\[\s*\d+[\s\d\-\,]*\]', ' ', clean_text)
            clean_text = re.sub(r'\[\s*(PDF|DOC|XLS|ZIP)\s*\]', ' ', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            path_parts = [p for p in urlparse(url).path.split('/') if p]
            if path_parts:
                title_text = path_parts[-1].replace("-", " ").title()
                if (title_text == "Summary" or title_text == "Facts") and len(path_parts) >= 3:
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
