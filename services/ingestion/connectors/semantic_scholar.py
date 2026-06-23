"""Semantic Scholar API connector.

Docs: https://api.semanticscholar.org/api-docs/
Free tier: 100 requests / 5 minutes (no key required)
With API key: 1 request / second
"""
import asyncio
import httpx
from ingestion.connectors.base import BaseConnector
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text

BASE = "https://api.semanticscholar.org/graph/v1"

ONCOLOGY_QUERIES = [
    "oncology clinical trial",
    "cancer immunotherapy",
    "tumor biomarker",
    "hematologic malignancy",
    "solid tumor targeted therapy",
]

PAPER_FIELDS = (
    "paperId,title,abstract,year,citationCount,influentialCitationCount,"
    "authors,journal,externalIds,fieldsOfStudy,publicationDate"
)

AUTHOR_FIELDS = "authorId,name,affiliations,citationCount,hIndex,externalIds"


class SemanticScholarConnector(BaseConnector):
    def __init__(self):
        super().__init__()
        settings = get_settings()
        self._api_key = getattr(settings, "semantic_scholar_api_key", "")

    def _headers(self) -> dict:
        h = {"User-Agent": "OncologyIntelBot/1.0"}
        if self._api_key:
            h["x-api-key"] = self._api_key
        return h

    async def fetch(self) -> list[dict]:
        papers = []
        async with httpx.AsyncClient(timeout=30, headers=self._headers()) as client:
            for query in ONCOLOGY_QUERIES:
                batch = await self._search_papers(client, query)
                papers.extend(batch)
                # Respect free-tier rate limit
                await asyncio.sleep(3)
        # Deduplicate by paperId
        seen = set()
        unique = []
        for p in papers:
            if p.get("paperId") and p["paperId"] not in seen:
                seen.add(p["paperId"])
                unique.append(p)
        self.log.info("SemanticScholar: fetched %d unique papers", len(unique))
        return unique

    async def _search_papers(self, client: httpx.AsyncClient, query: str) -> list[dict]:
        try:
            resp = await client.get(
                f"{BASE}/paper/search",
                params={
                    "query": query,
                    "fields": PAPER_FIELDS,
                    "limit": 100,
                    "publicationTypes": "JournalArticle,ClinicalTrial",
                    "year": "2020-",
                },
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as e:
            self.log.warning("SemanticScholar search failed for '%s': %s", query, e)
            return []

    async def fetch_author(self, author_id: str) -> dict | None:
        async with httpx.AsyncClient(timeout=20, headers=self._headers()) as client:
            try:
                resp = await client.get(
                    f"{BASE}/author/{author_id}",
                    params={"fields": AUTHOR_FIELDS},
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                self.log.warning("Author fetch failed %s: %s", author_id, e)
                return None

    async def store(self, records: list[dict]) -> None:
        factory = get_session_factory()
        stored = 0
        async with factory() as session:
            for paper in records:
                ext = paper.get("externalIds") or {}
                pubmed_id = ext.get("PubMed") or ext.get("PMID")
                doi = ext.get("DOI")
                pub_date = paper.get("publicationDate") or str(paper.get("year", ""))

                await session.execute(text("""
                    INSERT INTO publications (
                        pubmed_id, title, abstract, journal,
                        published_at, doi, citation_count, raw_json
                    )
                    VALUES (:pubmed_id, :title, :abstract, :journal,
                            :published_at, :doi, :citations, :raw)
                    ON CONFLICT (pubmed_id) DO UPDATE
                    SET citation_count = GREATEST(publications.citation_count, EXCLUDED.citation_count),
                        doi = COALESCE(publications.doi, EXCLUDED.doi)
                    WHERE pubmed_id IS NOT NULL
                """), {
                    "pubmed_id": pubmed_id,
                    "title": paper.get("title", ""),
                    "abstract": paper.get("abstract"),
                    "journal": (paper.get("journal") or {}).get("name"),
                    "published_at": pub_date[:10] if pub_date and len(pub_date) >= 10 else None,
                    "doi": doi,
                    "citations": paper.get("citationCount", 0),
                    "raw": str(paper),
                })
                stored += 1
            await session.commit()
        self.log.info("SemanticScholar: stored %d papers", stored)

    async def enrich_hcp_citation_metrics(self):
        """Fetch h-index and citation counts for known HCP authors."""
        factory = get_session_factory()
        async with factory() as session:
            hcps = (await session.execute(
                text("SELECT id, full_name FROM hcps LIMIT 200")
            )).fetchall()

        async with httpx.AsyncClient(timeout=20, headers=self._headers()) as client:
            for hcp_id, name in hcps:
                try:
                    resp = await client.get(
                        f"{BASE}/author/search",
                        params={"query": name, "fields": AUTHOR_FIELDS, "limit": 1},
                    )
                    if resp.status_code == 200:
                        authors = resp.json().get("data", [])
                        if authors:
                            a = authors[0]
                            async with factory() as session:
                                await session.execute(text("""
                                    UPDATE hcps
                                    SET influence_score = LEAST(:h_index * 5, 100),
                                        updated_at = NOW()
                                    WHERE id = :id
                                """), {"h_index": a.get("hIndex", 0), "id": hcp_id})
                                await session.commit()
                    await asyncio.sleep(1)
                except Exception as e:
                    self.log.warning("Author enrichment failed %s: %s", name, e)
