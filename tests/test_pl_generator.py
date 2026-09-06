"""Tests for the P&L generator."""

from __future__ import annotations

import pytest
from datetime import date

from src.accounting.pl_generator import PLGenerator, PLGeneratorError
from src.models.accounting import LedgerEntry, LedgerEntryStatus, PLReport, PLLineItem


def _make_entry(
    entry_id: str = "LED-000001",
    expense_id: str = "EXP-0001",
    client_id: str = "CLIENT-001",
    category: str = "Travel",
    amount: float = 150.0,
    month: str = "2026-08",
    source: str = "auto",
    status: LedgerEntryStatus = LedgerEntryStatus.POSTED,
) -> LedgerEntry:
    return LedgerEntry(
        entry_id=entry_id,
        expense_id=expense_id,
        client_id=client_id,
        category=category,
        amount=amount,
        description=f"Expense {expense_id}",
        vendor="Test Vendor",
        date=date(2026, 8, 15),
        status=status,
        month=month,
        source=source,
    )


class TestPLGeneratorEmpty:
    def test_empty_entries(self):
        gen = PLGenerator()
        report = gen.generate([], "CLIENT-001", "2026-08")
        assert report.total_expenses == 0.0
        assert report.line_items == []
        assert report.entry_count == 0
        assert report.client_id == "CLIENT-001"
        assert report.month == "2026-08"

    def test_empty_has_generated_at(self):
        gen = PLGenerator()
        report = gen.generate([], "CLIENT-001", "2026-08")
        assert report.generated_at != ""


class TestPLGeneratorSingleCategory:
    def test_single_entry(self):
        gen = PLGenerator()
        entries = [_make_entry(amount=100.0, category="Travel")]
        report = gen.generate(entries, "CLIENT-001", "2026-08")
        assert report.total_expenses == 100.0
        assert report.entry_count == 1
        assert len(report.line_items) == 1
        assert report.line_items[0].category == "Travel"
        assert report.line_items[0].total == 100.0
        assert report.line_items[0].count == 1

    def test_multiple_same_category(self):
        gen = PLGenerator()
        entries = [
            _make_entry("LED-000001", amount=100.0, category="Travel"),
            _make_entry("LED-000002", amount=200.0, category="Travel"),
            _make_entry("LED-000003", amount=50.0, category="Travel"),
        ]
        report = gen.generate(entries, "CLIENT-001", "2026-08")
        assert report.total_expenses == 350.0
        assert report.entry_count == 3
        assert len(report.line_items) == 1
        assert report.line_items[0].total == 350.0
        assert report.line_items[0].count == 3


class TestPLGeneratorMultipleCategories:
    def test_two_categories(self):
        gen = PLGenerator()
        entries = [
            _make_entry("LED-000001", amount=100.0, category="Travel"),
            _make_entry("LED-000002", amount=200.0, category="Software"),
        ]
        report = gen.generate(entries, "CLIENT-001", "2026-08")
        assert report.total_expenses == 300.0
        assert report.entry_count == 2
        assert len(report.line_items) == 2
        # Line items are sorted alphabetically
        assert report.line_items[0].category == "Software"
        assert report.line_items[0].total == 200.0
        assert report.line_items[1].category == "Travel"
        assert report.line_items[1].total == 100.0

    def test_categories_sorted(self):
        gen = PLGenerator()
        entries = [
            _make_entry("LED-000001", amount=50.0, category="Utilities"),
            _make_entry("LED-000002", amount=50.0, category="Office Supplies"),
            _make_entry("LED-000003", amount=50.0, category="Marketing"),
        ]
        report = gen.generate(entries, "CLIENT-001", "2026-08")
        cats = [li.category for li in report.line_items]
        assert cats == sorted(cats)

    def test_many_categories(self):
        gen = PLGenerator()
        categories = [
            "Travel", "Meals & Entertainment", "Software",
            "Office Supplies", "Professional Services", "Utilities",
            "Marketing", "Miscellaneous",
        ]
        entries = [
            _make_entry(f"LED-{i:06d}", amount=float(i * 10), category=cat)
            for i, cat in enumerate(categories, 1)
        ]
        report = gen.generate(entries, "CLIENT-001", "2026-08")
        assert report.entry_count == 8
        assert len(report.line_items) == 8
        total = sum(e.amount for e in entries)
        assert report.total_expenses == total


class TestPLGeneratorAmounts:
    def test_total_is_sum(self):
        gen = PLGenerator()
        entries = [
            _make_entry("LED-000001", amount=123.45, category="Travel"),
            _make_entry("LED-000002", amount=67.89, category="Software"),
            _make_entry("LED-000003", amount=234.56, category="Travel"),
        ]
        report = gen.generate(entries, "CLIENT-001", "2026-08")
        assert report.total_expenses == 425.9

    def test_amounts_rounded_to_two_decimals(self):
        gen = PLGenerator()
        entries = [
            _make_entry("LED-000001", amount=33.334, category="Travel"),
            _make_entry("LED-000002", amount=66.667, category="Travel"),
        ]
        report = gen.generate(entries, "CLIENT-001", "2026-08")
        # 33.334 + 66.667 = 100.001, rounded to 2 decimals = 100.0
        assert report.total_expenses == 100.0
        assert report.line_items[0].total == 100.0

    def test_zero_amounts(self):
        gen = PLGenerator()
        entries = [_make_entry(amount=0.0, category="Travel")]
        report = gen.generate(entries, "CLIENT-001", "2026-08")
        assert report.total_expenses == 0.0
        assert report.line_items[0].total == 0.0


