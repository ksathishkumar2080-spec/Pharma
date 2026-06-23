"""Lead Discovery Agent — L8 Lead Generation.

Identifies net-new HCP leads by mining:
- First/corresponding authors on high-impact oncology papers not yet in HCP master table
- Principal investigators on newly recruiting trials (NCT)
- Authors with publication velocity spikes (emerging KOLs)
- Co-author network expansion from known KOLs

Output feeds the Lead Generation layer (L8) which scores and qualifies leads
before handing off to Territory Intelligence (L9).
"""
from anthropic import AsyncAnthropic
import json
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)

LEAD_QUALIFICATION_PROMPT = """
You are an oncology commercial intelligence analyst. Given the profile of a potential new HCP lead,
assess their commercial potential for an oncology portfolio.

HCP Signal Profile:
- Name: {name}
- Discovered via: {discovery_source}
- Recent publications: {pub_count} in the last 18 months
- Trial activity: {trial_activity}
- Top biomarkers in their work: {biomarkers}
- Institution: {institution}
- Co-authors with existing KOLs: {kol_connections}

Produce JSON with keys:
  lead_score: integer 0-100
  kol_tier_prediction: one of ["national", "regional", "local", "emerging"]
  commercial_rationale: 2-3 sentence explanation
  recommended_first_action: one of ["send_linkedin", "invite_to_advisory", "share_data", "trial_referral"]
  priority: one of ["immediate", "this_quarter", "next_quarter", "monitor"]
"""


