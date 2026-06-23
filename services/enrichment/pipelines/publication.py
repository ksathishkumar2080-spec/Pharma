"""Enriches publications with disease areas, biomarkers, and therapies using Claude."""
import json
import anthropic
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)

EXTRACTION_PROMPT = """
Extract structured information from this oncology publication abstract.
Return ONLY valid JSON with keys: disease_areas (list), biomarkers (list), therapies (list).

Abstract:
{abstract}
"""


class PublicationEnrichmentPipeline:
    def __init__(self):
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def run(self):
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(
                text("""
                    SELECT id, abstract FROM publications
                    WHERE abstract IS NOT NULL
                    AND (disease_areas IS NULL OR array_length(disease_areas, 1) IS NULL)
                    LIMIT 100
                """)
            )).fetchall()

        log.info("Enriching %d publications", len(rows))
        for pub_id, abstract in rows:
            await self._enrich(pub_id, abstract)

    async def _enrich(self, pub_id, abstract: str):
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(abstract=abstract)}],
            )
            data = json.loads(response.content[0].text)
            factory = get_session_factory()
            async with factory() as session:
                await session.execute(
                    text("""
                        UPDATE publications
                        SET disease_areas = :da, biomarkers = :bm, therapies = :th
                        WHERE id = :id
                    """),
                    {
                        "da": data.get("disease_areas", []),
                        "bm": data.get("biomarkers", []),
                        "th": data.get("therapies", []),
                        "id": pub_id,
                    },
                )
                await session.commit()
        except Exception as exc:
            log.error("Failed to enrich publication %s: %s", pub_id, exc)
