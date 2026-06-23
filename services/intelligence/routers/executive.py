from fastapi import APIRouter
from ..agents.executive_insights import ExecutiveInsightsAgent

router = APIRouter()


@router.get("/briefing")
async def executive_briefing():
    """Full AI-synthesized executive briefing — pipeline, territory, messaging, risks (L18)."""
    agent = ExecutiveInsightsAgent()
    return await agent.generate_briefing()


@router.get("/kpis")
async def kpi_snapshot():
    """Fast KPI snapshot for executive dashboard widgets (no LLM call)."""
    agent = ExecutiveInsightsAgent()
    return await agent.kpi_snapshot()


@router.get("/top-opportunities")
async def top_opportunities(limit: int = 10):
    """Top N HCPs by commercial score + recent trigger activity."""
    agent = ExecutiveInsightsAgent()
    return await agent._get_top_opportunity_hcps(limit)
