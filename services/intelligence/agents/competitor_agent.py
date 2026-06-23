"""Competitor Intelligence Agent.

Provides:
- Pipeline monitoring (phase changes, approvals, label updates)
- Company news watcher (earnings, partnerships, M&A)
- Competitive positioning per disease area
- HCP competitor affinity alerts
- Market share signal detection from trial volumes
"""
from anthropic import AsyncAnthropic
import json
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)

try:
    from elasticsearch import AsyncElasticsearch
except ImportError:
    AsyncElasticsearch = None

COMPETITOR_BRIEF_PROMPT = """
You are an oncology competitive intelligence analyst.

Competitor: {company}

Known pipeline / approved drugs:
{pipeline}

Recent news signals from indexed sources:
{news}

Recent FDA approval events:
{fda_events}

HCPs with high affinity to this competitor:
{hcp_signals}

Produce JSON with keys:
  executive_summary: 2-3 sentence summary of competitive position
  pipeline_threats: list of up to 3 pipeline assets that threaten market position
  partnership_signals: any detected partnership or M&A activity
  hcp_engagement_risk: which HCP segments are most at risk of competitor capture
  recommended_response: list of 2-3 tactical commercial responses
"""


class CompetitorIntelligenceAgent:
    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def get_competitor_brief(self, company_name: str) -> dict:
        factory = get_session_factory()
        settings = get_settings()

        async with factory() as session:
            competitor = (await session.execute(text("""
                SELECT id, name, disease_areas, pipeline_assets
                FROM competitors WHERE name ILIKE :name
            """), {"name": f"%{company_name}%"})).fetchone()

            fda_events = (await session.execute(text("""
                SELECT event_data FROM trigger_events
                WHERE event_type = 'competitor_drug_approved'
                AND event_data::text ILIKE :name
                ORDER BY occurred_at DESC LIMIT 5
            """), {"name": f"%{company_name}%"})).fetchall()

        # Search news for company mentions
        news_snippets = []
        if AsyncElasticsearch is not None:
            try:
                es = AsyncElasticsearch(settings.elasticsearch_url)
                result = await es.search(
                    index="oncology_news",
                    body={"query": {"match": {"content": company_name}}, "size": 5},
                )
                news_snippets = [
                    h["_source"].get("content", "")[:300]
                    for h in result["hits"]["hits"]
                ]
                await es.close()
            except Exception:
                pass

        # HCPs with high competitor affinity
        top_hcps: list = []
        try:
            from scoring.competitor_affinity import CompetitorAffinityScorer
            scorer = CompetitorAffinityScorer()
            hcp_affinities = await scorer.score_all([company_name])
            top_hcps = hcp_affinities[:5]
        except ImportError:
            log.warning("CompetitorAffinityScorer not available; skipping HCP affinity signals")

        prompt = COMPETITOR_BRIEF_PROMPT.format(
            company=company_name,
            pipeline=str(competitor[3] if competitor else {}),
            news="\n".join(news_snippets) or "No news signals found",
            fda_events="\n".join(str(e[0]) for e in fda_events) or "None",
            hcp_signals="\n".join(
                f"- {h['name']}: affinity {h['competitor_affinity_score']}"
                for h in top_hcps
            ) or "None detected",
        )

        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            analysis = json.loads(response.content[0].text)
        except Exception:
            analysis = {"summary": response.content[0].text}

        return {
            "company": company_name,
            "competitor_record": {
                "disease_areas": competitor[2] if competitor else [],
                "pipeline_assets": competitor[3] if competitor else {},
            } if competitor else None,
            "fda_events_count": len(fda_events),
            "news_signals": len(news_snippets),
            "top_at_risk_hcps": top_hcps[:5],
            "analysis": analysis,
        }

    async def pipeline_tracker(self) -> list[dict]:
        """All recent competitor_drug_approved events as a timeline."""
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT event_data, occurred_at
                FROM trigger_events
                WHERE event_type = 'competitor_drug_approved'
                ORDER BY occurred_at DESC
                LIMIT 50
            """))).fetchall()
        return [
            {"event": r[0], "occurred_at": str(r[1])}
            for r in rows
        ]

    async def market_share_signals(self) -> dict:
        """Trial volume by sponsor as proxy for R&D investment."""
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT sponsor,
                       COUNT(*) AS total_trials,
                       COUNT(*) FILTER (WHERE status = 'RECRUITING') AS recruiting,
                       COUNT(*) FILTER (WHERE phase ILIKE '%3%') AS phase3
                FROM clinical_trials
                WHERE sponsor IS NOT NULL
                GROUP BY sponsor
                ORDER BY total_trials DESC
                LIMIT 20
            """))).fetchall()
        return {
            "sponsor_trial_volumes": [
                {"sponsor": r[0], "total_trials": r[1],
                 "recruiting": r[2], "phase3_trials": r[3]}
                for r in rows
            ]
        }
