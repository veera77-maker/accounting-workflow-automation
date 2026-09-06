"""End-to-end demo script for A.05.1 Workflow Automation Agent.

Runs deterministic demo scenarios that demonstrate the complete workflow:

SCENARIO A — Normal expense (happy path)
SCENARIO B — Reconciliation mismatch
SCENARIO C — Anomaly (HIGH_VALUE, DUPLICATE, NEW_VENDOR)
SCENARIO D — Human correction
SCENARIO E — Human rejection
SCENARIO F — LLM grounding failure

Each scenario produces a human-readable markdown file under artifacts/demo/.

Usage:
    python scripts/run_demo.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root and src to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from models.workflow import WorkflowRun, WorkflowStatus
from models.anomaly import AnomalyVerdict
from models.human_review import ReviewDecision
from triggers.monthly_trigger import trigger_monthly_expense
from processors.expense_processor import process_expenses
from processors.receipt_processor import process_receipts
from processors.reconciler import reconcile_expenses
from processors.categorizer import categorize_expenses
from decisions.anomaly_detector import detect_anomalies, AnomalyThresholds
from human_review.review_queue import HumanReviewQueue
from accounting.ledger import Ledger
from accounting.pl_generator import PLGenerator
from llm.client_summary import ClientSummaryGenerator, FakeLLMClient, NoOpLLMClient, ClientSummaryError
from workflow.orchestrator import WorkflowOrchestrator, WorkflowError


# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

DEMO_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "demo"
DEMO_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "outputs"


def _write_output(filename: str, content: str) -> Path:
    """Write content to a demo output file."""
    path = DEMO_DIR / filename
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_workflow_result(run: WorkflowRun, title: str) -> str:
    """Format a WorkflowRun as a human-readable markdown report."""
    lines = [
        f"# {title}",
        "",
        f"**Run ID:** {run.run_id}",
        f"**Client:** {run.client_id}",
        f"**Month:** {run.month}",
        f"**Status:** {run.status.value}",
        f"**Generated:** {datetime.now().isoformat()}",
        "",
        "## Stage Results",
        "",
        f"- **Expense Records:** {len(run.expense_records)}",
        f"- **Receipt Records:** {len(run.receipt_records)}",
        f"- **Reconciliation Results:** {len(run.reconciliation_results)}",
        f"- **Categorization Results:** {len(run.categorization_results)}",
        f"- **Anomaly Results:** {len(run.anomaly_results)}",
        f"- **Human Review Items:** {len(run.human_review_items)}",
        f"- **Human Review Decisions:** {len(run.human_review_decisions)}",
        f"- **Ledger Entries:** {len(run.ledger_entries)}",
        "",
    ]

    # Anomaly breakdown
    if run.anomaly_results:
        normal = sum(1 for a in run.anomaly_results if a["verdict"] == "normal")
        review = sum(1 for a in run.anomaly_results if a["verdict"] == "review")
        lines.extend([
            "## Anomaly Verdicts",
            "",
            f"- **NORMAL:** {normal}",
            f"- **REVIEW:** {review}",
            "",
        ])

    # Reconciliation breakdown
    if run.reconciliation_results:
        statuses = {}
        for r in run.reconciliation_results:
            s = r["status"]
            statuses[s] = statuses.get(s, 0) + 1
        lines.extend([
            "## Reconciliation Statuses",
            "",
        ])
        for s, count in sorted(statuses.items()):
            lines.append(f"- **{s}:** {count}")
        lines.append("")

    # Ledger entries
    if run.ledger_entries:
        lines.extend([
            "## Ledger Entries",
            "",
            "| Entry ID | Expense ID | Category | Amount | Source | Status |",
            "|----------|------------|----------|--------|--------|--------|",
        ])
        for e in run.ledger_entries:
            lines.append(
                f"| {e['entry_id']} | {e['expense_id']} | {e['category']} "
                f"| ${e['amount']:.2f} | {e['source']} | {e['status']} |"
            )
        lines.append("")

    # P&L
    if run.pl_report:
        pl = run.pl_report
        lines.extend([
            "## P&L Report",
            "",
            f"- **Total Expenses:** ${pl['total_expenses']:,.2f}",
            f"- **Entry Count:** {pl['entry_count']}",
            "",
            "| Category | Total | Count |",
            "|----------|-------|-------|",
        ])
        for li in pl["line_items"]:
            lines.append(f"| {li['category']} | ${li['total']:,.2f} | {li['count']} |")
        lines.append("")

    # Client summary
    if run.client_summary:
        lines.extend([
            "## Client Summary",
            "",
            "```",
            run.client_summary,
            "```",
            "",
        ])

    # Errors
    if run.errors:
        lines.extend([
            "## Errors",
            "",
        ])
        for err in run.errors:
            lines.append(f"- **{err.get('stage', 'unknown')}:** {err.get('error', 'unknown')}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SCENARIO A — Normal expense (happy path)
# ---------------------------------------------------------------------------

def run_scenario_a() -> str:
    """Demonstrate a clean expense flowing through the complete pipeline."""
    print("Running Scenario A — Normal expense (happy path)...")

    run = trigger_monthly_expense("TV-001", "2026-08", output_dir=DATA_DIR)
    orch = WorkflowOrchestrator()
    result = orch.run(run)
    orch.finalize(result)

    return _format_workflow_result(result, "Scenario A — Normal Expense (Happy Path)")


# ---------------------------------------------------------------------------
# SCENARIO B — Reconciliation mismatch
# ---------------------------------------------------------------------------

def run_scenario_b() -> str:
    """Demonstrate a reconciliation mismatch flowing through the pipeline.

    The synthetic data includes a vendor mismatch scenario (Delta Airlines
    vs Delta Air Lines) and an amount mismatch scenario.
    """
    print("Running Scenario B — Reconciliation mismatch...")

    run = trigger_monthly_expense("TV-001", "2026-08", output_dir=DATA_DIR)
    orch = WorkflowOrchestrator()
    result = orch.run(run)

    # Find reconciliation mismatches
    mismatches = [
        r for r in result.reconciliation_results
        if r["status"] != "exact_match"
    ]

    report = _format_workflow_result(result, "Scenario B — Reconciliation Mismatch")

    # Add mismatch detail section
    if mismatches:
        detail_lines = [
            "## Reconciliation Mismatch Details",
            "",
        ]
        for m in mismatches:
            detail_lines.extend([
                f"### Expense {m['expense_id']}",
                "",
                f"- **Status:** {m['status']}",
                f"- **Reason:** {m['reason']}",
                f"- **Evidence:** {json.dumps(m.get('evidence', {}), indent=2)}",
                "",
            ])
        report += "\n".join(detail_lines)

    return report


# ---------------------------------------------------------------------------
# SCENARIO C — Anomaly
# ---------------------------------------------------------------------------

def run_scenario_c() -> str:
    """Demonstrate anomaly detection with various anomaly types.

    The synthetic data includes:
    - HIGH_VALUE: A high meal expense ($385.75)
    - DUPLICATE: Two identical Uber rides
    - NEW_VENDOR: An expense from a vendor not in the known list
    """
    print("Running Scenario C — Anomaly detection...")

    run = trigger_monthly_expense("TV-001", "2026-08", output_dir=DATA_DIR)
    orch = WorkflowOrchestrator()
    result = orch.run(run)

    # Find anomalies
    anomalies = [
        a for a in result.anomaly_results
        if a["verdict"] == "review"
    ]

    report = _format_workflow_result(result, "Scenario C — Anomaly Detection")

    # Add anomaly detail section
    if anomalies:
        detail_lines = [
            "## Anomaly Details",
            "",
        ]
        for a in anomalies:
            detail_lines.extend([
                f"### Expense {a['expense_id']}",
                "",
                f"- **Verdict:** {a['verdict']}",
                f"- **Reasons:** {', '.join(a['reasons'])}",
                f"- **Explanation:** {a['explanation']}",
                "",
            ])
        report += "\n".join(detail_lines)

    return report


# ---------------------------------------------------------------------------
# SCENARIO D — Human correction
# ---------------------------------------------------------------------------

def run_scenario_d() -> str:
    """Demonstrate a human correcting an anomalous expense."""
    print("Running Scenario D — Human correction...")

    run = trigger_monthly_expense("TV-001", "2026-08", output_dir=DATA_DIR)
    orch = WorkflowOrchestrator()
    result = orch.run(run)

    # Find a review item to correct
    pending = orch.review_queue.pending_items
    if not pending:
        return _format_workflow_result(result, "Scenario D — Human Correction (No Items to Correct)")

    item = pending[0]

    # Process human correction
    orch.process_human_decision(
        review_id=item.review_id,
        reviewer="demo-reviewer",
        decision=ReviewDecision.CORRECT,
        reason="Amount was reported incorrectly; actual amount is $150.00",
        corrected_amount=150.00,
    )

    # Post corrected expense to ledger
    expense_map = {e["expense_id"]: e for e in result.expense_records}
    expense_data = expense_map.get(item.expense_id)
    if expense_data:
        from models.expense import ExpenseRecord, ExpenseCategory
        from datetime import date
        expense = ExpenseRecord(
            expense_id=expense_data["expense_id"],
            client_id=expense_data["client_id"],
            employee=expense_data["employee"],
            date=date.fromisoformat(expense_data["date"]),
            description=expense_data["description"],
            vendor=expense_data["vendor"],
            amount=expense_data["amount"],
            category=ExpenseCategory(expense_data["category"]),
            receipt_reference=expense_data.get("receipt_reference"),
            status=expense_data["status"],
            month=expense_data["month"],
        )
        decisions = orch.review_queue.decisions
        orch.ledger.post_human_reviewed([expense], decisions)

    # Regenerate P&L
    orch.generate_pl(result)
    orch.generate_client_summary(result)

    # Update run state
    result.human_review_decisions = [
        d.model_dump(mode="json") for d in orch.review_queue.decisions
    ]
    result.ledger_entries = [
        e.model_dump(mode="json") for e in orch.ledger.get_all_entries()
    ]

    report = _format_workflow_result(result, "Scenario D — Human Correction")

    # Add correction detail
    decision = orch.review_queue.get_decision(item.review_id)
    if decision:
        report += f"""
