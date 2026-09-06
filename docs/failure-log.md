# Failure Log — A.05.1 Workflow Automation Agent

This document records failures observed during development and testing of the A.05.1 workflow. Each entry includes the failure description, root cause, and resolution.

---

## F-001: Expense Processing Import Path Error

| Field | Value |
|-------|-------|
| **Failure ID** | F-001 |
| **Date** | 2026-09-06 |
| **Workflow Stage** | Expense Processing |
| **Failure Description** | `ModuleNotFoundError: No module named 'src'` when importing from `src.models.accounting` |
| **Input Condition** | Running demo script from project root |
| **Observed Behavior** | Import fails because `src` is not in Python path when running scripts directly |
| **Expected Behavior** | Imports should work when running from project root |
| **Root Cause** | `ledger.py` uses `from src.models.accounting import ...` which requires `src` to be in Python path. The `pyproject.toml` adds `src` to path for pytest but not for direct script execution |
| **Routing/Component Decision** | Deterministic logic — import path issue |
| **Resolution** | Added project root to `sys.path` in demo script |
| **Decision Location** | Demo script (`scripts/run_demo.py`) |
| **Test Coverage** | Not covered by unit tests; test runner handles path correctly |

---

## F-002: Data Generator Vendor Mismatch

| Field | Value |
|-------|-------|
| **Failure ID** | F-002 |
| **Date** | 2026-09-06 |
| **Workflow Stage** | Data Generation |
| **Failure Description** | Synthetic data did not include vendor mismatch scenarios for testing reconciliation |
| **Input Condition** | Phase 3 testing of reconciler |
| **Observed Behavior** | All expenses matched receipts exactly |
| **Expected Behavior** | Some expenses should have vendor mismatches to test reconciliation logic |
| **Root Cause** | Data generator created perfect matches only |
| **Routing/Component Decision** | Deterministic logic — data generation |
| **Resolution** | Modified `data_generator.py` to include vendor mismatch scenario (Delta Airlines vs Delta Air Lines) |
| **Decision Location** | `src/tools/data_generator.py` |
| **Test Coverage** | `tests/test_reconciler.py::TestReconcilerWithSyntheticData::test_vendor_mismatch_found` |

---

## F-003: Categorizer ML Assignment Considered

| Field | Value |
|-------|-------|
| **Failure ID** | F-003 |
| **Date** | 2026-09-06 |
| **Workflow Stage** | Categorization |
| **Type** | Design decision / issue considered during implementation |
| **Description** | Initial design considered using ML for categorization |
| **Input Condition** | Phase 3 planning |
| **Observed Behavior** | N/A — design decision |
| **Expected Behavior** | N/A |
| **Root Cause** | All vendors in synthetic data have clear, unambiguous category assignments |
| **Routing/Component Decision** | Moved from ML to deterministic rules |
| **Resolution** | Categorizer implemented with deterministic rules only (vendor lookup + keyword heuristics). ML would only be appropriate if future data includes vendors spanning multiple categories |
| **Decision Location** | `src/processors/categorizer.py` |
| **Test Coverage** | `tests/test_categorizer.py` — 27 tests |

---

## F-004: Anomaly Detector Threshold Sensitivity

| Field | Value |
|-------|-------|
| **Failure ID** | F-004 |
| **Date** | 2026-09-06 |
| **Workflow Stage** | Anomaly Detection |
| **Failure Description** | High-value threshold too sensitive for small datasets |
| **Input Condition** | Phase 4 testing with 13 expenses |
| **Observed Behavior** | Some normal expenses flagged as REVIEW |
| **Expected Behavior** | Only genuinely anomalous expenses should be flagged |
| **Root Cause** | With only 13 expenses, category means are based on small samples |
| **Routing/Component Decision** | Deterministic logic — threshold tuning |
| **Resolution** | Added `min_category_count_for_mean` threshold (default: 3). When fewer than 3 expenses in a category, uses max * multiplier instead of mean * multiplier |
| **Decision Location** | `src/decisions/anomaly_detector.py` |
| **Test Coverage** | `tests/test_anomaly_detector.py::TestHighValueCheck::test_insufficient_data_uses_max` |

---

## F-005: Human Review Queue Duplicate Prevention

