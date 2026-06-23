"""SABCS (San Antonio Breast Cancer Symposium) abstract scraper."""
from playwright.async_api import async_playwright
from ingestion.connectors.base import BaseConnector
import uuid

SABCS_URL = "https://www.sabcs.org/Meetings/San-Antonio-Breast-Cancer-Symposium/2024-SABCS/Abstracts"


class SABCSScraper(BaseConnector):
    async def fetch(self) -> list[dict]:
        records = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(SABCS_URL, wait_until="networkidle", timeout=30000)
            try:
                await page.wait_for_selector("table tr, .abstract-row, .abstract-item", timeout=10000)
                rows = await page.query_selector_all("table tr, .abstract-row, .abstract-item")
                for row in rows[:150]:
                    cells = await row.query_selector_all("td, .cell")
                    if len(cells) >= 2:
                        title = (await cells[0].inner_text()).strip()
                        authors = (await cells[1].inner_text()).strip() if len(cells) > 1 else ""
                        if title and len(title) > 10:
                            records.append({"source": "SABCS", "title": title, "authors": authors})
            except Exception as e:
                self.log.warning("SABCS scrape error: %s", e)
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
