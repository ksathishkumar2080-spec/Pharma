"""OpenAlex API connector.

Docs: https://docs.openalex.org/
Free, no API key required. Polite pool via email param.
Oncology concept: C71924100
"""
import asyncio
import httpx
from ingestion.connectors.base import BaseConnector
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text

BASE = "https://api.openalex.org"
ONCOLOGY_CONCEPT = "C71924100"   # Oncology concept ID in OpenAlex
ADDITIONAL_CONCEPTS = [
    "C2779455573",  # Immunotherapy
    "C2778793908",  # Clinical trial (oncology)
    "C186243641",   # Targeted therapy
]


class OpenAlexConnector(BaseConnector):
    def __init__(self):
        super().__init__()
        settings = get_settings()
        self._email = settings.ncbi_email or "oncology-intel@internal"

    def _params(self, extra: dict | None = None) -> dict:
        p = {"mailto": self._email, "per_page": 200}
        if extra:
            p.update(extra)
        return p

    async def fetch(self) -> list[dict]:
        works = []
        async with httpx.AsyncClient(timeout=30) as client:
            for concept in [ONCOLOGY_CONCEPT] + ADDITIONAL_CONCEPTS:
                batch = await self._fetch_works(client, concept)
                works.extend(batch)
                await asyncio.sleep(1)
        # Deduplicate by OpenAlex ID
        seen = set()
        unique = [w for w in works if w["id"] not in seen and not seen.add(w["id"])]
        self.log.info("OpenAlex: fetched %d unique works", len(unique))
        return unique

    async def _fetch_works(self, client: httpx.AsyncClient, concept_id: str) -> list[dict]:
        try:
            resp = await client.get(
                f"{BASE}/works",
                params=self._params({
                    "filter": f"concepts.id:{concept_id},publication_year:2020-2025,type:journal-article",
                    "sort": "cited_by_count:desc",
                    "select": "id,doi,title,abstract_inverted_index,authorships,publication_date,"
                              "cited_by_count,primary_location,concepts,open_access,grants",
                }),
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
        except Exception as e:
            self.log.warning("OpenAlex works fetch failed for %s: %s", concept_id, e)
            return []

    async def fetch_institution(self, ror_id: str) -> dict | None:
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.get(
                    f"{BASE}/institutions/{ror_id}",
                    params=self._params(),
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                self.log.warning("OpenAlex institution fetch failed %s: %s", ror_id, e)
                return None

    async def fetch_author(self, openalex_author_id: str) -> dict | None:
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.get(
                    f"{BASE}/authors/{openalex_author_id}",
                    params=self._params(),
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                self.log.warning("OpenAlex author fetch failed: %s", e)
                return None

    def _reconstruct_abstract(self, inverted_index: dict | None) -> str | None:
        """OpenAlex stores abstracts as inverted index {word: [positions]}."""
        if not inverted_index:
            return None
        position_word: dict[int, str] = {}
        for word, positions in inverted_index.items():
            for pos in positions:
                position_word[pos] = word
        return " ".join(position_word[i] for i in sorted(position_word))

    async def store(self, records: list[dict]) -> None:
        factory = get_session_factory()
        async with factory() as session:
            for work in records:
                doi = (work.get("doi") or "").replace("https://doi.org/", "")
                abstract = self._reconstruct_abstract(work.get("abstract_inverted_index"))
                journal = (
                    (work.get("primary_location") or {}).get("source") or {}
                ).get("display_name")
                concepts = [c["display_name"] for c in (work.get("concepts") or [])[:5]]

                # Upsert publication
                await session.execute(text("""
                    INSERT INTO publications (title, abstract, journal, published_at, doi, citation_count, raw_json)
                    VALUES (:title, :abstract, :journal, :pub_date, :doi, :citations, :raw)
                    ON CONFLICT (pubmed_id) DO NOTHING
                """), {
                    "title": work.get("title", ""),
                    "abstract": abstract,
                    "journal": journal,
                    "pub_date": work.get("publication_date"),
                    "doi": doi or None,
                    "citations": work.get("cited_by_count", 0),
                    "raw": str(work),
                })

                # Enrich institutions from authorships
                for authorship in (work.get("authorships") or []):
                    for inst in (authorship.get("institutions") or []):
                        ror = inst.get("ror")
                        name = inst.get("display_name", "")
                        if name:
                            await session.execute(text("""
                                INSERT INTO institutions (name)
                                VALUES (:name)
                                ON CONFLICT DO NOTHING
                            """), {"name": name})

            await session.commit()
        self.log.info("OpenAlex: stored %d works", len(records))

    async def sync_hcp_orcids(self):
        """Match HCPs to OpenAlex authors via name search, store ORCID."""
        factory = get_session_factory()
        async with factory() as session:
            hcps = (await session.execute(
                text("SELECT id, full_name FROM hcps WHERE researchgate_url IS NULL LIMIT 100")
            )).fetchall()

        async with httpx.AsyncClient(timeout=20) as client:
            for hcp_id, name in hcps:
                try:
                    resp = await client.get(
                        f"{BASE}/authors",
                        params=self._params({"search": name, "filter": "last_known_institution.type:healthcare"}),
                    )
                    if resp.status_code == 200:
                        results = resp.json().get("results", [])
                        if results:
                            author = results[0]
                            orcid = author.get("orcid")
                            h_index = (author.get("summary_stats") or {}).get("h_index", 0)
                            async with factory() as session:
                                await session.execute(text("""
                                    UPDATE hcps SET
                                        influence_score = LEAST(:h * 5, 100)
                                    WHERE id = :id
                                """), {"h": h_index, "id": hcp_id})
                                await session.commit()
                    await asyncio.sleep(0.5)
                except Exception as e:
                    self.log.warning("ORCID sync failed for %s: %s", name, e)
