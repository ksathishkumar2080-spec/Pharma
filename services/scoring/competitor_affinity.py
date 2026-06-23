"""Competitor affinity scoring — measures HCP's relationship with competitor drugs/companies."""
from shared.db import get_session_factory
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)


class CompetitorAffinityScorer:
    """
    Scans HCP publications and trial participations for competitor drug mentions.
    Produces a competitor_affinity score (0-100) where higher = more competitor-aligned.
    """

    async def score_all(self, competitor_terms: list[str]) -> list[dict]:
        if not competitor_terms:
            return []

        factory = get_session_factory()
        results = []
        async with factory() as session:
            hcps = (await session.execute(text("SELECT id, full_name FROM hcps"))).fetchall()

            for hcp_id, name in hcps:
                score = await self._compute(session, hcp_id, competitor_terms)
                results.append({"hcp_id": str(hcp_id), "name": name, "competitor_affinity_score": score})

        return sorted(results, key=lambda x: x["competitor_affinity_score"], reverse=True)

    async def _compute(self, session, hcp_id, competitor_terms: list[str]) -> float:
        mention_count = 0
        for term in competitor_terms:
            count = (await session.execute(text("""
                SELECT COUNT(*) FROM publications p
                JOIN publication_authors pa ON pa.publication_id = p.id
                WHERE pa.hcp_id = :id
                AND (p.title ILIKE :term OR p.abstract ILIKE :term)
            """), {"id": hcp_id, "term": f"%{term}%"})).scalar() or 0
            mention_count += count

            trial_count = (await session.execute(text("""
                SELECT COUNT(*) FROM clinical_trials ct
                JOIN trial_investigators ti ON ti.trial_id = ct.id
                WHERE ti.hcp_id = :id
                AND (ct.title ILIKE :term OR ct.sponsor ILIKE :term)
            """), {"id": hcp_id, "term": f"%{term}%"})).scalar() or 0
            mention_count += trial_count * 2  # trials weighted heavier

        return min(mention_count * 10, 100)
