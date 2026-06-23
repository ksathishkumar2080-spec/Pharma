from fastapi import APIRouter, Query, Body
from ..agents.lead_discovery import LeadDiscoveryAgent

router = APIRouter()


@router.get("/from-publications")
async def leads_from_publications(limit: int = Query(30, le=100)):
    """Discover leads from high-impact publications with no matched HCP (L8)."""
    agent = LeadDiscoveryAgent()
    return await agent.discover_from_publications(limit)


@router.get("/from-trials")
async def leads_from_trials(limit: int = Query(20, le=50)):
    """Discover leads from newly recruiting trial PIs with no HCP record (L8)."""
    agent = LeadDiscoveryAgent()
    return await agent.discover_from_trials(limit)


@router.get("/emerging-kols")
async def emerging_kols(limit: int = Query(20, le=50)):
    """HCPs in system with rapidly accelerating publication velocity — tier upgrade candidates."""
    agent = LeadDiscoveryAgent()
    return await agent.discover_emerging_kols(limit)


@router.post("/qualify")
async def qualify_lead(lead: dict = Body(..., description="Raw lead signal dict from /from-publications or /from-trials")):
    """Use Claude to score and qualify a raw lead signal."""
    agent = LeadDiscoveryAgent()
    return await agent.qualify_lead(lead)
