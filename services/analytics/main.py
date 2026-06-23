"""Analytics & Feedback service — port 8003."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.analytics.routers import feedback, conversions, funnel, cohort

app = FastAPI(title="Oncology Analytics Service", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(feedback.router)
app.include_router(conversions.router)
app.include_router(funnel.router)
app.include_router(cohort.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "analytics"}
