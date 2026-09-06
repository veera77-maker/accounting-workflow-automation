"""Tests for the simulated accounting ledger."""

from __future__ import annotations

import pytest
from datetime import date

from src.accounting.ledger import Ledger, AccountingError
from src.models.accounting import LedgerEntry, LedgerEntryStatus
from src.models.expense import ExpenseRecord, ExpenseCategory, ExpenseStatus
from src.models.anomaly import AnomalyResult, AnomalyVerdict, AnomalyReason
from src.models.human_review import HumanReviewDecision, ReviewDecision


def _make_expense(
    expense_id: str = "EXP-0001",
    amount: float = 150.0,
    category: ExpenseCategory = ExpenseCategory.TRAVEL,
    vendor: str = "Delta Airlines",
    employee: str = "EMP-001",
    client_id: str = "CLIENT-001",
    month: str = "2026-08",
    status: ExpenseStatus = ExpenseStatus.PENDING,
) -> ExpenseRecord:
    return ExpenseRecord(
        expense_id=expense_id,
        client_id=client_id,
        employee=employee,
        date=date(2026, 8, 15),
        description=f"Expense {expense_id}",
        vendor=vendor,
        amount=amount,
        category=category,
        receipt_reference=f"RCP-{expense_id[-4:]}",
        status=status,
        month=month,
    )


def _make_anomaly(
    expense_id: str = "EXP-0001",
    verdict: AnomalyVerdict = AnomalyVerdict.NORMAL,
) -> AnomalyResult:
    return AnomalyResult(
        expense_id=expense_id,
        verdict=verdict,
        reasons=[AnomalyReason.HIGH_VALUE] if verdict == AnomalyVerdict.REVIEW else [],
        explanation="Test",
        scores={"signal_count": 0},
        threshold_used=0.0,
        features={},
    )


def _make_decision(
    expense_id: str = "EXP-0001",
    decision: ReviewDecision = ReviewDecision.APPROVE,
    reviewer: str = "reviewer@example.com",
    reason: str = "Looks correct",
    corrected_amount: float | None = None,
    corrected_category: str | None = None,
    corrected_vendor: str | None = None,
) -> HumanReviewDecision:
    return HumanReviewDecision(
        review_id=f"REV-{expense_id[-4:]}",
        expense_id=expense_id,
        reviewer=reviewer,
        decision=decision,
        reason=reason,
        corrected_amount=corrected_amount,
        corrected_category=corrected_category,
        corrected_vendor=corrected_vendor,
        decided_at="2026-08-20T10:00:00",
    )


class TestLedgerInitialization:
    def test_empty_ledger(self):
        ledger = Ledger()
        assert ledger.get_all_entries() == []

    def test_entry_ids_start_at_one(self):
        ledger = Ledger()
        entries = ledger.post_clean_expenses(
            [_make_expense("EXP-0001")],
            [_make_anomaly("EXP-0001", AnomalyVerdict.NORMAL)],
        )
        assert entries[0].entry_id == "LED-000001"


