"""Human review data model."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ReviewDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    CORRECT = "correct"


class HumanReviewItem(BaseModel):
    """An item in the human review queue."""

    review_id: str
    expense_id: str
    anomaly_reasons: list[str] = []
    evidence: dict = {}
    queued_at: str = ""


class HumanReviewDecision(BaseModel):
    """A human reviewer's decision on an expense."""

    review_id: str
    expense_id: str
    reviewer: str
    decision: ReviewDecision
    reason: str
    corrected_amount: Optional[float] = None
    corrected_category: Optional[str] = None
    corrected_vendor: Optional[str] = None
    decided_at: str = ""
