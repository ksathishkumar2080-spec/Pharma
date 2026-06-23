from fastapi import APIRouter, Query, Body
from ..agents.qa_agent import QAAgent
from ..agents.message_planner import MessagePlannerAgent

router = APIRouter()


@router.post("/review")
async def review_message(
    message_body: str = Body(..., embed=True),
    channel: str = Body("email", embed=True),
    hcp_id: str | None = Body(None, embed=True),
    message_id: str | None = Body(None, embed=True),
):
    """Run QA gate on a message — returns pass/fail, issues, revised version (L13)."""
    agent = QAAgent()
    return await agent.review_message_as_dict(
        message_body=message_body,
        channel=channel,
        hcp_id=hcp_id,
        message_id=message_id,
    )


@router.get("/batch-review")
async def batch_review_pending(limit: int = Query(10, le=50)):
    """Review all pending unsent messages that haven't been QA-checked."""
    agent = QAAgent()
    return await agent.batch_review_pending(limit)


@router.get("/message-plan/{hcp_id}")
async def get_message_plan(hcp_id: str):
    """Generate a strategic communication plan before message generation (L13 Message Planner)."""
    agent = MessagePlannerAgent()
    return await agent.plan_as_dict(hcp_id)