class TestPostCleanExpenses:
    def test_posts_normal_expenses(self):
        ledger = Ledger()
        expenses = [_make_expense("EXP-0001"), _make_expense("EXP-0002")]
        anomalies = [
            _make_anomaly("EXP-0001", AnomalyVerdict.NORMAL),
            _make_anomaly("EXP-0002", AnomalyVerdict.NORMAL),
        ]
        posted = ledger.post_clean_expenses(expenses, anomalies)
        assert len(posted) == 2
        assert all(e.status == LedgerEntryStatus.POSTED for e in posted)

    def test_skips_review_expenses(self):
        ledger = Ledger()
        expenses = [_make_expense("EXP-0001"), _make_expense("EXP-0002")]
        anomalies = [
            _make_anomaly("EXP-0001", AnomalyVerdict.NORMAL),
            _make_anomaly("EXP-0002", AnomalyVerdict.REVIEW),
        ]
        posted = ledger.post_clean_expenses(expenses, anomalies)
        assert len(posted) == 1
        assert posted[0].expense_id == "EXP-0001"

    def test_all_reviewed_returns_empty(self):
        ledger = Ledger()
        expenses = [_make_expense("EXP-0001")]
        anomalies = [_make_anomaly("EXP-0001", AnomalyVerdict.REVIEW)]
        posted = ledger.post_clean_expenses(expenses, anomalies)
        assert len(posted) == 0

    def test_entry_fields_populated(self):
        ledger = Ledger()
        expense = _make_expense(
            "EXP-0001",
            amount=250.0,
            category=ExpenseCategory.SOFTWARE,
            vendor="GitHub Inc.",
            client_id="CLIENT-002",
            month="2026-09",
        )
        posted = ledger.post_clean_expenses(
            [expense],
            [_make_anomaly("EXP-0001", AnomalyVerdict.NORMAL)],
        )
        entry = posted[0]
        assert entry.expense_id == "EXP-0001"
        assert entry.client_id == "CLIENT-002"
        assert entry.category == "Software"
        assert entry.amount == 250.0
        assert entry.vendor == "GitHub Inc."
        assert entry.month == "2026-09"
        assert entry.source == "auto"

    def test_source_is_auto(self):
        ledger = Ledger()
        posted = ledger.post_clean_expenses(
            [_make_expense()],
            [_make_anomaly(verdict=AnomalyVerdict.NORMAL)],
        )
        assert posted[0].source == "auto"

    def test_entry_ids_sequential(self):
        ledger = Ledger()
        expenses = [_make_expense(f"EXP-{i:04d}") for i in range(1, 4)]
        anomalies = [_make_anomaly(f"EXP-{i:04d}", AnomalyVerdict.NORMAL) for i in range(1, 4)]
        posted = ledger.post_clean_expenses(expenses, anomalies)
        ids = [e.entry_id for e in posted]
        assert ids == ["LED-000001", "LED-000002", "LED-000003"]

    def test_no_expenses_returns_empty(self):
        ledger = Ledger()
        posted = ledger.post_clean_expenses([], [])
        assert posted == []


class TestPostHumanReviewed:
    def test_approve_posts_expense(self):
        ledger = Ledger()
        expense = _make_expense("EXP-0001")
        decision = _make_decision("EXP-0001", ReviewDecision.APPROVE)
        posted = ledger.post_human_reviewed([expense], [decision])
        assert len(posted) == 1
        assert posted[0].status == LedgerEntryStatus.HUMAN_REVIEWED
        assert posted[0].source == "human_review"

    def test_reject_does_not_post(self):
        ledger = Ledger()
        expense = _make_expense("EXP-0001")
        decision = _make_decision("EXP-0001", ReviewDecision.REJECT)
        posted = ledger.post_human_reviewed([expense], [decision])
        assert len(posted) == 0

    def test_correct_posts_with_corrected_values(self):
        ledger = Ledger()
        expense = _make_expense("EXP-0001", amount=150.0)
        decision = _make_decision(
            "EXP-0001",
            ReviewDecision.CORRECT,
            corrected_amount=175.0,
            corrected_category="Office Supplies",
            corrected_vendor="Office Depot",
        )
        posted = ledger.post_human_reviewed([expense], [decision])
        assert len(posted) == 1
        assert posted[0].amount == 175.0
        assert posted[0].category == "Office Supplies"
        assert posted[0].vendor == "Office Depot"

    def test_correct_partial_fields(self):
        ledger = Ledger()
        expense = _make_expense("EXP-0001", amount=150.0, vendor="Delta Airlines")
        decision = _make_decision(
            "EXP-0001",
            ReviewDecision.CORRECT,
            corrected_amount=200.0,
        )
        posted = ledger.post_human_reviewed([expense], [decision])
        assert posted[0].amount == 200.0
        assert posted[0].vendor == "Delta Airlines"  # unchanged

    def test_multiple_expenses_mixed_decisions(self):
        ledger = Ledger()
        expenses = [
            _make_expense("EXP-0001"),
            _make_expense("EXP-0002"),
            _make_expense("EXP-0003"),
        ]
        decisions = [
            _make_decision("EXP-0001", ReviewDecision.APPROVE),
            _make_decision("EXP-0002", ReviewDecision.REJECT),
            _make_decision("EXP-0003", ReviewDecision.CORRECT, corrected_amount=99.0),
        ]
        posted = ledger.post_human_reviewed(expenses, decisions)
        assert len(posted) == 2
        assert posted[0].expense_id == "EXP-0001"
        assert posted[1].expense_id == "EXP-0003"
        assert posted[1].amount == 99.0

    def test_no_decisions_returns_empty(self):
        ledger = Ledger()
        posted = ledger.post_human_reviewed([_make_expense()], [])
        assert posted == []

    def test_expense_without_decision_skipped(self):
        ledger = Ledger()
        expenses = [_make_expense("EXP-0001"), _make_expense("EXP-0002")]
        decisions = [_make_decision("EXP-0001", ReviewDecision.APPROVE)]
        posted = ledger.post_human_reviewed(expenses, decisions)
        assert len(posted) == 1
        assert posted[0].expense_id == "EXP-0001"


