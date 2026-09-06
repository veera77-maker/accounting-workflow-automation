"""Receipt data model."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class ReceiptLineItem(BaseModel):
    """A single line item on a receipt."""

    description: str
    amount: float = Field(ge=0)
    quantity: int = 1


class ReceiptRecord(BaseModel):
    """A receipt extracted from receipt images or synthetic data."""

    receipt_id: str
    expense_id: Optional[str] = None
    vendor: str
    amount: float = Field(ge=0)
    date: date
    line_items: list[ReceiptLineItem] = []
    raw_text: Optional[str] = None
    source_file: Optional[str] = None
