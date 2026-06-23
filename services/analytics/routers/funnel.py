"""Funnel analytics — HCP through the engagement funnel."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session

router = APIRouter(prefix="/analytics/funnel", tags=["funnel"])


@router.get("/overview")
async def funnel_overview(session: AsyncSession = Depends(get_session)):
    """Full engagement funnel from HCP identified → meeting booked."""
    rows = await session.execute(
        text("""
            WITH stages AS (
                SELECT
                    COUNT(DISTINCT h.id)  AS identified,
                    COUNT(DISTINCT te.hcp_id) AS triggered,
                    COUNT(DISTINCT om.hcp_id) AS messaged,
                    COUNT(DISTINCT mc.message_id)
                        FILTER (WHERE mc.event = 'opened') AS opened,
                    COUNT(DISTINCT mc.message_id)
                        FILTER (WHERE mc.event = 'replied') AS replied,
                    COUNT(DISTINCT mc.message_id)
                        FILTER (WHERE mc.event = 'meeting_booked') AS meeting_booked
                FROM hcps h
                LEFT JOIN trigger_events te ON te.hcp_id = h.id
                LEFT JOIN outreach_messages om ON om.hcp_id = h.id
                LEFT JOIN message_conversions mc ON mc.message_id = om.id::text
            )
            SELECT * FROM stages
        """)
    )
    return dict(rows.mappings().fetchone())


@router.get("/drop-off")
async def drop_off_analysis(session: AsyncSession = Depends(get_session)):
    """At which stage do HCPs most commonly drop off?"""
    funnel = await funnel_overview(session)
    stages = ["identified", "triggered", "messaged", "opened", "replied", "meeting_booked"]
    result = []
    for i, stage in enumerate(stages):
        current = funnel.get(stage, 0) or 0
        if i == 0:
            result.append({"stage": stage, "count": current, "drop_rate": 0.0})
        else:
            prev = funnel.get(stages[i - 1], 1) or 1
            drop = round(1 - (current / prev), 3) if prev else 0.0
            result.append({"stage": stage, "count": current, "drop_rate": drop})
    return result


@router.get("/by-tier")
async def funnel_by_tier(session: AsyncSession = Depends(get_session)):
    rows = await session.execute(
        text("""
            SELECT h.kol_tier,
                   COUNT(DISTINCT h.id) AS hcps,
                   COUNT(DISTINCT om.id) AS messages_sent,
                   COUNT(DISTINCT mc.message_id)
                       FILTER (WHERE mc.event = 'replied') AS replies
            FROM hcps h
            LEFT JOIN outreach_messages om ON om.hcp_id = h.id
            LEFT JOIN message_conversions mc ON mc.message_id = om.id::text
            GROUP BY h.kol_tier
            ORDER BY h.kol_tier
        """)
    )
    return [dict(r) for r in rows.mappings()]
