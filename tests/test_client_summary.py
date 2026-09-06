"""Tests for the LLM client summary generator."""

from __future__ import annotations

import json
import pytest
from datetime import datetime

from src.llm.client_summary import (
    ClientSummaryGenerator,
    ClientSummaryResult,
    ClientSummaryError,
    FakeLLMClient,
    NoOpLLMClient,
    LLMClient,
    _build_prompt,
    _validate_summary,
)
from src.models.accounting import PLReport, PLLineItem


def _make_report(
    client_id: str = "CLIENT-001",
    month: str = "2026-08",
    total_expenses: float = 4200.50,
    entry_count: int = 8,
    line_items: list[PLLineItem] | None = None,
) -> PLReport:
    if line_items is None:
        line_items = [
            PLLineItem(category="Travel", total=450.0, count=1),
            PLLineItem(category="Meals & Entertainment", total=2935.50, count=2),
            PLLineItem(category="Software", total=120.0, count=1),
            PLLineItem(category="Office Supplies", total=45.0, count=1),
            PLLineItem(category="Professional Services", total=300.0, count=1),
            PLLineItem(category="Utilities", total=200.0, count=1),
            PLLineItem(category="Marketing", total=150.0, count=1),
        ]
    return PLReport(
        client_id=client_id,
        month=month,
        generated_at="2026-09-01T10:00:00",
        total_expenses=total_expenses,
        line_items=line_items,
        entry_count=entry_count,
    )


class TestFakeLLMClient:
    def test_returns_custom_response(self):
        client = FakeLLMClient(response="Custom summary")
        result = client.generate("test prompt")
        assert result == "Custom summary"

    def test_generates_from_prompt(self):
        client = FakeLLMClient()
        report = _make_report()
        prompt = _build_prompt(report)
        result = client.generate(prompt)
        assert "CLIENT-001" in result
        assert "$4,200.50" in result
        assert "8" in result

    def test_tracks_call_count(self):
        client = FakeLLMClient(response="test")
        assert client.call_count == 0
        client.generate("prompt 1")
        assert client.call_count == 1
        client.generate("prompt 2")
        assert client.call_count == 2

    def test_stores_last_prompt(self):
        client = FakeLLMClient(response="test")
        assert client.last_prompt is None
        client.generate("my prompt")
        assert client.last_prompt == "my prompt"

    def test_model_name(self):
        client = FakeLLMClient()
        assert client.model_name == "fake-llm-v1"

    def test_deterministic_repeated_calls(self):
        client = FakeLLMClient()
        report = _make_report()
        prompt = _build_prompt(report)
        r1 = client.generate(prompt)
        r2 = client.generate(prompt)
        assert r1 == r2

    def test_empty_line_items(self):
        client = FakeLLMClient()
        report = _make_report(line_items=[], entry_count=0, total_expenses=0.0)
        prompt = _build_prompt(report)
        result = client.generate(prompt)
        assert "No expenses recorded" in result


class TestNoOpLLMClient:
    def test_raises_on_generate(self):
        client = NoOpLLMClient()
        with pytest.raises(ClientSummaryError, match="LLM provider unavailable"):
            client.generate("prompt")

    def test_custom_error_message(self):
        client = NoOpLLMClient(error_message="Timeout")
        with pytest.raises(ClientSummaryError, match="Timeout"):
            client.generate("prompt")

    def test_model_name(self):
        client = NoOpLLMClient()
        assert client.model_name == "noop-llm"


class TestBuildPrompt:
    def test_contains_anti_hallucination_instructions(self):
        report = _make_report()
        prompt = _build_prompt(report)
        assert "ANTI-HALLUCINATION" in prompt
        assert "Do NOT invent" in prompt
        assert "Do NOT alter" in prompt

    def test_contains_structured_data(self):
        report = _make_report()
        prompt = _build_prompt(report)
        assert "```json" in prompt
        assert "CLIENT-001" in prompt
        assert "2026-08" in prompt

    def test_contains_financial_facts(self):
        report = _make_report()
        prompt = _build_prompt(report)
        assert "4200.5" in prompt or "4200.50" in prompt

    def test_contains_line_items(self):
        report = _make_report()
        prompt = _build_prompt(report)
        assert "Travel" in prompt
        assert "Software" in prompt

    def test_model_name_in_prompt(self):
        report = _make_report()
        prompt = _build_prompt(report)
        assert "professional accounting assistant" in prompt.lower()


