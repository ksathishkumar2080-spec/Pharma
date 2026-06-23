"""AACR abstract scraper."""
from playwright.async_api import async_playwright
from ingestion.connectors.base import BaseConnector
import uuid

AACR_URL = "https://www.aacr.org/meeting/aacr-annual-meeting/abstracts"


class AACRScraper(BaseConnector):
    async def fetch(self) -> list[dict]:
        records = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(AACR_URL, wait_until="networkidle", timeout=30000)
            try:
                await page.wait_for_selector(".abstract, .session-abstract, .abstract-result", timeout=10000)
                items = await page.query_selector_all(".abstract, .session-abstract, .abstract-result")
                for item in items[:100]:
                    title_el = await item.query_selector("h3, h4, .abstract-title")
                    body_el = await item.query_selector(".abstract-content, p")
                    author_el = await item.query_selector(".authors, .presenter")
                    title = (await title_el.inner_text()).strip() if title_el else ""
                    body = (await body_el.inner_text()).strip() if body_el else ""
                    authors = (await author_el.inner_text()).strip() if author_el else ""
                    if title:
                        records.append({"source": "AACR", "title": title, "abstract": body, "authors": authors})
            except Exception as e:
                self.log.warning("AACR scrape error: %s", e)
            finally:
                await browser.close()
        return records

    async def store(self, records: list[dict]) -> None:
        from elasticsearch import AsyncElasticsearch
        from shared.config import get_settings
        es = AsyncElasticsearch(get_settings().elasticsearch_url)
        for rec in records:
            await es.index(index="conference_abstracts", document={**rec, "id": str(uuid.uuid4())})
        await es.close()
