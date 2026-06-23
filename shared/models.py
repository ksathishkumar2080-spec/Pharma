from datetime import datetime, date
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class HCP(BaseModel):
    id: Optional[UUID] = None
    full_name: str
    npi: Optional[str] = None
    specialty: Optional[str] = None
    subspecialty: Optional[str] = None
    institution_id: Optional[UUID] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "US"
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_handle: Optional[str] = None
    commercial_score: float = 0.0
    opportunity_score: float = 0.0
    influence_score: float = 0.0
    kol_tier: Optional[str] = None


class Publication(BaseModel):
    id: Optional[UUID] = None
    pubmed_id: Optional[str] = None
    title: str
    abstract: Optional[str] = None
    journal: Optional[str] = None
    published_at: Optional[date] = None
    doi: Optional[str] = None
    citation_count: int = 0
    disease_areas: list[str] = Field(default_factory=list)
    biomarkers: list[str] = Field(default_factory=list)
    therapies: list[str] = Field(default_factory=list)


class ClinicalTrial(BaseModel):
    id: Optional[UUID] = None
    nct_id: str
    title: str
    phase: Optional[str] = None
    status: Optional[str] = None
    sponsor: Optional[str] = None
    conditions: list[str] = Field(default_factory=list)
    interventions: list[str] = Field(default_factory=list)


class TriggerEvent(BaseModel):
    id: Optional[UUID] = None
    hcp_id: UUID
    event_type: str
    event_data: dict = Field(default_factory=dict)
    source: Optional[str] = None
    occurred_at: Optional[datetime] = None


class OutreachMessage(BaseModel):
    id: Optional[UUID] = None
    hcp_id: UUID
    channel: str
    subject: Optional[str] = None
    body: str
    evidence_citations: list[dict] = Field(default_factory=list)
    grammar_validated: bool = False
