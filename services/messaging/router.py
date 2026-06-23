from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from uuid import UUID
from messaging.generator import MessageGenerator

router = APIRouter()


class MessageRequest(BaseModel):
    hcp_id: UUID
    channel: str  # linkedin | email | conversation_starter | follow_up
    context_notes: str = ""


class MessageResponse(BaseModel):
    channel: str
    subject: str | None
    body: str
    evidence_citations: list[dict]
    grammar_validated: bool


@router.post("/generate", response_model=MessageResponse)
async def generate_message(req: MessageRequest):
    generator = MessageGenerator()
    result = await generator.generate(req.hcp_id, req.channel, req.context_notes)
    if not result:
        raise HTTPException(status_code=404, detail="HCP not found or insufficient data")
    return result
