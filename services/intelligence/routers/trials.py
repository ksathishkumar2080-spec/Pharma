from fastapi import APIRouter, Query
from intelligence.agents.trial_agent import ClinicalTrialIntelligenceAgent

router = APIRouter()


@router.get("/landscape")
async def trial_landscape(
    disease_area: str = Query(..., description="e.g. 'lung cancer', 'AML'")
):
    agent = ClinicalTrialIntelligenceAgent()
    return await agent.competitive_landscape(disease_area)


@router.get("/phase-progression")
async def phase_progression():
    agent = ClinicalTrialIntelligenceAgent()
    return await agent.phase_progression_tracker()


@router.get("/site-activations")
async def site_activations(state: str | None = None):
    agent = ClinicalTrialIntelligenceAgent()
    return await agent.site_activation_alerts(state)


@router.get("/match-hcps/{nct_id}")
async def match_hcps_to_trial(nct_id: str, limit: int = Query(20, le=50)):
    agent = ClinicalTrialIntelligenceAgent()
    return await agent.trial_hcp_matching(nct_id, limit)
