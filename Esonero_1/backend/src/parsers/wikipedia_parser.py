import asyncio
import json
import re
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

class WikipediaParser:
    def __init__(self):
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080
        )
        
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
        
        self.crawler_config = CrawlerRunConfig(
            css_selector="#mw-content-text",
            excluded_tags=["nav", "footer", "aside", "header", "form", "script", "style"],
            js_code=self.js_cleanup_script,
            word_count_threshold=1,
            exclude_external_links=False
        )

    async def parse(self, url: str, html_text: str = None) -> dict:
        domain = urlparse(url).netloc
        if not domain.endswith("wikipedia.org"):
            raise ValueError("Questo parser supporta solo il dominio wikipedia.org")

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            run_url = f"raw:{html_text}" if html_text else url
            result = await crawler.arun(url=run_url, config=self.crawler_config)
            if not result.success:
                raise Exception(f"Crawl failed: {result.error_message}")
                
            raw_md = result.markdown
            
            # Truncation at end sections
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
            
            # Cleanup
            clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', raw_md)
            clean_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean_text)
            clean_text = re.sub(r'\[\d+\]', ' ', clean_text)
            clean_text = re.sub(r'#+\s?', ' ', clean_text)
            clean_text = clean_text.replace('\n', ' ').replace('\r', ' ')
            
            # Parentheses and brackets cleanup
            for _ in range(2):
                clean_text = re.sub(r'\(\s*[;,\s]*\)', ' ', clean_text)
                clean_text = re.sub(r'\[\s*[;,\s]*\]', ' ', clean_text)
            
            # Common artifacts
            clean_text = re.sub(r'(?i)edit|citation needed|Jump up to', ' ', clean_text)
            clean_text = re.sub(r'https?://\S+|www\.\S+', ' ', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'\{\{[^}]+\}\}', ' ', clean_text)
            
            # Repeated punctuation and whitespace
            clean_text = re.sub(r'(?:[\*\.]\s*){3,}', ' ', clean_text)
            
            # --- CLEANUP REDUNDANCIES ---
            # Handles things like: The Swan's Way "Swan's Way (footpath)") 
            # by removing common nested link artifacts.
            clean_text = re.sub(r'["\']([^"\']+)["\']\s*\(\1[^)]*\)', r'\1', clean_text)
            clean_text = re.sub(r'([^ ]+)\s*\(\1[^)]*\)', r'\1', clean_text)
            
            # --- REFINED TRAILING TRASH REMOVAL ---
            # Remove trailing bullet lists (minimum 2 items) at the very end
            # only if they match a pattern of navigational links (short phrases).
            clean_text = re.sub(r'(?:\s*\*\s*[^#\*]{2,40}){2,}\.?$', '', clean_text).strip()
            
            # Remove trailing parenthetical boilerplate
            clean_text = re.sub(r'\s*\([^)]*(?:link|map|archive|original|reference)[^)]*\)\.?$', '', clean_text, flags=re.IGNORECASE)
            
            # Disambiguations and quote artifacts
            clean_text = clean_text.replace('""', ' ')
            clean_text = re.sub(r'\\([()])', r'\1', clean_text)
            clean_text = clean_text.replace('\\', '')
            clean_text = re.sub(r'\[\s*(?:PDF|DOC|XLS|ZIP)\s*\]', ' ', clean_text, flags=re.IGNORECASE)
            
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            path_end = urlparse(url).path.split('/')[-1]
            title_text = unquote(path_end).replace("_", " ")

            return {
                "url": url,
                "domain": domain,
                "title": title_text,
                "html_text": result.html,
                "parsed_text": clean_text
            }