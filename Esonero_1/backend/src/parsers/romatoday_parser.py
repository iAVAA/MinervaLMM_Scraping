import re
import html
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

class RomaTodayParser:
    def __init__(self):
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080
        )

        self.js_cleanup_script = """
        const selectors = [
            'footer', 'nav', 'aside',
            '.c-smb', '.o-link-category', '.article-authors', '.article-date',
            '.c-announcement', '.c-social-bar', '.c-related-articles',
            '.l-entry__header',
            '[class*="social"]', '[class*="share"]', '[class*="adv"]',
            '[class*="banner"]', '[class*="sponsor"]', '[class*="newsletter"]',
            '[class*="cookie"]', '[class*="gdpr"]', '[class*="popup"]',
            'script', 'style', 'noscript', 'iframe', 'form',
            'input', 'button', 'textarea', 'select',
            '.c-recommendation', '.c-trending', '[class*="related"]',
            '[class*="suggest"]', '[class*="taboola"]', '[class*="outbrain"]',
            '.c-stickyplayer', '.slot', '[data-share-btns]', '[data-share-native]',
            '.c-share', '.l-entry__byline', '.l-entry__podcast', '[data-podcast]',
            'figure.l-entry__media', '.c-tags',
            'img', 'picture', 'source', 'video', 'audio', 'canvas', 'svg',
            'figcaption', '.l-entry__media-caption', '.l-entry__media-attribution',
            'blockquote', 'cite', 'q', '.c-quote',
            '.btn', '.button', '[role="button"]', '.pagination', '.pager',
            '#comments', '.comments-section', '.c-comments'
        ];
        document.querySelectorAll(selectors.join(', ')).forEach(el => el.remove());

        // RIMOZIONE SICURA DOSSIER/ARTICOLI CORRELATI
        document.querySelectorAll('.l-entry__body h2, .l-entry__body h3, .l-entry__body h4').forEach(el => {
            const link = el.querySelector('a');
            if (link && el.textContent.trim() === link.textContent.trim()) {
                el.remove();
            }
        });
        """

        self.crawler_config = CrawlerRunConfig(
            css_selector=".l-entry__body",
            js_code=self.js_cleanup_script,
            excluded_tags=["nav", "footer", "aside", "form", "script", "style"],
            word_count_threshold=5,
            exclude_external_links=False,
            magic=True,
            cache_mode=CacheMode.BYPASS
        )

    def _extract_meta_from_html(self, raw_html: str) -> tuple[str, str]:
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

        title = html.unescape(title or "").strip()
        title = re.sub(r'\s+', ' ', title)
        
        summary = html.unescape(summary or "").strip()
        summary = re.sub(r'\s+', ' ', summary)

        return title, summary

    async def parse(self, url: str, html_text: str = None) -> dict:
        domain = urlparse(url).netloc
        if domain not in ["www.romatoday.it", "romatoday.it"]:
            raise ValueError("Questo parser supporta solo il dominio www.romatoday.it o romatoday.it")

        pre_title, pre_summary = "", ""
        
        if html_text:
            pre_title, pre_summary = self._extract_meta_from_html(html_text)
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, 'html.parser')
            
            selectors = [
                'footer', 'nav', 'aside',
                '.c-smb', '.o-link-category', '.article-authors', '.article-date',
                '.c-announcement', '.c-social-bar', '.c-related-articles',
                '.l-entry__header',
                'script', 'style', 'noscript', 'iframe', 'form',
                'input', 'button', 'textarea', 'select',
                '.c-recommendation', '.c-trending', '.c-stickyplayer', '.slot', 
                '.c-share', '.l-entry__byline', '.l-entry__podcast', 
                'figure.l-entry__media', '.c-tags',
                'img', 'picture', 'source', 'video', 'audio', 'canvas', 'svg',
                'figcaption', 'blockquote', 'cite', 'q', '.btn', '.button'
            ]
            for sel in selectors:
                for el in soup.select(sel):
                    el.decompose()
            
            for css in ['social', 'share', 'adv', 'banner', 'sponsor', 'newsletter', 'cookie', 'gdpr', 'popup', 'related', 'suggest', 'taboola', 'outbrain']:
                for el in soup.select(f'[class*="{css}"]'):
                    el.decompose()
                    
            for el in soup.select('[data-share-btns], [data-share-native], [data-podcast]'):
                el.decompose()

            for el in soup.select('.l-entry__body h2, .l-entry__body h3, .l-entry__body h4'):
                link = el.find('a')
                if link and el.get_text(strip=True) == link.get_text(strip=True):
                    el.decompose()
            
            content = soup.select_one('.l-entry__body')
            if content and soup.body:
                soup.body.clear()
                soup.body.append(content)
                
            html_text = str(soup)

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            run_url = f"raw:{html_text}" if html_text else url
            result = await crawler.arun(url=run_url, config=self.crawler_config)

            title = pre_title
            summary = pre_summary
            
            if not title:
                t, s = self._extract_meta_from_html(result.html)
                title = t or title
                summary = s or summary

            if not title:
                path_end = urlparse(url).path.rstrip('/').split('/')[-1]
                title = re.sub(r'\.\w+$', '', path_end).replace('-', ' ').capitalize()

            raw_md = result.markdown or ""

            clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', raw_md)
            
            # Rimozione link intrusivi "come [TUTTE LE INFORMAZIONI]" o varianti prima che vengano espansi
            promo_patterns = [
                r'(?i)\[.*?(?:tutte\s+le\s+informazioni|tutti\s+i\s+dettagli|leggi\s+anche|qui\s+i\s+dettagli).*?\](?:\([^\)]+\))?',
                r'(?i)(?:tutte\s+le\s+informazioni|tutti\s+i\s+dettagli)'
            ]
            for p in promo_patterns:
                clean_text = re.sub(p, ' ', clean_text)

            clean_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean_text)
            clean_text = re.sub(r'\[\d+\]', '', clean_text)
            clean_text = re.sub(r'#+\s?', '', clean_text)
            clean_text = clean_text.replace('\n', ' ').replace('\r', ' ')
            clean_text = re.sub(r'https?://\S+|www\.\S+', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'\|\s*[A-Z][a-zA-Z\s]+\s*\|', '', clean_text)
            clean_text = re.sub(r'\(\s*\)|\{\s*\}|\[\s*\]', '', clean_text)
            
            clean_text = re.sub(r'(?:---|___|\*\*\*(?!\*))\s*', '', clean_text)
            
            clean_text = re.sub(
                r'\b\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{4}(?:,\s*\d{2}:\d{2})?\b',
                '', clean_text, flags=re.IGNORECASE
            )

            clean_text = re.sub(
                r'_?RomaToday è anche su Mobile.*?aggiornato\.?_?', 
                '', clean_text, flags=re.IGNORECASE
            )
            
            clean_text = re.sub(r'\s+social\s+(?=[A-Z])', ' ', clean_text)
            
            clean_text = html.unescape(clean_text)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            final_parts = []
            if title: final_parts.append(title)
            if summary: final_parts.append(summary)
                
            if clean_text:
                temp_text = clean_text
                if title and title in temp_text:
                    temp_text = temp_text.replace(title, "", 1)
                if summary and summary in temp_text:
                    temp_text = temp_text.replace(summary, "", 1)
                    
                final_parts.append(temp_text.strip())

            full_clean_text = " ".join(final_parts)
            full_clean_text = re.sub(r'\s+', ' ', full_clean_text).strip()

            return {
                "url": url,
                "domain": domain,
                "title": title,
                "summary": summary,
                "html_text": result.html,
                "parsed_text": full_clean_text
            }