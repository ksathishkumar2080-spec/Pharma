"""ASCO abstract scraper using Playwright for JavaScript-rendered content."""
import asyncio
from playwright.async_api import async_playwright
from ingestion.connectors.base import BaseConnector
from shared.db import get_session_factory
from sqlalchemy import text
import uuid

ASCO_SEARCH_URL = "https://meetings.asco.org/abstracts-presentations/search?q=oncology&meetings=annual"


class ASCOScraper(BaseConnector):
    async def fetch(self) -> list[dict]:
        records = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(ASCO_SEARCH_URL, wait_until="networkidle", timeout=30000)

            # Wait for abstract cards to render
            try:
                await page.wait_for_selector(".abstract-card, .search-result-item", timeout=10000)
            except Exception:
                self.log.warning("ASCO: no abstract cards found, page may have changed")
                await browser.close()
                return []

            cards = await page.query_selector_all(".abstract-card, .search-result-item")
            for card in cards[:100]:
                try:
                    title_el = await card.query_selector("h3, .title, [data-testid='abstract-title']")
                    author_el = await card.query_selector(".authors, .author-list")
                    abstract_el = await card.query_selector(".abstract-text, .abstract-body, p")
                    link_el = await card.query_selector("a")

                    title = (await title_el.inner_text()).strip() if title_el else ""
                    authors = (await author_el.inner_text()).strip() if author_el else ""
                    abstract = (await abstract_el.inner_text()).strip() if abstract_el else ""
                    link = await link_el.get_attribute("href") if link_el else ""

                    if title:
                        records.append({
                            "source": "ASCO",
                            "title": title,
                            "authors": authors,
                            "abstract": abstract,
                            "url": f"https://meetings.asco.org{link}" if link and link.startswith("/") else link,
                        })
                except Exception as e:
                    self.log.warning("ASCO card parse error: %s", e)

            await browser.close()
        self.log.info("ASCO scraped %d abstracts", len(records))
        return records

    async def store(self, records: list[dict]) -> None:
        from elasticsearch import AsyncElasticsearch
        from shared.config import get_settings
        settings = get_settings()
        es = AsyncElasticsearch(settings.elasticsearch_url)
        for rec in records:
            await es.index(index="conference_abstracts", document={**rec, "id": str(uuid.uuid4())})
        await es.close()
