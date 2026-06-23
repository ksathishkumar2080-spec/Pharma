"""ESMO abstract scraper."""
from playwright.async_api import async_playwright
from ingestion.connectors.base import BaseConnector
import uuid

ESMO_URL = "https://www.esmo.org/meeting-calendar/esmo-congress/abstracts"


class ESMOScraper(BaseConnector):
    async def fetch(self) -> list[dict]:
        records = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(ESMO_URL, wait_until="networkidle", timeout=30000)
            try:
                await page.wait_for_selector(".abstract-item, .meeting-abstract, article", timeout=10000)
                items = await page.query_selector_all(".abstract-item, .meeting-abstract, article")
                for item in items[:100]:
                    title_el = await item.query_selector("h2, h3, .title")
                    body_el = await item.query_selector(".abstract-body, p")
                    title = (await title_el.inner_text()).strip() if title_el else ""
                    body = (await body_el.inner_text()).strip() if body_el else ""
                    if title:
                        records.append({"source": "ESMO", "title": title, "abstract": body})
            except Exception as e:
                self.log.warning("ESMO scrape error: %s", e)
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
