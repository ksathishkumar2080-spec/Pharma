"""Rep feedback capture — thumbs up/down on messages, NBA actions, scores."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session
from services.analytics.models import RepFeedbackIn

router = APIRouter(prefix="/analytics/feedback", tags=["feedback"])


@router.post("/")
async def submit_feedback(
    body: RepFeedbackIn,
    session: AsyncSession = Depends(get_session),
):
    await session.execute(
        text("""
            INSERT INTO rep_feedback
                (target_type, target_id, feedback, rep_id, note, created_at)
            VALUES
                (:target_type, :target_id, :feedback, :rep_id, :note, NOW())
        """),
        {
            "target_type": body.target_type.value,
            "target_id": body.target_id,
            "feedback": body.feedback.value,
            "rep_id": body.rep_id,
            "note": body.note,
        },
    )
    await session.commit()
    return {"status": "recorded"}


@router.get("/summary")
async def feedback_summary(session: AsyncSession = Depends(get_session)):
    rows = await session.execute(
        text("""
            SELECT target_type, feedback, COUNT(*) AS cnt
            FROM rep_feedback
            GROUP BY target_type, feedback
            ORDER BY target_type, feedback
        """)
    )
    return [dict(r) for r in rows.mappings()]


@router.get("/low-rated")
async def low_rated_messages(
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
):
    """Messages with most thumbs-down — feeds back into prompt improvement loop."""
    rows = await session.execute(
        text("""
            SELECT rf.target_id AS message_id,
                   COUNT(*) FILTER (WHERE rf.feedback = 'thumbs_down') AS downvotes,
                   COUNT(*) FILTER (WHERE rf.feedback = 'thumbs_up') AS upvotes,
                   om.content
            FROM rep_feedback rf
            LEFT JOIN outreach_messages om ON om.id::text = rf.target_id
            WHERE rf.target_type = 'message'
            GROUP BY rf.target_id, om.content
            HAVING COUNT(*) FILTER (WHERE rf.feedback = 'thumbs_down') > 0
            ORDER BY downvotes DESC
            LIMIT :limit
        """),
        {"limit": limit},
    )
    return [dict(r) for r in rows.mappings()]