class TestGetEntries:
    def test_get_all_entries(self):
        ledger = Ledger()
        ledger.post_clean_expenses(
            [_make_expense("EXP-0001", month="2026-08")],
            [_make_anomaly("EXP-0001", AnomalyVerdict.NORMAL)],
        )
        ledger.post_human_reviewed(
            [_make_expense("EXP-0002", month="2026-09")],
            [_make_decision("EXP-0002", ReviewDecision.APPROVE)],
        )
        assert len(ledger.get_all_entries()) == 2

    def test_filter_by_month(self):
        ledger = Ledger()
        ledger.post_clean_expenses(
            [_make_expense("EXP-0001", month="2026-08")],
            [_make_anomaly("EXP-0001", AnomalyVerdict.NORMAL)],
        )
        ledger.post_clean_expenses(
            [_make_expense("EXP-0002", month="2026-09")],
            [_make_anomaly("EXP-0002", AnomalyVerdict.NORMAL)],
        )
        aug = ledger.get_entries(month="2026-08")
        assert len(aug) == 1
        assert aug[0].month == "2026-08"

    def test_filter_by_client(self):
        ledger = Ledger()
        ledger.post_clean_expenses(
            [_make_expense("EXP-0001", client_id="CLIENT-001")],
            [_make_anomaly("EXP-0001", AnomalyVerdict.NORMAL)],
        )
        ledger.post_clean_expenses(
            [_make_expense("EXP-0002", client_id="CLIENT-002")],
            [_make_anomaly("EXP-0002", AnomalyVerdict.NORMAL)],
        )
        c1 = ledger.get_entries(client_id="CLIENT-001")
        assert len(c1) == 1
        assert c1[0].client_id == "CLIENT-001"

    def test_filter_by_month_and_client(self):
        ledger = Ledger()
        ledger.post_clean_expenses(
            [_make_expense("EXP-0001", month="2026-08", client_id="CLIENT-001")],
            [_make_anomaly("EXP-0001", AnomalyVerdict.NORMAL)],
        )
        ledger.post_clean_expenses(
            [_make_expense("EXP-0002", month="2026-09", client_id="CLIENT-001")],
            [_make_anomaly("EXP-0002", AnomalyVerdict.NORMAL)],
        )
        ledger.post_clean_expenses(
            [_make_expense("EXP-0003", month="2026-08", client_id="CLIENT-002")],
            [_make_anomaly("EXP-0003", AnomalyVerdict.NORMAL)],
        )
        result = ledger.get_entries(month="2026-08", client_id="CLIENT-001")
        assert len(result) == 1
        assert result[0].expense_id == "EXP-0001"

    def test_returns_copy(self):
        ledger = Ledger()
        ledger.post_clean_expenses(
            [_make_expense()],
            [_make_anomaly(verdict=AnomalyVerdict.NORMAL)],
        )
        entries1 = ledger.get_all_entries()
        entries2 = ledger.get_all_entries()
        assert entries1 is not entries2
        assert entries1 == entries2


