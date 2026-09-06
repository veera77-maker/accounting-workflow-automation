"""Expense data model."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ExpenseCategory(str, Enum):
    TRAVEL = "Travel"
    MEALS_ENTERTAINMENT = "Meals & Entertainment"
    SOFTWARE = "Software"
    OFFICE_SUPPLIES = "Office Supplies"
    PROFESSIONAL_SERVICES = "Professional Services"
    UTILITIES = "Utilities"
    MARKETING = "Marketing"
    MISCELLANEOUS = "Miscellaneous"


class ExpenseStatus(str, Enum):
    PENDING = "pending"
    MATCHED = "matched"
    RECONCILED = "reconciled"
    ANOMALOUS = "anomalous"
    HUMAN_REVIEW = "human_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CORRECTED = "corrected"
    POSTED = "posted"


class ExpenseRecord(BaseModel):
    """A single expense line item extracted from the client spreadsheet."""

    expense_id: str
    client_id: str
    employee: str
    date: date
    description: str
    vendor: str
    amount: float = Field(ge=0)
    category: Optional[ExpenseCategory] = None
    receipt_reference: Optional[str] = None
    status: ExpenseStatus = ExpenseStatus.PENDING
    month: str  # YYYY-MM format
