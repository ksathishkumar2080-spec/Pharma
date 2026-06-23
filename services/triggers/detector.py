"""Trigger detection engine — all 8 trigger types, aligned with trigger_events schema."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)
UTC = timezone.utc

PUB_WINDOW_DAYS = 7
TRIAL_WINDOW_DAYS = 3
CONF_WINDOW_DAYS = 14
INST_WINDOW_DAYS = 7
GRANT_WINDOW_DAYS = 14
ADVISORY_WINDOW_DAYS = 30
COMPETITOR_WINDOW_DAYS = 14
GUIDELINE_WINDOW_DAYS = 30
MAX_HCP_PER_TRIGGER = 200


async def _insert_trigger(
    session: AsyncSession,
    hcp_id: str,
    event_type: str,
    event_data: dict,
    source: str,
) -> None:
    dedup_key = hashlib.sha256(
        f"{hcp_id}:{event_type}:{json.dumps(event_data, sort_keys=True)[:120]}".encode()
    ).hexdigest()[:32]
    await session.execute(
        text("""
            INSERT INTO trigger_events
                (hcp_id, event_type, event_data, source, occurred_at, processed)
            VALUES
                (:hcp_id, :event_type, :event_data::jsonb, :source, NOW(), FALSE)
            ON CONFLICT DO NOTHING
        """),
        {
            "hcp_id": hcp_id,
            "event_type": event_type,
            "event_data": json.dumps({**event_data, "_dedup": dedup_key}),
            "source": source,
        },
    )


class TriggerDetector:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def detect_new_publications(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=PUB_WINDOW_DAYS)
        rows = await self.session.execute(
            text("""
                SELECT pa.hcp_id, p.id AS pub_id, p.title, p.doi,
                       p.published_at, p.abstract
                FROM publication_authors pa
                JOIN publications p ON p.id = pa.publication_id
                WHERE p.published_at >= :cutoff AND pa.hcp_id IS NOT NULL
            """),
            {"cutoff": cutoff},
        )
        count = 0
        for r in rows.mappings():
            await _insert_trigger(
                self.session, str(r["hcp_id"]), "new_publication",
                {"publication_id": str(r["pub_id"]), "title": (r["title"] or "")[:200],
                 "doi": r["doi"], "abstract": (r["abstract"] or "")[:400],
                 "source_url": f"https://doi.org/{r['doi']}" if r["doi"] else "",
                 "relevance_score": 0.75},
                "pubmed",
            )
            count += 1
        await self.session.commit()
        return count

    async def detect_trial_enrollments(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=TRIAL_WINDOW_DAYS)
        rows = await self.session.execute(
            text("""
                SELECT ti.hcp_id, ct.id AS trial_id, ct.nct_id, ct.title, ct.start_date
                FROM trial_investigators ti
                JOIN clinical_trials ct ON ct.id = ti.trial_id
                WHERE ct.status = 'RECRUITING' AND ct.start_date >= :cutoff
                  AND ti.hcp_id IS NOT NULL
            """),
            {"cutoff": cutoff},
        )
        count = 0
        for r in rows.mappings():
            await _insert_trigger(
                self.session, str(r["hcp_id"]), "trial_enrollment_opened",
                {"trial_id": str(r["trial_id"]), "nct_id": r["nct_id"],
                 "title": (r["title"] or "")[:200],
                 "source_url": f"https://clinicaltrials.gov/study/{r['nct_id']}",
                 "relevance_score": 0.85},
                "clinicaltrials_gov",
            )
            count += 1
        await self.session.commit()
        return count

    async def detect_conference_presentations(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=CONF_WINDOW_DAYS)
        rows = await self.session.execute(
            text("""
                SELECT cp.hcp_id, cp.id AS pres_id, cp.conference_name,
                       cp.title, cp.presentation_date, cp.abstract_url
                FROM conference_presentations cp
                WHERE cp.presentation_date >= :cutoff AND cp.hcp_id IS NOT NULL
            """),
            {"cutoff": cutoff},
        )
        count = 0
        for r in rows.mappings():
            await _insert_trigger(
                self.session, str(r["hcp_id"]), "conference_presentation",
                {"presentation_id": str(r["pres_id"]), "conference": r["conference_name"],
                 "title": (r["title"] or "")[:200],
                 "presentation_date": str(r["presentation_date"]),
                 "source_url": r["abstract_url"] or "", "relevance_score": 0.80},
                "conference_scraper",
            )
            count += 1
        await self.session.commit()
        return count

    async def detect_institution_changes(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=INST_WINDOW_DAYS)
        rows = await self.session.execute(
            text("""
                SELECT h.id AS hcp_id, h.full_name, i.name AS new_institution
                FROM hcps h JOIN institutions i ON i.id = h.institution_id
                WHERE h.institution_updated_at >= :cutoff
            """),
            {"cutoff": cutoff},
        )
        count = 0
        for r in rows.mappings():
            await _insert_trigger(
                self.session, str(r["hcp_id"]), "institution_change",
                {"new_institution": r["new_institution"],
                 "hcp_name": r["full_name"], "relevance_score": 0.70},
                "identity_resolver",
            )
            count += 1
        await self.session.commit()
        return count

    async def detect_grants_awarded(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=GRANT_WINDOW_DAYS)
        rows = await self.session.execute(
            text("""
                SELECT g.hcp_id, g.id AS grant_id, g.agency,
                       g.title, g.amount, g.award_date
                FROM grants g
                WHERE g.award_date >= :cutoff AND g.hcp_id IS NOT NULL
            """),
            {"cutoff": cutoff},
        )
        count = 0
        for r in rows.mappings():
            await _insert_trigger(
                self.session, str(r["hcp_id"]), "grant_awarded",
                {"grant_id": str(r["grant_id"]), "agency": r["agency"],
                 "title": (r["title"] or "")[:200],
                 "amount": float(r["amount"]) if r["amount"] else 0.0,
                 "award_date": str(r["award_date"]), "relevance_score": 0.75},
                "grant_tracker",
            )
            count += 1
        await self.session.commit()
        return count

    async def detect_advisory_appointments(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=ADVISORY_WINDOW_DAYS)
        rows = await self.session.execute(
            text("""
                SELECT ab.hcp_id, ab.id AS ab_id, ab.company, ab.role, ab.start_date
                FROM advisory_boards ab
                WHERE ab.start_date >= :cutoff AND ab.hcp_id IS NOT NULL
            """),
            {"cutoff": cutoff},
        )
        count = 0
        for r in rows.mappings():
            await _insert_trigger(
                self.session, str(r["hcp_id"]), "advisory_board_appointment",
                {"advisory_board_id": str(r["ab_id"]), "company": r["company"],
                 "role": r["role"], "start_date": str(r["start_date"]),
                 "relevance_score": 0.80},
                "advisory_tracker",
            )
            count += 1
        await self.session.commit()
        return count

    async def detect_competitor_approvals(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=COMPETITOR_WINDOW_DAYS)
        approval_rows = list((await self.session.execute(
            text("""
                SELECT te.event_data->>'drug_name' AS drug_name,
                       te.event_data->>'competitor_id' AS competitor_id,
                       te.event_data->>'title' AS approval_title
                FROM trigger_events te
                WHERE te.event_type = 'competitor_approval'
                  AND te.occurred_at >= :cutoff
                  AND (te.event_data->>'drug_name') IS NOT NULL
            """),
            {"cutoff": cutoff},
        )).mappings())
        count = 0
        for approval in approval_rows:
            drug = approval["drug_name"]
            hcps = list((await self.session.execute(
                text("""
                    SELECT DISTINCT pa.hcp_id FROM publication_authors pa
                    JOIN publications p ON p.id = pa.publication_id
                    WHERE pa.hcp_id IS NOT NULL
                      AND (p.title ILIKE :drug OR p.abstract ILIKE :drug)
                    LIMIT :lim
                """),
                {"drug": f"%{drug}%", "lim": MAX_HCP_PER_TRIGGER},
            )).mappings())
            for hr in hcps:
                await _insert_trigger(
                    self.session, str(hr["hcp_id"]), "competitor_drug_approved",
                    {"drug_name": drug, "competitor_id": approval["competitor_id"],
                     "approval_title": (approval["approval_title"] or "")[:200],
                     "relevance_score": 0.90},
                    "fda_tracker",
                )
                count += 1
        await self.session.commit()
        return count

    async def detect_guideline_updates(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=GUIDELINE_WINDOW_DAYS)
        guideline_rows = list((await self.session.execute(
            text("""
                SELECT te.event_data->>'guideline_category' AS category,
                       te.event_data->>'title' AS guideline_title,
                       te.event_data->>'source_url' AS source_url
                FROM trigger_events te
                WHERE te.event_type = 'guideline_change' AND te.occurred_at >= :cutoff
            """),
            {"cutoff": cutoff},
        )).mappings())
        count = 0
        for gl in guideline_rows:
            category = gl["category"] or ""
            hcps = list((await self.session.execute(
                text("""
                    SELECT id FROM hcps
                    WHERE specialty ILIKE :cat OR subspecialty ILIKE :cat
                    LIMIT :lim
                """),
                {"cat": f"%{category}%", "lim": MAX_HCP_PER_TRIGGER},
            )).mappings())
            for hr in hcps:
                await _insert_trigger(
                    self.session, str(hr["id"]), "guideline_update",
                    {"category": category,
                     "guideline_title": (gl["guideline_title"] or "")[:200],
                     "source_url": gl["source_url"] or "https://www.nccn.org/guidelines/",
                     "relevance_score": 0.85},
                    "nccn_watcher",
                )
                count += 1
        await self.session.commit()
        return count

    async def run_all(self) -> dict[str, int]:
        results: dict[str, int] = {}
        for name, fn in [
            ("new_publication", self.detect_new_publications),
            ("trial_enrollment_opened", self.detect_trial_enrollments),
            ("conference_presentation", self.detect_conference_presentations),
            ("institution_change", self.detect_institution_changes),
            ("grant_awarded", self.detect_grants_awarded),
            ("advisory_board_appointment", self.detect_advisory_appointments),
            ("competitor_drug_approved", self.detect_competitor_approvals),
            ("guideline_update", self.detect_guideline_updates),
        ]:
            try:
                results[name] = await fn()
                log.info("Trigger %s: %d events", name, results[name])
            except Exception as exc:
                log.error("Trigger %s failed: %s", name, exc, exc_info=True)
                results[name] = -1
        return results
