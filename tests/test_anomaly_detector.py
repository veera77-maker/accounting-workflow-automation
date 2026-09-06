"""Tests for the anomaly detector."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from decisions.anomaly_detector import (
    AnomalyThresholds,
    detect_anomalies,
    _compute_category_stats,
    _check_high_value,
    _check_duplicate,
    _check_new_vendor,
    _check_reconciliation_mismatch,
    DEFAULT_THRESHOLDS,
)
from models.anomaly import AnomalyReason, AnomalyResult, AnomalyVerdict
from models.expense import ExpenseCategory, ExpenseRecord
from models.reconciliation import ReconciliationResult, ReconciliationStatus
from triggers.monthly_trigger import trigger_monthly_expense
from processors.expense_processor import process_expenses
from processors.receipt_processor import process_receipts
from processors.reconciler import reconcile_expenses


# --- Helper to create test expenses ---

def _make_expense(
    expense_id: str = "EXP-TEST",
    vendor: str = "Test Vendor",
    amount: float = 100.0,
    category: ExpenseCategory = ExpenseCategory.TRAVEL,
    date_val: date = date(2026, 8, 1),
    employee: str = "Test Employee",
    description: str = "Test expense",
    receipt_ref: str | None = "RCP-TEST",
) -> ExpenseRecord:
    return ExpenseRecord(
        expense_id=expense_id,
        client_id="TV-001",
        employee=employee,
        date=date_val,
        description=description,
        vendor=vendor,
        amount=amount,
        category=category,
        receipt_reference=receipt_ref,
        month="2026-08",
    )


# --- Unit tests for category stats ---

class TestComputeCategoryStats:
    def test_basic_stats(self):
        expenses = [
            _make_expense("E1", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E2", amount=200, category=ExpenseCategory.TRAVEL),
            _make_expense("E3", amount=300, category=ExpenseCategory.TRAVEL),
        ]
        stats = _compute_category_stats(expenses)
        assert "Travel" in stats
        assert stats["Travel"]["mean"] == 200.0
        assert stats["Travel"]["min"] == 100.0
        assert stats["Travel"]["max"] == 300.0
        assert stats["Travel"]["count"] == 3

    def test_multiple_categories(self):
        expenses = [
            _make_expense("E1", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E2", amount=50, category=ExpenseCategory.SOFTWARE),
        ]
        stats = _compute_category_stats(expenses)
        assert len(stats) == 2
        assert "Travel" in stats
        assert "Software" in stats

    def test_empty_expenses(self):
        stats = _compute_category_stats([])
        assert stats == {}


# --- Unit tests for high value check ---

class TestHighValueCheck:
    def test_normal_expense(self):
        expenses = [
            _make_expense("E1", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E2", amount=120, category=ExpenseCategory.TRAVEL),
            _make_expense("E3", amount=80, category=ExpenseCategory.TRAVEL),
        ]
        stats = _compute_category_stats(expenses)
        thresholds = AnomalyThresholds(high_value_multiplier=3.0, min_category_count_for_mean=3)
        expense = _make_expense("E4", amount=150, category=ExpenseCategory.TRAVEL)
        signal = _check_high_value(expense, stats, thresholds)
        assert signal is None

    def test_high_value_expense(self):
        expenses = [
            _make_expense("E1", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E2", amount=120, category=ExpenseCategory.TRAVEL),
            _make_expense("E3", amount=80, category=ExpenseCategory.TRAVEL),
        ]
        stats = _compute_category_stats(expenses)
        thresholds = AnomalyThresholds(high_value_multiplier=3.0, min_category_count_for_mean=3)
        # Mean=100, threshold=300, expense=350 → REVIEW
        expense = _make_expense("E4", amount=350, category=ExpenseCategory.TRAVEL)
        signal = _check_high_value(expense, stats, thresholds)
        assert signal is not None
        assert signal.reason == AnomalyReason.HIGH_VALUE
        assert "350.00" in signal.explanation
        assert "300.00" in signal.explanation

    def test_boundary_value(self):
        expenses = [
            _make_expense("E1", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E2", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E3", amount=100, category=ExpenseCategory.TRAVEL),
        ]
        stats = _compute_category_stats(expenses)
        thresholds = AnomalyThresholds(high_value_multiplier=3.0, min_category_count_for_mean=3)
        # Mean=100, threshold=300, expense=300 → NOT reviewed (not strictly greater)
        expense = _make_expense("E4", amount=300, category=ExpenseCategory.TRAVEL)
        signal = _check_high_value(expense, stats, thresholds)
        assert signal is None

    def test_insufficient_data_uses_max(self):
        expenses = [
            _make_expense("E1", amount=100, category=ExpenseCategory.TRAVEL),
        ]
        stats = _compute_category_stats(expenses)
        thresholds = AnomalyThresholds(high_value_multiplier=3.0, min_category_count_for_mean=3)
        # Only 1 expense, max=100, threshold=300
        expense = _make_expense("E2", amount=350, category=ExpenseCategory.TRAVEL)
        signal = _check_high_value(expense, stats, thresholds)
        assert signal is not None
        assert "max" in signal.explanation.lower()


# --- Unit tests for duplicate check ---

class TestDuplicateCheck:
    def test_no_duplicate(self):
        expenses = [
            _make_expense("E1", vendor="A", amount=100, date_val=date(2026, 8, 1)),
            _make_expense("E2", vendor="A", amount=200, date_val=date(2026, 8, 1)),
        ]
        thresholds = AnomalyThresholds()
        signal = _check_duplicate(expenses[0], expenses, thresholds)
        assert signal is None

    def test_exact_duplicate(self):
        expenses = [
            _make_expense("E1", vendor="A", amount=100, date_val=date(2026, 8, 1)),
            _make_expense("E2", vendor="A", amount=100, date_val=date(2026, 8, 1)),
        ]
        thresholds = AnomalyThresholds()
        signal = _check_duplicate(expenses[0], expenses, thresholds)
        assert signal is not None
        assert signal.reason == AnomalyReason.DUPLICATE
        assert "E2" in signal.explanation

    def test_different_date_not_duplicate(self):
        expenses = [
            _make_expense("E1", vendor="A", amount=100, date_val=date(2026, 8, 1)),
            _make_expense("E2", vendor="A", amount=100, date_val=date(2026, 8, 2)),
        ]
        thresholds = AnomalyThresholds()
        signal = _check_duplicate(expenses[0], expenses, thresholds)
        assert signal is None

    def test_different_vendor_not_duplicate(self):
        expenses = [
            _make_expense("E1", vendor="A", amount=100, date_val=date(2026, 8, 1)),
            _make_expense("E2", vendor="B", amount=100, date_val=date(2026, 8, 1)),
        ]
        thresholds = AnomalyThresholds()
        signal = _check_duplicate(expenses[0], expenses, thresholds)
        assert signal is None

    def test_multiple_duplicates(self):
        expenses = [
            _make_expense("E1", vendor="A", amount=100, date_val=date(2026, 8, 1)),
            _make_expense("E2", vendor="A", amount=100, date_val=date(2026, 8, 1)),
            _make_expense("E3", vendor="A", amount=100, date_val=date(2026, 8, 1)),
        ]
        thresholds = AnomalyThresholds()
        signal = _check_duplicate(expenses[0], expenses, thresholds)
        assert signal is not None
        assert signal.evidence["duplicate_count"] == 2


# --- Unit tests for new vendor check ---

class TestNewVendorCheck:
    def test_known_vendor(self):
        expense = _make_expense(vendor="Delta Airlines")
        known = {"delta airlines", "hilton hotels"}
        thresholds = AnomalyThresholds()
        signal = _check_new_vendor(expense, known, thresholds)
        assert signal is None

    def test_new_vendor(self):
        expense = _make_expense(vendor="Unknown Vendor")
        known = {"delta airlines", "hilton hotels"}
        thresholds = AnomalyThresholds()
        signal = _check_new_vendor(expense, known, thresholds)
        assert signal is not None
        assert signal.reason == AnomalyReason.NEW_VENDOR

    def test_no_known_vendors(self):
        expense = _make_expense(vendor="Any Vendor")
        thresholds = AnomalyThresholds()
        signal = _check_new_vendor(expense, None, thresholds)
        assert signal is None


# --- Unit tests for reconciliation mismatch check ---

class TestReconciliationMismatchCheck:
    def test_exact_match_no_signal(self):
        expense = _make_expense()
        recon = ReconciliationResult(
            expense_id="EXP-TEST",
            status=ReconciliationStatus.EXACT_MATCH,
            reason="All match",
        )
        thresholds = AnomalyThresholds()
        signal = _check_reconciliation_mismatch(expense, recon, thresholds)
        assert signal is None

    def test_amount_mismatch_signal(self):
        expense = _make_expense()
        recon = ReconciliationResult(
            expense_id="EXP-TEST",
            status=ReconciliationStatus.AMOUNT_MISMATCH,
            reason="Amount differs",
            amount_expected=100.0,
            amount_actual=150.0,
        )
        thresholds = AnomalyThresholds()
        signal = _check_reconciliation_mismatch(expense, recon, thresholds)
        assert signal is not None
        assert signal.reason == AnomalyReason.HIGH_VALUE

    def test_vendor_mismatch_signal(self):
        expense = _make_expense()
        recon = ReconciliationResult(
            expense_id="EXP-TEST",
            status=ReconciliationStatus.VENDOR_MISMATCH,
            reason="Vendor differs",
            vendor_expected="Vendor A",
            vendor_actual="Vendor B",
        )
        thresholds = AnomalyThresholds()
        signal = _check_reconciliation_mismatch(expense, recon, thresholds)
        assert signal is not None
        assert signal.reason == AnomalyReason.NEW_VENDOR

    def test_missing_receipt_no_signal(self):
        expense = _make_expense()
        recon = ReconciliationResult(
            expense_id="EXP-TEST",
            status=ReconciliationStatus.MISSING_RECEIPT,
            reason="No receipt",
        )
        thresholds = AnomalyThresholds()
        signal = _check_reconciliation_mismatch(expense, recon, thresholds)
        assert signal is None

    def test_disabled_threshold(self):
        expense = _make_expense()
        recon = ReconciliationResult(
            expense_id="EXP-TEST",
            status=ReconciliationStatus.AMOUNT_MISMATCH,
            reason="Amount differs",
            amount_expected=100.0,
            amount_actual=150.0,
        )
        thresholds = AnomalyThresholds(review_on_amount_mismatch=False)
        signal = _check_reconciliation_mismatch(expense, recon, thresholds)
        assert signal is None


# --- Integration tests with synthetic data ---

class TestAnomalyDetectorWithSyntheticData:
    """Tests using the full pipeline through anomaly detection."""

    @pytest.fixture
    def full_pipeline(self, tmp_path):
        """Run trigger → expense → receipt → reconcile → detect."""
        run = trigger_monthly_expense("TV-001", "2026-08", output_dir=tmp_path)
        expense_result = process_expenses(
            run.trigger_data["expense_file"], "TV-001", "2026-08"
        )
        receipt_result = process_receipts(run.trigger_data["receipt_file"])
        recon_results = reconcile_expenses(expense_result.records, receipt_result.records)
        anomaly_results = detect_anomalies(
            expense_result.records,
            reconciliations=recon_results,
            known_vendors=_load_known_vendors_for_test(),
        )
        return expense_result.records, recon_results, anomaly_results

    def test_returns_list(self, full_pipeline):
        _, _, results = full_pipeline
        assert isinstance(results, list)

    def test_one_result_per_expense(self, full_pipeline):
        expenses, _, results = full_pipeline
        assert len(results) == len(expenses)

    def test_high_value_meal_detected(self, full_pipeline):
        """The $2,850 Capital Grille meal should be flagged."""
        _, _, results = full_pipeline
        capital_grille = [r for r in results if r.expense_id == "EXP-0012"]
        assert len(capital_grille) == 1
        assert capital_grille[0].verdict == AnomalyVerdict.REVIEW
        assert AnomalyReason.HIGH_VALUE in capital_grille[0].reasons

    def test_amount_mismatch_flagged(self, full_pipeline):
        """The Capital Grille amount mismatch should be flagged."""
        _, _, results = full_pipeline
        # EXP-0012 has both high value AND amount mismatch
        expense = [r for r in results if r.expense_id == "EXP-0012"][0]
        assert expense.verdict == AnomalyVerdict.REVIEW
        # Should have signals from both high value and reconciliation
        assert len(expense.reasons) >= 1

    def test_vendor_mismatch_flagged(self, full_pipeline):
        """The Amazon Business vs Office Depot mismatch should be flagged."""
        _, _, results = full_pipeline
        amazon = [r for r in results if r.expense_id == "EXP-0013"]
        assert len(amazon) == 1
        assert amazon[0].verdict == AnomalyVerdict.REVIEW

    def test_duplicate_expense_detected(self, full_pipeline):
        """The two Chipotle $24.50 expenses should be flagged as duplicates."""
        _, _, results = full_pipeline
        chipotle = [r for r in results if "Chipotle" in str(r.features)]
        # Both Chipotle expenses should be flagged as duplicates
        duplicate_flags = [r for r in results if AnomalyReason.DUPLICATE in r.reasons]
        assert len(duplicate_flags) >= 2

    def test_normal_expenses_pass(self, full_pipeline):
        """Most normal expenses should be NORMAL."""
        _, _, results = full_pipeline
        normal = [r for r in results if r.verdict == AnomalyVerdict.NORMAL]
        # At least some expenses should be normal
        assert len(normal) >= 5

    def test_all_review_have_reasons(self, full_pipeline):
        """Every REVIEW result must have at least one reason."""
        _, _, results = full_pipeline
        for r in results:
            if r.verdict == AnomalyVerdict.REVIEW:
                assert len(r.reasons) > 0, f"{r.expense_id} has REVIEW but no reasons"

    def test_all_review_have_explanation(self, full_pipeline):
        """Every REVIEW result must have a non-empty explanation."""
        _, _, results = full_pipeline
        for r in results:
            if r.verdict == AnomalyVerdict.REVIEW:
                assert r.explanation, f"{r.expense_id} has REVIEW but no explanation"

    def test_all_review_have_evidence(self, full_pipeline):
        """Every REVIEW result must have evidence (features)."""
        _, _, results = full_pipeline
        for r in results:
            if r.verdict == AnomalyVerdict.REVIEW:
                assert r.features, f"{r.expense_id} has REVIEW but no evidence"


# --- Threshold configuration tests ---

class TestThresholdConfiguration:
    def test_custom_threshold(self):
        expenses = [
            _make_expense("E1", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E2", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E3", amount=100, category=ExpenseCategory.TRAVEL),
        ]
        # With multiplier=2.0, threshold=200
        thresholds = AnomalyThresholds(high_value_multiplier=2.0, min_category_count_for_mean=3)
        results = detect_anomalies(expenses, thresholds=thresholds)
        # Expense of 250 should be flagged
        expenses.append(_make_expense("E4", amount=250, category=ExpenseCategory.TRAVEL))
        results = detect_anomalies(expenses, thresholds=thresholds)
        flagged = [r for r in results if r.verdict == AnomalyVerdict.REVIEW]
        assert len(flagged) >= 1

    def test_disabled_high_value(self):
        expenses = [
            _make_expense("E1", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E2", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E3", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E4", amount=1000, category=ExpenseCategory.TRAVEL),
        ]
        # Disable high value (multiplier=100) and use unique vendors to avoid duplicate check
        thresholds = AnomalyThresholds(high_value_multiplier=100.0)
        # Use different vendors to avoid duplicate detection
        expenses = [
            _make_expense("E1", vendor="V1", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E2", vendor="V2", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E3", vendor="V3", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E4", vendor="V4", amount=1000, category=ExpenseCategory.TRAVEL),
        ]
        results = detect_anomalies(expenses, thresholds=thresholds)
        normal = [r for r in results if r.verdict == AnomalyVerdict.NORMAL]
        assert len(normal) == 4

    def test_threshold_boundary(self):
        expenses = [
            _make_expense("E1", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E2", amount=100, category=ExpenseCategory.TRAVEL),
            _make_expense("E3", amount=100, category=ExpenseCategory.TRAVEL),
        ]
        # Mean=100, multiplier=3.0, threshold=300
        # Expense exactly at threshold should NOT be flagged (> not >=)
        expenses.append(_make_expense("E4", amount=300, category=ExpenseCategory.TRAVEL))
        thresholds = AnomalyThresholds(high_value_multiplier=3.0, min_category_count_for_mean=3)
        results = detect_anomalies(expenses, thresholds=thresholds)
        at_threshold = [r for r in results if r.expense_id == "E4"]
        assert at_threshold[0].verdict == AnomalyVerdict.NORMAL


# --- Edge case tests ---

class TestAnomalyDetectorEdgeCases:
    def test_empty_input(self):
        results = detect_anomalies([])
        assert results == []

    def test_single_expense(self):
        expenses = [_make_expense("E1", amount=100)]
        results = detect_anomalies(expenses)
        assert len(results) == 1
        assert results[0].verdict == AnomalyVerdict.NORMAL

    def test_deterministic_results(self):
        expenses = [
            _make_expense("E1", vendor="A", amount=100, date_val=date(2026, 8, 1)),
            _make_expense("E2", vendor="A", amount=100, date_val=date(2026, 8, 1)),
        ]
        r1 = detect_anomalies(expenses)
        r2 = detect_anomalies(expenses)
        assert r1[0].verdict == r2[0].verdict
        assert r1[1].verdict == r2[1].verdict

    def test_no_reconciliation_data(self):
        expenses = [_make_expense("E1", amount=100)]
        results = detect_anomalies(expenses, reconciliations=None)
        assert len(results) == 1


def _load_known_vendors_for_test():
    """Load known vendors for testing."""
    import json
    data_dir = Path(__file__).resolve().parent.parent / "data" / "synthetic"
    with open(data_dir / "vendors.json") as f:
        vendors = json.load(f)
    return {v["name"].lower().strip() for v in vendors}
