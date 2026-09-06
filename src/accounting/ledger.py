"""Simulated accounting ledger — maintains local accounting records."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.models.accounting import LedgerEntry, LedgerEntryStatus
from src.models.expense import ExpenseRecord
from src.models.anomaly import AnomalyResult, AnomalyVerdict
from src.models.human_review import HumanReviewDecision, ReviewDecision


class AccountingError(Exception):
    """Raised when an accounting operation fails."""


class Ledger:
    """Simulated accounting ledger.

    Maintains local accounting records. Clean expenses are posted
    automatically. Human-reviewed expenses are posted after the human
    decision. Rejected expenses are not posted.
    """

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []
        self._next_seq: int = 1

    def _generate_entry_id(self) -> str:
        entry_id = f"LED-{self._next_seq:06d}"
        self._next_seq += 1
        return entry_id

    def post_clean_expenses(
        self,
        expenses: list[ExpenseRecord],
        anomaly_results: list[AnomalyResult],
    ) -> list[LedgerEntry]:
        """Post expenses with NORMAL verdict as POSTED.

        Expenses flagged as REVIEW are skipped — they go to human review.
        """
        anomaly_map = {r.expense_id: r for r in anomaly_results}
        posted: list[LedgerEntry] = []

        for expense in expenses:
            anomaly = anomaly_map.get(expense.expense_id)
            if anomaly and anomaly.verdict == AnomalyVerdict.REVIEW:
                continue

            entry = LedgerEntry(
                entry_id=self._generate_entry_id(),
                expense_id=expense.expense_id,
                client_id=expense.client_id,
                category=expense.category.value if expense.category else "Uncategorized",
                amount=expense.amount,
                description=expense.description,
                vendor=expense.vendor,
                date=expense.date,
                status=LedgerEntryStatus.POSTED,
                month=expense.month,
                source="auto",
            )
            self._entries.append(entry)
            posted.append(entry)

        return posted

    def post_human_reviewed(
        self,
        expenses: list[ExpenseRecord],
        review_decisions: list[HumanReviewDecision],
    ) -> list[LedgerEntry]:
        """Post human-reviewed expenses based on reviewer decisions.

        APPROVE → posted with source="human_review"
        CORRECT → posted with corrected values, source="human_review"
        REJECT → not posted
        """
        expense_map = {e.expense_id: e for e in expenses}
        decision_map = {d.expense_id: d for d in review_decisions}
        posted: list[LedgerEntry] = []

        for expense in expenses:
            decision = decision_map.get(expense.expense_id)
            if not decision:
                continue

            if decision.decision == ReviewDecision.REJECT:
                continue

            amount = expense.amount
            category = expense.category.value if expense.category else "Uncategorized"
            vendor = expense.vendor

            if decision.decision == ReviewDecision.CORRECT:
                if decision.corrected_amount is not None:
                    amount = decision.corrected_amount
                if decision.corrected_category is not None:
                    category = decision.corrected_category
                if decision.corrected_vendor is not None:
                    vendor = decision.corrected_vendor

            entry = LedgerEntry(
                entry_id=self._generate_entry_id(),
                expense_id=expense.expense_id,
                client_id=expense.client_id,
                category=category,
                amount=amount,
                description=expense.description,
                vendor=vendor,
                date=expense.date,
                status=LedgerEntryStatus.HUMAN_REVIEWED,
                month=expense.month,
                source="human_review",
            )
            self._entries.append(entry)
            posted.append(entry)

        return posted

    def get_entries(
        self,
        month: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> list[LedgerEntry]:
        """Retrieve ledger entries, optionally filtered by month and/or client."""
        results = self._entries
        if month:
            results = [e for e in results if e.month == month]
        if client_id:
            results = [e for e in results if e.client_id == client_id]
        return list(results)

    def get_all_entries(self) -> list[LedgerEntry]:
        """Retrieve all ledger entries."""
        return list(self._entries)

    def get_total_by_category(
        self,
        month: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> dict[str, float]:
        """Get total expenses grouped by category."""
        entries = self.get_entries(month=month, client_id=client_id)
        totals: dict[str, float] = {}
        for entry in entries:
            totals[entry.category] = totals.get(entry.category, 0.0) + entry.amount
        return totals

    def get_entry_count(
        self,
        month: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> int:
        """Count ledger entries matching filters."""
        return len(self.get_entries(month=month, client_id=client_id))

    def to_dict(self) -> dict:
        """Serialize ledger state."""
        return {
            "entry_count": len(self._entries),
            "entries": [e.model_dump(mode="json") for e in self._entries],
        }
