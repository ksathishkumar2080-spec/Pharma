"""Relationship memory and interaction history endpoints."""
from fastapi import APIRouter, Depends
from shared.db import get_db
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
import uuid

router = APIRouter()


class InteractionCreate(BaseModel):
    hcp_id: UUID
    rep_id: str
    interaction_type: str   # call | meeting | email | linkedin | conference
    notes: str
    sentiment: str = "neutral"
    occurred_at: datetime | None = None


@router.get("/{hcp_id}")
async def get_relationship_history(hcp_id: str, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(text("""
        SELECT id, rep_id, interaction_type, notes, sentiment, occurred_at
        FROM relationship_memory
        WHERE hcp_id = :id
        ORDER BY occurred_at DESC
        LIMIT 50
    """), {"id": hcp_id})).fetchall()
    return [
        {"id": str(r[0]), "rep_id": r[1], "type": r[2], "notes": r[3], "sentiment": r[4], "occurred_at": str(r[5])}
        for r in rows
    ]


@router.post("/")
async def log_interaction(body: InteractionCreate, db: AsyncSession = Depends(get_db)):
    await db.execute(text("""
        INSERT INTO relationship_memory (id, hcp_id, rep_id, interaction_type, notes, sentiment, occurred_at)
        VALUES (:id, :hcp_id, :rep_id, :type, :notes, :sentiment, :occurred_at)
    """), {
        "id": str(uuid.uuid4()),
        "hcp_id": str(body.hcp_id),
        "rep_id": body.rep_id,
        "type": body.interaction_type,
        "notes": body.notes,
        "sentiment": body.sentiment,
        "occurred_at": body.occurred_at or datetime.utcnow(),
    })
    await db.commit()
    return {"status": "logged"}
