"""Evidence Extractor Agent — L5 Research Intelligence.

Extracts structured clinical evidence from publication abstracts:
- Primary/secondary endpoints and outcome data
- Statistical significance (p-values, HR, OR, CI)
- Patient population and biomarker subgroups
- Therapy comparisons and effect sizes
- Graded evidence quality (1a → 5)

Used by: Citation Validator (L16), Message Generator (L13), QA Agent (L13).
"""
from anthropic import AsyncAnthropic
import json
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)

EVIDENCE_EXTRACTION_PROMPT = """
You are a clinical evidence extraction specialist for oncology. Given the publication abstract below,
extract all structured clinical evidence.

Publication: {title}
Journal: {journal} ({published_at})
Abstract:
{abstract}

Extract JSON with keys:
  primary_endpoint: {{name, result, p_value, confidence_interval}} or null
  secondary_endpoints: list of {{name, result, p_value}} (max 4)
  patient_population: {{n, biomarker_selection, disease_stage, prior_therapies}}
  key_biomarkers: list of {{biomarker, direction, significance}}
  therapy_comparison: {{experimental_arm, control_arm, outcome_metric, effect_size}} or null
  evidence_grade: one of ["1a","1b","2a","2b","3","4","5"] per Oxford levels
  clinical_relevance: 1-2 sentence plain-English summary for a sales rep
  key_claim: single most commercially actionable finding (max 20 words)
"""


class EvidenceExtractorAgent:
    """L5 — extracts structured clinical evidence from publication abstracts."""

    def __init__(self):
        self._settings = get_settings()
        self.client = AsyncAnthropic(api_key=self._settings.anthropic_api_key)

    async def extract_from_publication(self, publication_id: str) -> dict:
        """Extract clinical evidence from a single publication by ID."""
        factory = get_session_factory()
        async with factory() as session:
            row = (await session.execute(text("""
                SELECT title, abstract, journal, published_at, doi
                FROM publications WHERE id = :id
            """), {"id": publication_id})).fetchone()

        if not row or not row[1]:
            return {"error": "Publication not found or has no abstract"}

        title, abstract, journal, published_at, doi = row
        evidence = await self._call_llm(title, abstract, journal, published_at)
        evidence["publication_id"] = publication_id
        evidence["doi"] = doi
        return evidence

    async def extract_batch(self, disease_area: str | None = None, limit: int = 20) -> list[dict]:
        """Extract evidence from recent high-citation publications."""
        factory = get_session_factory()
        async with factory() as session:
            where = "WHERE abstract IS NOT NULL AND published_at >= NOW() - INTERVAL '1 year'"
            params: dict = {"limit": limit}
            if disease_area:
                where += " AND :da = ANY(disease_areas)"
                params["da"] = disease_area

            rows = (await session.execute(text(f"""
                SELECT id, title, abstract, journal, published_at, citation_count
                FROM publications
                {where}
                ORDER BY citation_count DESC NULLS LAST
                LIMIT :limit
            """), params)).fetchall() or []

        results = []
        for row in rows:
            pub_id, title, abstract, journal, pub_date, _ = row
            try:
                evidence = await self._call_llm(title, abstract, journal, pub_date)
                evidence["publication_id"] = str(pub_id)
                results.append(evidence)
            except Exception as e:
                log.error("Evidence extraction failed for %s: %s", pub_id, e)
        return results

    async def _call_llm(self, title: str, abstract: str, journal: str, published_at) -> dict:
        prompt = EVIDENCE_EXTRACTION_PROMPT.format(
            title=title,
            abstract=abstract or "No abstract available",
            journal=journal or "Unknown journal",
            published_at=str(published_at)[:10] if published_at else "Unknown date",
        )
        response = await self.client.messages.create(
            model=self._settings.anthropic_model_sonnet,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            stripped = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(stripped)

    async def top_evidence_for_hcp(self, hcp_id: str, limit: int = 5) -> list[dict]:
        """Return pre-extracted key claims for the top publications of an HCP."""
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT p.id, p.title, p.abstract, p.journal, p.published_at, p.citation_count
                FROM publications p
                JOIN publication_authors pa ON pa.publication_id = p.id
                WHERE pa.hcp_id = :id AND p.abstract IS NOT NULL
                ORDER BY p.citation_count DESC NULLS LAST
                LIMIT :limit
            """), {"id": hcp_id, "limit": limit})).fetchall() or []

        results = []
        for row in rows:
            pub_id, title, abstract, journal, pub_date, _ = row
            try:
                evidence = await self._call_llm(title, abstract, journal, pub_date)
                evidence["publication_id"] = str(pub_id)
                results.append(evidence)
            except Exception as e:
                log.error("HCP evidence extraction failed: %s", e)
        return results