## Correction Details

- **Review ID:** {decision.review_id}
- **Expense ID:** {decision.expense_id}
- **Reviewer:** {decision.reviewer}
- **Decision:** {decision.decision.value}
- **Reason:** {decision.reason}
- **Corrected Amount:** ${decision.corrected_amount:.2f}

The corrected expense was posted to the ledger with source="human_review" and status=HUMAN_REVIEWED.
"""

    return report


# ---------------------------------------------------------------------------
# SCENARIO E — Human rejection
# ---------------------------------------------------------------------------

def run_scenario_e() -> str:
    """Demonstrate a human rejecting an anomalous expense."""
    print("Running Scenario E — Human rejection...")

    run = trigger_monthly_expense("TV-001", "2026-08", output_dir=DATA_DIR)
    orch = WorkflowOrchestrator()
    result = orch.run(run)

    # Find a review item to reject
    pending = orch.review_queue.pending_items
    if not pending:
        return _format_workflow_result(result, "Scenario E — Human Rejection (No Items to Reject)")

    item = pending[0]

    # Record initial ledger count
    initial_ledger_count = len(orch.ledger.get_all_entries())

    # Process human rejection
    orch.process_human_decision(
        review_id=item.review_id,
        reviewer="demo-reviewer",
        decision=ReviewDecision.REJECT,
        reason="Expense appears to be a duplicate and cannot be verified",
    )

    # Update run state
    result.human_review_decisions = [
        d.model_dump(mode="json") for d in orch.review_queue.decisions
    ]
    result.ledger_entries = [
        e.model_dump(mode="json") for e in orch.ledger.get_all_entries()
    ]

    # Regenerate P&L (should not include rejected expense)
    orch.generate_pl(result)
    orch.generate_client_summary(result)

    report = _format_workflow_result(result, "Scenario E — Human Rejection")

    # Add rejection detail
    decision = orch.review_queue.get_decision(item.review_id)
    report += f"""
