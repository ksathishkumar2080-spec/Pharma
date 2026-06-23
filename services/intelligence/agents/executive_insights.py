"""Executive Insights Agent — L18 Executive Command Center.

Synthesises the full pipeline into C-suite briefings:
- Weekly territory KPI snapshot
- Top opportunity HCPs with scoring rationale
- Competitive threat summary
- Pipeline / trial advancement highlights
- Recommended commercial priorities
"""
from anthropic import AsyncAnthropic
import json
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)

EXECUTIVE_BRIEFING_PROMPT = """
You are the Chief Commercial Intelligence Officer for an oncology biotech.

Current KPI Snapshot:
{kpis}

Top Opportunity HCPs (scored):
{top_hcps}

Recent Competitive Events:
{competitive_events}

Recent Trial Activations:
{trial_activations}

Pending Message Pipeline:
{message_pipeline}

Produce a concise JSON executive briefing with keys:
  headline: one sentence summarising the week
  commercial_priority: top 3 actions ranked by expected revenue impact
  risk_flags: up to 2 items that need immediate attention
  kol_momentum: brief note on KOL engagement trajectory
  competitive_watch: most important competitive development this week
  recommended_ceo_actions: list of 2 specific decisions needed from leadership
"""


class ExecutiveInsightsAgent:
    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model_sonnet

    async def generate_briefing(self) -> dict:
        kpis = await self.kpi_snapshot()
        factory = get_session_factory()

        async with factory() as session:
            comp_rows = (await session.execute(text("""
                SELECT event_data, occurred_at
                FROM trigger_events
                WHERE event_type = 'competitor_drug_approved'
                ORDER BY occurred_at DESC LIMIT 5
            """))).fetchall() or []

            trial_rows = (await session.execute(text("""
                SELECT title, phase, sponsor, created_at
                FROM clinical_trials
                WHERE status = 'RECRUITING'
                AND created_at >= NOW() - INTERVAL '30 days'
                ORDER BY created_at DESC LIMIT 5
            """))).fetchall() or []

            msg_rows = (await session.execute(text("""
                SELECT COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                       COUNT(*) FILTER (WHERE status = 'sent')    AS sent,
                       COUNT(*) FILTER (WHERE status = 'approved') AS approved
                FROM messages
            """))).fetchone()

        top_hcps = await self._get_top_opportunity_hcps()

        prompt = EXECUTIVE_BRIEFING_PROMPT.format(
            kpis=json.dumps(kpis, default=str),
            top_hcps="\n".join(
                f"- {h['name']} ({h['specialty']}, {h['state']}): score {h['commercial_score']}"
                for h in top_hcps
            ) or "No scored HCPs yet",
            competitive_events="\n".join(
                str(r[0]) for r in comp_rows
            ) or "None this period",
            trial_activations="\n".join(
                f"- {r[0]} | Phase {r[1]} | {r[2]}"
                for r in trial_rows
            ) or "None this period",
            message_pipeline=(
                f"Pending: {msg_rows[0]}, Sent: {msg_rows[1]}, Approved: {msg_rows[2]}"
                if msg_rows else "No data"
            ),
        )

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            analysis = json.loads(response.content[0].text)
        except Exception:
            analysis = {"summary": response.content[0].text}

        return {
            "kpis": kpis,
            "top_opportunities": top_hcps,
            "analysis": analysis,
        }

    async def kpi_snapshot(self) -> dict:
        factory = get_session_factory()
        async with factory() as session:
            hcp_row = (await session.execute(text("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE kol_tier IN ('KOL', 'Regional KOL')) AS kols,
                       AVG(commercial_score) AS avg_score
                FROM hcps WHERE is_active = TRUE
            """))).fetchone()

            msg_row = (await session.execute(text("""
                SELECT COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days') AS this_week,
                       COUNT(*) FILTER (WHERE status = 'pending') AS pending
                FROM messages
            """))).fetchone()

            trigger_row = (await session.execute(text("""
                SELECT COUNT(*) FROM trigger_events
                WHERE occurred_at >= NOW() - INTERVAL '7 days'
            """))).fetchone()

            trial_row = (await session.execute(text("""
                SELECT COUNT(*) FROM clinical_trials WHERE status = 'RECRUITING'
            """))).fetchone()

            top_states_rows = (await session.execute(text("""
                SELECT state, COUNT(*) AS hcp_count, AVG(commercial_score) AS avg_score
                FROM hcps WHERE is_active = TRUE AND state IS NOT NULL
                GROUP BY state ORDER BY hcp_count DESC LIMIT 5
            """))).fetchall() or []

        return {
            "active_hcps": hcp_row[0] if hcp_row else 0,
            "kol_count": hcp_row[1] if hcp_row else 0,
            "avg_commercial_score": round(float(hcp_row[2] or 0), 1) if hcp_row else 0,
            "messages_this_week": msg_row[0] if msg_row else 0,
            "messages_pending": msg_row[1] if msg_row else 0,
            "triggers_this_week": trigger_row[0] if trigger_row else 0,
            "active_recruiting_trials": trial_row[0] if trial_row else 0,
            "top_states": [
                {
                    "state": r[0],
                    "hcp_count": r[1],
                    "avg_score": f"{float(r[2] or 0):.0f}",
                }
                for r in top_states_rows
            ],
        }

    async def _get_top_opportunity_hcps(self, limit: int = 10) -> list[dict]:
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT h.id, h.full_name, h.specialty, h.state,
                       h.commercial_score, h.kol_tier,
                       COUNT(DISTINCT te.id) AS recent_triggers
                FROM hcps h
                LEFT JOIN trigger_events te ON te.hcp_id = h.id
                    AND te.occurred_at >= NOW() - INTERVAL '30 days'
                WHERE h.is_active = TRUE
                GROUP BY h.id, h.full_name, h.specialty, h.state,
                         h.commercial_score, h.kol_tier
                ORDER BY h.commercial_score DESC NULLS LAST
                LIMIT :limit
            """), {"limit": limit})).fetchall() or []

        return [
            {
                "hcp_id": str(r[0]),
                "name": r[1],
                "specialty": r[2],
                "state": r[3],
                "commercial_score": float(r[4] or 0),
                "kol_tier": r[5],
                "recent_triggers": r[6],
            }
            for r in rows
        ]
