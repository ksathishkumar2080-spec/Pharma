from fastapi import APIRouter, Depends, Query
from shared.db import get_db
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/")
async def list_publications(
    disease_area: str | None = None,
    biomarker: str | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    params: dict = {"limit": limit}
    base = "SELECT id, pubmed_id, title, journal, published_at, citation_count FROM publications"
    if disease_area:
        base += " WHERE :da = ANY(disease_areas)"
        params["da"] = disease_area
    base += " ORDER BY published_at DESC LIMIT :limit"
    rows = (await db.execute(text(base), params)).fetchall()
    return [{"id": str(r[0]), "pubmed_id": r[1], "title": r[2], "journal": r[3], "published_at": str(r[4]), "citation_count": r[5]} for r in rows]
