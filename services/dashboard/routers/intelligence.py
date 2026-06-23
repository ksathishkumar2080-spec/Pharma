"""Intelligence query endpoints — competitor analysis, KOL tiers, graph queries."""
from fastapi import APIRouter, Query, Depends
from shared.db import get_db
from shared.config import get_settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from neo4j import AsyncGraphDatabase

router = APIRouter()


@router.get("/kols")
async def list_kols(
    tier: str | None = None,
    specialty: str | None = None,
    state: str | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    filters = ["kol_tier IS NOT NULL"]
    params: dict = {"limit": limit}
    if tier:
        filters.append("kol_tier = :tier")
        params["tier"] = tier
    if specialty:
        filters.append("specialty ILIKE :specialty")
        params["specialty"] = f"%{specialty}%"
    if state:
        filters.append("state = :state")
        params["state"] = state

    where = " AND ".join(filters)
    rows = (await db.execute(text(f"""
        SELECT id, full_name, specialty, state, kol_tier,
               commercial_score, influence_score
        FROM hcps
        WHERE {where}
        ORDER BY influence_score DESC
        LIMIT :limit
    """), params)).fetchall()
    return [
        {"id": str(r[0]), "name": r[1], "specialty": r[2], "state": r[3],
         "kol_tier": r[4], "commercial_score": r[5], "influence_score": r[6]}
        for r in rows
    ]


@router.get("/competitors")
async def competitor_landscape(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(text(
        "SELECT id, name, disease_areas, pipeline_assets FROM competitors ORDER BY name"
    ))).fetchall()
    return [
        {"id": str(r[0]), "name": r[1], "disease_areas": r[2], "pipeline_assets": r[3]}
        for r in rows
    ]


@router.get("/graph/hcp/{hcp_id}")
async def hcp_knowledge_graph(hcp_id: str):
    settings = get_settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    async with driver.session() as gs:
        result = await gs.run("""
            MATCH (h:HCP {id: $id})
            OPTIONAL MATCH (h)-[r1:AUTHORED]->(p:Publication)
            OPTIONAL MATCH (h)-[r2:INVESTIGATES]->(t:Trial)
            OPTIONAL MATCH (h)-[r3:CO_AUTHOR]-(colleague:HCP)
            RETURN h, collect(DISTINCT p) as publications,
                   collect(DISTINCT t) as trials,
                   collect(DISTINCT colleague) as colleagues
        """, id=hcp_id)
        record = await result.single()
    await driver.close()
    if not record:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="HCP not found in graph")
    return {
        "hcp": dict(record["h"]),
        "publication_count": len(record["publications"]),
        "trial_count": len(record["trials"]),
        "colleague_count": len(record["colleagues"]),
    }


@router.get("/triggers/summary")
async def trigger_summary(db: AsyncSession = Depends(get_db)):
    row = (await db.execute(text("""
        SELECT
            event_type,
            COUNT(*) as count,
            MAX(occurred_at) as latest
        FROM trigger_events
        WHERE occurred_at >= NOW() - INTERVAL '30 days'
        GROUP BY event_type
        ORDER BY count DESC
    """))).fetchall()
    return [{"event_type": r[0], "count": r[1], "latest": str(r[2])} for r in row]
