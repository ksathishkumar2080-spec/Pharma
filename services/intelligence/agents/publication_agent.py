"""Publication Intelligence Agent — L5 Research Summarizer (citation & authorship layer).

Provides:
- Citation network analysis (who is citing whom)
- Journal velocity (publishing rate by journal)
- Co-authorship community detection
- Publication gap detection (topics with few recent papers)
- Author emergence scoring (rising new authors)
"""
from anthropic import AsyncAnthropic
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)


class PublicationIntelligenceAgent:
    def __init__(self):
        self._settings = get_settings()
        self.client = AsyncAnthropic(api_key=self._settings.anthropic_api_key)

    async def citation_network(self, hcp_id: str) -> dict:
        """Identify co-author network and citation impact for an HCP."""
        factory = get_session_factory()
        async with factory() as session:
            hcp = (await session.execute(
                text("SELECT full_name FROM hcps WHERE id = :id"), {"id": hcp_id}
            )).fetchone()
            if not hcp:
                return {"error": "HCP not found"}

            pubs = (await session.execute(text("""
                SELECT p.pubmed_id, p.title, p.citation_count, p.journal
                FROM publications p
                JOIN publication_authors pa ON p.id = pa.publication_id
                WHERE pa.hcp_id = :id
                ORDER BY p.citation_count DESC NULLS LAST
                LIMIT 20
            """), {"id": hcp_id})).fetchall() or []

            co_authors = (await session.execute(text("""
                SELECT DISTINCT h2.id, h2.full_name, h2.specialty,
                       COUNT(*) AS shared_papers
                FROM publication_authors pa1
                JOIN publication_authors pa2 ON pa1.publication_id = pa2.publication_id
                    AND pa1.hcp_id != pa2.hcp_id
                JOIN hcps h2 ON h2.id = pa2.hcp_id
                WHERE pa1.hcp_id = :id
                GROUP BY h2.id, h2.full_name, h2.specialty
                ORDER BY shared_papers DESC
                LIMIT 15
            """), {"id": hcp_id})).fetchall() or []

        return {
            "hcp_id": hcp_id,
            "hcp_name": hcp[0],
            "publication_count": len(pubs),
            "total_citations": sum(p[2] or 0 for p in pubs),
            "top_publications": [
                {"pubmed_id": p[0], "title": p[1], "citations": p[2], "journal": p[3]}
                for p in pubs
            ],
            "co_author_network": [
                {"id": str(c[0]), "name": c[1], "specialty": c[2], "shared_papers": c[3]}
                for c in co_authors
            ],
        }

    async def journal_velocity(self, limit: int = 20) -> list[dict]:
        """Rank journals by publication volume + citation momentum."""
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT
                    journal,
                    COUNT(*) AS total_papers,
                    COUNT(*) FILTER (WHERE published_at >= NOW() - INTERVAL '1 year') AS recent_papers,
                    AVG(citation_count) AS avg_citations,
                    SUM(citation_count) AS total_citations
                FROM publications
                WHERE journal IS NOT NULL
                GROUP BY journal
                HAVING COUNT(*) >= 3
                ORDER BY recent_papers DESC, avg_citations DESC
                LIMIT :limit
            """), {"limit": limit})).fetchall() or []
        return [
            {
                "journal": r[0],
                "total_papers": r[1],
                "recent_papers": r[2],
                "avg_citations": round(r[3] or 0, 1),
                "total_citations": r[4],
                "velocity_score": round((r[2] or 0) * (r[3] or 0) / max(r[1], 1), 2),
            }
            for r in rows
        ]

    async def emerging_authors(self, lookback_months: int = 18) -> list[dict]:
        """Find HCPs with rapidly growing publication activity (rising stars)."""
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT
                    h.id, h.full_name, h.specialty, h.state,
                    COUNT(*) FILTER (
                        WHERE p.published_at >= NOW() - INTERVAL '18 months'
                    ) AS recent_pubs,
                    COUNT(*) FILTER (
                        WHERE p.published_at < NOW() - INTERVAL '18 months'
                        AND p.published_at >= NOW() - INTERVAL '36 months'
                    ) AS prior_pubs,
                    SUM(p.citation_count) FILTER (
                        WHERE p.published_at >= NOW() - INTERVAL '18 months'
                    ) AS recent_citations
                FROM hcps h
                JOIN publication_authors pa ON pa.hcp_id = h.id
                JOIN publications p ON p.id = pa.publication_id
                GROUP BY h.id, h.full_name, h.specialty, h.state
                HAVING COUNT(*) FILTER (
                    WHERE p.published_at >= NOW() - INTERVAL '18 months'
                ) > COUNT(*) FILTER (
                    WHERE p.published_at < NOW() - INTERVAL '18 months'
                    AND p.published_at >= NOW() - INTERVAL '36 months'
                )
                ORDER BY recent_pubs DESC
                LIMIT 30
            """))).fetchall() or []

        return [
            {
                "id": str(r[0]), "name": r[1], "specialty": r[2], "state": r[3],
                "recent_publications": r[4], "prior_publications": r[5],
                "recent_citations": r[6] or 0,
                "growth_ratio": round((r[4] or 1) / max(r[5] or 1, 1), 2),
            }
            for r in rows
        ]

    async def whitespace_detection(self) -> dict:
        """Find disease areas and biomarkers with few publications — opportunity gaps."""
        factory = get_session_factory()
        async with factory() as session:
            disease_counts = (await session.execute(text("""
                SELECT unnest(disease_areas) AS da, COUNT(*) AS cnt
                FROM publications
                WHERE published_at >= NOW() - INTERVAL '2 years'
                GROUP BY da
                ORDER BY cnt
                LIMIT 20
            """))).fetchall() or []

            biomarker_counts = (await session.execute(text("""
                SELECT unnest(biomarkers) AS bm, COUNT(*) AS cnt
                FROM publications
                WHERE published_at >= NOW() - INTERVAL '2 years'
                GROUP BY bm
                ORDER BY cnt
                LIMIT 20
            """))).fetchall() or []

        return {
            "underexplored_disease_areas": [
                {"disease_area": r[0], "recent_publications": r[1]} for r in disease_counts
            ],
            "underexplored_biomarkers": [
                {"biomarker": r[0], "recent_publications": r[1]} for r in biomarker_counts
            ],
        }
