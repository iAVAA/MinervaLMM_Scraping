import asyncio
import re
from urllib.parse import urlparse, unquote
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig


class GovernoParser:
    def __init__(self):
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080
        )

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

        self.crawler_config = CrawlerRunConfig(
            css_selector="#main",
            excluded_tags=["nav", "footer", "aside", "header", "form", "script", "style"],
            js_code=self.js_cleanup_script,
            word_count_threshold=5,
            exclude_external_links=False
        )

    async def parse(self, url: str) -> dict:
        domain = urlparse(url).netloc
        if domain != "www.governo.it":
            raise ValueError("Questo parser supporta solo il dominio www.governo.it")

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=url, config=self.crawler_config)
            raw_md = result.markdown

            clean_text = raw_md

            clean_text = re.sub(r'Vai al Contenuto.*?(?=\n|$)', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'Raggiungi il piè di pagina.*?(?=\n|$)', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'Seguici su:\s*(?:Facebook|Twitter|Instagram|YouTube|Linkedin\s*)+', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'Follow us:\s*(?:Facebook|Twitter|Instagram|YouTube|Linkedin\s*)+', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'(?:Home|Homepage)\s*[›»>]\s*[^\n]*?(?=\n|$)', '', clean_text, flags=re.IGNORECASE)
            
            clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', clean_text) # Rimuove le immagini Markdown
            clean_text = re.sub(r'\[([^\]]*)\]\([^\)]+\)', r'\1', clean_text)
            clean_text = re.sub(r'\[\d+\]', '', clean_text)
            clean_text = re.sub(r'https?://\S+|www\.\S+', '', clean_text, flags=re.IGNORECASE)

            clean_text = re.sub(r'\(\s*\)|\{\s*\}', '', clean_text)
            clean_text = re.sub(r'\{\{[^}]+\}\}', '', clean_text)
            clean_text = re.sub(r'\\([^\s])', r'\1', clean_text)
            clean_text = re.sub(r'""([^"]+)""', r'\1', clean_text)
            clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()

            path_end = urlparse(url).path.rstrip("/").split('/')[-1]
            title_text = unquote(path_end).replace("-", " ").replace("_", " ")

            parsed_data = {
                "url": url,
                "domain": domain,
                "title": title_text,
                "html_text": result.html,
                "parsed_text": clean_text
            }
            return parsed_data