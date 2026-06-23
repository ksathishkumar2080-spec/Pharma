"""CrossRef API connector.

Docs: https://api.crossref.org/swagger-ui/index.html
Free, no API key. Polite pool via User-Agent + mailto.
Rate limit: 50 req/sec (polite pool)
"""
import asyncio
import httpx
from ingestion.connectors.base import BaseConnector
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text

BASE = "https://api.crossref.org"

ONCOLOGY_JOURNALS = [
    "Journal of Clinical Oncology",
    "Nature Medicine",
    "New England Journal of Medicine",
    "The Lancet Oncology",
    "Cancer Cell",
    "Cancer Discovery",
    "Annals of Oncology",
    "Blood",
    "Journal of Hematology & Oncology",
    "npj Precision Oncology",
]


class CrossRefConnector(BaseConnector):
    def __init__(self):
        super().__init__()
        settings = get_settings()
        self._email = settings.ncbi_email or "oncology-intel@internal"
        self._headers = {
            "User-Agent": f"OncologyIntelBot/1.0 (mailto:{self._email})",
        }

    async def fetch(self) -> list[dict]:
        """Fetch recent oncology works from key journals."""
        works = []
        async with httpx.AsyncClient(timeout=30, headers=self._headers) as client:
            for journal in ONCOLOGY_JOURNALS:
                batch = await self._fetch_journal_works(client, journal)
                works.extend(batch)
                await asyncio.sleep(0.5)
        self.log.info("CrossRef: fetched %d works", len(works))
        return works

    async def _fetch_journal_works(self, client: httpx.AsyncClient, journal: str) -> list[dict]:
        try:
            resp = await client.get(
                f"{BASE}/works",
                params={
                    "query.container-title": journal,
                    "filter": "from-pub-date:2023,type:journal-article",
                    "rows": 100,
                    "sort": "is-referenced-by-count",
                    "order": "desc",
                    "select": "DOI,title,abstract,author,published,container-title,"
                              "is-referenced-by-count,ISSN,funder,subject",
                },
            )
            resp.raise_for_status()
            return resp.json().get("message", {}).get("items", [])
        except Exception as e:
            self.log.warning("CrossRef journal fetch failed '%s': %s", journal, e)
            return []

    async def resolve_doi(self, doi: str) -> dict | None:
        """Fetch full metadata for a specific DOI."""
        async with httpx.AsyncClient(timeout=15, headers=self._headers) as client:
            try:
                resp = await client.get(f"{BASE}/works/{doi}")
                resp.raise_for_status()
                return resp.json().get("message")
            except Exception as e:
                self.log.warning("DOI resolve failed %s: %s", doi, e)
                return None

    async def get_funder_grants(self, funder_doi: str) -> list[dict]:
        """Get works funded by a specific organization (e.g., NCI)."""
        async with httpx.AsyncClient(timeout=20, headers=self._headers) as client:
            try:
                resp = await client.get(
                    f"{BASE}/funders/{funder_doi}/works",
                    params={"rows": 100, "filter": "from-pub-date:2022"},
                )
                resp.raise_for_status()
                return resp.json().get("message", {}).get("items", [])
            except Exception as e:
                self.log.warning("Funder grants fetch failed: %s", e)
                return []

    async def store(self, records: list[dict]) -> None:
        factory = get_session_factory()
        async with factory() as session:
            for work in records:
                doi = work.get("DOI", "")
                title_list = work.get("title", [])
                title = title_list[0] if title_list else ""
                abstract = work.get("abstract", "")
                authors = work.get("author", [])
                journal_list = work.get("container-title", [])
                journal = journal_list[0] if journal_list else ""
                pub = work.get("published", {}).get("date-parts", [[]])[0]
                pub_date = f"{pub[0]}-{pub[1]:02d}-01" if len(pub) >= 2 else (f"{pub[0]}-01-01" if pub else None)
                citations = work.get("is-referenced-by-count", 0)
                funders = work.get("funder", [])

                await session.execute(text("""
                    INSERT INTO publications (title, abstract, journal, published_at, doi, citation_count, raw_json)
                    VALUES (:title, :abstract, :journal, :pub_date, :doi, :citations, :raw)
                    ON CONFLICT DO NOTHING
                """), {
                    "title": title,
                    "abstract": abstract[:5000] if abstract else None,
                    "journal": journal,
                    "pub_date": pub_date,
                    "doi": doi,
                    "citations": citations,
                    "raw": str(work),
                })

                # Detect grant awards from funder metadata -> trigger events
                for funder in funders:
                    awards = funder.get("award", [])
                    if awards:
                        funder_name = funder.get("name", "Unknown")
                        for award in awards[:3]:
                            self.log.debug("Grant signal: %s from %s", award, funder_name)

            await session.commit()
        self.log.info("CrossRef: stored %d records", len(records))
