"""Accounting data model — ledger entries and P&L."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LedgerEntryStatus(str, Enum):
    PENDING = "pending"
    POSTED = "posted"
    HUMAN_REVIEWED = "human_reviewed"


class LedgerEntry(BaseModel):
    """A single accounting ledger entry."""

    entry_id: str
    expense_id: str
    client_id: str
    category: str
    amount: float = Field(ge=0)
    description: str
    vendor: str
    date: date
    status: LedgerEntryStatus = LedgerEntryStatus.PENDING
    month: str  # YYYY-MM
    source: str = "auto"  # "auto" or "human_review"


class PLLineItem(BaseModel):
    """A single line in the P&L report."""

    category: str
    total: float = 0.0
    count: int = 0


class PLReport(BaseModel):
    """Monthly Profit & Loss expense summary."""

    client_id: str
    month: str
    generated_at: str
    total_expenses: float = 0.0
    line_items: list[PLLineItem] = []
    entry_count: int = 0
