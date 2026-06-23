"""Trigger detection engine — all 8 trigger types."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

UTC = timezone.utc


async def _insert_trigger(
    session: AsyncSession,
    hcp_id: str,
    trigger_type: str,
    title: str,
    summary: str,
    source_url: str,
    relevance_score: float,
    metadata: dict,
) -> None:
    dedup_key = hashlib.sha256(
        f"{hcp_id}:{trigger_type}:{title[:120]}".encode()
    ).hexdigest()[:32]
    await session.execute(
        text("""
            INSERT INTO trigger_events
                (hcp_id, trigger_type, title, summary, source_url,
                 relevance_score, detected_at, metadata, dedup_key)
            VALUES
                (:hcp_id, :trigger_type, :title, :summary, :source_url,
                 :relevance_score, NOW(), :metadata, :dedup_key)
            ON CONFLICT (dedup_key) DO NOTHING
        """),
        {
            "hcp_id": hcp_id,
            "trigger_type": trigger_type,
            "title": title,
            "summary": summary,
            "source_url": source_url,
            "relevance_score": relevance_score,
            "metadata": metadata,
            "dedup_key": dedup_key,
        },
    )


class TriggerDetector:
    """Detects all 8 trigger types and writes to trigger_events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # 1. New publication (7-day window)
    # ------------------------------------------------------------------
    async def detect_new_publications(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=7)
        rows = await self.session.execute(
            text("""
                SELECT pa.hcp_id, p.id AS pub_id, p.title, p.doi,
                       p.published_date, p.abstract
                FROM publication_authors pa
                JOIN publications p ON p.id = pa.publication_id
                WHERE p.published_date >= :cutoff
                  AND pa.hcp_id IS NOT NULL
            """),
            {"cutoff": cutoff},
        )
        count = 0
        for r in rows.mappings():
            await _insert_trigger(
                self.session,
                hcp_id=str(r["hcp_id"]),
                trigger_type="new_publication",
                title=f"New publication: {r['title'][:120]}",
                summary=(r["abstract"] or "")[:400],
                source_url=f"https://doi.org/{r['doi']}" if r["doi"] else "",
                relevance_score=0.75,
                metadata={"publication_id": str(r["pub_id"])},
            )
            count += 1
        await self.session.commit()
        return count

    # ------------------------------------------------------------------
    # 2. Trial enrollment opened
    # ------------------------------------------------------------------
    async def detect_trial_enrollments(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=3)
        rows = await self.session.execute(
            text("""
                SELECT ti.hcp_id, ct.id AS trial_id, ct.nct_id,
                       ct.title, ct.start_date
                FROM trial_investigators ti
                JOIN clinical_trials ct ON ct.id = ti.trial_id
                WHERE ct.status = 'RECRUITING'
                  AND ct.start_date >= :cutoff
                  AND ti.hcp_id IS NOT NULL
            """),
            {"cutoff": cutoff},
        )
        count = 0
        for r in rows.mappings():
            await _insert_trigger(
                self.session,
                hcp_id=str(r["hcp_id"]),
                trigger_type="trial_enrollment_opened",
                title=f"Trial recruiting: {r['title'][:100]}",
                summary=f"NCT: {r['nct_id']} opened enrollment.",
                source_url=f"https://clinicaltrials.gov/study/{r['nct_id']}",
                relevance_score=0.85,
                metadata={"trial_id": str(r["trial_id"]), "nct_id": r["nct_id"]},
            )
            count += 1
        await self.session.commit()
        return count

    # ------------------------------------------------------------------
    # 3. Conference presentation
    # ------------------------------------------------------------------
    async def detect_conference_presentations(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=14)
        rows = await self.session.execute(
            text("""
                SELECT cp.hcp_id, cp.id AS pres_id, cp.conference_name,
                       cp.title, cp.presentation_date, cp.abstract_url
                FROM conference_presentations cp
                WHERE cp.presentation_date >= :cutoff
                  AND cp.hcp_id IS NOT NULL
            """),
            {"cutoff": cutoff},
        )
        count = 0
        for r in rows.mappings():
            await _insert_trigger(
                self.session,
                hcp_id=str(r["hcp_id"]),
                trigger_type="conference_presentation",
                title=f"{r['conference_name']}: {r['title'][:100]}",
                summary=f"Presented at {r['conference_name']} on {r['presentation_date']}.",
                source_url=r["abstract_url"] or "",
                relevance_score=0.80,
                metadata={"presentation_id": str(r["pres_id"]), "conference": r["conference_name"]},
            )
            count += 1
        await self.session.commit()
        return count

    # ------------------------------------------------------------------
    # 4. Institution change
    # ------------------------------------------------------------------
    async def detect_institution_changes(self) -> int:
        """Detects when hcps.institution_id was updated in the last 7 days."""
        cutoff = datetime.now(UTC) - timedelta(days=7)
        rows = await self.session.execute(
            text("""
                SELECT h.id AS hcp_id, h.name, i.name AS new_institution
                FROM hcps h
                JOIN institutions i ON i.id = h.institution_id
                WHERE h.institution_updated_at >= :cutoff
            """),
            {"cutoff": cutoff},
        )
        count = 0
        for r in rows.mappings():
            await _insert_trigger(
                self.session,
                hcp_id=str(r["hcp_id"]),
                trigger_type="institution_change",
                title=f"{r['name']} moved to {r['new_institution']}",
                summary=f"HCP institution updated to {r['new_institution']}.",
                source_url="",
                relevance_score=0.70,
                metadata={"new_institution": r["new_institution"]},
            )
            count += 1
        await self.session.commit()
        return count

    # ------------------------------------------------------------------
    # 5. Grant awarded
    # ------------------------------------------------------------------
    async def detect_grants_awarded(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=14)
        rows = await self.session.execute(
            text("""
                SELECT g.hcp_id, g.id AS grant_id, g.agency, g.title,
                       g.amount, g.award_date
                FROM grants g
                WHERE g.award_date >= :cutoff
                  AND g.hcp_id IS NOT NULL
            """),
            {"cutoff": cutoff},
        )
        count = 0
        for r in rows.mappings():
            amount_str = f"${r['amount']:,.0f}" if r["amount"] else "undisclosed"
            await _insert_trigger(
                self.session,
                hcp_id=str(r["hcp_id"]),
                trigger_type="grant_awarded",
                title=f"Grant from {r['agency']}: {r['title'][:80]}",
                summary=f"Awarded {amount_str} by {r['agency']}.",
                source_url="",
                relevance_score=0.75,
                metadata={"grant_id": str(r["grant_id"]), "agency": r["agency"], "amount": str(r["amount"])},
            )
            count += 1
        await self.session.commit()
        return count

    # ------------------------------------------------------------------
    # 6. Advisory board appointment
    # ------------------------------------------------------------------
    async def detect_advisory_appointments(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=30)
        rows = await self.session.execute(
            text("""
                SELECT ab.hcp_id, ab.id AS ab_id, ab.company, ab.role,
                       ab.start_date
                FROM advisory_boards ab
                WHERE ab.start_date >= :cutoff
                  AND ab.hcp_id IS NOT NULL
            """),
            {"cutoff": cutoff},
        )
        count = 0
        for r in rows.mappings():
            await _insert_trigger(
                self.session,
                hcp_id=str(r["hcp_id"]),
                trigger_type="advisory_board_appointment",
                title=f"Advisory board: {r['role']} at {r['company']}",
                summary=f"Appointed as {r['role']} on {r['company']} advisory board from {r['start_date']}.",
                source_url="",
                relevance_score=0.80,
                metadata={"advisory_board_id": str(r["ab_id"]), "company": r["company"]},
            )
            count += 1
        await self.session.commit()
        return count

    # ------------------------------------------------------------------
    # 7. Competitor drug approved — link to HCPs publishing on that drug
    # ------------------------------------------------------------------
    async def detect_competitor_approvals(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=14)
        rows = await self.session.execute(
            text("""
                SELECT te.id AS trigger_id, te.title AS approval_title,
                       te.metadata->>'drug_name' AS drug_name,
                       te.metadata->>'competitor_id' AS competitor_id,
                       te.detected_at
                FROM trigger_events te
                WHERE te.trigger_type = 'competitor_approval'
                  AND te.detected_at >= :cutoff
                  AND (te.metadata->>'drug_name') IS NOT NULL
            """),
            {"cutoff": cutoff},
        )
        approval_rows = list(rows.mappings())
        count = 0
        for approval in approval_rows:
            drug = approval["drug_name"]
            hcps = await self.session.execute(
                text("""
                    SELECT DISTINCT pa.hcp_id
                    FROM publication_authors pa
                    JOIN publications p ON p.id = pa.publication_id
                    WHERE pa.hcp_id IS NOT NULL
                      AND (p.title ILIKE :drug OR p.abstract ILIKE :drug)
                    LIMIT 100
                """),
                {"drug": f"%{drug}%"},
            )
            for hr in hcps.mappings():
                await _insert_trigger(
                    self.session,
                    hcp_id=str(hr["hcp_id"]),
                    trigger_type="competitor_drug_approved",
                    title=f"FDA approved {drug} — relevant to this KOL",
                    summary=f"{approval['approval_title']}. HCP publishes on {drug}.",
                    source_url="https://www.fda.gov/drugs/drug-approvals-and-databases",
                    relevance_score=0.90,
                    metadata={"drug_name": drug, "competitor_id": approval["competitor_id"]},
                )
                count += 1
        await self.session.commit()
        return count

    # ------------------------------------------------------------------
    # 8. Guideline update — link NCCN changes to HCPs by specialty
    # ------------------------------------------------------------------
    async def detect_guideline_updates(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=30)
        rows = await self.session.execute(
            text("""
                SELECT te.id AS trigger_id, te.title AS guideline_title,
                       te.metadata->>'guideline_category' AS category,
                       te.metadata->>'source_url' AS source_url,
                       te.detected_at
                FROM trigger_events te
                WHERE te.trigger_type = 'guideline_change'
                  AND te.detected_at >= :cutoff
            """),
            {"cutoff": cutoff},
        )
        guideline_rows = list(rows.mappings())
        count = 0
        for gl in guideline_rows:
            category = gl["category"] or ""
            hcps = await self.session.execute(
                text("""
                    SELECT id FROM hcps
                    WHERE specialty ILIKE :cat
                       OR disease_areas::text ILIKE :cat
                    LIMIT 200
                """),
                {"cat": f"%{category}%"},
            )
            for hr in hcps.mappings():
                await _insert_trigger(
                    self.session,
                    hcp_id=str(hr["id"]),
                    trigger_type="guideline_update",
                    title=f"NCCN guideline update: {gl['guideline_title'][:100]}",
                    summary=f"NCCN updated {category} guidelines. Relevant to HCP specialty.",
                    source_url=gl["source_url"] or "https://www.nccn.org/guidelines/",
                    relevance_score=0.85,
                    metadata={"category": category},
                )
                count += 1
        await self.session.commit()
        return count

    # ------------------------------------------------------------------
    # Run all detectors
    # ------------------------------------------------------------------
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
            except Exception as exc:  # noqa: BLE001
                log.error("Trigger %s failed: %s", name, exc)
                results[name] = -1
        return results
