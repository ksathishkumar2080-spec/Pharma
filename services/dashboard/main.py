"""Executive Command Center — main FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dashboard.routers import (
    hcps, trials, publications, scoring, triggers,
    search, territory, intelligence, semantic_search,
)

app = FastAPI(
    title="Oncology Intelligence OS",
    description="Internal intelligence platform for oncology commercial teams",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hcps.router,             prefix="/api/hcps",             tags=["HCPs"])
app.include_router(trials.router,           prefix="/api/trials",           tags=["Trials"])
app.include_router(publications.router,     prefix="/api/publications",     tags=["Publications"])
app.include_router(scoring.router,          prefix="/api/scoring",          tags=["Scoring"])
app.include_router(triggers.router,         prefix="/api/triggers",         tags=["Triggers"])
app.include_router(search.router,           prefix="/api/search",           tags=["Full-text Search"])
app.include_router(territory.router,        prefix="/api/territory",        tags=["Territory"])
app.include_router(intelligence.router,     prefix="/api/intelligence",     tags=["Intelligence"])
app.include_router(semantic_search.router,  prefix="/api/semantic",         tags=["Semantic Search"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/api/overview")
async def overview():
    """Executive dashboard summary."""
    from shared.db import get_engine
    from sqlalchemy import text
    async with get_engine().connect() as conn:
        stats = (await conn.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM hcps) AS hcp_count,
                (SELECT COUNT(*) FROM publications) AS publication_count,
                (SELECT COUNT(*) FROM clinical_trials) AS trial_count,
                (SELECT COUNT(*) FROM trigger_events WHERE processed = FALSE) AS pending_triggers,
                (SELECT COUNT(*) FROM outreach_messages WHERE sent_at IS NULL) AS unsent_messages,
                (SELECT COUNT(DISTINCT state) FROM hcps WHERE state IS NOT NULL) AS territories_covered
        """))).fetchone()
    return {
        "hcp_count": stats[0],
        "publication_count": stats[1],
        "trial_count": stats[2],
        "pending_triggers": stats[3],
        "unsent_messages": stats[4],
        "territories_covered": stats[5],
    }
