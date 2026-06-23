from fastapi import APIRouter, Query
from ..agents.trial_agent import ClinicalTrialIntelligenceAgent

router = APIRouter()


@router.get("/landscape")
async def trial_landscape(
    disease_area: str = Query(..., description="e.g. 'lung cancer', 'AML'")
):
    """Competitive trial landscape for a disease area (L6 Clinical Intelligence)."""
    agent = ClinicalTrialIntelligenceAgent()
    return await agent.competitive_landscape(disease_area)


@router.get("/phase-progression")
async def phase_progression():
    """Track phase transitions across all monitored trials."""
    agent = ClinicalTrialIntelligenceAgent()
    return await agent.phase_progression_tracker()


@router.get("/site-activations")
async def site_activations(state: str | None = None):
    """New trial site activations — signals for territory rep action."""
    agent = ClinicalTrialIntelligenceAgent()
    return await agent.site_activation_alerts(state)


@router.get("/match-hcps/{nct_id}")
async def match_hcps_to_trial(nct_id: str, limit: int = Query(20, le=50)):
    """Match HCPs in system to a trial by specialty and location."""
    agent = ClinicalTrialIntelligenceAgent()
    return await agent.trial_hcp_matching(nct_id, limit)
