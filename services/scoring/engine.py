"""Computes commercial, opportunity, and influence scores for every HCP."""
from shared.db import get_session_factory
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)

# Score weights
WEIGHTS = {
    "publication_count": 0.20,
    "recent_publication_count": 0.15,
    "trial_participation": 0.20,
    "conference_presentations": 0.10,
    "citation_count": 0.10,
    "institution_rank": 0.10,
    "digital_presence": 0.05,
    "trigger_events": 0.10,
}


class ScoringEngine:
    async def score_all(self):
        factory = get_session_factory()
        async with factory() as session:
            hcps = (await session.execute(text("SELECT id FROM hcps"))).fetchall()

        log.info("Scoring %d HCPs", len(hcps))
        for (hcp_id,) in hcps:
            scores = await self._compute(hcp_id)
            await self._save(hcp_id, scores)

    async def _compute(self, hcp_id) -> dict:
        factory = get_session_factory()
        async with factory() as session:
            pub_count = (await session.execute(
                text("SELECT COUNT(*) FROM publication_authors WHERE hcp_id = :id"),
                {"id": hcp_id},
            )).scalar() or 0

            recent_pub_count = (await session.execute(
                text("""
                    SELECT COUNT(*) FROM publication_authors pa
                    JOIN publications p ON pa.publication_id = p.id
                    WHERE pa.hcp_id = :id AND p.published_at >= NOW() - INTERVAL '2 years'
                """),
                {"id": hcp_id},
            )).scalar() or 0

            trial_count = (await session.execute(
                text("SELECT COUNT(*) FROM trial_investigators WHERE hcp_id = :id"),
                {"id": hcp_id},
            )).scalar() or 0

            trigger_count = (await session.execute(
                text("SELECT COUNT(*) FROM trigger_events WHERE hcp_id = :id AND occurred_at >= NOW() - INTERVAL '6 months'"),
                {"id": hcp_id},
            )).scalar() or 0

        raw_score = (
            min(pub_count / 50, 1.0) * WEIGHTS["publication_count"]
            + min(recent_pub_count / 10, 1.0) * WEIGHTS["recent_publication_count"]
            + min(trial_count / 5, 1.0) * WEIGHTS["trial_participation"]
            + min(trigger_count / 3, 1.0) * WEIGHTS["trigger_events"]
        ) * 100

        return {
            "commercial_score": round(raw_score, 2),
            "opportunity_score": round(raw_score * 0.9, 2),
            "influence_score": round(min(pub_count / 20, 1.0) * 100, 2),
        }

    async def _save(self, hcp_id, scores: dict):
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                text("""
                    UPDATE hcps
                    SET commercial_score = :commercial_score,
                        opportunity_score = :opportunity_score,
                        influence_score = :influence_score,
                        updated_at = NOW()
                    WHERE id = :id
                """),
                {**scores, "id": hcp_id},
            )
            await session.commit()
