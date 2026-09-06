"""Anomaly detection data model."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class AnomalyVerdict(str, Enum):
    NORMAL = "normal"
    REVIEW = "review"


class AnomalyReason(str, Enum):
    HIGH_VALUE = "high_value_for_category"
    DUPLICATE = "duplicate_or_similar_expense"
    UNUSUAL_PATTERN = "unusual_spending_pattern"
    NEW_VENDOR = "new_or_infrequent_vendor"
    SPENDING_CHANGE = "significant_historical_spending_change"


class AnomalyResult(BaseModel):
    """Result of anomaly detection for an expense."""

    expense_id: str
    verdict: AnomalyVerdict
    reasons: list[AnomalyReason] = []
    explanation: str = ""
    scores: dict = {}
    threshold_used: float = 0.0
    features: dict = {}
