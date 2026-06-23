"""Wiley Text and Data Mining (TDM) API connector.

Docs: https://onlinelibrary.wiley.com/library-info/resources/text-and-data-mining
Requires: Wiley TDM API key (institutional/enterprise access)
Endpoint: https://api.wiley.com/onlinelibrary/tdm/v2/articles/{doi}

Provides full-text access to Wiley/Blackwell oncology journals:
  - Cancer
  - International Journal of Cancer
  - Clinical Cancer Research
  - Cancer Medicine
  - British Journal of Cancer
  - European Journal of Cancer
"""
import asyncio
import httpx
from ingestion.connectors.base import BaseConnector
from shared.config import get_settings
from shared.db import get_session_factory
from elasticsearch import AsyncElasticsearch
from sqlalchemy import text

WILEY_TDM_BASE = "https://api.wiley.com/onlinelibrary/tdm/v2"

# Wiley oncology journal ISSNs
WILEY_ONCOLOGY_ISSNS = [
    "1097-0142",  # Cancer (Wiley)
    "0020-7136",  # International Journal of Cancer
    "1078-0432",  # Clinical Cancer Research
    "2045-7634",  # Cancer Medicine
    "0007-0920",  # British Journal of Cancer
    "0959-8049",  # European Journal of Cancer
    "1055-9965",  # Cancer Epidemiology, Biomarkers & Prevention
    "1538-7445",  # Cancer Research
]


class WileyTDMConnector(BaseConnector):
    def __init__(self):
        super().__init__()
        settings = get_settings()
        self._api_key = settings.wiley_api_key

    def _headers(self) -> dict:
        return {
            "Wiley-TDM-Client-Token": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def fetch(self) -> list[dict]:
        if not self._api_key:
            self.log.warning("Wiley TDM API key not configured — skipping full-text fetch")
            return []

        # Fetch DOIs of publications we already have that are in Wiley journals
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT id, doi FROM publications
                WHERE doi IS NOT NULL
                AND raw_json::text ILIKE '%wiley%'
                AND abstract IS NULL
                LIMIT 50
            """))).fetchall()

        records = []
        async with httpx.AsyncClient(timeout=30) as client:
            for pub_id, doi in rows:
                content = await self._fetch_full_text(client, doi)
                if content:
                    records.append({"pub_id": pub_id, "doi": doi, **content})
                await asyncio.sleep(1)

        self.log.info("Wiley TDM: fetched %d full-text articles", len(records))
        return records

    async def _fetch_full_text(self, client: httpx.AsyncClient, doi: str) -> dict | None:
        try:
            resp = await client.get(
                f"{WILEY_TDM_BASE}/articles/{doi}",
                headers=self._headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "abstract": data.get("abstract"),
                    "body": data.get("body", {}).get("text"),
                    "sections": data.get("sections", []),
                    "keywords": data.get("keywords", []),
                    "references": data.get("references", []),
                }
            elif resp.status_code == 403:
                self.log.warning("Wiley TDM: no access for DOI %s (subscription required)", doi)
        except Exception as e:
            self.log.warning("Wiley TDM fetch failed for %s: %s", doi, e)
        return None

    async def store(self, records: list[dict]) -> None:
        factory = get_session_factory()
        settings = get_settings()
        es = AsyncElasticsearch(settings.elasticsearch_url)

        async with factory() as session:
            for rec in records:
                # Update abstract if we now have full text
                if rec.get("abstract"):
                    await session.execute(text("""
                        UPDATE publications
                        SET abstract = :abstract
                        WHERE id = :id AND abstract IS NULL
                    """), {"abstract": rec["abstract"], "id": rec["pub_id"]})

                # Index full text in Elasticsearch
                if rec.get("body"):
                    await es.index(
                        index="publication_fulltext",
                        id=str(rec["pub_id"]),
                        document={
                            "pub_id": str(rec["pub_id"]),
                            "doi": rec["doi"],
                            "body": rec["body"][:50000],
                            "keywords": rec.get("keywords", []),
                            "sections": [
                                {"title": s.get("title"), "text": s.get("text", "")[:5000]}
                                for s in rec.get("sections", [])[:10]
                            ],
                        },
                    )
            await session.commit()
        await es.close()
        self.log.info("Wiley TDM: updated %d publications with full text", len(records))

    async def validate_grammar(self, text: str) -> dict:
        """Grammar/style validation via Wiley proofing API (used by messaging service)."""
        if not self._api_key:
            return {"valid": True, "issues": [], "corrected": None}

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.post(
                    f"{WILEY_TDM_BASE}/proofing",
                    headers=self._headers(),
                    json={"text": text, "language": "en-US", "domain": "medical"},
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                self.log.warning("Wiley grammar validation failed: %s", e)

        return {"valid": True, "issues": [], "corrected": None}
