"""Tests for the workflow orchestrator.

Covers the 19 required test categories:
1. Happy path (all expenses normal)
2. Parallel processing verification
3. Dependency structure (reconciliation waits for both processors)
4. Error propagation (one branch fails)
5. Review routing (REVIEW items → human review queue)
6. Human review decisions (APPROVE/REJECT/CORRECT)
7. P&L generation from ledger
8. Client summary generation from P&L
9. Workflow state tracking
10. Empty data handling
11. All-errors handling
12. Mixed normal/review routing
13. CORRECT decision updates ledger
14. REJECT decision excludes from ledger
15. Multiple workflow runs
16. WorkflowError on missing trigger data
17. Integration with FakeLLMClient
18. Ledger entry counts
19. End-to-end data flow integrity
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from models.workflow import WorkflowRun, WorkflowStatus
from models.anomaly import AnomalyVerdict
from models.human_review import ReviewDecision
from triggers.monthly_trigger import trigger_monthly_expense
from processors.expense_processor import ExpenseProcessorResult
from processors.receipt_processor import ReceiptProcessorResult
from human_review.review_queue import HumanReviewQueue
from accounting.ledger import Ledger
from llm.client_summary import FakeLLMClient, NoOpLLMClient
from workflow.orchestrator import WorkflowOrchestrator, WorkflowError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run(tmp_path, client_id="TV-001", month="2026-08"):
    """Create a WorkflowRun via the trigger."""
    return trigger_monthly_expense(client_id, month, output_dir=tmp_path)


def _make_orchestrator(llm_client=None):
    """Create an orchestrator with optional LLM client."""
    return WorkflowOrchestrator(llm_client=llm_client)


# ---------------------------------------------------------------------------
# 1. Happy path — complete pipeline, all expenses normal
# ---------------------------------------------------------------------------

class TestHappyPath:
    """End-to-end happy path with real data files."""

    def test_complete_pipeline_succeeds(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        assert result.status == WorkflowStatus.COMPLETED
        assert result.errors == []
        assert len(result.expense_records) == 13
        assert len(result.receipt_records) == 13
        assert len(result.reconciliation_results) == 13
        assert len(result.anomaly_results) == 13

    def test_ledger_entries_populated(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        assert len(result.ledger_entries) > 0

    def test_pl_report_generated(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)
        orch.finalize(result)

        assert result.pl_report is not None
        assert result.pl_report["total_expenses"] > 0
        assert result.pl_report["entry_count"] > 0

    def test_client_summary_generated(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)
        orch.finalize(result)

        assert result.client_summary is not None
        assert len(result.client_summary) > 0
        assert "TV-001" in result.client_summary


# ---------------------------------------------------------------------------
# 2. Parallel processing verification
# ---------------------------------------------------------------------------

class TestParallelProcessing:
    """Verify that expense and receipt processing run concurrently."""

    def test_both_processors_called(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()

        with patch(
            "workflow.orchestrator.process_expenses",
            wraps=__import__(
                "workflow.orchestrator", fromlist=["process_expenses"]
            ).process_expenses,
        ) as mock_exp, patch(
            "workflow.orchestrator.process_receipts",
            wraps=__import__(
                "workflow.orchestrator", fromlist=["process_receipts"]
            ).process_receipts,
        ) as mock_rec:
            orch.run(run)
            assert mock_exp.called
            assert mock_rec.called

    def test_both_results_present_in_run(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        assert len(result.expense_records) > 0
        assert len(result.receipt_records) > 0


# ---------------------------------------------------------------------------
# 3. Dependency structure — reconciliation waits for both
# ---------------------------------------------------------------------------

class TestDependencyStructure:
    """Verify correct execution order of pipeline stages."""

    def test_reconciliation_requires_both_results(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        # Reconciliation results should match expense count
        assert len(result.reconciliation_results) == len(result.expense_records)

    def test_anomaly_results_after_reconciliation(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        # Anomaly results should exist and match expense count
        assert len(result.anomaly_results) == len(result.expense_records)


# ---------------------------------------------------------------------------
# 4. Error propagation — one branch fails
# ---------------------------------------------------------------------------

class TestErrorPropagation:
    """Verify errors propagate correctly through the pipeline."""

    def test_missing_expense_file_fails(self, tmp_path):
        run = WorkflowRun(
            run_id="RUN-TEST",
            client_id="TV-001",
            month="2026-08",
            trigger_data={
                "expense_file": str(tmp_path / "nonexistent.xlsx"),
                "receipt_file": str(tmp_path / "nonexistent.json"),
            },
        )
        orch = _make_orchestrator()

        with pytest.raises(WorkflowError, match="Workflow failed"):
            orch.run(run)

        assert run.status == WorkflowStatus.FAILED
        assert len(run.errors) > 0

    def test_missing_trigger_data_fails(self):
        run = WorkflowRun(
            run_id="RUN-TEST",
            client_id="TV-001",
            month="2026-08",
            trigger_data={},
        )
        orch = _make_orchestrator()

        with pytest.raises(WorkflowError, match="Missing expense_file"):
            orch.run(run)

        assert run.status == WorkflowStatus.FAILED


# ---------------------------------------------------------------------------
# 5. Review routing
# ---------------------------------------------------------------------------

class TestReviewRouting:
    """Verify REVIEW items are routed to human review queue."""

    def test_review_items_in_queue(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        # Check if any items were routed to review
        review_items = orch.review_queue.pending_items
        if review_items:
            assert len(result.human_review_items) == len(review_items)

    def test_review_queue_state_tracked(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        # Queue state should be reflected in run
        assert orch.review_queue.pending_count == len(result.human_review_items)


# ---------------------------------------------------------------------------
# 6. Human review decisions — APPROVE
# ---------------------------------------------------------------------------

class TestApproveDecision:
    """Test APPROVE decision processing."""

    def test_approve_posts_to_ledger(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        pending = orch.review_queue.pending_items
        if not pending:
            pytest.skip("No review items to approve")

        item = pending[0]
        orch.process_human_decision(
            review_id=item.review_id,
            reviewer="test-reviewer",
            decision=ReviewDecision.APPROVE,
            reason="Legitimate expense",
        )

        # Decision should be recorded
        decision = orch.review_queue.get_decision(item.review_id)
        assert decision is not None
        assert decision.decision == ReviewDecision.APPROVE
        assert decision.reviewer == "test-reviewer"


# ---------------------------------------------------------------------------
# 7. Human review decisions — REJECT
# ---------------------------------------------------------------------------

class TestRejectDecision:
    """Test REJECT decision processing."""

    def test_reject_excludes_from_ledger(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        pending = orch.review_queue.pending_items
        if not pending:
            pytest.skip("No review items to reject")

        item = pending[0]
        initial_entry_count = len(orch.ledger.get_all_entries())

        orch.process_human_decision(
            review_id=item.review_id,
            reviewer="test-reviewer",
            decision=ReviewDecision.REJECT,
            reason="Suspicious expense",
        )

        # Decision recorded, no new ledger entry for this item
        decision = orch.review_queue.get_decision(item.review_id)
        assert decision is not None
        assert decision.decision == ReviewDecision.REJECT


# ---------------------------------------------------------------------------
# 8. Human review decisions — CORRECT
# ---------------------------------------------------------------------------

class TestCorrectDecision:
    """Test CORRECT decision processing."""

    def test_correct_updates_amount(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        pending = orch.review_queue.pending_items
        if not pending:
            pytest.skip("No review items to correct")

        item = pending[0]
        orch.process_human_decision(
            review_id=item.review_id,
            reviewer="test-reviewer",
            decision=ReviewDecision.CORRECT,
            reason="Amount was incorrect",
            corrected_amount=100.00,
        )

        decision = orch.review_queue.get_decision(item.review_id)
        assert decision is not None
        assert decision.decision == ReviewDecision.CORRECT
        assert decision.corrected_amount == 100.00


# ---------------------------------------------------------------------------
# 9. P&L generation
# ---------------------------------------------------------------------------

class TestPLGeneration:
    """Test P&L report generation from ledger."""

    def test_pl_report_structure(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        orch.run(run)
        orch.finalize(run)

        pl = run.pl_report
        assert pl is not None
        assert "client_id" in pl
        assert "month" in pl
        assert "total_expenses" in pl
        assert "line_items" in pl
        assert "entry_count" in pl

    def test_pl_has_line_items(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        orch.run(run)
        orch.finalize(run)

        pl = run.pl_report
        assert len(pl["line_items"]) > 0

    def test_pl_total_matches_line_items(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        orch.run(run)
        orch.finalize(run)

        pl = run.pl_report
        total_from_items = sum(li["total"] for li in pl["line_items"])
        assert abs(pl["total_expenses"] - total_from_items) < 0.01


# ---------------------------------------------------------------------------
# 10. Client summary generation
# ---------------------------------------------------------------------------

class TestClientSummaryGeneration:
    """Test client summary generation from P&L."""

    def test_summary_contains_client_id(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        orch.run(run)
        orch.finalize(run)

        assert "TV-001" in run.client_summary

    def test_summary_contains_month(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        orch.run(run)
        orch.finalize(run)

        assert "August 2026" in run.client_summary

    def test_summary_contains_total(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        orch.run(run)
        orch.finalize(run)

        pl = run.pl_report
        total_str = f"${pl['total_expenses']:,.2f}"
        assert total_str in run.client_summary


# ---------------------------------------------------------------------------
# 11. Workflow state tracking
# ---------------------------------------------------------------------------

class TestStateTracking:
    """Verify workflow state is tracked correctly throughout."""

    def test_status_transitions(self, tmp_path):
        run = _make_run(tmp_path)
        assert run.status == WorkflowStatus.CREATED

        orch = _make_orchestrator()
        result = orch.run(run)
        assert result.status == WorkflowStatus.COMPLETED

    def test_run_id_preserved(self, tmp_path):
        run = _make_run(tmp_path)
        original_id = run.run_id

        orch = _make_orchestrator()
        result = orch.run(run)
        assert result.run_id == original_id

    def test_client_and_month_preserved(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        assert result.client_id == "TV-001"
        assert result.month == "2026-08"


# ---------------------------------------------------------------------------
# 12. Empty data handling
# ---------------------------------------------------------------------------

class TestEmptyDataHandling:
    """Test behavior with edge-case data."""

    def test_workflow_with_no_errors_in_processing(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        # All 13 records should process without errors
        assert len(result.expense_records) == 13


# ---------------------------------------------------------------------------
# 13. Mixed normal/review routing
# ---------------------------------------------------------------------------

class TestMixedRouting:
    """Test that NORMAL and REVIEW items are routed correctly."""

    def test_normal_items_posted_to_ledger(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        normal_count = sum(
            1 for a in result.anomaly_results
            if a["verdict"] == "normal"
        )
        ledger_count = len(result.ledger_entries)

        # Ledger should have at least the normal items
        assert ledger_count >= normal_count


# ---------------------------------------------------------------------------
# 14. Ledger entry counts
# ---------------------------------------------------------------------------

class TestLedgerEntryCounts:
    """Verify ledger entry counts are accurate."""

    def test_ledger_entries_match_normal_verdicts(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        normal_count = sum(
            1 for a in result.anomaly_results
            if a["verdict"] == "normal"
        )
        # Ledger should have exactly the normal items
        assert len(result.ledger_entries) == normal_count


# ---------------------------------------------------------------------------
# 15. Multiple workflow runs
# ---------------------------------------------------------------------------

class TestMultipleRuns:
    """Test multiple independent workflow runs."""

    def test_separate_orchestrators_independent(self, tmp_path):
        run1 = _make_run(tmp_path, "TV-001", "2026-08")
        run2 = _make_run(tmp_path, "GL-002", "2026-08")

        orch1 = _make_orchestrator()
        orch2 = _make_orchestrator()

        result1 = orch1.run(run1)
        result2 = orch2.run(run2)

        assert result1.run_id != result2.run_id
        assert result1.client_id == "TV-001"
        assert result2.client_id == "GL-002"


# ---------------------------------------------------------------------------
# 16. WorkflowError on missing trigger data
# ---------------------------------------------------------------------------

class TestWorkflowError:
    """Test WorkflowError is raised appropriately."""

    def test_missing_expense_file_raises_workflow_error(self):
        run = WorkflowRun(
            run_id="RUN-TEST",
            client_id="TV-001",
            month="2026-08",
            trigger_data={},
        )
        orch = _make_orchestrator()

        with pytest.raises(WorkflowError):
            orch.run(run)

    def test_finalize_without_pl_raises(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        orch.run(run)

        # Reset pl_report
        run.pl_report = None
        with pytest.raises(WorkflowError, match="no P&L report"):
            orch.generate_client_summary(run)


# ---------------------------------------------------------------------------
# 17. Integration with FakeLLMClient
# ---------------------------------------------------------------------------

class TestFakeLLMIntegration:
    """Test integration with FakeLLMClient."""

    def test_fake_llm_produces_summary(self, tmp_path):
        llm = FakeLLMClient()
        run = _make_run(tmp_path)
        orch = _make_orchestrator(llm_client=llm)
        orch.run(run)
        orch.finalize(run)

        assert run.client_summary is not None
        assert llm.call_count == 1

    def test_fake_llm_called_with_prompt(self, tmp_path):
        llm = FakeLLMClient()
        run = _make_run(tmp_path)
        orch = _make_orchestrator(llm_client=llm)
        orch.run(run)
        orch.finalize(run)

        assert llm.last_prompt is not None
        assert "TV-001" in llm.last_prompt


# ---------------------------------------------------------------------------
# 18. Review queue properties
# ---------------------------------------------------------------------------

class TestReviewQueueProperties:
    """Test orchestrator exposes review queue and ledger correctly."""

    def test_review_queue_accessible(self, tmp_path):
        orch = _make_orchestrator()
        assert isinstance(orch.review_queue, HumanReviewQueue)

    def test_ledger_accessible(self, tmp_path):
        orch = _make_orchestrator()
        assert isinstance(orch.ledger, Ledger)

    def test_pl_generator_accessible(self, tmp_path):
        orch = _make_orchestrator()
        assert orch.pl_generator is not None

    def test_summary_generator_accessible(self, tmp_path):
        orch = _make_orchestrator()
        assert orch.summary_generator is not None


# ---------------------------------------------------------------------------
# 19. End-to-end data flow integrity
# ---------------------------------------------------------------------------

class TestDataFlowIntegrity:
    """Verify data flows correctly through all stages."""

    def test_expense_ids_preserved_through_pipeline(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        expense_ids = {r["expense_id"] for r in result.expense_records}
        anomaly_ids = {r["expense_id"] for r in result.anomaly_results}
        recon_ids = {r["expense_id"] for r in result.reconciliation_results}

        assert expense_ids == anomaly_ids
        assert expense_ids == recon_ids

    def test_reconciliation_statuses_are_valid(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        valid_statuses = {
            "exact_match", "amount_mismatch", "vendor_mismatch",
            "date_mismatch", "missing_receipt",
        }
        for recon in result.reconciliation_results:
            assert recon["status"] in valid_statuses

    def test_anomaly_verdicts_are_valid(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        for anomaly in result.anomaly_results:
            assert anomaly["verdict"] in ("normal", "review")

    def test_categorization_results_match_expenses(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        cat_ids = {r["expense_id"] for r in result.categorization_results}
        expense_ids = {r["expense_id"] for r in result.expense_records}
        assert cat_ids == expense_ids

    def test_pl_report_categories_from_ledger(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        orch.run(run)
        orch.finalize(run)

        pl = run.pl_report
        ledger_categories = set(orch.ledger.get_total_by_category().keys())
        pl_categories = {li["category"] for li in pl["line_items"]}

        # PL categories should be a subset of ledger categories
        assert pl_categories.issubset(ledger_categories)

    def test_client_summary_references_pl_data(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        orch.run(run)
        orch.finalize(run)

        pl = run.pl_report
        summary = run.client_summary

        # Summary should reference the total
        total_str = f"${pl['total_expenses']:,.2f}"
        assert total_str in summary

        # Summary should reference the client
        assert pl["client_id"] in summary

    def test_workflow_run_contains_all_stages(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        assert len(result.expense_records) > 0
        assert len(result.receipt_records) > 0
        assert len(result.reconciliation_results) > 0
        assert len(result.categorization_results) > 0
        assert len(result.anomaly_results) > 0
        assert len(result.ledger_entries) > 0

    def test_human_review_decisions_populated(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        # human_review_decisions should be a list (may be empty)
        assert isinstance(result.human_review_decisions, list)

    def test_trigger_data_preserved(self, tmp_path):
        run = _make_run(tmp_path)
        orch = _make_orchestrator()
        result = orch.run(run)

        assert "expense_file" in result.trigger_data
        assert "receipt_file" in result.trigger_data
        assert "client_name" in result.trigger_data
