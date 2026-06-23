"""Executive Insights Agent — L18 Executive Command Center.

Synthesizes a full-stack view across ALL pipeline layers for executive users
(Medical Affairs leadership, Commercial VP, Executive Portal).

Aggregates:
- Pipeline health: ingestion rates, enrichment coverage, trigger velocity
- Territory snapshot: top opportunity HCPs by region, tier distribution
- Messaging performance: conversion rates, reply rates, channel effectiveness
- Research landscape: emerging themes, competitor moves, hot biomarkers
- Compliance posture: audit log summary, citation validation rates
- Decision support: top 5 actions leadership should take this week

Used by the Executive Command Center dashboard (L18) and the Leadership portal.
"""
from anthropic import AsyncAnthropic
import json
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text
import logging
from datetime import datetime

log = logging.getLogger(__name__)

EXECUTIVE_BRIEFING_PROMPT = """
You are the chief intelligence officer for an oncology commercial team.
Synthesize the metrics below into an executive briefing for the VP of Commercial and Medical Affairs.

PIPELINE HEALTH:
- Total HCPs tracked: {total_hcps} ({active_hcps} active)
- Publications ingested (last 30d): {new_pubs}
- Recruiting trials monitored: {recruiting_trials}
- Trigger events (last 7d): {recent_triggers}

TERRITORY SNAPSHOT:
- National KOLs: {national_kols} | Regional: {regional_kols} | Local/Emerging: {local_kols}
- States with highest opportunity: {top_states}
- Average commercial score: {avg_score}

MESSAGING PERFORMANCE (last 30d):
- Messages sent: {messages_sent}
- Open rate: {open_rate}%
- Reply rate: {reply_rate}%
- Best channel: {best_channel}

RESEARCH SIGNALS:
- Top biomarkers trending: {hot_biomarkers}
- Competitor publications (last 30d): {competitor_pubs}

Produce JSON with keys:
  executive_summary: 3-4 sentence strategic narrative
  pipeline_health_score: integer 0-100
  top_opportunities: list of 5 {{hcp_name, tier, state, reason}} — highest-priority HCPs
  strategic_risks: list of up to 3 risks with brief description
  recommended_decisions: list of 5 executive actions for this week
  kpis: {{total_hcps, coverage_rate, message_reply_rate, trigger_velocity, pipeline_health_score}}
  generated_at: current ISO timestamp
"""