class LeadDiscoveryAgent:
    """L8 — discovers and qualifies new HCP leads from publication and trial signals."""

    def __init__(self):
        self._settings = get_settings()
        self.client = AsyncAnthropic(api_key=self._settings.anthropic_api_key)

    async def discover_from_publications(self, limit: int = 50) -> list[dict]:
        """Find corresponding/first authors of recent high-impact papers not yet in HCP master."""
        factory = get_session_factory()
        async with factory() as session:
            # Find publications with no matching HCP in our system
            rows = (await session.execute(text("""
                SELECT p.id, p.title, p.journal, p.citation_count, p.disease_areas, p.biomarkers,
                       p.raw_json->>'corresponding_author' AS corresponding_author,
                       p.raw_json->>'author_list' AS author_list
                FROM publications p
                WHERE p.published_at >= NOW() - INTERVAL '6 months'
                  AND p.citation_count >= 5
                  AND NOT EXISTS (
                      SELECT 1 FROM publication_authors pa WHERE pa.publication_id = p.id
                  )
                ORDER BY p.citation_count DESC
                LIMIT :limit
            """), {"limit": limit})).fetchall() or []

        leads = []
        for row in rows:
            pub_id, title, journal, citations, disease_areas, biomarkers, corr_author, author_list = row
            if corr_author:
                leads.append({
                    "discovery_source": "high_impact_publication",
                    "publication_id": str(pub_id),
                    "publication_title": title,
                    "journal": journal,
                    "citations": citations,
                    "potential_name": corr_author,
                    "disease_areas": disease_areas or [],
                    "biomarkers": biomarkers or [],
                    "status": "unmatched_to_hcp",
                })
        return leads

    async def discover_from_trials(self, limit: int = 30) -> list[dict]:
        """Find PIs on newly recruiting trials whose HCP records don't exist yet."""
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT ct.id, ct.nct_id, ct.title, ct.phase, ct.sponsor,
                       ct.conditions, ct.raw_json->>'principal_investigator' AS pi_name,
                       ct.raw_json->>'pi_institution' AS pi_institution
                FROM clinical_trials ct
                WHERE ct.status = 'RECRUITING'
                  AND ct.created_at >= NOW() - INTERVAL '3 months'
                  AND NOT EXISTS (
                      SELECT 1 FROM trial_investigators ti WHERE ti.trial_id = ct.id
                  )
                ORDER BY ct.created_at DESC
                LIMIT :limit
            """), {"limit": limit})).fetchall() or []

        leads = []
        for row in rows:
            trial_id, nct_id, title, phase, sponsor, conditions, pi_name, pi_institution = row
            if pi_name:
                leads.append({
                    "discovery_source": "trial_principal_investigator",
                    "trial_id": str(trial_id),
                    "nct_id": nct_id,
                    "trial_title": title,
                    "phase": phase,
                    "sponsor": sponsor,
                    "potential_name": pi_name,
                    "institution": pi_institution,
                    "conditions": conditions or [],
                    "status": "unmatched_to_hcp",
                })
        return leads

    async def discover_emerging_kols(self, limit: int = 20) -> list[dict]:
        """Find HCPs already in system with rapidly accelerating publication velocity."""
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT
                    h.id, h.full_name, h.specialty, h.institution_id, h.kol_tier,
                    COUNT(pa.hcp_id) FILTER (
                        WHERE p.published_at >= NOW() - INTERVAL '12 months'
                    ) AS recent_pubs,
                    COUNT(pa.hcp_id) FILTER (
                        WHERE p.published_at BETWEEN NOW() - INTERVAL '24 months'
                                              AND NOW() - INTERVAL '12 months'
                    ) AS prior_pubs,
                    ARRAY_AGG(DISTINCT unnest_bm) FILTER (WHERE unnest_bm IS NOT NULL) AS biomarkers
                FROM hcps h
                JOIN publication_authors pa ON pa.hcp_id = h.id
                JOIN publications p ON p.id = pa.publication_id
                LEFT JOIN LATERAL unnest(p.biomarkers) AS unnest_bm ON TRUE
                WHERE h.kol_tier IN ('local', 'emerging') OR h.kol_tier IS NULL
                GROUP BY h.id, h.full_name, h.specialty, h.institution_id, h.kol_tier
                HAVING COUNT(pa.hcp_id) FILTER (
                    WHERE p.published_at >= NOW() - INTERVAL '12 months'
                ) >= 3
                ORDER BY recent_pubs DESC
                LIMIT :limit
            """), {"limit": limit})).fetchall() or []

        return [
            {
                "hcp_id": str(r[0]),
                "name": r[1],
                "specialty": r[2],
                "current_tier": r[4],
                "recent_publications": r[5],
                "prior_publications": r[6],
                "growth_ratio": round((r[5] or 1) / max(r[6] or 1, 1), 2),
                "top_biomarkers": (r[7] or [])[:5],
                "recommendation": "upgrade_tier" if (r[5] or 0) > 2 * max(r[6] or 1, 1) else "monitor",
            }
            for r in rows
        ]

    async def qualify_lead(self, lead: dict) -> dict:
        """Use Claude to score and qualify a raw lead signal."""
        factory = get_session_factory()
        async with factory() as session:
            # Check if known KOLs co-authored with this person
            kol_connections = 0
            if lead.get("hcp_id"):
                kol_connections = (await session.execute(text("""
                    SELECT COUNT(DISTINCT pa2.hcp_id)
                    FROM publication_authors pa1
                    JOIN publication_authors pa2 ON pa1.publication_id = pa2.publication_id
                    JOIN hcps h2 ON h2.id = pa2.hcp_id
                    WHERE pa1.hcp_id = :id AND h2.kol_tier = 'national'
                """), {"id": lead["hcp_id"]})).scalar() or 0

        prompt = LEAD_QUALIFICATION_PROMPT.format(
            name=lead.get("potential_name") or lead.get("name", "Unknown"),
            discovery_source=lead.get("discovery_source", "unknown"),
            pub_count=lead.get("recent_publications", 0),
            trial_activity="Active PI" if lead.get("discovery_source") == "trial_principal_investigator" else "Author",
            biomarkers=", ".join(lead.get("biomarkers") or lead.get("top_biomarkers") or []) or "Unknown",
            institution=lead.get("institution") or "Unknown",
            kol_connections=kol_connections,
        )
        try:
            response = await self.client.messages.create(
                model=self._settings.anthropic_model_haiku,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            try:
                qualification = json.loads(raw)
            except json.JSONDecodeError:
                stripped = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                qualification = json.loads(stripped)
        except Exception as e:
            log.error("Lead qualification failed: %s", e)
            qualification = {"lead_score": 0, "priority": "monitor", "commercial_rationale": str(e)}

        return {**lead, **qualification}
