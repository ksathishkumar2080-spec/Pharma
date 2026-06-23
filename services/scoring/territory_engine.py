"""Territory Opportunity Engine — scores geographic territories and ranks accounts."""
from shared.db import get_session_factory
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)


class TerritoryOpportunityEngine:
    """
    Scores each state/region by:
    - HCP density and quality (commercial scores)
    - Trial activity volume
    - Competitor presence
    - Referral network strength
    - Recent trigger event frequency
    """

    async def score_territories(self) -> list[dict]:
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT
                    h.state,
                    COUNT(DISTINCT h.id) AS hcp_count,
                    AVG(h.commercial_score) AS avg_commercial,
                    SUM(h.commercial_score) AS total_commercial,
                    COUNT(DISTINCT ti.trial_id) AS active_trials,
                    COUNT(DISTINCT te.id) AS recent_triggers,
                    COUNT(DISTINCT h.id) FILTER (WHERE h.kol_tier IN ('national','regional')) AS kol_count
                FROM hcps h
                LEFT JOIN trial_investigators ti ON ti.hcp_id = h.id
                LEFT JOIN trigger_events te ON te.hcp_id = h.id
                    AND te.occurred_at >= NOW() - INTERVAL '90 days'
                WHERE h.state IS NOT NULL AND h.is_active = TRUE
                GROUP BY h.state
                ORDER BY total_commercial DESC
            """))).fetchall()

        territories = []
        for row in rows:
            state, hcp_count, avg_comm, total_comm, trials, triggers, kols = row
            opportunity_score = (
                min(total_comm / 1000, 40) +       # up to 40 pts from HCP quality
                min(hcp_count / 50, 20) +          # up to 20 pts from density
                min(trials / 10, 20) +             # up to 20 pts from trial activity
                min(triggers / 20, 10) +           # up to 10 pts from momentum
                min(kols / 5, 10)                  # up to 10 pts from KOL presence
            )
            territories.append({
                "state": state,
                "hcp_count": hcp_count,
                "avg_commercial_score": round(avg_comm or 0, 2),
                "total_commercial_score": round(total_comm or 0, 2),
                "active_trials": trials,
                "recent_triggers": triggers,
                "kol_count": kols,
                "territory_opportunity_score": round(opportunity_score, 2),
            })
        return territories

    async def top_accounts_in_territory(self, state: str, limit: int = 20) -> list[dict]:
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT h.id, h.full_name, h.specialty, i.name as institution,
                       h.commercial_score, h.opportunity_score, h.kol_tier,
                       COUNT(te.id) as recent_triggers
                FROM hcps h
                LEFT JOIN institutions i ON i.id = h.institution_id
                LEFT JOIN trigger_events te ON te.hcp_id = h.id
                    AND te.occurred_at >= NOW() - INTERVAL '90 days'
                WHERE h.state = :state AND h.is_active = TRUE
                GROUP BY h.id, h.full_name, h.specialty, i.name,
                         h.commercial_score, h.opportunity_score, h.kol_tier
                ORDER BY h.commercial_score DESC
                LIMIT :limit
            """), {"state": state, "limit": limit})).fetchall()

        return [
            {
                "id": str(r[0]), "name": r[1], "specialty": r[2], "institution": r[3],
                "commercial_score": r[4], "opportunity_score": r[5],
                "kol_tier": r[6], "recent_triggers": r[7],
            }
            for r in rows
        ]
