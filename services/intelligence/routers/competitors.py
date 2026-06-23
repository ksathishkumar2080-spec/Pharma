from fastapi import APIRouter, Query
from intelligence.agents.competitor_agent import CompetitorIntelligenceAgent

router = APIRouter()


@router.get("/brief")
async def competitor_brief(
    company: str = Query(..., description="Competitor company name")
):
    agent = CompetitorIntelligenceAgent()
    return await agent.get_competitor_brief(company)


@router.get("/pipeline")
async def pipeline_tracker():
    agent = CompetitorIntelligenceAgent()
    return await agent.pipeline_tracker()


@router.get("/market-signals")
async def market_signals():
    agent = CompetitorIntelligenceAgent()
    return await agent.market_share_signals()