class TestGetTotalByCategory:
    def test_totals_by_category(self):
        ledger = Ledger()
        ledger.post_clean_expenses(
            [
                _make_expense("EXP-0001", amount=100.0, category=ExpenseCategory.TRAVEL),
                _make_expense("EXP-0002", amount=200.0, category=ExpenseCategory.TRAVEL),
                _make_expense("EXP-0003", amount=50.0, category=ExpenseCategory.SOFTWARE),
            ],
            [_make_anomaly(f"EXP-{i:04d}", AnomalyVerdict.NORMAL) for i in range(1, 4)],
        )
        totals = ledger.get_total_by_category()
        assert totals["Travel"] == 300.0
        assert totals["Software"] == 50.0

    def test_totals_with_month_filter(self):
        ledger = Ledger()
        ledger.post_clean_expenses(
            [_make_expense("EXP-0001", amount=100.0, month="2026-08")],
            [_make_anomaly("EXP-0001", AnomalyVerdict.NORMAL)],
        )
        ledger.post_clean_expenses(
            [_make_expense("EXP-0002", amount=200.0, month="2026-09")],
            [_make_anomaly("EXP-0002", AnomalyVerdict.NORMAL)],
        )
        totals = ledger.get_total_by_category(month="2026-08")
        assert totals["Travel"] == 100.0

    def test_empty_entries_returns_empty(self):
        ledger = Ledger()
        assert ledger.get_total_by_category() == {}


class TestGetEntryCount:
    def test_count_all(self):
        ledger = Ledger()
        ledger.post_clean_expenses(
            [_make_expense(f"EXP-{i:04d}") for i in range(1, 6)],
            [_make_anomaly(f"EXP-{i:04d}", AnomalyVerdict.NORMAL) for i in range(1, 6)],
        )
        assert ledger.get_entry_count() == 5

    def test_count_with_filters(self):
        ledger = Ledger()
        ledger.post_clean_expenses(
            [
                _make_expense("EXP-0001", month="2026-08"),
                _make_expense("EXP-0002", month="2026-09"),
            ],
            [
                _make_anomaly("EXP-0001", AnomalyVerdict.NORMAL),
                _make_anomaly("EXP-0002", AnomalyVerdict.NORMAL),
            ],
        )
        assert ledger.get_entry_count(month="2026-08") == 1


class TestToDict:
    def test_to_dict(self):
        ledger = Ledger()
        ledger.post_clean_expenses(
            [_make_expense()],
            [_make_anomaly(verdict=AnomalyVerdict.NORMAL)],
        )
        d = ledger.to_dict()
        assert d["entry_count"] == 1
        assert len(d["entries"]) == 1
        assert d["entries"][0]["expense_id"] == "EXP-0001"

    def test_empty_to_dict(self):
        ledger = Ledger()
        d = ledger.to_dict()
        assert d["entry_count"] == 0
        assert d["entries"] == []


class TestLedgerIntegration:
    def test_full_lifecycle(self):
        ledger = Ledger()
        # Post clean expenses
        clean = [
            _make_expense("EXP-0001", amount=100.0),
            _make_expense("EXP-0002", amount=200.0),
        ]
        anomalies = [
            _make_anomaly("EXP-0001", AnomalyVerdict.NORMAL),
            _make_anomaly("EXP-0002", AnomalyVerdict.REVIEW),
        ]
        posted_clean = ledger.post_clean_expenses(clean, anomalies)
        assert len(posted_clean) == 1

        # Post human-reviewed expenses
        review_expenses = [_make_expense("EXP-0002", amount=200.0)]
        decisions = [_make_decision("EXP-0002", ReviewDecision.APPROVE)]
        posted_review = ledger.post_human_reviewed(review_expenses, decisions)
        assert len(posted_review) == 1

        # Total should include both
        assert ledger.get_entry_count() == 2
        totals = ledger.get_total_by_category()
        assert totals["Travel"] == 300.0

    def test_corrected_expense_reflects_in_totals(self):
        ledger = Ledger()
        ledger.post_human_reviewed(
            [_make_expense("EXP-0001", amount=100.0)],
            [_make_decision("EXP-0001", ReviewDecision.CORRECT, corrected_amount=150.0)],
        )
        totals = ledger.get_total_by_category()
        assert totals["Travel"] == 150.0
