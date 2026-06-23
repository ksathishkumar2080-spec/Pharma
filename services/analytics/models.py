from __future__ import annotations
from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class FeedbackType(str, Enum):
    thumbs_up = "thumbs_up"
    thumbs_down = "thumbs_down"
    flagged = "flagged"


class FeedbackTarget(str, Enum):
    message = "message"
    nba = "nba"
    hcp_score = "hcp_score"
    territory = "territory"


class RepFeedbackIn(BaseModel):
    target_type: FeedbackTarget
    target_id: str
    feedback: FeedbackType
    rep_id: str
    note: Optional[str] = None


class ConversionEventIn(BaseModel):
    message_id: str
    event: str  # sent | opened | replied | meeting_booked
    rep_id: str
    occurred_at: Optional[datetime] = None
