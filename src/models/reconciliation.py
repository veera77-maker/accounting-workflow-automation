"""Reconciliation data model."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ReconciliationStatus(str, Enum):
    EXACT_MATCH = "exact_match"
    AMOUNT_MISMATCH = "amount_mismatch"
    VENDOR_MISMATCH = "vendor_mismatch"
    DATE_MISMATCH = "date_mismatch"
    MISSING_RECEIPT = "missing_receipt"


class ReconciliationResult(BaseModel):
    """Result of matching an expense against a receipt."""

    expense_id: str
    receipt_id: Optional[str] = None
    status: ReconciliationStatus
    reason: str
    evidence: dict = {}
    amount_expected: Optional[float] = None
    amount_actual: Optional[float] = None
    vendor_expected: Optional[str] = None
    vendor_actual: Optional[str] = None
    date_expected: Optional[str] = None
    date_actual: Optional[str] = None
