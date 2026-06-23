"""Research Intelligence Service — L5-L8, L13, L18 intelligence agents.

Layers served by this service:
  L5  Research Intelligence  — /research (synthesize, trends, evidence extraction)
  L5  Publication Intelligence — /publications (citation network, whitespace, velocity)
  L6  Clinical Intelligence   — /trials (landscape, phase progression, site activations)
  L7  Competitor Intelligence — /competitors (pipeline tracker, market signals)
  L8  Lead Generation        — /leads (publication leads, trial PIs, emerging KOLs)
  L13 Message Planner + QA   — /qa (message plan, QA review, batch review)
  L18 Executive Command Center — /executive (briefing, KPIs, top opportunities)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import get_settings
from .routers import research, publications, trials, competitors, leads, qa, executive

settings = get_settings()

app = FastAPI(
    title="Research Intelligence Service",
    version="2.0.0",
    description="AI agent layer: L5 Research/Evidence, L6 Clinical, L7 Competitor, L8 Leads, L13 QA/Planner, L18 Executive",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(research.router,     prefix="/research",     tags=["L5 Research Intelligence"])
app.include_router(publications.router, prefix="/publications", tags=["L5 Publication Intelligence"])
app.include_router(trials.router,       prefix="/trials",       tags=["L6 Clinical Intelligence"])
app.include_router(competitors.router,  prefix="/competitors",  tags=["L7 Competitor Intelligence"])
app.include_router(leads.router,        prefix="/leads",        tags=["L8 Lead Generation"])
app.include_router(qa.router,           prefix="/qa",           tags=["L13 QA & Message Planner"])
app.include_router(executive.router,    prefix="/executive",    tags=["L18 Executive Command Center"])


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "layers": ["L5", "L6", "L7", "L8", "L13", "L18"],
    }
