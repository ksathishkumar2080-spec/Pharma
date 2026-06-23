"""Oncology news connector (Fierce Pharma, Endpoints, STAT, PharmaVoice)."""
import httpx
from ingestion.connectors.base import BaseConnector

RSS_FEEDS = {
    "FiercePharma": "https://www.fiercepharma.com/rss/xml",
    "EndpointsNews": "https://endpts.com/feed",
    "STAT": "https://www.statnews.com/feed",
    "PharmaVoice": "https://www.pharmavoice.com/feed",
}


class NewsConnector(BaseConnector):
    async def fetch(self) -> list[dict]:
        records = []
        async with httpx.AsyncClient(timeout=20) as client:
            for source, url in RSS_FEEDS.items():
                try:
                    resp = await client.get(url)
                    records.append({"source": source, "content": resp.text[:2000]})
                except Exception as exc:
                    self.log.warning("Failed %s: %s", source, exc)
        return records

    async def store(self, records: list[dict]) -> None:
        # Store parsed news items into Elasticsearch for full-text search
        from elasticsearch import AsyncElasticsearch
        from shared.config import get_settings

        settings = get_settings()
        es = AsyncElasticsearch(settings.elasticsearch_url)
        for item in records:
            await es.index(index="oncology_news", document=item)
        await es.close()
