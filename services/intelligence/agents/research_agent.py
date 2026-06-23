"""Research Intelligence Agent — L5 Research Summarizer.

Synthesizes trends, white spaces, and emerging signals across:
- PubMed / Semantic Scholar / OpenAlex / Europe PMC / bioRxiv
- Conference abstracts (ASCO, ESMO, AACR, SABCS)
- ClinVar biomarkers
- Clinical trials
"""
from anthropic import AsyncAnthropic
import json
from shared.config import get_settings
from shared.db import get_session_factory
from elasticsearch import AsyncElasticsearch
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)

RESEARCH_SYNTHESIS_PROMPT = """
You are an oncology research intelligence analyst. Based on the publication and trial data below,
produce a structured intelligence briefing.

Recent Publications ({pub_count} total, sample below):
{publications}

Active Recruiting Trials ({trial_count} total, sample below):
{trials}

Top Biomarkers in recent literature:
{biomarkers}

Conference Abstracts (recent):
{abstracts}

Produce JSON with keys:
  emerging_themes: list of up to 5 emerging research themes with evidence
  white_spaces: list of up to 3 underexplored areas with high opportunity
  hot_biomarkers: list of up to 5 biomarkers with rising publication frequency
  trial_landscape_summary: 2-3 sentence summary of current trial activity
  competitor_activity_signals: list of notable competitor moves detected
  recommended_focus_areas: list of 3 areas for commercial team attention
"""


class ResearchIntelligenceAgent:
    def __init__(self):
        self._settings = get_settings()
        self.client = AsyncAnthropic(api_key=self._settings.anthropic_api_key)

    async def synthesize(self, disease_area: str | None = None) -> dict:
        context = await self._gather_context(disease_area)
        prompt = RESEARCH_SYNTHESIS_PROMPT.format(**context)

        response = await self.client.messages.create(
            model=self._settings.anthropic_model_sonnet,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            result = json.loads(response.content[0].text)
        except Exception:
            stripped = response.content[0].text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            try:
                result = json.loads(stripped)
            except Exception:
                result = {"raw": response.content[0].text}
        result["disease_area_filter"] = disease_area
        result["publication_count"] = context["pub_count"]
        result["trial_count"] = context["trial_count"]
        return result

    async def _gather_context(self, disease_area: str | None) -> dict:
        factory = get_session_factory()

        async with factory() as session:
            pub_where = "WHERE p.published_at >= NOW() - INTERVAL '6 months'"
            params: dict = {}
            if disease_area:
                pub_where += " AND :da = ANY(p.disease_areas)"
                params["da"] = disease_area

            pubs = (await session.execute(text(f"""
                SELECT p.title, p.journal, p.citation_count, p.disease_areas, p.biomarkers
                FROM publications p
                {pub_where}
                ORDER BY p.citation_count DESC NULLS LAST
                LIMIT 20
            """), params)).fetchall() or []

            pub_count = (await session.execute(text(f"""
                SELECT COUNT(*) FROM publications p {pub_where}
            """), params)).scalar() or 0

            trials = (await session.execute(text("""
                SELECT title, phase, sponsor, conditions
                FROM clinical_trials
                WHERE status = 'RECRUITING'
                ORDER BY created_at DESC
                LIMIT 10
            """))).fetchall() or []

            trial_count = (await session.execute(text(
                "SELECT COUNT(*) FROM clinical_trials WHERE status = 'RECRUITING'"
            ))).scalar() or 0

        biomarker_freq: dict[str, int] = {}
        for pub in pubs:
            for bm in (pub[4] or []):
                biomarker_freq[bm] = biomarker_freq.get(bm, 0) + 1
        top_biomarkers = sorted(biomarker_freq, key=lambda k: biomarker_freq[k], reverse=True)[:10]

        abstracts_text = "None indexed yet"
        try:
            es = AsyncElasticsearch(self._settings.elasticsearch_url)
            es_result = await es.search(
                index="conference_abstracts",
                body={"query": {"match_all": {}}, "size": 5},
            )
            abstracts = [h["_source"].get("title", "") for h in es_result["hits"]["hits"]]
            abstracts_text = "\n".join(f"- {a}" for a in abstracts) or "None indexed yet"
            await es.close()
        except Exception:
            pass

        return {
            "pub_count": pub_count,
            "publications": "\n".join(
                f"- {p[0]} ({p[1]}, {p[2]} citations, biomarkers: {p[4]})"
                for p in pubs
            ) or "None",
            "trial_count": trial_count,
            "trials": "\n".join(
                f"- {t[0]} | Phase {t[1]} | {t[2]}"
                for t in trials
            ) or "None",
            "biomarkers": ", ".join(top_biomarkers) or "None identified",
            "abstracts": abstracts_text,
        }

    async def trend_analysis(self, biomarker: str | None = None, disease: str | None = None) -> dict:
        """Compute publication velocity for a biomarker or disease over time."""
        factory = get_session_factory()
        async with factory() as session:
            where = "WHERE p.published_at IS NOT NULL"
            params: dict = {}
            if biomarker:
                where += " AND :bm = ANY(p.biomarkers)"
                params["bm"] = biomarker
            if disease:
                where += " AND :da = ANY(p.disease_areas)"
                params["da"] = disease

            rows = (await session.execute(text(f"""
                SELECT
                    DATE_TRUNC('month', p.published_at) AS month,
                    COUNT(*) AS count,
                    AVG(p.citation_count) AS avg_citations
                FROM publications p
                {where}
                AND p.published_at >= NOW() - INTERVAL '3 years'
                GROUP BY 1
                ORDER BY 1
            """), params)).fetchall() or []

        return {
            "filter": {"biomarker": biomarker, "disease": disease},
            "monthly_trend": [
                {"month": str(r[0])[:7], "publications": r[1], "avg_citations": round(r[2] or 0, 1)}
                for r in rows
            ],
        }
