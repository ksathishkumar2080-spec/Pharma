"""ClinicalTrials.gov connector via public REST API v2."""
import httpx
from ingestion.connectors.base import BaseConnector

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


class ClinicalTrialsConnector(BaseConnector):
    async def fetch(self) -> list[dict]:
        params = {
            "query.cond": "cancer OR oncology OR neoplasm",
            "filter.overallStatus": "RECRUITING,ACTIVE_NOT_RECRUITING",
            "pageSize": 200,
            "format": "json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        return data.get("studies", [])

    async def store(self, records: list[dict]) -> None:
        from shared.db import get_session_factory
        from sqlalchemy import text

        factory = get_session_factory()
        async with factory() as session:
            for study in records:
                proto = study.get("protocolSection", {})
                id_module = proto.get("identificationModule", {})
                status_module = proto.get("statusModule", {})
                design_module = proto.get("designModule", {})
                nct_id = id_module.get("nctId", "")
                if not nct_id:
                    continue
                await session.execute(
                    text("""
                        INSERT INTO clinical_trials (nct_id, title, phase, status, raw_json)
                        VALUES (:nct_id, :title, :phase, :status, :raw_json)
                        ON CONFLICT (nct_id) DO UPDATE
                        SET status = EXCLUDED.status
                    """),
                    {
                        "nct_id": nct_id,
                        "title": id_module.get("briefTitle", ""),
                        "phase": str(design_module.get("phases", [])),
                        "status": status_module.get("overallStatus", ""),
                        "raw_json": str(study),
                    },
                )
            await session.commit()
