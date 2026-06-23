from fastapi import APIRouter, Depends, Query
from shared.db import get_db
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/")
async def list_trials(
    status: str | None = None,
    phase: str | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    filters = ["1=1"]
    params: dict = {"limit": limit}
    if status:
        filters.append("status = :status")
        params["status"] = status
    if phase:
        filters.append("phase ILIKE :phase")
        params["phase"] = f"%{phase}%"

    where = " AND ".join(filters)
    rows = (await db.execute(
        text(f"SELECT id, nct_id, title, phase, status, sponsor FROM clinical_trials WHERE {where} LIMIT :limit"),
        params,
    )).fetchall()
    return [{"id": str(r[0]), "nct_id": r[1], "title": r[2], "phase": r[3], "status": r[4], "sponsor": r[5]} for r in rows]