## Rejection Details

- **Review ID:** {decision.review_id}
- **Expense ID:** {decision.expense_id}
- **Reviewer:** {decision.reviewer}
- **Decision:** {decision.decision.value}
- **Reason:** {decision.reason}

The rejected expense was NOT posted to the ledger. The ledger entry count remains {initial_ledger_count}.
"""

    return report


# ---------------------------------------------------------------------------
# SCENARIO F — LLM grounding failure
# ---------------------------------------------------------------------------

def run_scenario_f() -> str:
    """Demonstrate LLM grounding failure when summary doesn't contain source facts.

    Uses a custom LLM client that returns a hallucinated summary missing
    required financial facts. The validation system catches this.
    """
    print("Running Scenario F — LLM grounding failure...")

    class HallucinatingLLMClient(FakeLLMClient):
        """LLM client that returns a summary without required financial facts."""
        def generate(self, prompt: str) -> str:
            return (
                "This is a summary that does not contain any of the required "
                "financial facts. It mentions no totals, no client ID, and no month."
            )

    run = trigger_monthly_expense("TV-001", "2026-08", output_dir=DATA_DIR)
    orch = WorkflowOrchestrator(llm_client=HallucinatingLLMClient())
    result = orch.run(run)

    # Try to finalize — this should fail validation
    error_occurred = False
    error_message = ""
    try:
        orch.generate_pl(result)
        orch.generate_client_summary(result)
    except ClientSummaryError as e:
        error_occurred = True
        error_message = str(e)

    report = f"""# Scenario F — LLM Grounding Failure