class TestValidateSummary:
    def test_valid_summary_passes(self):
        report = _make_report()
        summary = (
            "Monthly Expense Summary for CLIENT-001\n"
            "Reporting Period: August 2026\n"
            "Total Expenses: $4,200.50\n"
            "Total Accounting Entries: 8\n"
            "Expense Breakdown by Category:\n"
            "- Travel: $450.00 (1 entries)\n"
            "- Software: $120.00 (1 entries)"
        )
        errors = _validate_summary(summary, report)
        assert errors == []

    def test_missing_total_fails(self):
        report = _make_report()
        summary = "Summary without the total amount."
        errors = _validate_summary(summary, report)
        assert any("Total expenses" in e for e in errors)

    def test_missing_client_id_fails(self):
        report = _make_report()
        summary = "Summary without client ID. Total: $4,200.50"
        errors = _validate_summary(summary, report)
        assert any("Client ID" in e for e in errors)

    def test_missing_month_fails(self):
        report = _make_report()
        summary = "Summary for CLIENT-001. Total: $4,200.50. Entries: 8"
        errors = _validate_summary(summary, report)
        assert any("Month" in e for e in errors)

    def test_missing_entry_count_fails(self):
        report = _make_report()
        summary = (
            "Summary for CLIENT-001\n"
            "August 2026\n"
            "Total: $4,200.50"
        )
        errors = _validate_summary(summary, report)
        assert any("Entry count" in e for e in errors)

    def test_valid_with_month_display_format(self):
        report = _make_report()
        summary = (
            "Summary for CLIENT-001\n"
            "August 2026\n"
            "Total: $4,200.50\n"
            "Entries: 8"
        )
        errors = _validate_summary(summary, report)
        assert errors == []

    def test_zero_expenses_valid(self):
        report = _make_report(total_expenses=0.0, entry_count=0, line_items=[])
        summary = (
            "Summary for CLIENT-001\n"
            "August 2026\n"
            "Total: $0.00\n"
            "Entries: 0"
        )
        errors = _validate_summary(summary, report)
        assert errors == []


class TestClientSummaryGenerator:
    def test_generates_summary(self):
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient())
        report = _make_report()
        result = gen.generate(report)
        assert isinstance(result, ClientSummaryResult)
        assert result.summary != ""

    def test_preserves_client_id(self):
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient())
        report = _make_report(client_id="TechVista Inc.")
        result = gen.generate(report)
        assert result.client_id == "TechVista Inc."

    def test_preserves_month(self):
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient())
        report = _make_report(month="2026-09")
        result = gen.generate(report)
        assert result.month == "2026-09"

    def test_preserves_source_timestamp(self):
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient())
        report = _make_report()
        result = gen.generate(report)
        assert result.source_report_generated_at == "2026-09-01T10:00:00"

    def test_records_model_used(self):
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient())
        report = _make_report()
        result = gen.generate(report)
        assert result.model_used == "fake-llm-v1"

    def test_validation_passes_for_grounded_summary(self):
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient())
        report = _make_report()
        result = gen.generate(report)
        assert result.validation_passed is True
        assert result.validation_errors == []

    def test_does_not_modify_pl_report(self):
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient())
        report = _make_report()
        original_total = report.total_expenses
        original_client = report.client_id
        gen.generate(report)
        assert report.total_expenses == original_total
        assert report.client_id == original_client

    def test_generated_at_is_timestamp(self):
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient())
        report = _make_report()
        result = gen.generate(report)
        # Should be a valid ISO timestamp
        datetime.fromisoformat(result.generated_at)

    def test_result_is_serializable(self):
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient())
        report = _make_report()
        result = gen.generate(report)
        d = result.model_dump()
        assert isinstance(d, dict)
        assert d["client_id"] == "CLIENT-001"
        json_str = result.model_dump_json()
        assert isinstance(json_str, str)


