"""Tests for the receipt processor."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from processors.receipt_processor import (
    ReceiptProcessorResult,
    process_receipts,
)
from models.receipt import ReceiptRecord
from triggers.monthly_trigger import trigger_monthly_expense


class TestReceiptProcessor:
    """Tests for process_receipts function."""

    @pytest.fixture
    def receipt_data(self, tmp_path):
        """Generate receipt JSON and return path."""
        run = trigger_monthly_expense("TV-001", "2026-08", output_dir=tmp_path)
        return run.trigger_data["receipt_file"]

    def test_returns_processor_result(self, receipt_data):
        result = process_receipts(receipt_data)
        assert isinstance(result, ReceiptProcessorResult)

    def test_extracts_all_receipts(self, receipt_data):
        result = process_receipts(receipt_data)
        # 13 receipts in the synthetic data
        assert result.success_count == 13
        assert result.error_count == 0

    def test_receipt_fields_are_populated(self, receipt_data):
        result = process_receipts(receipt_data)
        first = result.records[0]
        assert first.receipt_id == "RCP-001"
        assert first.vendor == "Delta Airlines"
        assert first.amount == 487.00
        assert first.date.year == 2026
        assert first.date.month == 8
        assert first.date.day == 3

    def test_line_items_are_extracted(self, receipt_data):
        result = process_receipts(receipt_data)
        # RCP-004 (Capital Grille) has 4 line items
        capital_grille = [r for r in result.records if r.receipt_id == "RCP-004"][0]
        assert len(capital_grille.line_items) == 4
        assert capital_grille.line_items[0].description == "Ribeye steak"
        assert capital_grille.line_items[0].amount == 89.00

    def test_receipts_without_line_items(self, receipt_data):
        result = process_receipts(receipt_data)
        # RCP-001 (Delta) has 1 line item
        delta = [r for r in result.records if r.receipt_id == "RCP-001"][0]
        assert len(delta.line_items) == 1

    def test_source_file_is_set(self, receipt_data):
        result = process_receipts(receipt_data)
        for record in result.records:
            assert record.source_file is not None

    def test_amounts_are_non_negative(self, receipt_data):
        result = process_receipts(receipt_data)
        for record in result.records:
            assert record.amount >= 0

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            process_receipts("/nonexistent/receipts.json")

    def test_invalid_json_bad_amount(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        with open(bad_file, "w") as f:
            json.dump([{
                "receipt_id": "RCP-BAD",
                "vendor": "Test",
                "amount": "not_a_number",
                "date": "2026-08-01",
            }], f)
        result = process_receipts(bad_file)
        assert result.error_count == 1
        assert result.success_count == 0

    def test_invalid_json_missing_receipt_id(self, tmp_path):
        bad_file = tmp_path / "no_id.json"
        with open(bad_file, "w") as f:
            json.dump([{
                "receipt_id": "",
                "vendor": "Test",
                "amount": 100,
                "date": "2026-08-01",
            }], f)
        result = process_receipts(bad_file)
        assert result.error_count == 1
        assert "Missing receipt_id" in result.errors[0].error_message

    def test_invalid_json_missing_vendor(self, tmp_path):
        bad_file = tmp_path / "no_vendor.json"
        with open(bad_file, "w") as f:
            json.dump([{
                "receipt_id": "RCP-001",
                "vendor": "",
                "amount": 100,
                "date": "2026-08-01",
            }], f)
        result = process_receipts(bad_file)
        assert result.error_count == 1
        assert "Missing vendor" in result.errors[0].error_message

    def test_result_to_dict(self, receipt_data):
        result = process_receipts(receipt_data)
        d = result.to_dict()
        assert "records" in d
        assert "errors" in d
        assert d["success_count"] == 13
        assert isinstance(d["records"][0], dict)
