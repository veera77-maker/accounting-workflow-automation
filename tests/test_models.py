"""Tests for data models."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from models.expense import ExpenseCategory, ExpenseRecord, ExpenseStatus
from models.receipt import ReceiptLineItem, ReceiptRecord
from models.reconciliation import ReconciliationResult, ReconciliationStatus
from models.anomaly import AnomalyReason, AnomalyResult, AnomalyVerdict
from models.human_review import HumanReviewDecision, HumanReviewItem, ReviewDecision
from models.accounting import LedgerEntry, LedgerEntryStatus, PLLineItem, PLReport
from models.workflow import WorkflowRun, WorkflowStatus


class TestExpenseRecord:
    def test_create_expense(self):
        expense = ExpenseRecord(
            expense_id="EXP-001",
            client_id="TV-001",
            employee="Alice Johnson",
            date=date(2026, 8, 15),
            description="Flight to NYC",
            vendor="Delta Airlines",
            amount=450.00,
            month="2026-08",
        )
        assert expense.expense_id == "EXP-001"
        assert expense.amount == 450.00
        assert expense.status == ExpenseStatus.PENDING

    def test_expense_categories(self):
        categories = list(ExpenseCategory)
        assert len(categories) == 8
        assert ExpenseCategory.TRAVEL == "Travel"
        assert ExpenseCategory.MEALS_ENTERTAINMENT == "Meals & Entertainment"

    def test_expense_negative_amount_rejected(self):
        with pytest.raises(Exception):
            ExpenseRecord(
                expense_id="EXP-BAD",
                client_id="TV-001",
                employee="Test",
                date=date(2026, 8, 1),
                description="Bad",
                vendor="Test",
                amount=-10.0,
                month="2026-08",
            )


class TestReceiptRecord:
    def test_create_receipt(self):
        receipt = ReceiptRecord(
            receipt_id="RCP-001",
            vendor="Delta Airlines",
            amount=450.00,
            date=date(2026, 8, 15),
            line_items=[
                ReceiptLineItem(description="Flight JFK-LAX", amount=450.00, quantity=1)
            ],
        )
        assert receipt.receipt_id == "RCP-001"
        assert len(receipt.line_items) == 1


class TestReconciliationResult:
    def test_exact_match(self):
        result = ReconciliationResult(
            expense_id="EXP-001",
            receipt_id="RCP-001",
            status=ReconciliationStatus.EXACT_MATCH,
            reason="Vendor, amount, and date match",
            evidence={"vendor_match": True, "amount_match": True, "date_match": True},
        )
        assert result.status == ReconciliationStatus.EXACT_MATCH

    def test_missing_receipt(self):
        result = ReconciliationResult(
            expense_id="EXP-002",
            status=ReconciliationStatus.MISSING_RECEIPT,
            reason="No receipt found for this expense",
        )
        assert result.status == ReconciliationStatus.MISSING_RECEIPT


class TestAnomalyResult:
    def test_normal_expense(self):
        result = AnomalyResult(
            expense_id="EXP-001",
            verdict=AnomalyVerdict.NORMAL,
            explanation="Within normal range",
        )
        assert result.verdict == AnomalyVerdict.NORMAL

    def test_review_expense(self):
        result = AnomalyResult(
            expense_id="EXP-099",
            verdict=AnomalyVerdict.REVIEW,
            reasons=[AnomalyReason.HIGH_VALUE, AnomalyReason.NEW_VENDOR],
            explanation="Meal expense significantly above average for category",
            scores={"anomaly_score": 0.85},
            threshold_used=0.7,
        )
        assert result.verdict == AnomalyVerdict.REVIEW
        assert len(result.reasons) == 2


class TestHumanReview:
    def test_review_item(self):
        item = HumanReviewItem(
            review_id="REV-001",
            expense_id="EXP-099",
            anomaly_reasons=["high_value_for_category"],
            evidence={"amount": 2500.00, "category_avg": 150.00},
        )
        assert item.expense_id == "EXP-099"

    def test_review_decision(self):
        decision = HumanReviewDecision(
            review_id="REV-001",
            expense_id="EXP-099",
            reviewer="John Smith",
            decision=ReviewDecision.APPROVE,
            reason="Valid client entertainment expense",
        )
        assert decision.decision == ReviewDecision.APPROVE


class TestAccounting:
    def test_ledger_entry(self):
        entry = LedgerEntry(
            entry_id="LED-001",
            expense_id="EXP-001",
            client_id="TV-001",
            category="Travel",
            amount=450.00,
            description="Flight to NYC",
            vendor="Delta Airlines",
            date=date(2026, 8, 15),
            month="2026-08",
        )
        assert entry.status == LedgerEntryStatus.PENDING

    def test_pl_report(self):
        report = PLReport(
            client_id="TV-001",
            month="2026-08",
            generated_at="2026-09-01T10:00:00",
            total_expenses=5000.00,
            line_items=[
                PLLineItem(category="Travel", total=2000.00, count=5),
                PLLineItem(category="Meals & Entertainment", total=1500.00, count=10),
            ],
            entry_count=15,
        )
        assert report.total_expenses == 5000.00
        assert len(report.line_items) == 2


class TestWorkflow:
    def test_workflow_run(self):
        run = WorkflowRun(
            run_id="RUN-001",
            client_id="TV-001",
            month="2026-08",
        )
        assert run.status == WorkflowStatus.CREATED
        assert run.client_id == "TV-001"
