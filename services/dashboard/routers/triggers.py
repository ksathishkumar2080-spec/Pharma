from fastapi import APIRouter, Depends, Query
from shared.db import get_db
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/")
async def list_triggers(
    event_type: str | None = None,
    processed: bool | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    filters = ["1=1"]
    params: dict = {"limit": limit}
    if event_type:
        filters.append("event_type = :event_type")
        params["event_type"] = event_type
    if processed is not None:
        filters.append("processed = :processed")
        params["processed"] = processed

    where = " AND ".join(filters)
    rows = (await db.execute(
        text(f"SELECT te.id, te.hcp_id, h.full_name, te.event_type, te.occurred_at, te.processed FROM trigger_events te JOIN hcps h ON te.hcp_id = h.id WHERE {where} ORDER BY te.occurred_at DESC LIMIT :limit"),
        params,
    )).fetchall()
    return [
        {"id": str(r[0]), "hcp_id": str(r[1]), "hcp_name": r[2], "event_type": r[3], "occurred_at": str(r[4]), "processed": r[5]}
        for r in rows
    ]
