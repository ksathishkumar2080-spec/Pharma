"""WHO ICTRP (International Clinical Trials Registry Platform) connector.

Docs: https://www.who.int/clinical-trials-registry-platform
Public API: https://trialsearch.who.int/API/
Free, no API key required.
Covers trials not on ClinicalTrials.gov: EU CTR, ISRCTN, ANZCTR, IRCT, etc.
"""
import asyncio
import httpx
from ingestion.connectors.base import BaseConnector
from shared.db import get_session_factory
from sqlalchemy import text

WHO_API = "https://trialsearch.who.int/API"

ONCOLOGY_CONDITIONS = [
    "cancer",
    "carcinoma",
    "lymphoma",
    "leukemia",
    "solid tumor",
    "oncology",
]


class WHOICTRPConnector(BaseConnector):
    async def fetch(self) -> list[dict]:
        trials = []
        async with httpx.AsyncClient(timeout=30) as client:
            for condition in ONCOLOGY_CONDITIONS:
                batch = await self._search(client, condition)
                trials.extend(batch)
                await asyncio.sleep(2)

        # Deduplicate by TrialID
        seen = set()
        unique = []
        for t in trials:
            tid = t.get("TrialID", "")
            if tid and tid not in seen:
                seen.add(tid)
                unique.append(t)

        self.log.info("WHO ICTRP: fetched %d trials", len(unique))
        return unique

    async def _search(self, client: httpx.AsyncClient, condition: str) -> list[dict]:
        try:
            resp = await client.get(
                f"{WHO_API}/search",
                params={
                    "query": condition,
                    "status": "recruiting",
                    "format": "json",
                    "count": 100,
                },
                headers={"Accept": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else data.get("trials", data.get("results", []))
        except Exception as e:
            self.log.warning("WHO ICTRP search failed for '%s': %s", condition, e)
        return []

    async def store(self, records: list[dict]) -> None:
        factory = get_session_factory()
        async with factory() as session:
            stored = 0
            for trial in records:
                trial_id = trial.get("TrialID", "")
                nct_id = trial.get("SecondaryIDs", "") if "NCT" in str(trial.get("SecondaryIDs", "")) else None

                # Skip if already in DB as NCT trial
                if nct_id:
                    existing = (await session.execute(
                        text("SELECT 1 FROM clinical_trials WHERE nct_id = :nct"),
                        {"nct": nct_id},
                    )).fetchone()
                    if existing:
                        continue

                await session.execute(text("""
                    INSERT INTO clinical_trials (
                        nct_id, title, phase, status, sponsor, conditions, raw_json
                    )
                    VALUES (:nct_id, :title, :phase, :status, :sponsor, :conditions, :raw)
                    ON CONFLICT (nct_id) DO NOTHING
                """), {
                    "nct_id": trial_id,  # Use WHO trial ID as identifier
                    "title": trial.get("Scientific_title") or trial.get("Public_title", ""),
                    "phase": trial.get("Phase"),
                    "status": trial.get("Recruitment_Status", "RECRUITING"),
                    "sponsor": trial.get("Primary_Sponsor"),
                    "conditions": [trial.get("Condition", "")],
                    "raw": str(trial)[:3000],
                })
                stored += 1

            await session.commit()
        self.log.info("WHO ICTRP: stored %d new trials", stored)
