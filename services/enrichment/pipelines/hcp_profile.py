"""Enriches HCP profiles using Apollo.io and public data sources."""
import httpx
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)


class HCPProfilePipeline:
    async def run(self):
        settings = get_settings()
        if not settings.apollo_api_key:
            log.warning("No Apollo API key — skipping HCP enrichment")
            return

        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(
                text("""
                    SELECT id, full_name, email FROM hcps
                    WHERE last_enriched_at IS NULL
                    LIMIT 50
                """)
            )).fetchall()

        log.info("Enriching %d HCP profiles", len(rows))
        async with httpx.AsyncClient(timeout=20) as client:
            for hcp_id, name, email in rows:
                await self._enrich_hcp(client, settings, hcp_id, name, email)

    async def _enrich_hcp(self, client, settings, hcp_id, name: str, email: str):
        try:
            resp = await client.post(
                "https://api.apollo.io/v1/people/match",
                json={"name": name, "email": email},
                headers={"x-api-key": settings.apollo_api_key},
            )
            if resp.status_code == 200:
                data = resp.json().get("person", {})
                factory = get_session_factory()
                async with factory() as session:
                    await session.execute(
                        text("""
                            UPDATE hcps
                            SET linkedin_url = :linkedin,
                                twitter_handle = :twitter,
                                last_enriched_at = NOW()
                            WHERE id = :id
                        """),
                        {
                            "linkedin": data.get("linkedin_url"),
                            "twitter": data.get("twitter_url"),
                            "id": hcp_id,
                        },
                    )
                    await session.commit()
        except Exception as exc:
            log.error("Apollo enrichment failed for %s: %s", hcp_id, exc)
