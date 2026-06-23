"""Messaging intelligence service — FastAPI app exposing message generation endpoints."""
from fastapi import FastAPI
from messaging.router import router

app = FastAPI(title="Oncology Messaging Intelligence")
app.include_router(router, prefix="/messaging")
