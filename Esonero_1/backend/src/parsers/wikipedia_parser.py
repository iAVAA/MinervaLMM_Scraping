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
            'form', 'input', 'button', 'textarea', 'select'
        ];
        document.querySelectorAll(selectors.join(', ')).forEach(el => el.remove());

        const endSectionIds = ['References', 'Bibliography', 'See_also', 'External_links', 'Further_reading', 'Notes', 'Note', 'Bibliografia', 'Voci_correlate', 'Collegamenti_esterni', 'Citations', 'Sources', 'Reference', 'Notes_and_references', 'References_and_notes', 'Works_cited', 'General_references'];
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
            word_count_threshold=5,
            exclude_external_links=False
        )

    async def parse(self, url: str) -> dict:
        domain = urlparse(url).netloc
        if domain != "en.wikipedia.org":
            raise ValueError("Questo parser supporta solo il dominio en.wikipedia.org")

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=url, config=self.crawler_config)
            raw_md = result.markdown
            
            end_sections = [
                'See also', 'References', 'External links', 'Further reading',
                'Bibliography', 'Notes', 'Citations', 'Sources', 'Works cited', 
                'General references', 'Notes and references'
            ]
            for section in end_sections:
                pattern = r'(?mi)^#{2,5}\s*' + re.escape(section) + r'\b.*$'
                match = re.search(pattern, raw_md)
                if match:
                    raw_md = raw_md[:match.start()]
            
            clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', raw_md)
            clean_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean_text)
            clean_text = re.sub(r'\[\d+\]', '', clean_text)
            clean_text = re.sub(r'#+\s?', '', clean_text)
            clean_text = clean_text.replace('\n', ' ').replace('\r', ' ')
            clean_text = re.sub(r'FOOTNOTE[A-Z0-9]*', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'https?://\S+|www\.\S+', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'(?:ISBN|doi|ISSN|JSTOR)\s*\"?[^\"]*\"?\s*[\d\-X]*', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'\[(?:[^\]]*needed|edit|update|page)\]', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'\^?\s*Jump up to:[\s\(\)]*', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'\*\*\^\*\*', '', clean_text)
            clean_text = re.sub(r'\^\s', '', clean_text)
            clean_text = re.sub(r'\(\s*\)|\{\s*\}|\[\s*\]', '', clean_text)
            clean_text = re.sub(r'\*\[c\.\]:\scirca', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'\(Subscription or participating institution membership required\.\)', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'This article incorporates text from this source, which is in the public domain\.?', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'CS1 maint:.*?(?=\n|$)', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'Archived\s+.*?at the Wayback Machine', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'WikiMiniAtlas.*?(?=\n|$)', '', clean_text, flags=re.IGNORECASE)
            
            # --- AGGIUNTE RICHIESTE ---
            # 14. Rimuove macro template residui
            clean_text = re.sub(r'`?\{\{\s*citation[^}]*\}\}`?', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'`?\{\{cite[^}]+\}\}`?', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'(?:["`\'])?Template:Citation[^\)]*\)?(?:["`\'])?', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'\{\{[^}]+\}\}', '', clean_text) # Catch-all per {{...}} residui
            
            # 15. Rimuove pattern ripetuti di punteggiatura (es: * * *, *.*.*.)
            clean_text = re.sub(r'(?:[\*\.]\s*){3,}', ' ', clean_text)
            clean_text = re.sub(r'(?:[\*\.\-~_]\s*){5,}', ' ', clean_text)
            
            # 16. Pialla numerazioni orfane create dai drop delle references
            clean_text = re.sub(r'(?:\b\d+\.\s*[\(\)\{\}\[\]\s]*)+', ' ', clean_text)
            
            # 17. Rimuove spazi vuoti multipli
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            # 18. Removes escaped parenthetical disambiguations (e.g., \(mythology\))
            clean_text = re.sub(r'\s*\\\([^)]+\\\)', '', clean_text)

            # 19. Removes redundant double quotes surrounding single words or phrases (e.g., ""Neptune"" -> Neptune)
            clean_text = re.sub(r'""([^"]+)""', r'\1', clean_text)

            path_end = urlparse(url).path.split('/')[-1]
            title_text = unquote(path_end).replace("_", " ")

            parsed_data = {
                "url": url,
                "domain": domain,
                "title": title_text,
                "html_text": result.html,
                "parsed_text": clean_text
            }
            return parsed_data