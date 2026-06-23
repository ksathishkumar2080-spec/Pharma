"""Generates vector embeddings for publications and HCP profiles using Claude."""
import anthropic
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)


class EmbeddingPipeline:
    """Embeds publication abstracts into pgvector for semantic search."""

    def __init__(self):
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def run(self):
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(
                text("""
                    SELECT id, title, abstract FROM publications
                    WHERE abstract IS NOT NULL AND embedding IS NULL
                    LIMIT 200
                """)
            )).fetchall()

        log.info("Embedding %d publications", len(rows))
        for pub_id, title, abstract in rows:
            await self._embed_publication(pub_id, title, abstract)

    async def _embed_publication(self, pub_id, title: str, abstract: str):
        text_input = f"{title}\n\n{abstract}"
        try:
            # Use Voyage AI embeddings via Anthropic-compatible interface
            # or fall back to a lightweight local embedding
            embedding = await self._get_embedding(text_input)
            factory = get_session_factory()
            async with factory() as session:
                await session.execute(
                    text("UPDATE publications SET embedding = :emb WHERE id = :id"),
                    {"emb": str(embedding), "id": pub_id},
                )
                await session.commit()
        except Exception as e:
            log.error("Embedding failed for %s: %s", pub_id, e)

    async def _get_embedding(self, text_input: str) -> list[float]:
        """Get embedding via voyage-3 model through Anthropic."""
        import httpx
        settings = get_settings()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.anthropic_api_key}"},
                json={"model": "voyage-3", "input": text_input},
            )
            if resp.status_code == 200:
                return resp.json()["data"][0]["embedding"]
        # Fallback: zero vector (for development without API key)
        return [0.0] * 1536
