"""Computes commercial, opportunity, and influence scores for every HCP."""
from shared.db import get_session_factory
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)


class ScoringEngine:
    async def score_all(self):
        """Single-pass batch score update — no N+1 queries."""
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(text("""
                WITH pub_counts AS (
                    SELECT hcp_id, COUNT(*) AS total
                    FROM publication_authors
                    GROUP BY hcp_id
                ),
                recent_pub_counts AS (
                    SELECT pa.hcp_id, COUNT(*) AS recent
                    FROM publication_authors pa
                    JOIN publications p ON pa.publication_id = p.id
                    WHERE p.published_at >= NOW() - INTERVAL '2 years'
                    GROUP BY pa.hcp_id
                ),
                trial_counts AS (
                    SELECT hcp_id, COUNT(*) AS total
                    FROM trial_investigators
                    GROUP BY hcp_id
                ),
                trigger_counts AS (
                    SELECT hcp_id, COUNT(*) AS recent
                    FROM trigger_events
                    WHERE occurred_at >= NOW() - INTERVAL '6 months'
                    GROUP BY hcp_id
                ),
                scores AS (
                    SELECT
                        h.id,
                        COALESCE(pc.total, 0)  AS pub_count,
                        COALESCE(rp.recent, 0) AS recent_pub_count,
                        COALESCE(tc.total, 0)  AS trial_count,
                        COALESCE(tg.recent, 0) AS trigger_count
                    FROM hcps h
                    LEFT JOIN pub_counts pc ON h.id = pc.hcp_id
                    LEFT JOIN recent_pub_counts rp ON h.id = rp.hcp_id
                    LEFT JOIN trial_counts tc ON h.id = tc.hcp_id
                    LEFT JOIN trigger_counts tg ON h.id = tg.hcp_id
                )
                UPDATE hcps h
                SET
                    commercial_score  = ROUND(CAST((
                        LEAST(s.pub_count        / 50.0, 1.0) * 0.20 +
                        LEAST(s.recent_pub_count / 10.0, 1.0) * 0.15 +
                        LEAST(s.trial_count      /  5.0, 1.0) * 0.20 +
                        LEAST(s.trigger_count    /  3.0, 1.0) * 0.10
                    ) * 100 AS numeric), 2),
                    opportunity_score = ROUND(CAST((
                        LEAST(s.pub_count        / 50.0, 1.0) * 0.20 +
                        LEAST(s.recent_pub_count / 10.0, 1.0) * 0.15 +
                        LEAST(s.trial_count      /  5.0, 1.0) * 0.20 +
                        LEAST(s.trigger_count    /  3.0, 1.0) * 0.10
                    ) * 90 AS numeric), 2),
                    influence_score   = ROUND(CAST(LEAST(s.pub_count / 20.0, 1.0) * 100 AS numeric), 2),
                    updated_at        = NOW()
                FROM scores s
                WHERE h.id = s.id
            """))
            await session.commit()
            log.info("ScoringEngine: batch score update complete (rowcount=%s)", result.rowcount)