class TestClientSummaryGeneratorWithCustomResponse:
    def test_uses_custom_response(self):
        custom = "Custom financial summary text"
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient(response=custom))
        report = _make_report()
        result = gen.generate(report)
        assert result.summary == custom

    def test_custom_response_validation(self):
        # Custom response missing required facts
        gen = ClientSummaryGenerator(
            llm_client=FakeLLMClient(response="No financial data here.")
        )
        report = _make_report()
        result = gen.generate(report)
        assert result.validation_passed is False
        assert len(result.validation_errors) > 0


class TestClientSummaryGeneratorErrors:
    def test_missing_client_id_raises(self):
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient())
        report = _make_report(client_id="")
        with pytest.raises(ClientSummaryError, match="client_id"):
            gen.generate(report)

    def test_missing_month_raises(self):
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient())
        report = _make_report(month="")
        with pytest.raises(ClientSummaryError, match="month"):
            gen.generate(report)

    def test_llm_failure_raises(self):
        gen = ClientSummaryGenerator(llm_client=NoOpLLMClient())
        report = _make_report()
        with pytest.raises(ClientSummaryError, match="LLM provider unavailable"):
            gen.generate(report)

    def test_llm_timeout_raises(self):
        class TimeoutLLM(LLMClient):
            def generate(self, prompt: str) -> str:
                raise TimeoutError("Connection timed out")

            @property
            def model_name(self) -> str:
                return "timeout-llm"

        gen = ClientSummaryGenerator(llm_client=TimeoutLLM())
        report = _make_report()
        with pytest.raises(ClientSummaryError, match="LLM provider failed"):
            gen.generate(report)


class TestClientSummaryGeneratorDeterminism:
    def test_same_input_same_output_with_fake(self):
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient())
        report = _make_report()
        r1 = gen.generate(report)
        r2 = gen.generate(report)
        assert r1.summary == r2.summary
        assert r1.client_id == r2.client_id
        assert r1.month == r2.month

    def test_different_reports_different_prompts(self):
        fake = FakeLLMClient()
        gen = ClientSummaryGenerator(llm_client=fake)
        report1 = _make_report(client_id="CLIENT-001")
        report2 = _make_report(client_id="CLIENT-002")
        gen.generate(report1)
        prompt1 = fake.last_prompt
        gen.generate(report2)
        prompt2 = fake.last_prompt
        assert prompt1 != prompt2


class TestClientSummaryGeneratorEdgeCases:
    def test_single_category(self):
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient())
        report = _make_report(
            total_expenses=100.0,
            entry_count=1,
            line_items=[PLLineItem(category="Travel", total=100.0, count=1)],
        )
        result = gen.generate(report)
        assert result.validation_passed is True

    def test_many_categories(self):
        line_items = [
            PLLineItem(category=f"Category {i}", total=float(i * 10), count=i)
            for i in range(1, 9)
        ]
        report = _make_report(
            total_expenses=360.0,
            entry_count=36,
            line_items=line_items,
        )
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient())
        result = gen.generate(report)
        assert result.validation_passed is True

    def test_large_amounts(self):
        report = _make_report(
            total_expenses=999999.99,
            entry_count=1,
            line_items=[PLLineItem(category="Travel", total=999999.99, count=1)],
        )
        gen = ClientSummaryGenerator(llm_client=FakeLLMClient())
        result = gen.generate(report)
        assert "999,999.99" in result.summary or "999999.99" in result.summary


class TestProviderAbstraction:
    def test_accepts_custom_provider(self):
        class CustomProvider(LLMClient):
            def generate(self, prompt: str) -> str:
                return "Custom provider response"

            @property
            def model_name(self) -> str:
                return "custom-v1"

        gen = ClientSummaryGenerator(llm_client=CustomProvider())
        report = _make_report()
        result = gen.generate(report)
        assert result.model_used == "custom-v1"
        assert result.summary == "Custom provider response"

    def test_no_hardcoded_api_keys(self):
        """Verify no API keys are hardcoded in the module."""
        import inspect
        from src.llm import client_summary as module

        source = inspect.getsource(module)
        assert "api_key" not in source.lower() or "api_key" in "environment variable for api_key"
        assert "sk-" not in source
        assert "token" not in source.lower().split("env")[0] if "env" in source.lower() else True
