from fastapi import APIRouter, Query
from ..agents.competitor_agent import CompetitorIntelligenceAgent

router = APIRouter()


@router.get("/brief")
async def competitor_brief(
    company: str = Query(..., description="Competitor company name")
):
    """AI-synthesized competitor brief: pipeline, publications, HCP affiliations (L7)."""
    agent = CompetitorIntelligenceAgent()
    return await agent.get_competitor_brief(company)


@router.get("/pipeline")
async def pipeline_tracker():
    """Track all competitor pipeline assets in the knowledge graph."""
    agent = CompetitorIntelligenceAgent()
    return await agent.pipeline_tracker()


@router.get("/market-signals")
async def market_signals():
    """Market share and territory penetration signals from publication data."""
    agent = CompetitorIntelligenceAgent()
    return await agent.market_share_signals()
