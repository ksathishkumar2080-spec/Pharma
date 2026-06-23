"""Generates vector embeddings for publications using Voyage AI voyage-3."""
import httpx
import logging
from sqlalchemy import text

from shared.config import get_settings
from shared.db import get_session_factory

log = logging.getLogger(__name__)


class EmbeddingPipeline:
    """Embeds publication abstracts into pgvector for semantic search."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def run(self) -> int:
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
        embedded = 0
        for pub_id, title, abstract in rows:
            ok = await self._embed_publication(pub_id, title, abstract)
            if ok:
                embedded += 1
        log.info("Successfully embedded %d / %d publications", embedded, len(rows))
        return embedded

    async def _embed_publication(self, pub_id: str, title: str, abstract: str) -> bool:
        text_input = f"{title}\n\n{abstract}"
        try:
            embedding = await self._get_embedding(text_input)
            if embedding is None:
                return False
            factory = get_session_factory()
            async with factory() as session:
                # Pass list directly — asyncpg + pgvector handles list[float] natively
                await session.execute(
                    text("UPDATE publications SET embedding = :emb WHERE id = :id"),
                    {"emb": embedding, "id": pub_id},
                )
                await session.commit()
            return True
        except Exception as e:
            log.error("Embedding failed for pub %s: %s", pub_id, e, exc_info=True)
            return False

    async def _get_embedding(self, text_input: str) -> list[float] | None:
        """Fetch embedding from Voyage AI; returns None on failure (no silent zero vectors)."""
        api_key = self.settings.voyage_api_key
        if not api_key:
            log.warning("VOYAGE_API_KEY not set — skipping embedding")
            return None

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.voyageai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": self.settings.voyage_model, "input": text_input},
                )
                resp.raise_for_status()
                data = resp.json()
                return data["data"][0]["embedding"]
        except httpx.HTTPStatusError as e:
            log.error("Voyage API HTTP error %s: %s", e.response.status_code, e.response.text)
            return None
        except Exception as e:
            log.error("Voyage API request failed: %s", e, exc_info=True)
            return None
