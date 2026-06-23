from fastapi import APIRouter, Depends, Query
from shared.db import get_db
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/")
async def list_hcps(
    specialty: str | None = None,
    state: str | None = None,
    kol_tier: str | None = None,
    min_score: float = 0,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    filters = ["commercial_score >= :min_score"]
    params = {"min_score": min_score, "limit": limit, "offset": offset}
    if specialty:
        filters.append("specialty ILIKE :specialty")
        params["specialty"] = f"%{specialty}%"
    if state:
        filters.append("state = :state")
        params["state"] = state
    if kol_tier:
        filters.append("kol_tier = :kol_tier")
        params["kol_tier"] = kol_tier

    where = " AND ".join(filters)
    rows = (await db.execute(
        text(f"SELECT id, full_name, specialty, state, kol_tier, commercial_score, opportunity_score FROM hcps WHERE {where} ORDER BY commercial_score DESC LIMIT :limit OFFSET :offset"),
        params,
    )).fetchall()
    return [{"id": str(r[0]), "name": r[1], "specialty": r[2], "state": r[3], "kol_tier": r[4], "commercial_score": r[5], "opportunity_score": r[6]} for r in rows]


@router.get("/{hcp_id}")
async def get_hcp(hcp_id: str, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(
        text("SELECT * FROM hcps WHERE id = :id"),
        {"id": hcp_id},
    )).fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="HCP not found")
    return dict(row._mapping)
