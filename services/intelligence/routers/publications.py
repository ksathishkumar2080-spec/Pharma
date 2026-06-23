from fastapi import APIRouter, Query
from ..agents.publication_agent import PublicationIntelligenceAgent

router = APIRouter()


@router.get("/citation-network/{hcp_id}")
async def citation_network(hcp_id: str):
    """Co-author network and citation impact for an HCP."""
    agent = PublicationIntelligenceAgent()
    return await agent.citation_network(hcp_id)


@router.get("/journal-velocity")
async def journal_velocity(limit: int = Query(20, le=50)):
    """Journals ranked by publication velocity + citation momentum."""
    agent = PublicationIntelligenceAgent()
    return await agent.journal_velocity(limit)


@router.get("/emerging-authors")
async def emerging_authors():
    """HCPs with rapidly growing publication activity — rising stars."""
    agent = PublicationIntelligenceAgent()
    return await agent.emerging_authors()


@router.get("/whitespace")
async def whitespace_detection():
    """Identify underexplored research areas and biomarkers — opportunity gaps."""
    agent = PublicationIntelligenceAgent()
    return await agent.whitespace_detection()
