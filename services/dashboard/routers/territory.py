from fastapi import APIRouter, Query, Depends
from scoring.territory_engine import TerritoryOpportunityEngine
from scoring.nba_engine import NextBestActionEngine
from scoring.referral_analyzer import ReferralAnalyzer

router = APIRouter()


@router.get("/")
async def territory_scores():
    engine = TerritoryOpportunityEngine()
    return await engine.score_territories()


@router.get("/{state}/accounts")
async def territory_accounts(state: str, limit: int = Query(20, le=100)):
    engine = TerritoryOpportunityEngine()
    return await engine.top_accounts_in_territory(state.upper(), limit)


@router.get("/nba")
async def next_best_actions(
    state: str | None = None,
    limit: int = Query(50, le=200),
):
    engine = NextBestActionEngine()
    return await engine.get_actions_for_territory(state, limit)


@router.get("/network/{hcp_id}")
async def referral_network(hcp_id: str, depth: int = Query(2, le=3)):
    analyzer = ReferralAnalyzer()
    return await analyzer.get_referral_network(hcp_id, depth)
