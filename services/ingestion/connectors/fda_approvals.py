"""FDA openFDA drug approvals connector.

Docs: https://open.fda.gov/apis/drug/
Free, no API key for basic use (240 req/min with key).
Endpoints used:
  - /drug/drugsfda (approval history)
  - /drug/label (prescribing info / indication changes)
"""
import asyncio
import httpx
from ingestion.connectors.base import BaseConnector
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text
import uuid
from datetime import datetime, timezone

BASE = "https://api.fda.gov/drug"

ONCOLOGY_INDICATIONS = [
    "cancer", "carcinoma", "lymphoma", "leukemia", "melanoma",
    "sarcoma", "myeloma", "glioma", "mesothelioma", "neoplasm",
    "tumor", "oncology", "antineoplastic",
]


class FDAApprovalsConnector(BaseConnector):
    def __init__(self):
        super().__init__()
        settings = get_settings()
        self._api_key = getattr(settings, "openfda_api_key", "")

    def _params(self, extra: dict) -> dict:
        p = {**extra, "limit": 100}
        if self._api_key:
            p["api_key"] = self._api_key
        return p

    async def fetch(self) -> list[dict]:
        """Fetch recent oncology drug approvals from FDA."""
        approvals = []
        async with httpx.AsyncClient(timeout=30) as client:
            # Search drugsfda for oncology application types
            for app_type in ["NDA", "BLA"]:
                batch = await self._fetch_approvals(client, app_type)
                approvals.extend(batch)
                await asyncio.sleep(1)
        self.log.info("FDA: fetched %d oncology drug records", len(approvals))
        return approvals

    async def _fetch_approvals(self, client: httpx.AsyncClient, app_type: str) -> list[dict]:
        try:
            # Use search=_exists_:products.te_code to find cancer drugs
            resp = await client.get(
                f"{BASE}/drugsfda.json",
                params=self._params({
                    "search": f'application_number:{app_type}* AND products.te_code:AA',
                    "sort": "submissions.submission_status_date:desc",
                }),
            )
            if resp.status_code == 200:
                return resp.json().get("results", [])
            # Fallback: search by oncology indication keywords
            for term in ONCOLOGY_INDICATIONS[:3]:
                resp2 = await client.get(
                    f"{BASE}/drugsfda.json",
                    params=self._params({
                        "search": f'application_number:{app_type}*',
                        "limit": 50,
                    }),
                )
                if resp2.status_code == 200:
                    return resp2.json().get("results", [])
        except Exception as e:
            self.log.warning("FDA approvals fetch failed for %s: %s", app_type, e)
        return []

    async def fetch_label_changes(self) -> list[dict]:
        """Detect recent oncology label updates (new indications, warnings)."""
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(
                    f"{BASE}/label.json",
                    params=self._params({
                        "search": 'indications_and_usage:cancer OR indications_and_usage:tumor',
                        "sort": "effective_time:desc",
                    }),
                )
                if resp.status_code == 200:
                    return resp.json().get("results", [])
            except Exception as e:
                self.log.warning("FDA label fetch failed: %s", e)
        return []

    def _is_oncology(self, record: dict) -> bool:
        text_blob = " ".join([
            str(record.get("products", "")),
            str(record.get("openfda", {}).get("pharm_class_epc", "")),
        ]).lower()
        return any(term in text_blob for term in ONCOLOGY_INDICATIONS)

    async def store(self, records: list[dict]) -> None:
        factory = get_session_factory()
        async with factory() as session:
            for rec in records:
                if not self._is_oncology(rec):
                    continue

                app_num = rec.get("application_number", "")
                products = rec.get("products", [])
                drug_name = products[0].get("brand_name", "") if products else app_num
                sponsor = rec.get("sponsor_name", "Unknown")

                # Upsert competitor record
                await session.execute(text("""
                    INSERT INTO competitors (name)
                    VALUES (:name)
                    ON CONFLICT DO NOTHING
                """), {"name": sponsor})

                # Fire competitor_drug_approved trigger (global event, no specific HCP)
                submissions = rec.get("submissions", [])
                approvals = [
                    s for s in submissions
                    if s.get("submission_status") == "AP"
                ]
                for approval in approvals[:1]:
                    await session.execute(text("""
                        INSERT INTO trigger_events (
                            id, event_type, event_data, source, occurred_at
                        )
                        VALUES (:id, 'competitor_drug_approved', :data, 'fda', :now)
                        ON CONFLICT DO NOTHING
                    """), {
                        "id": str(uuid.uuid4()),
                        "data": str({
                            "drug": drug_name,
                            "sponsor": sponsor,
                            "application": app_num,
                            "approval_date": approval.get("submission_status_date"),
                        }),
                        "now": datetime.now(timezone.utc),
                    })

            await session.commit()
        self.log.info("FDA: processed %d records", len(records))