class ExecutiveInsightsAgent:
    """L18 — full-stack synthesis for the Executive Command Center."""

    def __init__(self):
        self._settings = get_settings()
        self.client = AsyncAnthropic(api_key=self._settings.anthropic_api_key)

    async def generate_briefing(self) -> dict:
        """Generate a complete executive briefing from live data."""
        metrics = await self._gather_metrics()
        top_hcps = await self._get_top_opportunity_hcps()
        prompt = EXECUTIVE_BRIEFING_PROMPT.format(**metrics)

        response = await self.client.messages.create(
            model=self._settings.anthropic_model_sonnet,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        try:
            briefing = json.loads(raw)
        except json.JSONDecodeError:
            stripped = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            try:
                briefing = json.loads(stripped)
            except Exception:
                briefing = {"executive_summary": raw}

        briefing["top_opportunity_hcps_detail"] = top_hcps
        briefing["generated_at"] = datetime.utcnow().isoformat() + "Z"
        briefing["raw_metrics"] = metrics
        return briefing

    async def kpi_snapshot(self) -> dict:
        """Fast KPI snapshot without LLM — for dashboard widgets."""
        return await self._gather_metrics()

    async def _gather_metrics(self) -> dict:
        factory = get_session_factory()
        async with factory() as session:
            total_hcps = (await session.execute(text("SELECT COUNT(*) FROM hcps"))).scalar() or 0
            active_hcps = (await session.execute(text("SELECT COUNT(*) FROM hcps WHERE is_active = TRUE"))).scalar() or 0

            new_pubs = (await session.execute(text(
                "SELECT COUNT(*) FROM publications WHERE created_at >= NOW() - INTERVAL '30 days'"
            ))).scalar() or 0

            recruiting_trials = (await session.execute(text(
                "SELECT COUNT(*) FROM clinical_trials WHERE status = 'RECRUITING'"
            ))).scalar() or 0

            recent_triggers = (await session.execute(text(
                "SELECT COUNT(*) FROM trigger_events WHERE occurred_at >= NOW() - INTERVAL '7 days'"
            ))).scalar() or 0

            national_kols = (await session.execute(text(
                "SELECT COUNT(*) FROM hcps WHERE kol_tier = 'national'"
            ))).scalar() or 0
            regional_kols = (await session.execute(text(
                "SELECT COUNT(*) FROM hcps WHERE kol_tier = 'regional'"
            ))).scalar() or 0
            local_kols = (await session.execute(text(
                "SELECT COUNT(*) FROM hcps WHERE kol_tier IN ('local', 'emerging')"
            ))).scalar() or 0

            top_states_rows = (await session.execute(text("""
                SELECT state, COUNT(*) AS cnt, AVG(commercial_score) AS avg_score
                FROM hcps WHERE is_active = TRUE AND state IS NOT NULL
                GROUP BY state ORDER BY avg_score DESC LIMIT 5
            """))).fetchall() or []

            avg_score = (await session.execute(text(
                "SELECT AVG(commercial_score) FROM hcps WHERE is_active = TRUE"
            ))).scalar() or 0

            messages_sent = (await session.execute(text(
                "SELECT COUNT(*) FROM outreach_messages WHERE sent_at >= NOW() - INTERVAL '30 days'"
            ))).scalar() or 0

            opened = (await session.execute(text(
                "SELECT COUNT(*) FROM outreach_messages WHERE opened_at IS NOT NULL AND sent_at >= NOW() - INTERVAL '30 days'"
            ))).scalar() or 0

            replied = (await session.execute(text(
                "SELECT COUNT(*) FROM outreach_messages WHERE replied_at IS NOT NULL AND sent_at >= NOW() - INTERVAL '30 days'"
            ))).scalar() or 0

            best_channel_row = (await session.execute(text("""
                SELECT channel, COUNT(*) AS cnt
                FROM outreach_messages
                WHERE replied_at IS NOT NULL AND sent_at >= NOW() - INTERVAL '30 days'
                GROUP BY channel ORDER BY cnt DESC LIMIT 1
            """))).fetchone()

            biomarker_rows = (await session.execute(text("""
                SELECT unnest(biomarkers) AS bm, COUNT(*) AS cnt
                FROM publications
                WHERE published_at >= NOW() - INTERVAL '30 days'
                GROUP BY bm ORDER BY cnt DESC LIMIT 5
            """))).fetchall() or []

            competitor_pubs = (await session.execute(text(
                "SELECT COUNT(*) FROM publications WHERE created_at >= NOW() - INTERVAL '30 days'"
            ))).scalar() or 0

        open_rate = round(opened / max(messages_sent, 1) * 100, 1)
        reply_rate = round(replied / max(messages_sent, 1) * 100, 1)

        return {
            "total_hcps": total_hcps,
            "active_hcps": active_hcps,
            "new_pubs": new_pubs,
            "recruiting_trials": recruiting_trials,
            "recent_triggers": recent_triggers,
            "national_kols": national_kols,
            "regional_kols": regional_kols,
            "local_kols": local_kols,
            "top_states": ", ".join(f"{r[0]} (avg score {r[2]:.0f})" for r in top_states_rows) or "N/A",
            "avg_score": round(avg_score, 1),
            "messages_sent": messages_sent,
            "open_rate": open_rate,
            "reply_rate": reply_rate,
            "best_channel": best_channel_row[0] if best_channel_row else "N/A",
            "hot_biomarkers": ", ".join(r[0] for r in biomarker_rows) or "None detected",
            "competitor_pubs": competitor_pubs,
        }

    async def _get_top_opportunity_hcps(self, limit: int = 10) -> list[dict]:
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT h.id, h.full_name, h.specialty, h.kol_tier, h.state,
                       h.commercial_score,
                       COUNT(te.id) FILTER (WHERE te.occurred_at >= NOW() - INTERVAL '30 days') AS recent_triggers
                FROM hcps h
                LEFT JOIN trigger_events te ON te.hcp_id = h.id
                WHERE h.is_active = TRUE
                GROUP BY h.id, h.full_name, h.specialty, h.kol_tier, h.state, h.commercial_score
                ORDER BY h.commercial_score DESC, recent_triggers DESC
                LIMIT :limit
            """), {"limit": limit})).fetchall() or []

        return [
            {
                "hcp_id": str(r[0]),
                "name": r[1],
                "specialty": r[2],
                "tier": r[3],
                "state": r[4],
                "commercial_score": r[5],
                "recent_triggers": r[6],
            }
            for r in rows
        ]
