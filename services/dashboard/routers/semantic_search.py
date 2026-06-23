"""Semantic (vector) search over publications and HCPs using pgvector."""
from fastapi import APIRouter, Query, Depends
from shared.db import get_db
from shared.config import get_settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import logging

log = logging.getLogger(__name__)
router = APIRouter()


async def _embed_query(query: str) -> list[float]:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.anthropic_api_key}"},
                json={"model": "voyage-3", "input": query},
            )
            if resp.status_code == 200:
                return resp.json()["data"][0]["embedding"]
    except Exception as e:
        log.warning("Embedding API error: %s", e)
    return [0.0] * 1536


@router.get("/publications")
async def semantic_search_publications(
    q: str = Query(..., description="Natural language query"),
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Find publications semantically similar to the query."""
    embedding = await _embed_query(q)
    emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
    rows = (await db.execute(
        text("""
            SELECT id, pubmed_id, title, journal, published_at,
                   1 - (embedding <=> :emb::vector) AS similarity
            FROM publications
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :emb::vector
            LIMIT :limit
        """),
        {"emb": emb_str, "limit": limit},
    )).fetchall()
    return [
        {
            "id": str(r[0]), "pubmed_id": r[1], "title": r[2],
            "journal": r[3], "published_at": str(r[4]), "similarity": round(r[5], 4),
        }
        for r in rows
    ]


@router.get("/hcps")
async def semantic_search_hcps(
    q: str = Query(..., description="Research area or clinical interest"),
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Find HCPs whose publication portfolio best matches a research interest."""
    embedding = await _embed_query(q)
    emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
    rows = (await db.execute(
        text("""
            SELECT h.id, h.full_name, h.specialty, h.state, h.commercial_score,
                   AVG(1 - (p.embedding <=> :emb::vector)) AS avg_similarity
            FROM hcps h
            JOIN publication_authors pa ON pa.hcp_id = h.id
            JOIN publications p ON p.id = pa.publication_id
            WHERE p.embedding IS NOT NULL
            GROUP BY h.id, h.full_name, h.specialty, h.state, h.commercial_score
            ORDER BY avg_similarity DESC
            LIMIT :limit
        """),
        {"emb": emb_str, "limit": limit},
    )).fetchall()
    return [
        {
            "id": str(r[0]), "name": r[1], "specialty": r[2],
            "state": r[3], "commercial_score": r[4], "relevance_score": round(r[5], 4),
        }
        for r in rows
    ]
