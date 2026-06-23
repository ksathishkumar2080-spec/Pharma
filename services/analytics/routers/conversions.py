"""Message conversion tracking — sent / opened / replied / meeting_booked."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session
from services.analytics.models import ConversionEventIn

router = APIRouter(prefix="/analytics/conversions", tags=["conversions"])

EVENT_ORDER = ["sent", "opened", "replied", "meeting_booked"]


@router.post("/event")
async def record_conversion(
    body: ConversionEventIn,
    session: AsyncSession = Depends(get_session),
):
    await session.execute(
        text("""
            INSERT INTO message_conversions
                (message_id, event, rep_id, occurred_at)
            VALUES
                (:message_id, :event, :rep_id, COALESCE(:occurred_at, NOW()))
            ON CONFLICT (message_id, event) DO UPDATE
                SET occurred_at = EXCLUDED.occurred_at
        """),
        {
            "message_id": body.message_id,
            "event": body.event,
            "rep_id": body.rep_id,
            "occurred_at": body.occurred_at,
        },
    )
    await session.commit()
    return {"status": "recorded"}


@router.get("/rates")
async def conversion_rates(session: AsyncSession = Depends(get_session)):
    rows = await session.execute(
        text("""
            SELECT
                COUNT(DISTINCT message_id) FILTER (WHERE event = 'sent')  AS sent,
                COUNT(DISTINCT message_id) FILTER (WHERE event = 'opened') AS opened,
                COUNT(DISTINCT message_id) FILTER (WHERE event = 'replied') AS replied,
                COUNT(DISTINCT message_id) FILTER (WHERE event = 'meeting_booked') AS meeting_booked
            FROM message_conversions
        """)
    )
    rec = dict(rows.mappings().fetchone())
    sent = rec["sent"] or 1
    return {
        **rec,
        "open_rate": round(rec["opened"] / sent, 3),
        "reply_rate": round(rec["replied"] / sent, 3),
        "meeting_rate": round(rec["meeting_booked"] / sent, 3),
    }


@router.get("/by-action-type")
async def rates_by_action(session: AsyncSession = Depends(get_session)):
    rows = await session.execute(
        text("""
            SELECT om.action_type,
                   COUNT(DISTINCT mc.message_id) FILTER (WHERE mc.event = 'sent')  AS sent,
                   COUNT(DISTINCT mc.message_id) FILTER (WHERE mc.event = 'replied') AS replied
            FROM message_conversions mc
            JOIN outreach_messages om ON om.id::text = mc.message_id
            GROUP BY om.action_type
            ORDER BY replied DESC
        """)
    )
    return [dict(r) for r in rows.mappings()]
