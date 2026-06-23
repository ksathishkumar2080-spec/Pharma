"""Europe PMC API connector.

Docs: https://europepmc.org/RestfulWebService
Free, no API key required.
Provides: full-text open access, MeSH terms, grants, ORCID
"""
import asyncio
import httpx
from ingestion.connectors.base import BaseConnector
from shared.db import get_session_factory
from sqlalchemy import text

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"

ONCOLOGY_MESH_TERMS = [
    "Neoplasms",
    "Antineoplastic Agents",
    "Immunotherapy",
    "Biomarkers, Tumor",
    "Precision Medicine",
]


class EuropePMCConnector(BaseConnector):
    async def fetch(self) -> list[dict]:
        papers = []
        async with httpx.AsyncClient(timeout=30) as client:
            for term in ONCOLOGY_MESH_TERMS:
                batch = await self._search(client, term)
                papers.extend(batch)
                await asyncio.sleep(1)
        seen = set()
        unique = []
        for p in papers:
            pid = p.get("pmid") or p.get("id")
            if pid and pid not in seen:
                seen.add(pid)
                unique.append(p)
        self.log.info("EuropePMC: fetched %d papers", len(unique))
        return unique

    async def _search(self, client: httpx.AsyncClient, mesh_term: str) -> list[dict]:
        try:
            resp = await client.get(
                f"{BASE}/search",
                params={
                    "query": f'MESH:"{mesh_term}" AND OPEN_ACCESS:y AND PUB_YEAR:[2022 TO 2025]',
                    "format": "json",
                    "resultType": "core",
                    "pageSize": 100,
                    "sort": "CITED desc",
                },
            )
            resp.raise_for_status()
            return resp.json().get("resultList", {}).get("result", [])
        except Exception as e:
            self.log.warning("EuropePMC search failed for '%s': %s", mesh_term, e)
            return []

    async def get_full_text_xml(self, pmcid: str) -> str | None:
        """Fetch full-text XML for open-access papers."""
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(f"{BASE}/{pmcid}/fullTextXML")
                if resp.status_code == 200:
                    return resp.text
            except Exception as e:
                self.log.warning("Full text fetch failed %s: %s", pmcid, e)
        return None

    async def get_citations(self, pmid: str) -> list[dict]:
        """Get papers that cite a given PMID."""
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.get(
                    f"{BASE}/MED/{pmid}/citations",
                    params={"format": "json", "pageSize": 50},
                )
                resp.raise_for_status()
                return resp.json().get("citationList", {}).get("citation", [])
            except Exception as e:
                self.log.warning("Citations fetch failed %s: %s", pmid, e)
                return []

    async def store(self, records: list[dict]) -> None:
        factory = get_session_factory()
        async with factory() as session:
            for paper in records:
                pmid = paper.get("pmid")
                pmcid = paper.get("pmcid")
                mesh_list = [
                    m["descriptorName"]
                    for m in (paper.get("meshHeadingList") or {}).get("meshHeading", [])
                    if "descriptorName" in m
                ][:10]
                grants = [
                    g.get("agency", "")
                    for g in (paper.get("grantsList") or {}).get("grant", [])
                ][:5]
                authors = [
                    f"{a.get('lastName', '')} {a.get('firstName', '')} (ORCID: {a.get('authorId', {}).get('value', 'N/A')})"
                    for a in (paper.get("authorList") or {}).get("author", [])[:10]
                ]

                if pmid:
                    await session.execute(text("""
                        INSERT INTO publications (
                            pubmed_id, title, abstract, journal, published_at,
                            citation_count, disease_areas, raw_json
                        )
                        VALUES (:pmid, :title, :abstract, :journal, :pub_date,
                                :citations, :mesh, :raw)
                        ON CONFLICT (pubmed_id) DO UPDATE
                        SET disease_areas = COALESCE(EXCLUDED.disease_areas, publications.disease_areas),
                            citation_count = GREATEST(publications.citation_count, EXCLUDED.citation_count)
                    """), {
                        "pmid": pmid,
                        "title": paper.get("title", ""),
                        "abstract": paper.get("abstractText"),
                        "journal": paper.get("journalTitle"),
                        "pub_date": paper.get("firstPublicationDate"),
                        "citations": paper.get("citedByCount", 0),
                        "mesh": mesh_list or None,
                        "raw": str(paper)[:5000],
                    })
            await session.commit()
        self.log.info("EuropePMC: stored %d papers", len(records))