| Field | Value |
|-------|-------|
| **Failure ID** | F-005 |
| **Date** | 2026-09-06 |
| **Workflow Stage** | Human Review |
| **Failure Description** | Same expense could be added to review queue multiple times |
| **Input Condition** | Testing review queue operations |
| **Observed Behavior** | `add_to_queue` succeeded for duplicate expense_id |
| **Expected Behavior** | Should reject duplicate expense_id with clear error |
| **Root Cause** | No duplicate check in queue implementation |
| **Routing/Component Decision** | Deterministic logic — queue validation |
| **Resolution** | Added `_reviewed_ids` set to track expenses already in queue. `add_to_queue` raises `ReviewQueueError` for duplicates |
| **Decision Location** | `src/human_review/review_queue.py` |
| **Test Coverage** | `tests/test_review_queue.py::TestQueueBasics::test_cannot_add_duplicate_expense` |

---

## F-006: P&L Generated from Raw Input

| Field | Value |
|-------|-------|
| **Failure ID** | F-006 |
| **Date** | 2026-09-06 |
| **Workflow Stage** | P&L Generation |
| **Type** | Design decision / issue considered during implementation |
| **Description** | Initial design considered generating P&L from raw expense records |
| **Input Condition** | Phase 5 planning |
| **Observed Behavior** | N/A — design decision |
| **Expected Behavior** | N/A |
| **Root Cause** | Spec requires "Do not calculate final P&L directly from raw input" |
| **Routing/Component Decision** | Moved from raw input to ledger entries |
| **Resolution** | P&L generator only accepts ledger entries (accounting records), not raw expenses. This ensures only posted expenses appear in P&L |
| **Decision Location** | `src/accounting/pl_generator.py` |
| **Test Coverage** | `tests/test_pl_generator.py` — 21 tests |

---

## F-007: LLM Hallucination Not Caught

| Field | Value |
|-------|-------|
| **Failure ID** | F-007 |
| **Date** | 2026-09-06 |
| **Workflow Stage** | Client Summary |
| **Failure Description** | Initial LLM validation only checked total expenses amount |
| **Input Condition** | Phase 6 testing |
| **Observed Behavior** | LLM could hallucinate client ID or month without detection |
| **Expected Behavior** | All financial facts should be validated |
| **Root Cause** | Incomplete validation checks |
| **Routing/Component Decision** | Deterministic logic — validation expansion |
| **Resolution** | Expanded `_validate_summary()` to check: total expenses, client ID, month, entry count |
| **Decision Location** | `src/llm/client_summary.py` |
| **Test Coverage** | `tests/test_client_summary.py::TestValidateSummary` — 7 tests |

---

## F-008: Orchestrator Missing Error Propagation

| Field | Value |
|-------|-------|
| **Failure ID** | F-008 |
| **Date** | 2026-09-06 |
| **Workflow Stage** | Orchestration |
| **Type** | Design decision / issue considered during implementation |
| **Description** | Initial orchestrator design did not propagate errors from parallel branches |
| **Input Condition** | Phase 7 design |
| **Observed Behavior** | N/A — design decision |
| **Expected Behavior** | N/A |
| **Root Cause** | N/A |
| **Routing/Component Decision** | Error handling design |
| **Resolution** | Orchestrator catches exceptions from both parallel branches and raises `WorkflowError` with status set to `FAILED` |
| **Decision Location** | `src/workflow/orchestrator.py` |
| **Test Coverage** | `tests/test_orchestrator.py::TestErrorPropagation` — 2 tests |

---

## Summary

| Category | Count | Resolution |
|----------|-------|------------|
| Observed Failures | 5 | Fixed in implementation |
| Design Decisions | 3 | Issues considered during implementation |

**Observed Failures (5):**
- F-001: Import path error (real failure when running demo script)
- F-002: Data generator missing vendor mismatch scenarios (real failure during testing)
- F-004: Anomaly detector threshold sensitivity (real failure during testing)
- F-005: Human review queue duplicate prevention (real failure during testing)
- F-007: LLM hallucination not caught (real failure during testing)

**Design Decisions (3):**
- F-003: ML categorization considered (moved to rules)
- F-006: P&L from raw input considered (moved to ledger entries)
- F-008: Error propagation design (added WorkflowError handling)

**Failures Not Observed (Covered by Tests):**
- LLM provider timeout (covered by `NoOpLLMClient` tests)
- Missing expense file (covered by `TestWorkflowError` tests)
- Empty data handling (covered by `TestEmptyDataHandling` tests)

---

*Generated: 2026-09-06*
*Phase: 8 — Evidence*
