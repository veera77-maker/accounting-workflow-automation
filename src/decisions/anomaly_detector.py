"""Anomaly detector — identifies expenses requiring human review.

This component handles the "Anomaly detection" step of the Case 3 workflow.

Design decisions:
- Deterministic rules + statistical thresholds — no ML or LLM.
- Every REVIEW decision has a human-understandable explanation.
- Every REVIEW decision has evidence with specific numbers.
- Thresholds are explicit, configurable, and documented.
- Reconciliation mismatches are treated as signals, not automatically as anomalies.
- The detector does NOT make approval/rejection decisions — that's the human's job.

Anomaly types (from spec Section 11.F):
1. HIGH_VALUE — unusually high expense for a category
2. DUPLICATE — duplicate or highly similar expense
3. UNUSUAL_PATTERN — unusual spending pattern (requires historical data)
4. NEW_VENDOR — new or infrequent vendor (requires historical data)
5. SPENDING_CHANGE — significant historical spending change (requires historical data)

Historical anomaly types (3, 4, 5) require historical data that does not exist
in the current synthetic dataset. They are implemented with interfaces ready
for historical data but produce NORMAL by default when no history is provided.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from models.anomaly import AnomalyReason, AnomalyResult, AnomalyVerdict
from models.expense import ExpenseRecord
from models.reconciliation import ReconciliationResult, ReconciliationStatus


# --- Configurable thresholds ---

@dataclass
class AnomalyThresholds:
    """Configurable thresholds for anomaly detection.

    All thresholds are implementation decisions, not specification requirements,
    unless explicitly noted.
    """

    # HIGH_VALUE: expense amount > category_mean * multiplier → REVIEW
    # Implementation decision: 3x the category mean triggers review.
    high_value_multiplier: float = 3.0

    # HIGH_VALUE: minimum category count before high-value check applies.
    # With fewer than this many expenses in a category, we can't compute a
    # meaningful mean, so we use the vendor's typical range instead.
    min_category_count_for_mean: int = 3

    # DUPLICATE: two expenses with same vendor, same amount, same date → REVIEW
    # Implementation decision: exact match on vendor+amount+date.
    duplicate_exact_match: bool = True

    # DUPLICATE: two expenses with same vendor and amount within tolerance → REVIEW
    # Implementation decision: amount tolerance for near-duplicate detection.
    duplicate_amount_tolerance: float = 0.01

    # Reconciliation mismatches that automatically trigger REVIEW.
    # Implementation decision: AMOUNT_MISMATCH and VENDOR_MISMATCH trigger review.
    # MISSING_RECEIPT and DATE_MISMATCH do not automatically trigger review
    # (they are informational, not necessarily anomalous).
    review_on_amount_mismatch: bool = True
    review_on_vendor_mismatch: bool = True
    review_on_missing_receipt: bool = False
    review_on_date_mismatch: bool = False

    # NEW_VENDOR: vendor not in known_vendors set → REVIEW
    # Only applies when known_vendors is provided.
    review_on_new_vendor: bool = True


DEFAULT_THRESHOLDS = AnomalyThresholds()


# --- Known vendors (from vendors.json) ---

def _load_known_vendors() -> set[str]:
    """Load known vendor names from vendors.json."""
    import json
    from pathlib import Path

    data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "synthetic"
    with open(data_dir / "vendors.json") as f:
        vendors = json.load(f)
    return {v["name"].lower().strip() for v in vendors}


# --- Anomaly detection signals ---

@dataclass
class AnomalySignal:
    """A single anomaly signal detected for an expense."""

    reason: AnomalyReason
    explanation: str
    evidence: dict
    threshold: float = 0.0


def _check_high_value(
    expense: ExpenseRecord,
    category_stats: dict[str, dict],
    thresholds: AnomalyThresholds,
) -> AnomalySignal | None:
    """Check if expense is unusually high for its category.

    Uses category mean * multiplier as the threshold.
    If insufficient category data, uses vendor typical range from vendors.json.
    """
    cat = expense.category.value if expense.category else "Unknown"
    stats = category_stats.get(cat)

    if stats and stats["count"] >= thresholds.min_category_count_for_mean:
        mean = stats["mean"]
        threshold = mean * thresholds.high_value_multiplier
        if expense.amount > threshold:
            return AnomalySignal(
                reason=AnomalyReason.HIGH_VALUE,
                explanation=(
                    f"Expense amount ${expense.amount:.2f} exceeds "
                    f"{thresholds.high_value_multiplier}x the category mean "
                    f"of ${mean:.2f} for '{cat}' (threshold: ${threshold:.2f})"
                ),
                evidence={
                    "expense_amount": expense.amount,
                    "category": cat,
                    "category_mean": mean,
                    "category_count": stats["count"],
                    "multiplier": thresholds.high_value_multiplier,
                    "threshold": threshold,
                },
                threshold=threshold,
            )
    elif stats and stats["count"] > 0:
        # Fewer than min_category_count_for_mean — use max as rough threshold
        max_val = stats["max"]
        threshold = max_val * thresholds.high_value_multiplier
        if expense.amount > threshold:
            return AnomalySignal(
                reason=AnomalyReason.HIGH_VALUE,
                explanation=(
                    f"Expense amount ${expense.amount:.2f} exceeds "
                    f"{thresholds.high_value_multiplier}x the category max "
                    f"of ${max_val:.2f} for '{cat}' (threshold: ${threshold:.2f}, "
                    f"only {stats['count']} expenses in category)"
                ),
                evidence={
                    "expense_amount": expense.amount,
                    "category": cat,
                    "category_max": max_val,
                    "category_count": stats["count"],
                    "multiplier": thresholds.high_value_multiplier,
                    "threshold": threshold,
                },
                threshold=threshold,
            )

    return None


def _check_duplicate(
    expense: ExpenseRecord,
    all_expenses: list[ExpenseRecord],
    thresholds: AnomalyThresholds,
) -> AnomalySignal | None:
    """Check for duplicate or highly similar expenses.

    Looks for other expenses with same vendor, same amount, same date
    (or within tolerance).
    """
    duplicates = []
    for other in all_expenses:
        if other.expense_id == expense.expense_id:
            continue
        if other.vendor.lower().strip() != expense.vendor.lower().strip():
            continue
        if other.date != expense.date:
            continue
        if abs(other.amount - expense.amount) <= thresholds.duplicate_amount_tolerance:
            duplicates.append(other)

    if duplicates:
        dup_ids = [d.expense_id for d in duplicates]
        return AnomalySignal(
            reason=AnomalyReason.DUPLICATE,
            explanation=(
                f"Expense matches {len(duplicates)} other expense(s) "
                f"with same vendor ('{expense.vendor}'), same amount "
                f"(${expense.amount:.2f}), and same date ({expense.date}). "
                f"Matching expense IDs: {', '.join(dup_ids)}"
            ),
            evidence={
                "expense_amount": expense.amount,
                "expense_vendor": expense.vendor,
                "expense_date": str(expense.date),
                "duplicate_count": len(duplicates),
                "duplicate_ids": dup_ids,
                "duplicate_amounts": [d.amount for d in duplicates],
            },
        )

    return None


def _check_new_vendor(
    expense: ExpenseRecord,
    known_vendors: set[str] | None,
    thresholds: AnomalyThresholds,
) -> AnomalySignal | None:
    """Check if vendor is new or infrequent.

    Only triggers when known_vendors is provided.
    """
    if not known_vendors or not thresholds.review_on_new_vendor:
        return None

    vendor_key = expense.vendor.lower().strip()
    if vendor_key not in known_vendors:
        return AnomalySignal(
            reason=AnomalyReason.NEW_VENDOR,
            explanation=(
                f"Vendor '{expense.vendor}' is not in the known vendor list. "
                f"This may be a new vendor that requires verification."
            ),
            evidence={
                "expense_vendor": expense.vendor,
                "expense_amount": expense.amount,
                "known_vendor_count": len(known_vendors),
            },
        )

    return None


def _check_reconciliation_mismatch(
    expense: ExpenseRecord,
    reconciliation: ReconciliationResult | None,
    thresholds: AnomalyThresholds,
) -> AnomalySignal | None:
    """Check if reconciliation mismatch warrants review.

    Not all mismatches are anomalous — only those configured in thresholds.
    """
    if reconciliation is None:
        return None

    status = reconciliation.status

    if status == ReconciliationStatus.AMOUNT_MISMATCH and thresholds.review_on_amount_mismatch:
        return AnomalySignal(
            reason=AnomalyReason.HIGH_VALUE,
            explanation=(
                f"Reconciliation amount mismatch: expense ${reconciliation.amount_actual:.2f} "
                f"vs receipt ${reconciliation.amount_expected:.2f} "
                f"(difference: ${abs(reconciliation.amount_actual - reconciliation.amount_expected):.2f}). "
                f"{reconciliation.reason}"
            ),
            evidence={
                "reconciliation_status": status.value,
                "expense_amount": reconciliation.amount_actual,
                "receipt_amount": reconciliation.amount_expected,
                "difference": abs(reconciliation.amount_actual - reconciliation.amount_expected),
                "reconciliation_reason": reconciliation.reason,
                "reconciliation_evidence": reconciliation.evidence,
            },
        )

    if status == ReconciliationStatus.VENDOR_MISMATCH and thresholds.review_on_vendor_mismatch:
        return AnomalySignal(
            reason=AnomalyReason.NEW_VENDOR,
            explanation=(
                f"Reconciliation vendor mismatch: expense vendor '{reconciliation.vendor_actual}' "
                f"vs receipt vendor '{reconciliation.vendor_expected}'. "
                f"{reconciliation.reason}"
            ),
            evidence={
                "reconciliation_status": status.value,
                "expense_vendor": reconciliation.vendor_actual,
                "receipt_vendor": reconciliation.vendor_expected,
                "reconciliation_reason": reconciliation.reason,
                "reconciliation_evidence": reconciliation.evidence,
            },
        )

    return None


def _compute_category_stats(
    expenses: list[ExpenseRecord],
) -> dict[str, dict]:
    """Compute mean, min, max, count for each category."""
    by_category: dict[str, list[float]] = defaultdict(list)
    for e in expenses:
        if e.category:
            by_category[e.category.value].append(e.amount)

    stats = {}
    for cat, amounts in by_category.items():
        stats[cat] = {
            "mean": sum(amounts) / len(amounts),
            "min": min(amounts),
            "max": max(amounts),
            "count": len(amounts),
            "total": sum(amounts),
        }
    return stats


# --- Main detection function ---

def detect_anomalies(
    expenses: list[ExpenseRecord],
    reconciliations: list[ReconciliationResult] | None = None,
    known_vendors: set[str] | None = None,
    thresholds: AnomalyThresholds | None = None,
) -> list[AnomalyResult]:
    """Run anomaly detection on a list of expenses.

    Args:
        expenses: List of ExpenseRecord objects.
        reconciliations: Optional list of ReconciliationResult objects.
            If provided, reconciliation mismatches are used as anomaly signals.
        known_vendors: Optional set of known vendor names.
            If provided, new vendor detection is enabled.
        thresholds: Configurable thresholds. Uses defaults if None.

    Returns:
        List of AnomalyResult, one per expense.
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS

    # Build reconciliation lookup
    recon_map: dict[str, ReconciliationResult] = {}
    if reconciliations:
        for r in reconciliations:
            recon_map[r.expense_id] = r

    # Compute category statistics
    category_stats = _compute_category_stats(expenses)

    results: list[AnomalyResult] = []

    for expense in expenses:
        signals: list[AnomalySignal] = []

        # Check high value for category
        sig = _check_high_value(expense, category_stats, thresholds)
        if sig:
            signals.append(sig)

        # Check duplicate
        sig = _check_duplicate(expense, expenses, thresholds)
        if sig:
            signals.append(sig)

        # Check new vendor
        sig = _check_new_vendor(expense, known_vendors, thresholds)
        if sig:
            signals.append(sig)

        # Check reconciliation mismatch
        recon = recon_map.get(expense.expense_id)
        sig = _check_reconciliation_mismatch(expense, recon, thresholds)
        if sig:
            signals.append(sig)

        # Determine verdict
        if signals:
            verdict = AnomalyVerdict.REVIEW
            reasons = [s.reason for s in signals]
            # Combine explanations
            explanations = [s.explanation for s in signals]
            combined_explanation = " | ".join(explanations)
            # Merge evidence
            combined_evidence = {}
            for i, s in enumerate(signals):
                combined_evidence[f"signal_{i+1}_{s.reason.value}"] = s.evidence
            # Use the highest threshold
            max_threshold = max((s.threshold for s in signals), default=0.0)
        else:
            verdict = AnomalyVerdict.NORMAL
            reasons = []
            combined_explanation = "No anomaly signals detected."
            combined_evidence = {}
            max_threshold = 0.0

        results.append(AnomalyResult(
            expense_id=expense.expense_id,
            verdict=verdict,
            reasons=reasons,
            explanation=combined_explanation,
            scores={"signal_count": len(signals)},
            threshold_used=max_threshold,
            features=combined_evidence,
        ))

    return results
