"""P&L generator — aggregates ledger entries into monthly P&L reports."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.models.accounting import LedgerEntry, PLLineItem, PLReport


class PLGeneratorError(Exception):
    """Raised when P&L generation fails."""


class PLGenerator:
    """Generates monthly P&L expense reports from ledger entries.

    Aggregates posted ledger entries into category totals and a
    monthly summary. Does not compute P&L from raw input — only
    from accounting records.
    """

    def generate(
        self,
        entries: list[LedgerEntry],
        client_id: str,
        month: str,
    ) -> PLReport:
        """Generate a monthly P&L report from ledger entries.

        Args:
            entries: Ledger entries to aggregate (already posted).
            client_id: Client identifier.
            month: Reporting month in YYYY-MM format.

        Returns:
            PLReport with line items by category and totals.
        """
        if not entries:
            return PLReport(
                client_id=client_id,
                month=month,
                generated_at=datetime.now().isoformat(),
                total_expenses=0.0,
                line_items=[],
                entry_count=0,
            )

        category_data: dict[str, dict[str, float]] = {}
        for entry in entries:
            cat = entry.category
            if cat not in category_data:
                category_data[cat] = {"total": 0.0, "count": 0.0}
            category_data[cat]["total"] += entry.amount
            category_data[cat]["count"] += 1

        line_items: list[PLLineItem] = []
        total_expenses = 0.0

        for cat in sorted(category_data.keys()):
            data = category_data[cat]
            line_item = PLLineItem(
                category=cat,
                total=round(data["total"], 2),
                count=int(data["count"]),
            )
            line_items.append(line_item)
            total_expenses += data["total"]

        return PLReport(
            client_id=client_id,
            month=month,
            generated_at=datetime.now().isoformat(),
            total_expenses=round(total_expenses, 2),
            line_items=line_items,
            entry_count=len(entries),
        )

    def generate_from_ledger(
        self,
        ledger_entries: list[LedgerEntry],
        client_id: str,
        month: str,
    ) -> PLReport:
        """Generate P&L from all ledger entries for a given month and client.

        Filters entries by client_id and month before aggregating.
        """
        filtered = [
            e for e in ledger_entries
            if e.client_id == client_id and e.month == month
        ]
        return self.generate(filtered, client_id, month)
