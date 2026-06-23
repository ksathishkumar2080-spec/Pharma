from fastapi import APIRouter, Query
from intelligence.agents.publication_agent import PublicationIntelligenceAgent

router = APIRouter()


@router.get("/citation-network/{hcp_id}")
async def citation_network(hcp_id: str):
    agent = PublicationIntelligenceAgent()
    return await agent.citation_network(hcp_id)


@router.get("/journal-velocity")
async def journal_velocity(limit: int = Query(20, le=50)):
    agent = PublicationIntelligenceAgent()
    return await agent.journal_velocity(limit)


@router.get("/emerging-authors")
async def emerging_authors():
    agent = PublicationIntelligenceAgent()
    return await agent.emerging_authors()


@router.get("/whitespace")
async def whitespace_detection():
    """Identify underexplored research areas — opportunity gaps."""
    agent = PublicationIntelligenceAgent()
    return await agent.whitespace_detection()
