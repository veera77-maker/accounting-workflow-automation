"""Tests for the reconciler."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from processors.reconciler import reconcile_expenses, _normalize_vendor, _vendor_match
from models.expense import ExpenseCategory, ExpenseRecord, ExpenseStatus
from models.receipt import ReceiptLineItem, ReceiptRecord
from models.reconciliation import ReconciliationStatus
from triggers.monthly_trigger import trigger_monthly_expense
from processors.expense_processor import process_expenses
from processors.receipt_processor import process_receipts


# --- Unit tests for helper functions ---

class TestNormalizeVendor:
    def test_basic_normalization(self):
        assert _normalize_vendor("Delta Airlines") == "delta airlines"

    def test_strips_whitespace(self):
        assert _normalize_vendor("  Uber Technologies  ") == "uber technologies"

    def test_removes_inc(self):
        assert _normalize_vendor("Acme Inc.") == "acme"
        assert _normalize_vendor("Acme Inc") == "acme"

    def test_removes_llc(self):
        assert _normalize_vendor("Widget LLC") == "widget"

    def test_removes_llp(self):
        assert _normalize_vendor("Baker & McKenzie LLP") == "baker & mckenzie"

    def test_removes_corp(self):
        assert _normalize_vendor("Acme Corp.") == "acme"
        assert _normalize_vendor("Acme Corp") == "acme"


class TestVendorMatch:
    def test_exact_match(self):
        match, method = _vendor_match("Delta Airlines", "Delta Airlines")
        assert match is True
        assert method == "exact"

    def test_case_insensitive(self):
        match, method = _vendor_match("delta airlines", "Delta Airlines")
        assert match is True

    def test_fuzzy_match(self):
        match, method = _vendor_match("Delta Airlines", "Delta Airline")
        assert match is True
        assert "similarity" in method

    def test_no_match(self):
        match, method = _vendor_match("Delta Airlines", "Hilton Hotels")
        assert match is False


# --- Integration tests with synthetic data ---

class TestReconcilerWithSyntheticData:
    """Tests using the full pipeline: trigger → expense processor → receipt processor → reconciler."""

    @pytest.fixture
    def reconciliation_results(self, tmp_path):
        """Run the full pipeline and return reconciliation results."""
        run = trigger_monthly_expense("TV-001", "2026-08", output_dir=tmp_path)
        expense_result = process_expenses(
            run.trigger_data["expense_file"], "TV-001", "2026-08"
        )
        receipt_result = process_receipts(run.trigger_data["receipt_file"])
        return reconcile_expenses(expense_result.records, receipt_result.records)

    def test_returns_list(self, reconciliation_results):
        assert isinstance(reconciliation_results, list)

    def test_one_result_per_expense(self, reconciliation_results):
        assert len(reconciliation_results) == 13

    def test_exact_matches_found(self, reconciliation_results):
        exact = [r for r in reconciliation_results if r.status == ReconciliationStatus.EXACT_MATCH]
        assert len(exact) == 11

    def test_amount_mismatch_found(self, reconciliation_results):
        amount_mismatch = [r for r in reconciliation_results if r.status == ReconciliationStatus.AMOUNT_MISMATCH]
        assert len(amount_mismatch) == 1
        assert amount_mismatch[0].expense_id == "EXP-0012"

    def test_vendor_mismatch_found(self, reconciliation_results):
        vendor_mismatch = [r for r in reconciliation_results if r.status == ReconciliationStatus.VENDOR_MISMATCH]
        assert len(vendor_mismatch) == 1
        assert vendor_mismatch[0].expense_id == "EXP-0013"

    def test_missing_receipt_found(self, reconciliation_results):
        missing = [r for r in reconciliation_results if r.status == ReconciliationStatus.MISSING_RECEIPT]
        assert len(missing) == 0

    def test_duplicate_expense_matched(self, reconciliation_results):
        # Expense row 13 (Chipotle, $24.50) should match RCP-012
        dup = [r for r in reconciliation_results if r.expense_id == "EXP-0014"]
        assert len(dup) == 1
        assert dup[0].status == ReconciliationStatus.EXACT_MATCH
        assert dup[0].receipt_id == "RCP-012"

    def test_all_results_have_reason(self, reconciliation_results):
        for r in reconciliation_results:
            assert r.reason, f"Missing reason for {r.expense_id}"

    def test_all_results_have_evidence(self, reconciliation_results):
        for r in reconciliation_results:
            assert r.evidence, f"Missing evidence for {r.expense_id}"

    def test_no_record_discarded(self, reconciliation_results):
        ids = [r.expense_id for r in reconciliation_results]
        assert len(ids) == 13
        assert len(set(ids)) == 13


# --- Edge case tests ---

class TestReconcilerEdgeCases:
    def test_empty_expenses(self):
        results = reconcile_expenses([], [])
        assert results == []

    def test_no_receipts_all_missing(self):
        expenses = [
            ExpenseRecord(
                expense_id="EXP-001", client_id="TV-001", employee="Test",
                date=date(2026, 8, 1), description="Test", vendor="Test Vendor",
                amount=100.0, category=ExpenseCategory.TRAVEL, month="2026-08",
            ),
        ]
        results = reconcile_expenses(expenses, [])
        assert len(results) == 1
        assert results[0].status == ReconciliationStatus.MISSING_RECEIPT

    def test_receipt_not_found(self):
        expenses = [
            ExpenseRecord(
                expense_id="EXP-001", client_id="TV-001", employee="Test",
                date=date(2026, 8, 1), description="Test", vendor="Test Vendor",
                amount=100.0, category=ExpenseCategory.TRAVEL,
                receipt_reference="RCP-NONEXISTENT", month="2026-08",
            ),
        ]
        results = reconcile_expenses(expenses, [])
        assert len(results) == 1
        assert results[0].status == ReconciliationStatus.MISSING_RECEIPT
        assert "RCP-NONEXISTENT" in results[0].reason

    def test_amount_mismatch_detail(self):
        expenses = [
            ExpenseRecord(
                expense_id="EXP-001", client_id="TV-001", employee="Test",
                date=date(2026, 8, 1), description="Test", vendor="Delta Airlines",
                amount=500.0, category=ExpenseCategory.TRAVEL,
                receipt_reference="RCP-001", month="2026-08",
            ),
        ]
        receipts = [
            ReceiptRecord(
                receipt_id="RCP-001", vendor="Delta Airlines", amount=487.0,
                date=date(2026, 8, 1),
            ),
        ]
        results = reconcile_expenses(expenses, receipts)
        assert results[0].status == ReconciliationStatus.AMOUNT_MISMATCH
        assert "500.00" in results[0].reason
        assert "487.00" in results[0].reason

    def test_vendor_mismatch_detail(self):
        expenses = [
            ExpenseRecord(
                expense_id="EXP-001", client_id="TV-001", employee="Test",
                date=date(2026, 8, 1), description="Test", vendor="Acme Corp",
                amount=100.0, category=ExpenseCategory.OFFICE_SUPPLIES,
                receipt_reference="RCP-001", month="2026-08",
            ),
        ]
        receipts = [
            ReceiptRecord(
                receipt_id="RCP-001", vendor="Beta Inc", amount=100.0,
                date=date(2026, 8, 1),
            ),
        ]
        results = reconcile_expenses(expenses, receipts)
        assert results[0].status == ReconciliationStatus.VENDOR_MISMATCH
        assert "Acme Corp" in results[0].reason
        assert "Beta Inc" in results[0].reason

    def test_date_mismatch_detail(self):
        expenses = [
            ExpenseRecord(
                expense_id="EXP-001", client_id="TV-001", employee="Test",
                date=date(2026, 8, 1), description="Test", vendor="Test Vendor",
                amount=100.0, category=ExpenseCategory.TRAVEL,
                receipt_reference="RCP-001", month="2026-08",
            ),
        ]
        receipts = [
            ReceiptRecord(
                receipt_id="RCP-001", vendor="Test Vendor", amount=100.0,
                date=date(2026, 8, 15),
            ),
        ]
        results = reconcile_expenses(expenses, receipts)
        assert results[0].status == ReconciliationStatus.DATE_MISMATCH
        assert "2026-08-01" in results[0].reason
        assert "2026-08-15" in results[0].reason

    def test_amount_within_tolerance_matches(self):
        expenses = [
            ExpenseRecord(
                expense_id="EXP-001", client_id="TV-001", employee="Test",
                date=date(2026, 8, 1), description="Test", vendor="Test Vendor",
                amount=100.005, category=ExpenseCategory.TRAVEL,
                receipt_reference="RCP-001", month="2026-08",
            ),
        ]
        receipts = [
            ReceiptRecord(
                receipt_id="RCP-001", vendor="Test Vendor", amount=100.0,
                date=date(2026, 8, 1),
            ),
        ]
        results = reconcile_expenses(expenses, receipts)
        assert results[0].status == ReconciliationStatus.EXACT_MATCH
