"""Reconciler — matches expense records against receipt records.

This component handles the "Expense / receipt reconciliation" step of the
Case 3 workflow. It compares each expense against its corresponding receipt
and produces a reconciliation result.

Design decisions:
- Deterministic rules only — no ML or LLM involved.
- Every expense gets a reconciliation result (no silent discards).
- Matching is done by receipt_reference (expense) → receipt_id (receipt).
- Comparison checks: vendor, amount, date.
- Evidence is provided as a dict with per-field match results.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path

from models.expense import ExpenseRecord
from models.receipt import ReceiptRecord
from models.reconciliation import ReconciliationResult, ReconciliationStatus


# Tolerance for amount comparison (abs diff ≤ this is considered a match).
AMOUNT_TOLERANCE = 0.01

# Threshold for vendor name similarity (0-1 scale).
VENDOR_SIMILARITY_THRESHOLD = 0.85


def _normalize_vendor(name: str) -> str:
    """Normalize a vendor name for comparison.

    Lowercases, strips whitespace, removes common suffixes.
    """
    normalized = name.lower().strip()
    for suffix in [" inc.", " inc", " llc", " llp", " corp.", " corp", " co.", " co"]:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
    return normalized


def _vendor_match(vendor_a: str, vendor_b: str) -> tuple[bool, str]:
    """Check if two vendor names match.

    Returns (match: bool, method: str) where method is "exact" or "similarity".
    """
    norm_a = _normalize_vendor(vendor_a)
    norm_b = _normalize_vendor(vendor_b)

    if norm_a == norm_b:
        return True, "exact"

    similarity = SequenceMatcher(None, norm_a, norm_b).ratio()
    if similarity >= VENDOR_SIMILARITY_THRESHOLD:
        return True, f"similarity({similarity:.2f})"

    return False, f"similarity({similarity:.2f})"


def _amount_match(amount_a: float, amount_b: float) -> bool:
    """Check if two amounts match within tolerance."""
    return abs(amount_a - amount_b) <= AMOUNT_TOLERANCE


def _date_match(date_a, date_b) -> bool:
    """Check if two dates match exactly."""
    return date_a == date_b


def reconcile_expenses(
    expenses: list[ExpenseRecord],
    receipts: list[ReceiptRecord],
) -> list[ReconciliationResult]:
    """Reconcile expense records against receipt records.

    Args:
        expenses: List of ExpenseRecord objects from the expense processor.
        receipts: List of ReceiptRecord objects from the receipt processor.

    Returns:
        List of ReconciliationResult, one per expense.
    """
    receipt_map: dict[str, ReceiptRecord] = {
        r.receipt_id: r for r in receipts
    }

    results: list[ReconciliationResult] = []

    for expense in expenses:
        receipt_ref = expense.receipt_reference

        # Case 1: No receipt reference → MISSING_RECEIPT
        if receipt_ref is None:
            results.append(ReconciliationResult(
                expense_id=expense.expense_id,
                receipt_id=None,
                status=ReconciliationStatus.MISSING_RECEIPT,
                reason="No receipt reference provided for this expense",
                evidence={
                    "expense_vendor": expense.vendor,
                    "expense_amount": expense.amount,
                    "expense_date": str(expense.date),
                },
            ))
            continue

        # Case 2: Receipt reference exists but receipt not found → MISSING_RECEIPT
        receipt = receipt_map.get(receipt_ref)
        if receipt is None:
            results.append(ReconciliationResult(
                expense_id=expense.expense_id,
                receipt_id=receipt_ref,
                status=ReconciliationStatus.MISSING_RECEIPT,
                reason=f"Receipt reference '{receipt_ref}' not found in receipt data",
                evidence={
                    "expense_vendor": expense.vendor,
                    "expense_amount": expense.amount,
                    "expense_date": str(expense.date),
                },
            ))
            continue

        # Case 3: Receipt found — compare fields
        vendor_ok, vendor_method = _vendor_match(expense.vendor, receipt.vendor)
        amount_ok = _amount_match(expense.amount, receipt.amount)
        date_ok = _date_match(expense.date, receipt.date)

        evidence = {
            "vendor_match": vendor_ok,
            "vendor_method": vendor_method,
            "amount_match": amount_ok,
            "date_match": date_ok,
            "expense_vendor": expense.vendor,
            "receipt_vendor": receipt.vendor,
            "expense_amount": expense.amount,
            "receipt_amount": receipt.amount,
            "expense_date": str(expense.date),
            "receipt_date": str(receipt.date),
        }

        # All match → EXACT_MATCH
        if vendor_ok and amount_ok and date_ok:
            results.append(ReconciliationResult(
                expense_id=expense.expense_id,
                receipt_id=receipt.receipt_id,
                status=ReconciliationStatus.EXACT_MATCH,
                reason="Vendor, amount, and date all match",
                evidence=evidence,
                amount_expected=receipt.amount,
                amount_actual=expense.amount,
                vendor_expected=receipt.vendor,
                vendor_actual=expense.vendor,
                date_expected=str(receipt.date),
                date_actual=str(expense.date),
            ))
            continue

        # Determine primary mismatch reason
        # Priority: amount > vendor > date
        if not amount_ok:
            results.append(ReconciliationResult(
                expense_id=expense.expense_id,
                receipt_id=receipt.receipt_id,
                status=ReconciliationStatus.AMOUNT_MISMATCH,
                reason=(
                    f"Amount mismatch: expense ${expense.amount:.2f} "
                    f"vs receipt ${receipt.amount:.2f} "
                    f"(difference: ${abs(expense.amount - receipt.amount):.2f})"
                ),
                evidence=evidence,
                amount_expected=receipt.amount,
                amount_actual=expense.amount,
                vendor_expected=receipt.vendor,
                vendor_actual=expense.vendor,
                date_expected=str(receipt.date),
                date_actual=str(expense.date),
            ))
        elif not vendor_ok:
            results.append(ReconciliationResult(
                expense_id=expense.expense_id,
                receipt_id=receipt.receipt_id,
                status=ReconciliationStatus.VENDOR_MISMATCH,
                reason=(
                    f"Vendor mismatch: expense '{expense.vendor}' "
                    f"vs receipt '{receipt.vendor}'"
                ),
                evidence=evidence,
                amount_expected=receipt.amount,
                amount_actual=expense.amount,
                vendor_expected=receipt.vendor,
                vendor_actual=expense.vendor,
                date_expected=str(receipt.date),
                date_actual=str(expense.date),
            ))
        else:
            results.append(ReconciliationResult(
                expense_id=expense.expense_id,
                receipt_id=receipt.receipt_id,
                status=ReconciliationStatus.DATE_MISMATCH,
                reason=(
                    f"Date mismatch: expense {expense.date} "
                    f"vs receipt {receipt.date}"
                ),
                evidence=evidence,
                amount_expected=receipt.amount,
                amount_actual=expense.amount,
                vendor_expected=receipt.vendor,
                vendor_actual=expense.vendor,
                date_expected=str(receipt.date),
                date_actual=str(expense.date),
            ))

    return results
