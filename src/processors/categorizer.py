"""Categorizer — assigns expense categories using deterministic rules.

This component handles the "Expense categorization" step of the Case 3 workflow.

Design decisions:
- Deterministic rules only for this prototype — no ML or LLM.
- Rules are based on:
  1. Vendor name → known category (from vendors.json)
  2. Description keywords → category heuristics
- ML is NOT necessary yet because:
  - All vendors in the synthetic data have clear, unambiguous category assignments.
  - The 8 Case 3 categories map directly to known vendor types.
  - There is no ambiguous classification problem in the current dataset.
- If future data includes vendors that span multiple categories, or descriptions
  that don't match known vendors, ML would be appropriate then.
- This module does NOT modify the expense records — it returns a list of
  categorization results, keeping processing pure.
"""

from __future__ import annotations

import json
from pathlib import Path

from models.expense import ExpenseCategory, ExpenseRecord


DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "synthetic"


def _load_vendor_categories() -> dict[str, str]:
    """Load vendor → category mapping from vendors.json.

    Returns a dict keyed by normalized vendor name.
    """
    with open(DATA_DIR / "vendors.json") as f:
        vendors = json.load(f)
    return {v["name"].lower().strip(): v["category"] for v in vendors}


# Description keyword → category mapping (fallback when vendor is unknown).
KEYWORD_CATEGORY_MAP: dict[list[str], ExpenseCategory] = {
    ("flight", "airline", "airfare", "airport", "travel"): ExpenseCategory.TRAVEL,
    ("hotel", "motel", "lodge", "accommodation", "stay"): ExpenseCategory.TRAVEL,
    ("uber", "lyft", "taxi", "cab", "rideshare"): ExpenseCategory.TRAVEL,
    ("mileage", "mile", "driving"): ExpenseCategory.TRAVEL,
    ("dinner", "lunch", "breakfast", "meal", "restaurant", "cafe", "coffee",
     "food", "entertainment", "client dinner", "team lunch"): ExpenseCategory.MEALS_ENTERTAINMENT,
    ("software", "license", "subscription", "saas", "cloud"): ExpenseCategory.SOFTWARE,
    ("office supply", "paper", "toner", "printer", "pen", "supplies"): ExpenseCategory.OFFICE_SUPPLIES,
    ("consulting", "legal", "audit", "accounting", "professional"): ExpenseCategory.PROFESSIONAL_SERVICES,
    ("internet", "electric", "gas", "water", "utility", "phone", "telecom"): ExpenseCategory.UTILITIES,
    ("marketing", "advertising", "ad", "campaign", "promotion"): ExpenseCategory.MARKETING,
}


class CategorizationResult:
    """Result of categorizing a single expense."""

    def __init__(
        self,
        expense_id: str,
        category: ExpenseCategory,
        method: str,
        confidence: float = 1.0,
        original_category: ExpenseCategory | None = None,
    ):
        self.expense_id = expense_id
        self.category = category
        self.method = method
        self.confidence = confidence
        self.original_category = original_category

    def to_dict(self) -> dict:
        return {
            "expense_id": self.expense_id,
            "category": self.category.value,
            "method": self.method,
            "confidence": self.confidence,
            "original_category": self.original_category.value if self.original_category else None,
        }


class CategorizerResult:
    """Output of the categorizer — results plus summary stats."""

    def __init__(self, results: list[CategorizationResult]):
        self.results = results

    @property
    def count(self) -> int:
        return len(self.results)

    @property
    def vendor_matched(self) -> int:
        return sum(1 for r in self.results if r.method == "vendor_lookup")

    @property
    def keyword_matched(self) -> int:
        return sum(1 for r in self.results if r.method == "keyword_heuristic")

    @property
    def unmatched(self) -> int:
        return sum(1 for r in self.results if r.method == "unmatched")

    def to_dict(self) -> dict:
        return {
            "results": [r.to_dict() for r in self.results],
            "count": self.count,
            "vendor_matched": self.vendor_matched,
            "keyword_matched": self.keyword_matched,
            "unmatched": self.unmatched,
        }


def _match_by_keywords(description: str) -> ExpenseCategory | None:
    """Try to match a description to a category using keyword heuristics."""
    desc_lower = description.lower()
    for keywords, category in KEYWORD_CATEGORY_MAP.items():
        for keyword in keywords:
            if keyword in desc_lower:
                return category
    return None


def categorize_expenses(
    expenses: list[ExpenseRecord],
) -> CategorizerResult:
    """Assign categories to expense records using deterministic rules.

    This function does NOT modify the input records. It returns a list of
    CategorizationResult objects that can be applied to records by the caller.

    Args:
        expenses: List of ExpenseRecord objects.

    Returns:
        CategorizerResult with categorization for each expense.
    """
    vendor_categories = _load_vendor_categories()

    results: list[CategorizationResult] = []

    for expense in expenses:
        # Strategy 1: Exact vendor match from vendors.json
        vendor_key = expense.vendor.lower().strip()
        if vendor_key in vendor_categories:
            cat_str = vendor_categories[vendor_key]
            try:
                category = ExpenseCategory(cat_str)
                results.append(CategorizationResult(
                    expense_id=expense.expense_id,
                    category=category,
                    method="vendor_lookup",
                    confidence=1.0,
                    original_category=expense.category,
                ))
                continue
            except ValueError:
                pass

        # Strategy 2: Fuzzy vendor match (contains check)
        matched_category = None
        for known_vendor, cat_str in vendor_categories.items():
            if known_vendor in vendor_key or vendor_key in known_vendor:
                try:
                    matched_category = ExpenseCategory(cat_str)
                    break
                except ValueError:
                    pass

        if matched_category is not None:
            results.append(CategorizationResult(
                expense_id=expense.expense_id,
                category=matched_category,
                method="vendor_lookup",
                confidence=0.9,
                original_category=expense.category,
            ))
            continue

        # Strategy 3: Description keyword heuristics
        keyword_category = _match_by_keywords(expense.description)
        if keyword_category is not None:
            results.append(CategorizationResult(
                expense_id=expense.expense_id,
                category=keyword_category,
                method="keyword_heuristic",
                confidence=0.7,
                original_category=expense.category,
            ))
            continue

        # Strategy 4: No match — return original category or Miscellaneous
        fallback = expense.category if expense.category else ExpenseCategory.MISCELLANEOUS
        results.append(CategorizationResult(
            expense_id=expense.expense_id,
            category=fallback,
            method="unmatched",
            confidence=0.5,
            original_category=expense.category,
        ))

    return CategorizerResult(results)
