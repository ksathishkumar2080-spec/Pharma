"""Executive Command Center — main FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dashboard.routers import hcps, trials, publications, scoring, triggers, search

app = FastAPI(
    title="Oncology Intelligence OS",
    description="Internal intelligence platform for oncology commercial teams",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hcps.router, prefix="/api/hcps", tags=["HCPs"])
app.include_router(trials.router, prefix="/api/trials", tags=["Trials"])
app.include_router(publications.router, prefix="/api/publications", tags=["Publications"])
app.include_router(scoring.router, prefix="/api/scoring", tags=["Scoring"])
app.include_router(triggers.router, prefix="/api/triggers", tags=["Triggers"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])


@app.get("/health")
async def health():
    return {"status": "ok"}
