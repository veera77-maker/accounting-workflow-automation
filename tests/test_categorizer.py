"""Tests for the categorizer."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from processors.categorizer import (
    CategorizerResult,
    CategorizationResult,
    _match_by_keywords,
    categorize_expenses,
)
from models.expense import ExpenseCategory, ExpenseRecord
from triggers.monthly_trigger import trigger_monthly_expense
from processors.expense_processor import process_expenses


# --- Unit tests for keyword matching ---

class TestKeywordMatching:
    def test_flight_matches_travel(self):
        result = _match_by_keywords("Flight to NYC for client meeting")
        assert result == ExpenseCategory.TRAVEL

    def test_hotel_matches_travel(self):
        result = _match_by_keywords("Hotel stay - NYC 2 nights")
        assert result == ExpenseCategory.TRAVEL

    def test_uber_matches_travel(self):
        result = _match_by_keywords("Uber to/from airport")
        assert result == ExpenseCategory.TRAVEL

    def test_dinner_matches_meals(self):
        result = _match_by_keywords("Client dinner - Pinnacle pitch")
        assert result == ExpenseCategory.MEALS_ENTERTAINMENT

    def test_lunch_matches_meals(self):
        result = _match_by_keywords("Team lunch")
        assert result == ExpenseCategory.MEALS_ENTERTAINMENT

    def test_coffee_matches_meals(self):
        result = _match_by_keywords("Office coffee run")
        assert result == ExpenseCategory.MEALS_ENTERTAINMENT

    def test_software_matches_software(self):
        result = _match_by_keywords("Microsoft 365 annual license")
        assert result == ExpenseCategory.SOFTWARE

    def test_supplies_matches_office(self):
        result = _match_by_keywords("Printer paper and toner")
        assert result == ExpenseCategory.OFFICE_SUPPLIES

    def test_consulting_matches_professional(self):
        result = _match_by_keywords("Legal consulting services")
        assert result == ExpenseCategory.PROFESSIONAL_SERVICES

    def test_internet_matches_utilities(self):
        result = _match_by_keywords("Internet service - August")
        assert result == ExpenseCategory.UTILITIES

    def test_marketing_matches_marketing(self):
        result = _match_by_keywords("Google advertising campaign")
        assert result == ExpenseCategory.MARKETING

    def test_unknown_returns_none(self):
        result = _match_by_keywords("Something completely unrelated")
        assert result is None


# --- Integration tests with synthetic data ---

class TestCategorizerWithSyntheticData:
    """Tests using the full pipeline: trigger → expense processor → categorizer."""

    @pytest.fixture
    def categorizer_result(self, tmp_path):
        """Run the pipeline and return categorizer results."""
        run = trigger_monthly_expense("TV-001", "2026-08", output_dir=tmp_path)
        expense_result = process_expenses(
            run.trigger_data["expense_file"], "TV-001", "2026-08"
        )
        return categorize_expenses(expense_result.records)

    def test_returns_categorizer_result(self, categorizer_result):
        assert isinstance(categorizer_result, CategorizerResult)

    def test_all_expenses_categorized(self, categorizer_result):
        assert categorizer_result.count == 13

    def test_all_via_vendor_lookup(self, categorizer_result):
        # All vendors in synthetic data are in vendors.json
        assert categorizer_result.vendor_matched == 13
        assert categorizer_result.keyword_matched == 0
        assert categorizer_result.unmatched == 0

    def test_travel_categories(self, categorizer_result):
        travel = [r for r in categorizer_result.results if r.category == ExpenseCategory.TRAVEL]
        assert len(travel) == 3

    def test_meals_categories(self, categorizer_result):
        meals = [r for r in categorizer_result.results if r.category == ExpenseCategory.MEALS_ENTERTAINMENT]
        assert len(meals) == 5

    def test_software_categories(self, categorizer_result):
        software = [r for r in categorizer_result.results if r.category == ExpenseCategory.SOFTWARE]
        assert len(software) == 2

    def test_office_supplies_categories(self, categorizer_result):
        office = [r for r in categorizer_result.results if r.category == ExpenseCategory.OFFICE_SUPPLIES]
        assert len(office) == 2

    def test_utilities_categories(self, categorizer_result):
        utilities = [r for r in categorizer_result.results if r.category == ExpenseCategory.UTILITIES]
        assert len(utilities) == 1

    def test_category_distribution(self, categorizer_result):
        """Verify the expected distribution across categories."""
        from collections import Counter
        dist = Counter(r.category.value for r in categorizer_result.results)
        assert dist["Travel"] == 3
        assert dist["Meals & Entertainment"] == 5
        assert dist["Software"] == 2
        assert dist["Office Supplies"] == 2
        assert dist["Utilities"] == 1

    def test_all_results_have_method(self, categorizer_result):
        for r in categorizer_result.results:
            assert r.method in ("vendor_lookup", "keyword_heuristic", "unmatched")

    def test_all_results_have_confidence(self, categorizer_result):
        for r in categorizer_result.results:
            assert 0.0 <= r.confidence <= 1.0

    def test_no_record_modified(self, tmp_path):
        """Categorizer should not modify original expense records."""
        run = trigger_monthly_expense("TV-001", "2026-08", output_dir=tmp_path)
        expense_result = process_expenses(
            run.trigger_data["expense_file"], "TV-001", "2026-08"
        )
        original_categories = [r.category for r in expense_result.records]
        categorize_expenses(expense_result.records)
        current_categories = [r.category for r in expense_result.records]
        assert original_categories == current_categories

    def test_result_to_dict(self, categorizer_result):
        d = categorizer_result.to_dict()
        assert "results" in d
        assert "count" in d
        assert d["count"] == 13
        assert isinstance(d["results"][0], dict)


# --- Edge case tests ---

class TestCategorizerEdgeCases:
    def test_empty_expenses(self):
        result = categorize_expenses([])
        assert result.count == 0

    def test_unknown_vendor_falls_to_keywords(self):
        expenses = [
            ExpenseRecord(
                expense_id="EXP-001", client_id="TV-001", employee="Test",
                date=date(2026, 8, 1), description="Flight to NYC",
                vendor="Unknown Airline Co", amount=500.0,
                category=ExpenseCategory.MISCELLANEOUS, month="2026-08",
            ),
        ]
        result = categorize_expenses(expenses)
        assert result.results[0].category == ExpenseCategory.TRAVEL
        assert result.results[0].method == "keyword_heuristic"

    def test_unknown_vendor_unknown_description(self):
        expenses = [
            ExpenseRecord(
                expense_id="EXP-001", client_id="TV-001", employee="Test",
                date=date(2026, 8, 1), description="Some random thing",
                vendor="Unknown Vendor", amount=50.0,
                category=ExpenseCategory.MISCELLANEOUS, month="2026-08",
            ),
        ]
        result = categorize_expenses(expenses)
        assert result.results[0].method == "unmatched"
        assert result.results[0].category == ExpenseCategory.MISCELLANEOUS
