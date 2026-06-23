"""Cohort analysis — HCP scoring model improvement signals."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session

router = APIRouter(prefix="/analytics/cohort", tags=["cohort"])


@router.get("/score-vs-engagement")
async def score_vs_engagement(session: AsyncSession = Depends(get_session)):
    """Correlation between HCP score buckets and actual engagement rates."""
    rows = await session.execute(
        text("""
            SELECT
                WIDTH_BUCKET(h.influence_score, 0, 100, 10) * 10 AS score_bucket,
                COUNT(DISTINCT h.id) AS hcps,
                COUNT(DISTINCT om.id) AS messages,
                COUNT(DISTINCT mc.message_id)
                    FILTER (WHERE mc.event = 'replied') AS replies,
                ROUND(
                    COUNT(DISTINCT mc.message_id) FILTER (WHERE mc.event = 'replied')
                    ::numeric /
                    NULLIF(COUNT(DISTINCT om.id), 0) * 100, 1
                ) AS reply_rate_pct
            FROM hcps h
            LEFT JOIN outreach_messages om ON om.hcp_id = h.id
            LEFT JOIN message_conversions mc ON mc.message_id = om.id::text
            GROUP BY score_bucket
            ORDER BY score_bucket
        """)
    )
    return [dict(r) for r in rows.mappings()]


@router.get("/model-improvement-signals")
async def model_signals(session: AsyncSession = Depends(get_session)):
    """Returns HCPs whose engagement rate diverges from predicted score.
    High engagement + low score = underrated KOLs.
    Low engagement + high score = overrated KOLs.
    """
    rows = await session.execute(
        text("""
            WITH engagement AS (
                SELECT om.hcp_id,
                       COUNT(DISTINCT om.id) AS messages_sent,
                       COUNT(DISTINCT mc.message_id)
                           FILTER (WHERE mc.event = 'replied') AS replies
                FROM outreach_messages om
                LEFT JOIN message_conversions mc ON mc.message_id = om.id::text
                GROUP BY om.hcp_id
            )
            SELECT h.id, h.name, h.kol_tier, h.influence_score,
                   e.messages_sent, e.replies,
                   ROUND(e.replies::numeric / NULLIF(e.messages_sent, 0) * 100, 1)
                       AS actual_reply_rate_pct,
                   CASE
                       WHEN h.influence_score > 70
                            AND e.replies::numeric / NULLIF(e.messages_sent, 0) < 0.1
                       THEN 'overrated'
                       WHEN h.influence_score < 40
                            AND e.replies::numeric / NULLIF(e.messages_sent, 0) > 0.3
                       THEN 'underrated'
                       ELSE 'calibrated'
                   END AS signal
            FROM hcps h
            JOIN engagement e ON e.hcp_id = h.id
            WHERE e.messages_sent >= 3
            ORDER BY signal, h.influence_score DESC
            LIMIT 100
        """)
    )
    return [dict(r) for r in rows.mappings()]
