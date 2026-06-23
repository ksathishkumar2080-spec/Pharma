"""bioRxiv / medRxiv preprint connector.

Docs: https://api.biorxiv.org/
Free, no API key required.
Monitors oncology preprints for early-signal detection.
"""
import asyncio
import httpx
from datetime import datetime, timedelta
from ingestion.connectors.base import BaseConnector
from shared.db import get_session_factory
from sqlalchemy import text
import uuid

BASE = "https://api.biorxiv.org"

ONCOLOGY_KEYWORDS = [
    "oncology", "cancer", "tumor", "chemotherapy", "immunotherapy",
    "CAR-T", "checkpoint inhibitor", "biomarker", "liquid biopsy",
    "KRAS", "BRCA", "HER2", "PD-L1", "EGFR",
]


class BioRxivConnector(BaseConnector):
    """Fetches recent oncology preprints from bioRxiv and medRxiv."""

    async def fetch(self) -> list[dict]:
        # Fetch last 30 days of preprints from both servers
        start = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        end = datetime.utcnow().strftime("%Y-%m-%d")
        preprints = []

        async with httpx.AsyncClient(timeout=30) as client:
            for server in ["biorxiv", "medrxiv"]:
                batch = await self._fetch_server(client, server, start, end)
                # Filter to oncology-relevant preprints
                relevant = [
                    p for p in batch
                    if self._is_oncology_relevant(p)
                ]
                preprints.extend(relevant)
                await asyncio.sleep(1)

        self.log.info("bioRxiv/medRxiv: fetched %d oncology preprints", len(preprints))
        return preprints

    async def _fetch_server(self, client: httpx.AsyncClient, server: str, start: str, end: str) -> list[dict]:
        preprints = []
        cursor = 0
        while cursor < 500:  # max 5 pages of 100
            try:
                resp = await client.get(
                    f"{BASE}/details/{server}/{start}/{end}/{cursor}/json",
                )
                resp.raise_for_status()
                data = resp.json()
                collection = data.get("collection", [])
                if not collection:
                    break
                preprints.extend([{**p, "server": server} for p in collection])
                if len(collection) < 100:
                    break
                cursor += 100
                await asyncio.sleep(0.5)
            except Exception as e:
                self.log.warning("%s fetch failed at cursor %d: %s", server, cursor, e)
                break
        return preprints

    def _is_oncology_relevant(self, preprint: dict) -> bool:
        text = " ".join([
            preprint.get("title", ""),
            preprint.get("abstract", ""),
            preprint.get("category", ""),
        ]).lower()
        return any(kw.lower() in text for kw in ONCOLOGY_KEYWORDS)

    async def store(self, records: list[dict]) -> None:
        factory = get_session_factory()
        async with factory() as session:
            for p in records:
                doi = p.get("doi")
                await session.execute(text("""
                    INSERT INTO publications (
                        title, abstract, journal, published_at, doi, raw_json
                    )
                    VALUES (:title, :abstract, :journal, :pub_date, :doi, :raw)
                    ON CONFLICT DO NOTHING
                """), {
                    "title": p.get("title", ""),
                    "abstract": p.get("abstract"),
                    "journal": f"{p['server'].capitalize()} (preprint)",
                    "pub_date": p.get("date"),
                    "doi": doi,
                    "raw": str(p)[:3000],
                })

                # Fire trigger for preprints from known HCPs
                authors_str = p.get("authors", "")
                if authors_str:
                    author_names = [a.strip() for a in authors_str.split(";")]
                    for name in author_names[:5]:
                        hcp = (await session.execute(text("""
                            SELECT id FROM hcps WHERE full_name ILIKE :name LIMIT 1
                        """), {"name": f"%{name}%"})).fetchone()
                        if hcp:
                            await session.execute(text("""
                                INSERT INTO trigger_events (id, hcp_id, event_type, event_data, source, occurred_at)
                                VALUES (:id, :hcp_id, 'new_publication', :data, 'biorxiv', NOW())
                                ON CONFLICT DO NOTHING
                            """), {
                                "id": str(uuid.uuid4()),
                                "hcp_id": hcp[0],
                                "data": f'{{"title": "{p.get("title", "")[:200]}", "source": "preprint"}}',
                            })

            await session.commit()
        self.log.info("bioRxiv: stored %d preprints", len(records))
