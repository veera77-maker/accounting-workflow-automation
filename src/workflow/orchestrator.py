"""Workflow orchestrator — connects all components into one executable pipeline.

This component is the ORCHESTRATOR in the A.05.1 template.
It connects all existing components into one coherent end-to-end workflow:

    TRIGGER
       |
 +-----+-----+
 |           |
 v           v
EXPENSE    RECEIPT
 |           |
 +-----+-----+
       |
 wait for BOTH
       |
       v
RECONCILIATION → CATEGORIZATION → ANOMALY DETECTION
                                           |
                                    +------+------+
                                    |             |
                                  NORMAL        REVIEW
                                    |             |
                                    v       HUMAN REVIEW
                                    |             |
                                    +------+------+------+
                                           |
                                           v
                                    ACCOUNTING LEDGER
                                           |
                                           v
                                           P&L
                                           |
                                           v
                                    LLM CLIENT SUMMARY

Design decisions:
- Expense and receipt processing run in parallel using ThreadPoolExecutor.
- Reconciliation waits for both processing steps to complete.
- NORMAL expenses are posted to the ledger automatically.
- REVIEW expenses are routed to the human review queue.
- Human review decisions (APPROVE/REJECT/CORRECT) update the ledger.
- P&L is generated from ledger entries (not raw input).
- Client summary is generated from validated P&L data.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from models.workflow import WorkflowRun, WorkflowStatus
from models.anomaly import AnomalyVerdict
from models.human_review import ReviewDecision
from triggers.monthly_trigger import trigger_monthly_expense
from processors.expense_processor import process_expenses, ExpenseProcessorResult
from processors.receipt_processor import process_receipts, ReceiptProcessorResult
from processors.reconciler import reconcile_expenses
from processors.categorizer import categorize_expenses
from decisions.anomaly_detector import detect_anomalies
from human_review.review_queue import HumanReviewQueue
from accounting.ledger import Ledger
from accounting.pl_generator import PLGenerator
from llm.client_summary import ClientSummaryGenerator, FakeLLMClient, LLMClient


class WorkflowError(Exception):
    """Raised when a workflow operation fails."""


class WorkflowOrchestrator:
    """Orchestrates the complete monthly expense workflow.

    Connects all components into one executable end-to-end pipeline.
    Maintains clear state throughout: run ID, client, month, results
    from each stage.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        """Initialize the orchestrator with optional LLM client.

        Args:
            llm_client: LLM provider for client summary generation.
                       Defaults to FakeLLMClient for deterministic testing.
        """
        if llm_client is None:
            llm_client = FakeLLMClient()
        self._llm_client = llm_client
        self._review_queue = HumanReviewQueue()
        self._ledger = Ledger()
        self._pl_generator = PLGenerator()
        self._summary_generator = ClientSummaryGenerator(self._llm_client)

    def run(self, run: WorkflowRun) -> WorkflowRun:
        """Execute the automated pipeline for a given WorkflowRun.

        Runs expense processing and receipt processing in parallel,
        then proceeds through reconciliation, categorization, anomaly
        detection, and ledger posting. REVIEW items are routed to the
        human review queue.

        Args:
            run: The WorkflowRun from the trigger, containing trigger_data
                 with expense_file and receipt_file paths.

        Returns:
            Updated WorkflowRun with all intermediate results populated.

        Raises:
            WorkflowError: If a required stage fails.
        """
        run.status = WorkflowStatus.PROCESSING

        try:
            # Stage 1: Parallel expense and receipt processing
            expense_result, receipt_result = self._process_parallel(run)

            # Stage 2: Reconciliation (waits for both processors)
            reconciliation_results = self._reconcile(expense_result, receipt_result)

            # Stage 3: Categorization
            categorization_result = self._categorize(expense_result)

            # Stage 4: Anomaly detection
            anomaly_results = self._detect_anomalies(
                expense_result, reconciliation_results
            )

            # Stage 5: Route NORMAL → ledger, REVIEW → human review queue
            self._route_to_ledger_and_review(expense_result, anomaly_results)

            # Update run with all results
            self._update_run(
                run,
                expense_result,
                receipt_result,
                reconciliation_results,
                categorization_result,
                anomaly_results,
            )

            run.status = WorkflowStatus.COMPLETED

        except Exception as e:
            run.status = WorkflowStatus.FAILED
            run.errors.append({
                "stage": "orchestrator",
                "error": str(e),
            })
            raise WorkflowError(f"Workflow failed: {e}") from e

        return run

    def process_human_decision(
        self,
        review_id: str,
        reviewer: str,
        decision: ReviewDecision,
        reason: str,
        corrected_amount: Optional[float] = None,
        corrected_category: Optional[str] = None,
        corrected_vendor: Optional[str] = None,
    ) -> None:
        """Process a human review decision and update the ledger.

        Args:
            review_id: The review ID to process.
            reviewer: Name/ID of the human reviewer.
            decision: The review decision (APPROVE/REJECT/CORRECT).
            reason: Human-readable reason for the decision.
            corrected_amount: New amount (only for CORRECT).
            corrected_category: New category (only for CORRECT).
            corrected_vendor: New vendor (only for CORRECT).

        Raises:
            WorkflowError: If the decision processing fails.
        """
        try:
            if decision == ReviewDecision.APPROVE:
                self._review_queue.approve(review_id, reviewer, reason)
            elif decision == ReviewDecision.REJECT:
                self._review_queue.reject(review_id, reviewer, reason)
            elif decision == ReviewDecision.CORRECT:
                self._review_queue.correct(
                    review_id,
                    reviewer,
                    reason,
                    corrected_amount=corrected_amount,
                    corrected_category=corrected_category,
                    corrected_vendor=corrected_vendor,
                )
            else:
                raise WorkflowError(f"Unknown decision type: {decision}")
        except Exception as e:
            raise WorkflowError(f"Failed to process human decision: {e}") from e

    def generate_pl(self, run: WorkflowRun) -> None:
        """Generate P&L report from current ledger state.

        Updates the run with the generated P&L report.

        Args:
            run: The WorkflowRun to update with P&L data.
        """
        entries = self._ledger.get_entries(
            month=run.month, client_id=run.client_id
        )
        pl_report = self._pl_generator.generate(
            entries, run.client_id, run.month
        )
        run.pl_report = pl_report.model_dump(mode="json")

    def generate_client_summary(self, run: WorkflowRun) -> None:
        """Generate client summary from P&L report.

        Updates the run with the generated client summary.

        Args:
            run: The WorkflowRun to update with client summary.

        Raises:
            WorkflowError: If no P&L report exists or generation fails.
        """
        if run.pl_report is None:
            raise WorkflowError("Cannot generate client summary: no P&L report")

        from models.accounting import PLReport

        pl_report = PLReport(**run.pl_report)
        summary_result = self._summary_generator.generate(pl_report)
        run.client_summary = summary_result.summary

    def finalize(self, run: WorkflowRun) -> WorkflowRun:
        """Finalize the workflow: generate P&L and client summary.

        Call this after all human review decisions have been processed.

        Args:
            run: The WorkflowRun to finalize.

        Returns:
            Updated WorkflowRun with P&L and client summary.
        """
        self.generate_pl(run)
        self.generate_client_summary(run)
        return run

    def _process_parallel(
        self, run: WorkflowRun
    ) -> tuple[ExpenseProcessorResult, ReceiptProcessorResult]:
        """Process expenses and receipts in parallel.

        Args:
            run: The WorkflowRun containing file paths in trigger_data.

        Returns:
            Tuple of (expense_result, receipt_result).

        Raises:
            WorkflowError: If either processing step fails.
        """
        excel_path = run.trigger_data.get("expense_file")
        receipt_path = run.trigger_data.get("receipt_file")

        if not excel_path or not receipt_path:
            raise WorkflowError(
                "Missing expense_file or receipt_file in trigger_data"
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            expense_future = executor.submit(
                process_expenses, excel_path, run.client_id, run.month
            )
            receipt_future = executor.submit(process_receipts, receipt_path)

            # Wait for both to complete
            expense_result = expense_future.result()
            receipt_result = receipt_future.result()

        return expense_result, receipt_result

    def _reconcile(
        self,
        expense_result: ExpenseProcessorResult,
        receipt_result: ReceiptProcessorResult,
    ) -> list:
        """Reconcile expenses against receipts.

        Args:
            expense_result: Result from expense processing.
            receipt_result: Result from receipt processing.

        Returns:
            List of ReconciliationResult objects.
        """
        return reconcile_expenses(expense_result.records, receipt_result.records)

    def _categorize(self, expense_result: ExpenseProcessorResult):
        """Categorize expenses using deterministic rules.

        Args:
            expense_result: Result from expense processing.

        Returns:
            CategorizerResult with categorization for each expense.
        """
        return categorize_expenses(expense_result.records)

    def _detect_anomalies(
        self,
        expense_result: ExpenseProcessorResult,
        reconciliation_results: list,
    ) -> list:
        """Detect anomalies in expenses.

        Args:
            expense_result: Result from expense processing.
            reconciliation_results: Results from reconciliation.

        Returns:
            List of AnomalyResult objects.
        """
        return detect_anomalies(
            expense_result.records, reconciliation_results
        )

    def _route_to_ledger_and_review(
        self,
        expense_result: ExpenseProcessorResult,
        anomaly_results: list,
    ) -> None:
        """Route expenses to ledger (NORMAL) or human review queue (REVIEW).

        Args:
            expense_result: Result from expense processing.
            anomaly_results: Results from anomaly detection.
        """
        # Post NORMAL expenses to ledger
        self._ledger.post_clean_expenses(
            expense_result.records, anomaly_results
        )

        # Add REVIEW expenses to human review queue
        expense_map = {e.expense_id: e for e in expense_result.records}
        for anomaly in anomaly_results:
            if anomaly.verdict == AnomalyVerdict.REVIEW:
                expense = expense_map.get(anomaly.expense_id)
                if expense:
                    self._review_queue.add_to_queue(expense, anomaly)

    def _update_run(
        self,
        run: WorkflowRun,
        expense_result: ExpenseProcessorResult,
        receipt_result: ReceiptProcessorResult,
        reconciliation_results: list,
        categorization_result,
        anomaly_results: list,
    ) -> None:
        """Update the WorkflowRun with all intermediate results.

        Args:
            run: The WorkflowRun to update.
            expense_result: Result from expense processing.
            receipt_result: Result from receipt processing.
            reconciliation_results: Results from reconciliation.
            categorization_result: Result from categorization.
            anomaly_results: Results from anomaly detection.
        """
        run.expense_records = [
            r.model_dump(mode="json") for r in expense_result.records
        ]
        run.receipt_records = [
            r.model_dump(mode="json") for r in receipt_result.records
        ]
        run.reconciliation_results = [
            r.model_dump(mode="json") for r in reconciliation_results
        ]
        run.categorization_results = [
            r.to_dict() for r in categorization_result.results
        ]
        run.anomaly_results = [
            r.model_dump(mode="json") for r in anomaly_results
        ]
        run.human_review_items = [
            item.model_dump(mode="json")
            for item in self._review_queue.pending_items
        ]
        run.human_review_decisions = [
            d.model_dump(mode="json")
            for d in self._review_queue.decisions
        ]
        run.ledger_entries = [
            e.model_dump(mode="json")
            for e in self._ledger.get_all_entries()
        ]

    @property
    def review_queue(self) -> HumanReviewQueue:
        """Access the human review queue."""
        return self._review_queue

    @property
    def ledger(self) -> Ledger:
        """Access the accounting ledger."""
        return self._ledger

    @property
    def pl_generator(self) -> PLGenerator:
        """Access the P&L generator."""
        return self._pl_generator

    @property
    def summary_generator(self) -> ClientSummaryGenerator:
        """Access the client summary generator."""
        return self._summary_generator
