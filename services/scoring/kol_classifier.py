"""KOL (Key Opinion Leader) tier classification using publication + network signals."""
from shared.db import get_session_factory
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)

# Thresholds for KOL tier assignment
TIERS = {
    "national": {"publications": 50, "citations": 1000, "trials": 10, "score": 80},
    "regional": {"publications": 20, "citations": 200, "trials": 3, "score": 50},
    "local":    {"publications": 5,  "citations": 20,  "trials": 1, "score": 20},
}


class KOLClassifier:
    async def classify_all(self):
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT
                    h.id,
                    COUNT(DISTINCT pa.publication_id) AS pub_count,
                    COALESCE(SUM(p.citation_count), 0) AS total_citations,
                    COUNT(DISTINCT ti.trial_id) AS trial_count,
                    h.commercial_score
                FROM hcps h
                LEFT JOIN publication_authors pa ON pa.hcp_id = h.id
                LEFT JOIN publications p ON p.id = pa.publication_id
                LEFT JOIN trial_investigators ti ON ti.hcp_id = h.id
                GROUP BY h.id, h.commercial_score
            """))).fetchall()

        log.info("Classifying KOL tiers for %d HCPs", len(rows))
        async with factory() as session:
            for row in rows:
                hcp_id, pubs, citations, trials, score = row
                tier = self._assign_tier(pubs, citations, trials, score or 0)
                await session.execute(
                    text("UPDATE hcps SET kol_tier = :tier WHERE id = :id"),
                    {"tier": tier, "id": hcp_id},
                )
            await session.commit()

    def _assign_tier(self, pubs: int, citations: int, trials: int, score: float) -> str:
        for tier_name, thresholds in TIERS.items():
            if (
                pubs >= thresholds["publications"]
                or citations >= thresholds["citations"]
                or trials >= thresholds["trials"]
                or score >= thresholds["score"]
            ):
                return tier_name
        return "emerging"
