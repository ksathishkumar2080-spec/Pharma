"""Research Intelligence Service — synthesizes insights across all ingested sources."""
from fastapi import FastAPI
from .routers import research, publications, trials, competitors

app = FastAPI(title="Research Intelligence Service", version="1.0.0")
app.include_router(research.router,     prefix="/research",     tags=["Research"])
app.include_router(publications.router, prefix="/publications", tags=["Publication Intelligence"])
app.include_router(trials.router,       prefix="/trials",       tags=["Trial Intelligence"])
app.include_router(competitors.router,  prefix="/competitors",  tags=["Competitor Intelligence"])


@app.get("/health")
async def health():
    return {"status": "ok"}
