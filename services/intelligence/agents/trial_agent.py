"""Clinical Trial Intelligence Agent.

Provides:
- Phase progression tracking (Phase I → II → III → approval)
- Competitive trial landscape per disease area
- Site activation alerts (trials newly open in a territory)
- Trial-to-HCP matching (which HCPs should be referred to a trial)
- Enrollment velocity analysis
"""
from shared.db import get_session_factory
from sqlalchemy import text
from anthropic import AsyncAnthropic
import json
from shared.config import get_settings
import logging

log = logging.getLogger(__name__)

TRIAL_LANDSCAPE_PROMPT = """
You are an oncology clinical trial intelligence analyst.

Active Recruiting Trials in {disease_area}:
{trials}

Provide JSON with keys:
  competitive_landscape: 2-3 sentence summary of who is running what trials
  phase_distribution: dict of {{"Phase I": N, "Phase II": N, "Phase III": N}}
  dominant_sponsors: list of top 3 sponsors with trial counts
  key_biomarker_targets: list of biomarkers/targets most commonly studied
  trial_gaps: list of 2-3 disease areas or patient populations underrepresented
  hcp_referral_opportunities: 1-2 sentence note on which HCP types to engage
"""


class ClinicalTrialIntelligenceAgent:
    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def competitive_landscape(self, disease_area: str) -> dict:
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT title, phase, status, sponsor, conditions, interventions,
                       enrollment, start_date, primary_completion_date
                FROM clinical_trials
                WHERE status IN ('RECRUITING', 'ACTIVE_NOT_RECRUITING')
                AND (
                    title ILIKE :da
                    OR EXISTS (
                        SELECT 1 FROM unnest(conditions) c WHERE c ILIKE :da
                    )
                )
                ORDER BY enrollment DESC NULLS LAST
                LIMIT 30
            """), {"da": f"%{disease_area}%"})).fetchall()

        if not rows:
            return {"disease_area": disease_area, "trials": [], "analysis": "No trials found"}

        trial_text = "\n".join(
            f"- {r[0]} | Phase {r[1]} | {r[3]} | Enrollment: {r[6]}"
            for r in rows
        )
        prompt = TRIAL_LANDSCAPE_PROMPT.format(disease_area=disease_area, trials=trial_text)
        response = await self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            analysis = json.loads(response.content[0].text)
        except Exception:
            analysis = {"summary": response.content[0].text}

        return {
            "disease_area": disease_area,
            "active_trial_count": len(rows),
            "trials": [
                {"title": r[0], "phase": r[1], "status": r[2], "sponsor": r[3],
                 "enrollment": r[6]}
                for r in rows
            ],
            "analysis": analysis,
        }

    async def phase_progression_tracker(self) -> list[dict]:
        """Identify trials that changed phase recently — signal of drug advancement."""
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT nct_id, title, phase, status, sponsor, updated_at
                FROM clinical_trials
                WHERE updated_at >= NOW() - INTERVAL '90 days'
                AND phase IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 50
            """))).fetchall()

        return [
            {"nct_id": r[0], "title": r[1], "phase": r[2],
             "status": r[3], "sponsor": r[4], "updated_at": str(r[5])}
            for r in rows
        ]

    async def site_activation_alerts(self, state: str | None = None) -> list[dict]:
        """Trials that just opened sites in a territory — referral opportunity."""
        factory = get_session_factory()
        async with factory() as session:
            where = "ct.status = 'RECRUITING' AND ct.created_at >= NOW() - INTERVAL '60 days'"
            params: dict = {}
            if state:
                where += " AND h.state = :state"
                params["state"] = state

            rows = (await session.execute(text(f"""
                SELECT ct.nct_id, ct.title, ct.phase, ct.sponsor,
                       h.full_name, h.specialty, h.state, h.id as hcp_id
                FROM clinical_trials ct
                JOIN trial_investigators ti ON ti.trial_id = ct.id
                JOIN hcps h ON h.id = ti.hcp_id
                WHERE {where}
                ORDER BY ct.created_at DESC
                LIMIT 50
            """), params)).fetchall()

        return [
            {
                "nct_id": r[0], "trial_title": r[1], "phase": r[2],
                "sponsor": r[3], "investigator_name": r[4],
                "investigator_specialty": r[5], "state": r[6],
                "hcp_id": str(r[7]),
            }
            for r in rows
        ]

    async def trial_hcp_matching(self, nct_id: str, limit: int = 20) -> list[dict]:
        """Find HCPs most likely to refer patients to a given trial."""
        factory = get_session_factory()
        async with factory() as session:
            trial = (await session.execute(
                text("SELECT title, conditions, interventions FROM clinical_trials WHERE nct_id = :id"),
                {"id": nct_id},
            )).fetchone()
            if not trial:
                return []

            conditions = trial[1] or []
            rows = (await session.execute(text("""
                SELECT h.id, h.full_name, h.specialty, h.state,
                       h.commercial_score, h.kol_tier,
                       COUNT(DISTINCT pa.publication_id) AS related_pubs
                FROM hcps h
                LEFT JOIN publication_authors pa ON pa.hcp_id = h.id
                LEFT JOIN publications p ON p.id = pa.publication_id
                    AND p.disease_areas && :conditions
                WHERE h.is_active = TRUE
                GROUP BY h.id, h.full_name, h.specialty, h.state, h.commercial_score, h.kol_tier
                ORDER BY related_pubs DESC, h.commercial_score DESC
                LIMIT :limit
            """), {"conditions": conditions, "limit": limit})).fetchall()

        return [
            {
                "hcp_id": str(r[0]), "name": r[1], "specialty": r[2],
                "state": r[3], "commercial_score": r[4], "kol_tier": r[5],
                "related_publications": r[6],
            }
            for r in rows
        ]
