"""Outreach message history and management."""
from fastapi import APIRouter, Depends, Query
from shared.db import get_db
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/")
async def list_messages(
    hcp_id: str | None = None,
    channel: str | None = None,
    sent: bool | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    filters = ["1=1"]
    params: dict = {"limit": limit}
    if hcp_id:
        filters.append("m.hcp_id = :hcp_id")
        params["hcp_id"] = hcp_id
    if channel:
        filters.append("m.channel = :channel")
        params["channel"] = channel
    if sent is not None:
        filters.append("m.sent_at IS " + ("NOT NULL" if sent else "NULL"))

    where = " AND ".join(filters)
    rows = (await db.execute(text(f"""
        SELECT m.id, m.hcp_id, h.full_name, m.channel, m.subject,
               m.body, m.grammar_validated, m.sent_at, m.created_at
        FROM outreach_messages m
        JOIN hcps h ON m.hcp_id = h.id
        WHERE {where}
        ORDER BY m.created_at DESC
        LIMIT :limit
    """), params)).fetchall()

    return [
        {
            "id": str(r[0]), "hcp_id": str(r[1]), "hcp_name": r[2],
            "channel": r[3], "subject": r[4], "body": r[5],
            "grammar_validated": r[6], "sent_at": str(r[7]) if r[7] else None,
            "created_at": str(r[8]),
        }
        for r in rows
    ]


@router.patch("/{message_id}/mark-sent")
async def mark_sent(message_id: str, db: AsyncSession = Depends(get_db)):
    await db.execute(
        text("UPDATE outreach_messages SET sent_at = NOW() WHERE id = :id"),
        {"id": message_id},
    )
    await db.commit()
    return {"status": "marked sent"}
