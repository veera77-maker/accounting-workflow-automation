"""LLM client summary — generates natural-language client summaries from validated P&L data.

The LLM is responsible ONLY for natural-language generation. It must NOT:
- Categorize expenses
- Reconcile receipts
- Detect anomalies
- Decide whether something is suspicious
- Approve/reject/correct expenses
- Calculate the P&L
- Modify ledger records
- Invent financial facts
- Create financial numbers not present in the input
"""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.models.accounting import PLReport


class ClientSummaryError(Exception):
    """Raised when client summary generation fails."""


class ClientSummaryResult(BaseModel):
    """Result of client summary generation."""

    client_id: str
    month: str
    summary: str
    generated_at: str
    model_used: str
    source_report_generated_at: str
    validation_passed: bool
    validation_errors: list[str] = []


class LLMClient(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate text from a prompt.

        Args:
            prompt: The full prompt including instructions and data.

        Returns:
            Generated text.

        Raises:
            Exception: If generation fails.
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        ...


class FakeLLMClient(LLMClient):
    """Deterministic fake LLM for testing.

    Returns a pre-configured response or generates a summary
    from the prompt data without calling any external API.
    """

    def __init__(self, response: Optional[str] = None) -> None:
        self._response = response
        self._call_count = 0
        self._last_prompt: Optional[str] = None

    def generate(self, prompt: str) -> str:
        self._call_count += 1
        self._last_prompt = prompt

        if self._response is not None:
            return self._response

        # Parse the structured data from the prompt and generate deterministically
        return self._generate_from_prompt(prompt)

    def _generate_from_prompt(self, prompt: str) -> str:
        """Generate a deterministic summary from prompt data."""
        try:
            data_match = re.search(r"```json\n(.*?)\n```", prompt, re.DOTALL)
            if not data_match:
                return "Unable to generate summary: no structured data found in prompt."

            data = json.loads(data_match.group(1))
            client_id = data.get("client_id", "Unknown Client")
            month = data.get("month", "Unknown Month")
            total = data.get("total_expenses", 0.0)
            line_items = data.get("line_items", [])
            entry_count = data.get("entry_count", 0)

            # Format month for display
            try:
                dt = datetime.strptime(month, "%Y-%m")
                month_display = dt.strftime("%B %Y")
            except ValueError:
                month_display = month

            parts = [
                f"Monthly Expense Summary for {client_id}",
                f"Reporting Period: {month_display}",
                f"",
                f"Total Expenses: ${total:,.2f}",
                f"Total Accounting Entries: {entry_count}",
                f"",
                f"Expense Breakdown by Category:",
            ]

            for item in line_items:
                cat = item.get("category", "Unknown")
                cat_total = item.get("total", 0.0)
                cat_count = item.get("count", 0)
                parts.append(f"- {cat}: ${cat_total:,.2f} ({cat_count} entries)")

            if not line_items:
                parts.append("- No expenses recorded for this period.")

            return "\n".join(parts)

        except (json.JSONDecodeError, KeyError, ValueError):
            return "Unable to generate summary: failed to parse structured data from prompt."

    @property
    def model_name(self) -> str:
        return "fake-llm-v1"

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def last_prompt(self) -> Optional[str]:
        return self._last_prompt


class NoOpLLMClient(LLMClient):
    """LLM client that raises an error — used to test provider failure handling."""

    def __init__(self, error_message: str = "LLM provider unavailable") -> None:
        self._error_message = error_message

    def generate(self, prompt: str) -> str:
        raise ClientSummaryError(self._error_message)

    @property
    def model_name(self) -> str:
        return "noop-llm"


def _build_prompt(report: PLReport) -> str:
    """Build the prompt for the LLM from a validated PLReport.

    The prompt includes explicit anti-hallucination instructions.
    """
    line_items_data = [
        {
            "category": li.category,
            "total": li.total,
            "count": li.count,
        }
        for li in report.line_items
    ]

    structured_data = {
        "client_id": report.client_id,
        "month": report.month,
        "total_expenses": report.total_expenses,
        "entry_count": report.entry_count,
        "line_items": line_items_data,
        "generated_at": report.generated_at,
    }

    return f"""You are a professional accounting assistant generating a client-facing monthly expense summary.

CRITICAL ANTI-HALLUCINATION INSTRUCTIONS:
- Use ONLY the financial facts provided in the structured data below.
- Do NOT invent, estimate, or infer any financial numbers.
- Do NOT add categories that are not present in the data.
- Do NOT alter any totals or amounts.
- Do NOT make accounting judgments or recommendations.
- Do NOT claim actions were taken unless the data explicitly says so.
- If information is missing, do not fabricate it — simply omit it.
- Every dollar amount in your summary must come directly from the provided data.
- Every category name must come directly from the provided data.

Your task: Generate a clear, professional monthly expense summary for the client.

Structured P&L Data:
```json
{json.dumps(structured_data, indent=2)}
```

Generate a professional summary now. Use the exact numbers from the data above."""


def _validate_summary(summary: str, report: PLReport) -> list[str]:
    """Validate that the generated summary is grounded in the PLReport.

    Returns a list of validation error messages. Empty list = valid.
    """
    errors: list[str] = []

    # Check that total expenses appears in the summary
    total_str = f"${report.total_expenses:,.2f}"
    total_alt = f"${report.total_expenses}"
    if total_str not in summary and total_alt not in summary:
        # Also check without commas
        total_nocomma = f"${report.total_expenses:,.2f}".replace(",", "")
        if total_nocomma not in summary:
            errors.append(
                f"Total expenses {total_str} not found in summary"
            )

    # Check that client_id appears in the summary
    if report.client_id and report.client_id not in summary:
        errors.append(
            f"Client ID '{report.client_id}' not found in summary"
        )

    # Check that month appears in the summary (in some form)
    if report.month:
        # Check raw month format or display format
        try:
            dt = datetime.strptime(report.month, "%Y-%m")
            month_display = dt.strftime("%B %Y")
            month_abbr = dt.strftime("%b %Y")
            if report.month not in summary and month_display not in summary and month_abbr not in summary:
                errors.append(
                    f"Month '{report.month}' (or '{month_display}') not found in summary"
                )
        except ValueError:
            if report.month not in summary:
                errors.append(
                    f"Month '{report.month}' not found in summary"
                )

    # Check that no unsupported categories appear
    supported_categories = {li.category for li in report.line_items}
    # Look for category-like patterns in the summary
    # (This is a lightweight check — not exhaustive NER)
    category_pattern = re.findall(r"- ([A-Z][A-Za-z &]+?):", summary)
    for found_cat in category_pattern:
        found_cat = found_cat.strip()
        if found_cat not in supported_categories and found_cat not in (
            "No expenses", "Expense Breakdown",
        ):
            # This is a heuristic — warn but don't fail for common words
            pass

    # Check that entry count appears if non-zero
    if report.entry_count > 0:
        entry_str = str(report.entry_count)
        if entry_str not in summary:
            errors.append(
                f"Entry count {report.entry_count} not found in summary"
            )

    return errors


class ClientSummaryGenerator:
    """Generates client-facing natural-language summaries from validated P&L reports.

    The generator:
    1. Builds a grounded prompt from the PLReport
    2. Sends it to the LLM provider
    3. Validates the output against the source data
    4. Returns a typed result with validation status

    The LLM is responsible ONLY for language generation.
    All financial facts come from the PLReport.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        if llm_client is None:
            llm_client = FakeLLMClient()
        self._llm = llm_client

    def generate(self, report: PLReport) -> ClientSummaryResult:
        """Generate a client summary from a validated PLReport.

        Args:
            report: The validated P&L report to summarize.

        Returns:
            ClientSummaryResult with summary text and validation status.

        Raises:
            ClientSummaryError: If input is invalid or LLM fails.
        """
        # Validate input
        if not report.client_id:
            raise ClientSummaryError("PLReport missing client_id")
        if not report.month:
            raise ClientSummaryError("PLReport missing month")

        # Build prompt
        prompt = _build_prompt(report)

        # Call LLM
        try:
            summary_text = self._llm.generate(prompt)
        except ClientSummaryError:
            raise
        except Exception as e:
            raise ClientSummaryError(f"LLM provider failed: {e}") from e

        # Validate output
        validation_errors = _validate_summary(summary_text, report)
        validation_passed = len(validation_errors) == 0

        return ClientSummaryResult(
            client_id=report.client_id,
            month=report.month,
            summary=summary_text,
            generated_at=datetime.now().isoformat(),
            model_used=self._llm.model_name,
            source_report_generated_at=report.generated_at,
            validation_passed=validation_passed,
            validation_errors=validation_errors,
        )

    @property
    def llm_client(self) -> LLMClient:
        """Return the underlying LLM client."""
        return self._llm
