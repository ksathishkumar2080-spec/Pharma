from fastapi import APIRouter, Query
from ..agents.research_agent import ResearchIntelligenceAgent
from ..agents.evidence_extractor import EvidenceExtractorAgent

router = APIRouter()


@router.get("/synthesize")
async def synthesize_research(
    disease_area: str | None = Query(None, description="Filter by disease area e.g. 'lung cancer'")
):
    """AI-synthesized research briefing across all ingested sources (L5)."""
    agent = ResearchIntelligenceAgent()
    return await agent.synthesize(disease_area)


@router.get("/trends")
async def publication_trends(
    biomarker: str | None = None,
    disease: str | None = None,
):
    """Monthly publication velocity trend for a biomarker or disease area."""
    agent = ResearchIntelligenceAgent()
    return await agent.trend_analysis(biomarker, disease)


@router.get("/evidence/{publication_id}")
async def extract_evidence(publication_id: str):
    """Extract structured clinical evidence from a publication abstract (L5 Evidence Extractor)."""
    agent = EvidenceExtractorAgent()
    return await agent.extract_from_publication(publication_id)


@router.get("/evidence/batch")
async def extract_evidence_batch(
    disease_area: str | None = None,
    limit: int = Query(10, le=50),
):
    """Extract evidence from top recent publications."""
    agent = EvidenceExtractorAgent()
    return await agent.extract_batch(disease_area, limit)


@router.get("/evidence/hcp/{hcp_id}")
async def hcp_evidence_hooks(hcp_id: str, limit: int = Query(5, le=10)):
    """Top evidence hooks from an HCP's own publications — for message planning."""
    agent = EvidenceExtractorAgent()
    return await agent.top_evidence_for_hcp(hcp_id, limit)
