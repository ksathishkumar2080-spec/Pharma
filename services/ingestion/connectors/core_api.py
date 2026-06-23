"""CORE API connector — open access full-text papers.

Docs: https://core.ac.uk/documentation/api-v3/
Free tier: 100 req/day (no key). With API key: 10,000 req/day.
Provides open-access full text for 200M+ research papers.
"""
import asyncio
import httpx
from ingestion.connectors.base import BaseConnector
from shared.config import get_settings
from shared.db import get_session_factory
from elasticsearch import AsyncElasticsearch
from sqlalchemy import text

BASE = "https://api.core.ac.uk/v3"

ONCOLOGY_QUERIES = [
    "immunotherapy cancer clinical trial",
    "precision oncology biomarker",
    "tumor microenvironment therapy",
    "CAR-T cell therapy lymphoma",
    "checkpoint inhibitor solid tumor",
]


class COREAPIConnector(BaseConnector):
    def __init__(self):
        super().__init__()
        settings = get_settings()
        self._api_key = getattr(settings, "core_api_key", "")

    def _headers(self) -> dict:
        h = {"User-Agent": "OncologyIntelBot/1.0"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    async def fetch(self) -> list[dict]:
        papers = []
        async with httpx.AsyncClient(timeout=30, headers=self._headers()) as client:
            for query in ONCOLOGY_QUERIES:
                batch = await self._search(client, query)
                papers.extend(batch)
                await asyncio.sleep(2 if not self._api_key else 0.5)
        # Deduplicate
        seen = set()
        unique = [p for p in papers if p.get("id") not in seen and not seen.add(p.get("id", ""))]
        self.log.info("CORE: fetched %d open access papers", len(unique))
        return unique

    async def _search(self, client: httpx.AsyncClient, query: str) -> list[dict]:
        try:
            resp = await client.post(
                f"{BASE}/search/works",
                json={
                    "q": query,
                    "limit": 50,
                    "fields": ["id", "doi", "title", "abstract", "authors",
                               "yearPublished", "publisher", "fullText", "downloadUrl"],
                    "filters": {"yearPublished": {"gte": 2020}},
                },
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
        except Exception as e:
            self.log.warning("CORE search failed for '%s': %s", query, e)
            return []

    async def store(self, records: list[dict]) -> None:
        factory = get_session_factory()
        settings = get_settings()
        es = AsyncElasticsearch(settings.elasticsearch_url)

        async with factory() as session:
            for paper in records:
                doi = paper.get("doi")
                await session.execute(text("""
                    INSERT INTO publications (title, abstract, journal, published_at, doi, raw_json)
                    VALUES (:title, :abstract, :journal, :pub_date, :doi, :raw)
                    ON CONFLICT DO NOTHING
                """), {
                    "title": paper.get("title", ""),
                    "abstract": paper.get("abstract"),
                    "journal": paper.get("publisher"),
                    "pub_date": f"{paper['yearPublished']}-01-01" if paper.get("yearPublished") else None,
                    "doi": doi,
                    "raw": str(paper)[:3000],
                })

                # Index full text if available
                if paper.get("fullText"):
                    await es.index(
                        index="publication_fulltext",
                        id=f"core_{paper['id']}",
                        document={
                            "doi": doi,
                            "title": paper.get("title"),
                            "body": paper["fullText"][:50000],
                            "source": "core",
                        },
                    )
            await session.commit()
        await es.close()
        self.log.info("CORE: stored %d papers", len(records))
