"""Conference abstract connector (ASCO, ESMO, AACR, SABCS) via web scraping."""
import httpx
from ingestion.connectors.base import BaseConnector

# Public abstract search endpoints
SOURCES = {
    "ASCO": "https://meetings.asco.org/abstracts-presentations/search",
    "ESMO": "https://www.esmo.org/meeting-calendar/search",
    "AACR": "https://www.aacr.org/meeting/search",
    "SABCS": "https://www.sabcs.org/abstracts",
}


class ConferenceConnector(BaseConnector):
    async def fetch(self) -> list[dict]:
        records = []
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            for source, url in SOURCES.items():
                try:
                    resp = await client.get(url, headers={"User-Agent": "OncologyIntelBot/1.0"})
                    records.append({"source": source, "url": url, "status": resp.status_code})
                except Exception as exc:
                    self.log.warning("Failed to fetch %s: %s", source, exc)
        return records

    async def store(self, records: list[dict]) -> None:
        # Placeholder — full Playwright-based extraction handled by scraping workers
        self.log.info("Conference ping results: %s", records)