class TestPLGeneratorFields:
    def test_report_fields(self):
        gen = PLGenerator()
        entries = [_make_entry(amount=100.0)]
        report = gen.generate(entries, "CLIENT-002", "2026-09")
        assert report.client_id == "CLIENT-002"
        assert report.month == "2026-09"
        assert report.generated_at != ""
        assert isinstance(report.generated_at, str)

    def test_line_item_fields(self):
        gen = PLGenerator()
        entries = [_make_entry(amount=100.0, category="Software")]
        report = gen.generate(entries, "CLIENT-001", "2026-08")
        li = report.line_items[0]
        assert li.category == "Software"
        assert li.total == 100.0
        assert li.count == 1


class TestPLGeneratorFromLedger:
    def test_filters_by_client(self):
        gen = PLGenerator()
        entries = [
            _make_entry("LED-000001", client_id="CLIENT-001", month="2026-08", amount=100.0),
            _make_entry("LED-000002", client_id="CLIENT-002", month="2026-08", amount=200.0),
            _make_entry("LED-000003", client_id="CLIENT-001", month="2026-08", amount=50.0),
        ]
        report = gen.generate_from_ledger(entries, "CLIENT-001", "2026-08")
        assert report.total_expenses == 150.0
        assert report.entry_count == 2

    def test_filters_by_month(self):
        gen = PLGenerator()
        entries = [
            _make_entry("LED-000001", month="2026-08", amount=100.0),
            _make_entry("LED-000002", month="2026-09", amount=200.0),
        ]
        report = gen.generate_from_ledger(entries, "CLIENT-001", "2026-08")
        assert report.total_expenses == 100.0
        assert report.entry_count == 1

    def test_filters_by_client_and_month(self):
        gen = PLGenerator()
        entries = [
            _make_entry("LED-000001", client_id="CLIENT-001", month="2026-08", amount=100.0),
            _make_entry("LED-000002", client_id="CLIENT-001", month="2026-09", amount=200.0),
            _make_entry("LED-000003", client_id="CLIENT-002", month="2026-08", amount=300.0),
        ]
        report = gen.generate_from_ledger(entries, "CLIENT-001", "2026-08")
        assert report.total_expenses == 100.0
        assert report.entry_count == 1

    def test_no_matching_entries(self):
        gen = PLGenerator()
        entries = [
            _make_entry("LED-000001", client_id="CLIENT-002", month="2026-09"),
        ]
        report = gen.generate_from_ledger(entries, "CLIENT-001", "2026-08")
        assert report.total_expenses == 0.0
        assert report.entry_count == 0
        assert report.line_items == []


class TestPLGeneratorSyntheticData:
    def test_with_typical_expenses(self):
        gen = PLGenerator()
        entries = [
            _make_entry("LED-000001", amount=450.0, category="Travel"),
            _make_entry("LED-000002", amount=85.50, category="Meals & Entertainment"),
            _make_entry("LED-000003", amount=120.0, category="Software"),
            _make_entry("LED-000004", amount=45.0, category="Office Supplies"),
            _make_entry("LED-000005", amount=300.0, category="Professional Services"),
            _make_entry("LED-000006", amount=200.0, category="Utilities"),
            _make_entry("LED-000007", amount=150.0, category="Marketing"),
            _make_entry("LED-000008", amount=2850.0, category="Meals & Entertainment"),
        ]
        report = gen.generate(entries, "CLIENT-001", "2026-08")
        assert report.entry_count == 8
        assert report.total_expenses == 4200.5
        assert len(report.line_items) == 7
        # Verify all categories present
        cats = {li.category for li in report.line_items}
        expected = {
            "Travel", "Meals & Entertainment", "Software",
            "Office Supplies", "Professional Services", "Utilities",
            "Marketing",
        }
        assert cats == expected


class TestPLGeneratorDeterministic:
    def test_same_input_same_output(self):
        gen = PLGenerator()
        entries = [
            _make_entry("LED-000001", amount=100.0, category="Travel"),
            _make_entry("LED-000002", amount=200.0, category="Software"),
        ]
        r1 = gen.generate(entries, "CLIENT-001", "2026-08")
        r2 = gen.generate(entries, "CLIENT-001", "2026-08")
        assert r1.total_expenses == r2.total_expenses
        assert r1.entry_count == r2.entry_count
        assert len(r1.line_items) == len(r2.line_items)


class TestPLGeneratorEdgeCases:
    def test_single_category_multiple_entries(self):
        gen = PLGenerator()
        entries = [_make_entry(amount=10.0, category="Travel") for _ in range(100)]
        report = gen.generate(entries, "CLIENT-001", "2026-08")
        assert report.total_expenses == 1000.0
        assert report.entry_count == 100
        assert len(report.line_items) == 1
        assert report.line_items[0].count == 100

    def test_large_amounts(self):
        gen = PLGenerator()
        entries = [_make_entry(amount=999999.99, category="Travel")]
        report = gen.generate(entries, "CLIENT-001", "2026-08")
        assert report.total_expenses == 999999.99
