from fastapi import APIRouter, Query
from intelligence.agents.research_agent import ResearchIntelligenceAgent

router = APIRouter()


@router.get("/synthesize")
async def synthesize_research(
    disease_area: str | None = Query(None, description="Filter by disease area")
):
    """AI-synthesized research briefing across all ingested sources."""
    agent = ResearchIntelligenceAgent()
    return await agent.synthesize(disease_area)


@router.get("/trends")
async def publication_trends(
    biomarker: str | None = None,
    disease: str | None = None,
):
    agent = ResearchIntelligenceAgent()
    return await agent.trend_analysis(biomarker, disease)
