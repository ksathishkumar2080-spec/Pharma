"""Dashboard API gateway — mounts all service routers."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import get_settings
from services.compliance.middleware import ComplianceAuditMiddleware
from services.dashboard.routers import (
    hcps, trials, publications, scoring, triggers,
    search, semantic_search, territory, intelligence,
    relationship, messages, system, biomarkers,
)
from services.compliance.router import router as compliance_router

settings = get_settings()
app = FastAPI(title="Oncology Intelligence Dashboard", version="0.4.0")

app.add_middleware(ComplianceAuditMiddleware, service_name="dashboard")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(hcps.router)
app.include_router(trials.router)
app.include_router(publications.router)
app.include_router(scoring.router)
app.include_router(triggers.router)
app.include_router(search.router)
app.include_router(semantic_search.router)
app.include_router(territory.router)
app.include_router(intelligence.router)
app.include_router(relationship.router)
app.include_router(messages.router)
app.include_router(system.router)
app.include_router(biomarkers.router)
app.include_router(compliance_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.4.0"}