**Run ID:** {result.run_id}
**Client:** {result.client_id}
**Month:** {result.month}
**Status:** {result.status.value}
**Generated:** {datetime.now().isoformat()}

## Overview

This scenario demonstrates the anti-hallucination safeguards in the LLM client summary
generator. A custom LLM client returns a summary that does NOT contain the required
financial facts (total expenses, client ID, month, entry count).

## LLM Output

```
This is a summary that does not contain any of the required financial facts.
It mentions no totals, no client ID, and no month.
```

## Validation Result

"""

    if error_occurred:
        report += f"""**Validation FAILED as expected.**

Error: `{error_message}`

The system correctly detected that the LLM-generated summary does not contain
the required source facts from the P&L report. This prevents unsupported
financial information from reaching the client.
"""
    else:
        report += """**Validation passed unexpectedly.**

The hallucinated summary was accepted. This should not happen with proper
anti-hallucination validation.
"""

    report += f"""
## P&L Data (Source of Truth)

- **Total Expenses:** ${result.pl_report['total_expenses']:,.2f}
- **Entry Count:** {result.pl_report['entry_count']}
- **Client ID:** {result.pl_report['client_id']}
- **Month:** {result.pl_report['month']}

## Anti-Hallucination Safeguards

1. **Pre-generation:** PLReport validated (client_id and month required)
2. **Prompt level:** Explicit anti-hallucination instructions in prompt
3. **Post-generation:** Validation checks that summary contains:
   - Total expenses amount
   - Client ID
   - Reporting month
   - Entry count

