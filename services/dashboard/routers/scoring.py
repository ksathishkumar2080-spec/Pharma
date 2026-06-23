from fastapi import APIRouter, Depends
from shared.db import get_db
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/top")
async def top_hcps(
    n: int = 20,
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        text("""
            SELECT id, full_name, specialty, state, commercial_score, opportunity_score, influence_score, kol_tier
            FROM hcps ORDER BY commercial_score DESC LIMIT :n
        """),
        {"n": n},
    )).fetchall()
    return [
        {"id": str(r[0]), "name": r[1], "specialty": r[2], "state": r[3],
         "commercial_score": r[4], "opportunity_score": r[5], "influence_score": r[6], "kol_tier": r[7]}
        for r in rows
    ]


@router.get("/summary")
async def scoring_summary(db: AsyncSession = Depends(get_db)):
    row = (await db.execute(text("""
        SELECT
            COUNT(*) as total_hcps,
            AVG(commercial_score) as avg_commercial,
            AVG(opportunity_score) as avg_opportunity,
            COUNT(*) FILTER (WHERE kol_tier = 'national') as national_kols,
            COUNT(*) FILTER (WHERE kol_tier = 'regional') as regional_kols
        FROM hcps
    """))).fetchone()
    return {
        "total_hcps": row[0],
        "avg_commercial_score": round(row[1] or 0, 2),
        "avg_opportunity_score": round(row[2] or 0, 2),
        "national_kols": row[3],
        "regional_kols": row[4],
    }
