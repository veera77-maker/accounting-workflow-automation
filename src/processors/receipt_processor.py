"""Receipt processor — extracts structured data from receipt files.

This component handles the "Receipt processing" step of the Case 3 workflow.
It reads receipt data and produces validated ReceiptRecord objects.

Design decisions:
- Current implementation reads from JSON (synthetic data).
- The interface is designed so that an OCR backend can be substituted later
  by implementing a different _load_raw_receipts function.
- Receipt processing is kept separate from reconciliation (per spec Section 11.C).
- Errors are collected, not silently discarded.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from models.receipt import ReceiptLineItem, ReceiptRecord


class ReceiptProcessingError:
    """Records a single receipt-level processing failure."""

    def __init__(self, receipt_index: int, raw_receipt: dict, error_message: str):
        self.receipt_index = receipt_index
        self.raw_receipt = raw_receipt
        self.error_message = error_message

    def to_dict(self) -> dict:
        return {
            "receipt_index": self.receipt_index,
            "raw_receipt": self.raw_receipt,
            "error": self.error_message,
        }


class ReceiptProcessorResult:
    """Output of the receipt processor — records plus any errors."""

    def __init__(
        self,
        records: list[ReceiptRecord],
        errors: list[ReceiptProcessingError],
    ):
        self.records = records
        self.errors = errors

    @property
    def success_count(self) -> int:
        return len(self.records)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def to_dict(self) -> dict:
        return {
            "records": [r.model_dump(mode="json") for r in self.records],
            "errors": [e.to_dict() for e in self.errors],
            "success_count": self.success_count,
            "error_count": self.error_count,
        }


def _parse_date(value: str) -> date:
    """Parse a date string in YYYY-MM-DD format."""
    parts = value.strip().split("-")
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


def _load_raw_receipts(json_path: Path) -> list[dict]:
    """Load raw receipt data from a JSON file.

    This is the function to replace when adding OCR support.
    """
    with open(json_path) as f:
        return json.load(f)


def process_receipts(json_path: Path | str) -> ReceiptProcessorResult:
    """Read receipt data from a JSON file and return validated ReceiptRecord objects.

    Args:
        json_path: Path to the receipt JSON file.

    Returns:
        ReceiptProcessorResult with records and errors.
    """
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"Receipt file not found: {json_path}")

    raw_receipts = _load_raw_receipts(json_path)

    records: list[ReceiptRecord] = []
    errors: list[ReceiptProcessingError] = []

    for idx, raw in enumerate(raw_receipts):
        try:
            receipt_id = str(raw.get("receipt_id", "")).strip()
            if not receipt_id:
                raise ValueError("Missing receipt_id")

            vendor = str(raw.get("vendor", "")).strip()
            if not vendor:
                raise ValueError("Missing vendor")

            amount_raw = raw.get("amount")
            if amount_raw is None:
                raise ValueError("Missing amount")
            amount = float(amount_raw)
            if amount < 0:
                raise ValueError(f"Negative amount: {amount}")

            date_str = str(raw.get("date", "")).strip()
            if not date_str:
                raise ValueError("Missing date")
            parsed_date = _parse_date(date_str)

            line_items: list[ReceiptLineItem] = []
            for li in raw.get("line_items", []):
                line_items.append(ReceiptLineItem(
                    description=str(li.get("description", "")),
                    amount=float(li.get("amount", 0)),
                    quantity=int(li.get("quantity", 1)),
                ))

            record = ReceiptRecord(
                receipt_id=receipt_id,
                vendor=vendor,
                amount=amount,
                date=parsed_date,
                line_items=line_items,
                source_file=str(json_path),
            )
            records.append(record)

        except (ValueError, TypeError, KeyError) as exc:
            errors.append(ReceiptProcessingError(
                receipt_index=idx,
                raw_receipt=raw,
                error_message=str(exc),
            ))

    return ReceiptProcessorResult(records, errors)