If any check fails, `ClientSummaryError` is raised and the workflow fails explicitly
rather than silently accepting unsupported information.
"""

    return report


# ---------------------------------------------------------------------------
# Latency benchmark
# ---------------------------------------------------------------------------

def run_latency_benchmark(runs: int = 10) -> dict:
    """Run the workflow multiple times and measure latency."""
    print(f"Running latency benchmark ({runs} runs)...")

    latencies = {
        "total": [],
        "expense_processing": [],
        "receipt_processing": [],
        "parallel_stage": [],
        "reconciliation": [],
        "categorization": [],
        "anomaly_detection": [],
        "ledger_posting": [],
        "pl_generation": [],
        "client_summary": [],
    }

    for i in range(runs):
        run = trigger_monthly_expense("TV-001", "2026-08", output_dir=DATA_DIR)
        orch = WorkflowOrchestrator()

        # Measure total and individual stages
        t_total_start = time.perf_counter()

        # Parallel stage
        t_parallel_start = time.perf_counter()
        expense_result, receipt_result = orch._process_parallel(run)
        t_parallel_end = time.perf_counter()
        latencies["parallel_stage"].append(t_parallel_end - t_parallel_start)

        # Individual processors (measured from parallel stage)
        # Note: These overlap in time, so we measure them separately
        t_exp_start = time.perf_counter()
        process_expenses(run.trigger_data["expense_file"], run.client_id, run.month)
        t_exp_end = time.perf_counter()
        latencies["expense_processing"].append(t_exp_end - t_exp_start)

        t_rec_start = time.perf_counter()
        process_receipts(run.trigger_data["receipt_file"])
        t_rec_end = time.perf_counter()
        latencies["receipt_processing"].append(t_rec_end - t_rec_start)

        # Reconciliation
        t_recon_start = time.perf_counter()
        reconciliation_results = orch._reconcile(expense_result, receipt_result)
        t_recon_end = time.perf_counter()
        latencies["reconciliation"].append(t_recon_end - t_recon_start)

        # Categorization
        t_cat_start = time.perf_counter()
        categorization_result = orch._categorize(expense_result)
        t_cat_end = time.perf_counter()
        latencies["categorization"].append(t_cat_end - t_cat_start)

        # Anomaly detection
        t_anom_start = time.perf_counter()
        anomaly_results = orch._detect_anomalies(expense_result, reconciliation_results)
        t_anom_end = time.perf_counter()
        latencies["anomaly_detection"].append(t_anom_end - t_anom_start)

        # Ledger posting
        t_ledger_start = time.perf_counter()
        orch._route_to_ledger_and_review(expense_result, anomaly_results)
        t_ledger_end = time.perf_counter()
        latencies["ledger_posting"].append(t_ledger_end - t_ledger_start)

        # P&L generation
        t_pl_start = time.perf_counter()
        orch.generate_pl(run)
        t_pl_end = time.perf_counter()
        latencies["pl_generation"].append(t_pl_end - t_pl_start)

        # Client summary
        t_summary_start = time.perf_counter()
        orch.generate_client_summary(run)
        t_summary_end = time.perf_counter()
        latencies["client_summary"].append(t_summary_end - t_summary_start)

        t_total_end = time.perf_counter()
        latencies["total"].append(t_total_end - t_total_start)

    # Calculate statistics
    stats = {}
    for stage, times in latencies.items():
        times_ms = [t * 1000 for t in times]  # Convert to ms
        stats[stage] = {
            "runs": runs,
            "min_ms": round(min(times_ms), 3),
            "max_ms": round(max(times_ms), 3),
            "mean_ms": round(sum(times_ms) / len(times_ms), 3),
            "median_ms": round(sorted(times_ms)[len(times_ms) // 2], 3),
            "total_ms": round(sum(times_ms), 3),
        }

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Run all demo scenarios and produce evidence files."""
    print("=" * 60)
    print("A.05.1 Workflow Automation Agent — End-to-End Demo")
    print("=" * 60)
    print()

    results = {}

    # Scenario A
    report_a = run_scenario_a()
    path_a = _write_output("normal_run.md", report_a)
    results["scenario_a"] = str(path_a)
    print(f"  Written: {path_a}")
    print()

    # Scenario B
    report_b = run_scenario_b()
    path_b = _write_output("anomaly_review.md", report_b)
    results["scenario_b"] = str(path_b)
    print(f"  Written: {path_b}")
    print()

    # Scenario C
    report_c = run_scenario_c()
    path_c = _write_output("anomaly_detection.md", report_c)
    results["scenario_c"] = str(path_c)
    print(f"  Written: {path_c}")
    print()

    # Scenario D
    report_d = run_scenario_d()
    path_d = _write_output("human_correction.md", report_d)
    results["scenario_d"] = str(path_d)
    print(f"  Written: {path_d}")
    print()

    # Scenario E
    report_e = run_scenario_e()
    path_e = _write_output("human_rejection.md", report_e)
    results["scenario_e"] = str(path_e)
    print(f"  Written: {path_e}")
    print()

    # Scenario F
    report_f = run_scenario_f()
    path_f = _write_output("failure_case.md", report_f)
    results["scenario_f"] = str(path_f)
    print(f"  Written: {path_f}")
    print()

    # Latency benchmark
    latency_stats = run_latency_benchmark(runs=10)
    latency_path = _write_output(
        "latency_results.json",
        json.dumps(latency_stats, indent=2)
    )
    results["latency"] = str(latency_path)
    print(f"  Written: {latency_path}")
    print()

    # Summary
    print("=" * 60)
    print("Demo complete. Files produced:")
    for key, path in results.items():
        print(f"  {key}: {path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
