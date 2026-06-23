from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session
from services.compliance.citation_verifier import CitationVerifier

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/audit-log")
async def get_audit_log(
    limit: int = 100,
    service: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    q = "SELECT * FROM compliance_audit_log"
    params: dict = {}
    if service:
        q += " WHERE service = :service"
        params["service"] = service
    q += " ORDER BY created_at DESC LIMIT :limit"
    params["limit"] = limit
    rows = await session.execute(text(q), params)
    return [dict(r) for r in rows.mappings()]


@router.post("/verify-message/{message_id}")
async def verify_message(
    message_id: str,
    session: AsyncSession = Depends(get_session),
):
    row = await session.execute(
        text("SELECT content FROM outreach_messages WHERE id = :id"),
        {"id": message_id},
    )
    rec = row.fetchone()
    if not rec:
        from fastapi import HTTPException
        raise HTTPException(404, "Message not found")
    verifier = CitationVerifier(session)
    report = await verifier.verify_message(message_id, rec[0])
    return report.__dict__
