import asyncio
import json
import re
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

class NobelParser:
    def __init__(self):
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080
        )
        
        # Analogous to Wikipedia's JS cleanup script
        self.js_cleanup_script = """
        const selectors = [
            '.site-header', '.site-footer', '.nav-main', '.nav-secondary', 
            '.share-buttons', '.social-links', '.citation-container', 
            '.related-links', '.sidebar', '.menu-toggle', '#mobile-menu',
            '.cookie-notice', '.ad-slot', '.hidden-print', '.noprint',
            'form', 'input', 'button', 'textarea', 'select', 'iframe',
            '.back-to-top', '.breadcrumb', '.pagination', '.laureate-nav',
            '.newsletter-signup', '.overlay', '.modal'
        ];
        
        // Remove known noise
        document.querySelectorAll(selectors.join(', ')).forEach(el => el.remove());
        
        // Remove specific sections by ID if helpful (analogous to Wikipedia's endSectionIds)
        const endSections = ['related-items', 'further-reading'];
        endSections.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.remove();
        });
        """
        
        self.crawler_config = CrawlerRunConfig(
            css_selector="main#content", 
            excluded_tags=["nav", "footer", "aside", "header", "form", "script", "style"],
            js_code=self.js_cleanup_script,
            word_count_threshold=5,
            exclude_external_links=False
        )

    async def parse(self, url: str) -> dict:
        domain = urlparse(url).netloc
        if domain not in ["www.nobelprize.org", "nobelprize.org"]:
             raise ValueError("Questo parser supporta solo il dominio www.nobelprize.org")

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            # We add a small wait to allow for dynamic content hydration
            # NobelPrize.org is more dynamic than Wikipedia
            result = await crawler.arun(url=url, config=self.crawler_config)
            
            if not result.success or len(result.markdown) < 100:
                # Fallback: try without selector and with more wait
                print("[DEBUG] Targeted crawl failed or too short, falling back...")
                self.crawler_config.css_selector = None
                # Inject a sleep in JS
                self.crawler_config.js_code = "await new Promise(r => setTimeout(r, 4000)); " + self.js_cleanup_script
                result = await crawler.arun(url=url, config=self.crawler_config)
                # Restore config
                self.crawler_config.css_selector = "main#content"
                self.crawler_config.js_code = self.js_cleanup_script

            raw_md = result.markdown
            
            # Markdown cleaning (analogous to WikipediaParser)
            # 1. Remove images and links
            clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', raw_md)
            clean_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean_text)
            
            # 2. Convert to single line
            clean_text = clean_text.replace('\n', ' ').replace('\r', ' ')
            
            # 3. Remove metadata and navigation noise
            noise_patterns = [
                r'(?i)To cite this section.*$',
                r'(?i)Go to the top of the page',
                r'(?i)Share this',
                r'(?i)MLA style:.*',
                r'(?i)Enhanced Page Navigation'
            ]
            for pattern in noise_patterns:
                clean_text = re.sub(pattern, '', clean_text)
            
            # 4. Remove headers symbols and normalize whitespace
            clean_text = re.sub(r'#+\s?', '', clean_text)
            
            # --- AGGIUNTE RICHIESTE (Analogous to WikipediaParser) ---
            # Remove remaining brackets artifacts
            clean_text = re.sub(r'\[\s*\]|\(\s*\)|\{\s*\}', ' ', clean_text)
            
            # Remove repeated punctuation patterns
            clean_text = re.sub(r'(?:[\*\.]\s*){3,}', ' ', clean_text)
            clean_text = re.sub(r'(?:[\*\.\-~_]\s*){5,}', ' ', clean_text)
            
            # Remove orphan numbering
            clean_text = re.sub(r'(?:\b\d+\.\s*[\(\)\{\}\[\]\s]*)+', ' ', clean_text)
            
            # Disambiguations and redundant quotes
            clean_text = re.sub(r'\s*\\\([^)]+\\\)', '', clean_text)
            clean_text = re.sub(r'""([^"]+)""', r'\1', clean_text)
            
            # Final whitespace normalization
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
            # 5. Remove URLs
            clean_text = re.sub(r'https?://\S+|www\.\S+', '', clean_text, flags=re.IGNORECASE)

            # Title extraction
            path_parts = [p for p in urlparse(url).path.split('/') if p]
            if path_parts:
                title_text = path_parts[-1].replace("-", " ").title()
                if title_text == "Summary" and len(path_parts) >= 3:
                     title_text = f"The Nobel Prize in {path_parts[1].title()} {path_parts[2]}"
            else:
                title_text = "Nobel Prize"

            parsed_data = {
                "url": url,
                "domain": domain,
                "title": title_text,
                "html_text": result.html,
                "parsed_text": clean_text
            }
            return parsed_data
