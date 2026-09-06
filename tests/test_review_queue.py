"""Tests for the human review queue."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from human_review.review_queue import HumanReviewQueue, ReviewQueueError
from models.anomaly import AnomalyReason, AnomalyResult, AnomalyVerdict
from models.expense import ExpenseCategory, ExpenseRecord
from models.human_review import ReviewDecision


# --- Helper to create test data ---

def _make_expense(
    expense_id: str = "EXP-TEST",
    vendor: str = "Test Vendor",
    amount: float = 100.0,
    category: ExpenseCategory = ExpenseCategory.TRAVEL,
) -> ExpenseRecord:
    return ExpenseRecord(
        expense_id=expense_id,
        client_id="TV-001",
        employee="Test Employee",
        date=date(2026, 8, 1),
        description="Test expense",
        vendor=vendor,
        amount=amount,
        category=category,
        receipt_reference="RCP-TEST",
        month="2026-08",
    )


def _make_anomaly_result(
    expense_id: str = "EXP-TEST",
    verdict: AnomalyVerdict = AnomalyVerdict.REVIEW,
    reasons: list[AnomalyReason] | None = None,
) -> AnomalyResult:
    if reasons is None:
        reasons = [AnomalyReason.HIGH_VALUE]
    return AnomalyResult(
        expense_id=expense_id,
        verdict=verdict,
        reasons=reasons,
        explanation="Test anomaly",
        features={"test": "evidence"},
    )


# --- Queue basics ---

class TestQueueBasics:
    def test_empty_queue(self):
        queue = HumanReviewQueue()
        assert queue.pending_count == 0
        assert queue.decided_count == 0

    def test_add_to_queue(self):
        queue = HumanReviewQueue()
        expense = _make_expense()
        result = _make_anomaly_result()
        item = queue.add_to_queue(expense, result)
        assert queue.pending_count == 1
        assert item.expense_id == "EXP-TEST"

    def test_add_multiple(self):
        queue = HumanReviewQueue()
        for i in range(3):
            expense = _make_expense(expense_id=f"EXP-{i}")
            result = _make_anomaly_result(expense_id=f"EXP-{i}")
            queue.add_to_queue(expense, result)
        assert queue.pending_count == 3

    def test_cannot_add_normal_verdict(self):
        queue = HumanReviewQueue()
        expense = _make_expense()
        result = _make_anomaly_result(verdict=AnomalyVerdict.NORMAL)
        with pytest.raises(ReviewQueueError, match="not 'review'"):
            queue.add_to_queue(expense, result)
        assert queue.pending_count == 0

    def test_cannot_add_duplicate_expense(self):
        queue = HumanReviewQueue()
        expense = _make_expense()
        result = _make_anomaly_result()
        queue.add_to_queue(expense, result)
        with pytest.raises(ReviewQueueError, match="already in the review queue"):
            queue.add_to_queue(expense, result)
        assert queue.pending_count == 1

    def test_pending_items_returns_copy(self):
        queue = HumanReviewQueue()
        expense = _make_expense()
        result = _make_anomaly_result()
        queue.add_to_queue(expense, result)
        items = queue.pending_items
        items.clear()
        assert queue.pending_count == 1


# --- Approve ---

class TestApprove:
    def test_approve(self):
        queue = HumanReviewQueue()
        expense = _make_expense()
        result = _make_anomaly_result()
        item = queue.add_to_queue(expense, result)

        decision = queue.approve(item.review_id, "John Smith", "Valid expense")
        assert decision.decision == ReviewDecision.APPROVE
        assert decision.reviewer == "John Smith"
        assert decision.reason == "Valid expense"
        assert decision.expense_id == "EXP-TEST"
        assert queue.pending_count == 0
        assert queue.decided_count == 1

    def test_approve_preserves_timestamp(self):
        queue = HumanReviewQueue()
        expense = _make_expense()
        result = _make_anomaly_result()
        item = queue.add_to_queue(expense, result)

        decision = queue.approve(item.review_id, "John Smith", "Valid")
        assert decision.decided_at != ""
        assert "2026" in decision.decided_at or "T" in decision.decided_at

    def test_approve_not_found(self):
        queue = HumanReviewQueue()
        with pytest.raises(ReviewQueueError, match="not found"):
            queue.approve("REV-NONEXISTENT", "John Smith", "Reason")


# --- Reject ---

class TestReject:
    def test_reject(self):
        queue = HumanReviewQueue()
        expense = _make_expense()
        result = _make_anomaly_result()
        item = queue.add_to_queue(expense, result)

        decision = queue.reject(item.review_id, "Jane Doe", "Suspicious")
        assert decision.decision == ReviewDecision.REJECT
        assert decision.reviewer == "Jane Doe"
        assert decision.reason == "Suspicious"
        assert queue.pending_count == 0
        assert queue.decided_count == 1

    def test_reject_not_found(self):
        queue = HumanReviewQueue()
        with pytest.raises(ReviewQueueError, match="not found"):
            queue.reject("REV-NONEXISTENT", "Jane Doe", "Reason")


# --- Correct ---

class TestCorrect:
    def test_correct_amount(self):
        queue = HumanReviewQueue()
        expense = _make_expense(amount=2850.0)
        result = _make_anomaly_result()
        item = queue.add_to_queue(expense, result)

        decision = queue.correct(
            item.review_id, "Bob Wilson", "Actual amount was $2650",
            corrected_amount=2650.0,
        )
        assert decision.decision == ReviewDecision.CORRECT
        assert decision.corrected_amount == 2650.0
        assert decision.corrected_category is None
        assert decision.corrected_vendor is None
        assert queue.pending_count == 0

    def test_correct_category(self):
        queue = HumanReviewQueue()
        expense = _make_expense()
        result = _make_anomaly_result()
        item = queue.add_to_queue(expense, result)

        decision = queue.correct(
            item.review_id, "Bob Wilson", "Wrong category",
            corrected_category="Office Supplies",
        )
        assert decision.corrected_category == "Office Supplies"

    def test_correct_vendor(self):
        queue = HumanReviewQueue()
        expense = _make_expense()
        result = _make_anomaly_result()
        item = queue.add_to_queue(expense, result)

        decision = queue.correct(
            item.review_id, "Bob Wilson", "Wrong vendor",
            corrected_vendor="Correct Vendor Inc",
        )
        assert decision.corrected_vendor == "Correct Vendor Inc"

    def test_correct_multiple_fields(self):
        queue = HumanReviewQueue()
        expense = _make_expense()
        result = _make_anomaly_result()
        item = queue.add_to_queue(expense, result)

        decision = queue.correct(
            item.review_id, "Bob Wilson", "Multiple corrections",
            corrected_amount=100.0,
            corrected_category="Software",
            corrected_vendor="New Vendor",
        )
        assert decision.corrected_amount == 100.0
        assert decision.corrected_category == "Software"
        assert decision.corrected_vendor == "New Vendor"

    def test_correct_not_found(self):
        queue = HumanReviewQueue()
        with pytest.raises(ReviewQueueError, match="not found"):
            queue.correct("REV-NONEXISTENT", "Bob Wilson", "Reason")


# --- Auditability ---

class TestAuditability:
    def test_get_decision_by_review_id(self):
        queue = HumanReviewQueue()
        expense = _make_expense()
        result = _make_anomaly_result()
        item = queue.add_to_queue(expense, result)

        queue.approve(item.review_id, "John Smith", "Valid")
        decision = queue.get_decision(item.review_id)
        assert decision is not None
        assert decision.decision == ReviewDecision.APPROVE

    def test_get_decision_by_expense_id(self):
        queue = HumanReviewQueue()
        expense = _make_expense(expense_id="EXP-AUDIT")
        result = _make_anomaly_result(expense_id="EXP-AUDIT")
        item = queue.add_to_queue(expense, result)

        queue.reject(item.review_id, "Jane Doe", "No")
        decision = queue.get_decision_by_expense("EXP-AUDIT")
        assert decision is not None
        assert decision.decision == ReviewDecision.REJECT

    def test_all_decisions_recorded(self):
        queue = HumanReviewQueue()
        for i in range(5):
            expense = _make_expense(expense_id=f"EXP-{i}")
            result = _make_anomaly_result(expense_id=f"EXP-{i}")
            item = queue.add_to_queue(expense, result)
            if i % 2 == 0:
                queue.approve(item.review_id, "Reviewer A", f"Approve {i}")
            else:
                queue.reject(item.review_id, "Reviewer B", f"Reject {i}")

        assert queue.decided_count == 5
        decisions = queue.decisions
        approvals = [d for d in decisions if d.decision == ReviewDecision.APPROVE]
        rejections = [d for d in decisions if d.decision == ReviewDecision.REJECT]
        assert len(approvals) == 3
        assert len(rejections) == 2

    def test_to_dict(self):
        queue = HumanReviewQueue()
        expense = _make_expense()
        result = _make_anomaly_result()
        item = queue.add_to_queue(expense, result)
        queue.approve(item.review_id, "John", "OK")

        d = queue.to_dict()
        assert "pending_count" in d
        assert "decided_count" in d
        assert "pending_items" in d
        assert "decisions" in d
        assert d["decided_count"] == 1


# --- Integration with anomaly detector ---

class TestReviewQueueIntegration:
    def test_review_items_flow_from_detector(self, tmp_path):
        """Test that REVIEW items from the anomaly detector can enter the queue."""
        from triggers.monthly_trigger import trigger_monthly_expense
        from processors.expense_processor import process_expenses
        from processors.receipt_processor import process_receipts
        from processors.reconciler import reconcile_expenses
        from decisions.anomaly_detector import detect_anomalies

        run = trigger_monthly_expense("TV-001", "2026-08", output_dir=tmp_path)
        expenses = process_expenses(run.trigger_data["expense_file"], "TV-001", "2026-08")
        receipts = process_receipts(run.trigger_data["receipt_file"])
        reconciliations = reconcile_expenses(expenses.records, receipts.records)

        # Load known vendors
        import json
        data_dir = Path(__file__).resolve().parent.parent / "data" / "synthetic"
        with open(data_dir / "vendors.json") as f:
            vendors = json.load(f)
        known_vendors = {v["name"].lower().strip() for v in vendors}

        anomalies = detect_anomalies(
            expenses.records, reconciliations, known_vendors
        )

        queue = HumanReviewQueue()
        for expense, anomaly in zip(expenses.records, anomalies):
            if anomaly.verdict == AnomalyVerdict.REVIEW:
                queue.add_to_queue(expense, anomaly)

        assert queue.pending_count > 0

        # Approve all pending items
        for item in queue.pending_items:
            queue.approve(item.review_id, "Test Reviewer", "Approved in test")

        assert queue.pending_count == 0
        assert queue.decided_count > 0
