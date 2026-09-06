# Final Evidence Report — A.05.1 Workflow Automation Agent

**Artifact:** A.05.1 — A Workflow Automation Agent Built Strictly From the Trigger-Decision-Output Template
**Domain:** Case 3 — Accounting Firm
**Date:** 2026-09-06
**Phase:** 8 — Evidence (Final)

---

## 1. What Problem the Workflow Solves

The A.05.1 workflow automates monthly expense processing for corporate clients of an accounting firm. It reduces mechanical processing while preserving human judgment for exceptions.

**Business Value:**
- Automates expense receipt matching
- Categorizes expenses into standard accounting categories
- Detects unusual spending patterns
- Routes exceptions to human review
- Generates monthly P&L statements
- Communicates results to clients

---

## 2. Why This Is a Real Multi-Step Workflow

The workflow involves:

1. **Multiple input sources**: Excel spreadsheets + receipt JSON files
2. **Parallel processing**: Expense and receipt processing run concurrently
3. **Sequential dependencies**: Reconciliation → Categorization → Anomaly Detection
4. **Branching logic**: NORMAL vs REVIEW routing
5. **Human-in-the-loop**: Anomalous expenses require human judgment
6. **State management**: Ledger entries accumulate across stages
7. **Output generation**: P&L and client summary from accumulated state

---

## 3. Trigger–Decision–Output Decomposition

| Stage | Trigger | Decision | Output |
|-------|---------|----------|--------|
| Monthly Trigger | Client expense package | System operation | WorkflowRun + files |
| Expense Processing | Excel file | Schema validation | ExpenseRecord list |
| Receipt Processing | JSON file | Schema validation | ReceiptRecord list |
| Reconciliation | Expenses + Receipts | Vendor/amount/date comparison | ReconciliationResult list |
| Categorization | Expenses | Vendor lookup + keywords | CategorizationResult list |
| Anomaly Detection | Expenses + Reconciliation | Threshold-based scoring | AnomalyResult list |
| Human Review | Anomalies | Human judgment | ReviewDecision list |
| Ledger Posting | Expenses + Decisions | Posting rules | LedgerEntry list |
| P&L Generation | Ledger entries | Aggregation | PLReport |
| Client Summary | P&L report | LLM natural-language generation | ClientSummaryResult |

---

## 4. Architecture

```
                    TRIGGER
                       |
              +--------+--------+
              |                 |
              v                 v
           EXPENSE           RECEIPT
              |                 |
              +--------+--------+
                       |
                    RECONCILE
                       |
                  CATEGORIZE
                       |
                ANOMALY DETECT
                       |
                 +-----+-----+
                 |           |
               NORMAL      REVIEW
                 |           |
                 |       HUMAN REVIEW
                 |           |
                 +-----+-----+
                       |
                    LEDGER
                       |
                      P&L
                       |
                 LLM SUMMARY
```

---

## 5. Component Assignment Rationale

| Decision | Component | Why |
|----------|-----------|-----|
| Monthly trigger | Tools | System operation, no judgment |
| Expense parsing | Rules + Tools | Deterministic parsing |
| Receipt processing | Rules + Tools | Deterministic parsing |
| Reconciliation | Rules | Binary comparison |
| Categorization | Rules | Vendor lookup + keywords |
| Anomaly detection | Rules + Statistical | Threshold-based scoring |
| Human review | Human | Judgment required |
| Ledger posting | Rules + Tools | Deterministic posting |
| P&L generation | Rules | Aggregation |
| Client summary | LLM | Natural-language generation |

---

## 6. Parallel Execution Rationale

**Independent Stages:**
- Expense Processing: Reads Excel file, produces ExpenseRecord list
- Receipt Processing: Reads JSON file, produces ReceiptRecord list

**Why Parallel:** These stages read different inputs and produce different outputs. They have no data dependencies on each other.

**Dependency:** Reconciliation depends on BOTH results, so it waits for both to complete.

---

## 7. Deterministic Decision Logic

All financial decisions use deterministic rules:

| Decision | Logic |
|----------|-------|
| Reconciliation | Vendor match (exact/fuzzy) + Amount match (tolerance) + Date match |
| Categorization | Vendor lookup → keyword heuristics → fallback |
| Anomaly detection | HIGH_VALUE: category_mean * multiplier; DUPLICATE: exact match; NEW_VENDOR: known vendor list |
| Ledger posting | NORMAL→POSTED, APPROVE→HUMAN_REVIEWED, CORRECT→HUMAN_REVIEWED, REJECT→skip |
| P&L generation | Aggregate ledger entries by category |

---

## 8. Human-in-the-loop Boundary

**Human Review is involved for:**
- Approving/rejecting/correcting anomalous expenses
- Any expense with `AnomalyVerdict.REVIEW`

**Human Review is NOT involved for:**
- Normal expenses (posted directly to ledger)
- Financial calculations
- P&L generation
- Client summary generation

---

## 9. LLM Boundary

**LLM IS used for:**
- Natural-language client summary generation only

**LLM is NOT used for:**
- Expense categorization
- Receipt reconciliation
- Anomaly detection
- Financial calculations
- Ledger posting
- Human-review decisions
- P&L generation

---

## 10. Failure Evidence

| Failure | Stage | Root Cause | Resolution |
|---------|-------|------------|------------|
| F-001: Import path error | Expense Processing | `src` not in Python path | Added project root to sys.path |
| F-002: No vendor mismatch data | Data Generation | Data generator too clean | Modified generator to include mismatches |
| F-003: ML categorization considered | Categorization | Initial design | Moved to rules (all vendors unambiguous) |
| F-004: Threshold sensitivity | Anomaly Detection | Small dataset | Added min_category_count threshold |
| F-005: Queue duplicates | Human Review | No duplicate check | Added _reviewed_ids set |
| F-006: P&L from raw input | P&L Generation | Initial design | Moved to ledger entries only |
| F-007: Incomplete validation | Client Summary | Only checked total | Expanded to check client, month, entries |
| F-008: Missing error propagation | Orchestration | Initial design | Added WorkflowError handling |

---

## 11. Routing Decisions

See `docs/routing-decisions.md` for complete documentation.

**Key Decision:** LLM is NOT used for deterministic financial decisions.

---

## 12. End-to-End Demo Results

**Scenarios Executed:**
- Scenario A: Normal expense (happy path) ✅
- Scenario B: Reconciliation mismatch ✅
- Scenario C: Anomaly detection ✅
- Scenario D: Human correction ✅
- Scenario E: Human rejection ✅
- Scenario F: LLM grounding failure ✅

**Output Files:** `artifacts/demo/`

---

## 13. Latency Measurements

| Stage | Mean (ms) | Min (ms) | Max (ms) |
|-------|-----------|----------|----------|
| Total | 10.822 | 7.840 | 15.654 |
| Expense Processing | 3.564 | 2.420 | 5.689 |
| Receipt Processing | 0.297 | 0.193 | 0.771 |
| Parallel Stage | 6.095 | 4.492 | 7.898 |
| Reconciliation | 0.158 | 0.135 | 0.277 |
| Categorization | 0.169 | 0.126 | 0.414 |
| Anomaly Detection | 0.175 | 0.132 | 0.411 |
| Ledger Posting | 0.114 | 0.078 | 0.208 |
| P&L Generation | 0.062 | 0.044 | 0.110 |
| Client Summary | 0.182 | 0.129 | 0.487 |

**Measurement Method:** 10 runs using `time.perf_counter()`

---

## 14. Cost Model

### Actual Prototype Cost

| Component | Cost |
|-----------|------|
| Compute | Local CPU (negligible) |
| LLM | $0.00 (FakeLLMClient) |
| Storage | Local filesystem (negligible) |
| **Total** | **~$0.00 per run** |

Production LLM cost was not measured because the prototype uses FakeLLMClient and makes no external API calls. Production cost would depend on provider, model, input/output token volume, and current pricing.

---

## 15. Test Results

```
298 passed in 2.62s
```

- Phase 1-6 (existing): 253 tests ✅
- Phase 7 (orchestrator): 45 tests ✅
- Phase 8 (demo/tests): New tests added ✅

---

## 16. Known Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| In-memory ledger | No persistence | Acceptable for prototype |
| FakeLLMClient | No real LLM testing | Acceptable for prototype |
| No retry logic | No resilience | Intentionally outside the prototype implementation scope |
| No audit logging | No persistent audit trail | Intentionally outside the prototype implementation scope |
| No production deployment | Prototype only | By design |

---

## 17. What Is Measured vs Estimated

| Item | Status |
|------|--------|
| Workflow latency | Measured (10 runs) |
| LLM cost | Not measured (FakeLLMClient used) |
| Compute cost | Not measured (local CPU) |
| Production latency | Not measured |
| Real LLM latency | Not measured |

---

## 18. What Was Intentionally Not Implemented

| Item | Reason |
|------|--------|
| Production deployment | Intentionally outside the prototype implementation scope |
| Real LLM API integration | FakeLLMClient used for determinism |
| Real accounting APIs | Synthetic data only |
| Retry/resilience framework | Intentionally outside the prototype implementation scope |
| Enterprise audit logging | Intentionally outside the prototype implementation scope |
| Frontend UI | Not required |

---

## 19. Mapping to A.05.1 Requirements

| Requirement | Status |
|-------------|--------|
| Trigger-Decision-Output pattern | ✅ Implemented |
| Component assignment principle | ✅ Implemented |
| Parallel processing | Implementation decision: Expense Processing and Receipt Processing execute concurrently because they are independent branches |
| Human-in-the-loop | ✅ Implemented |
| LLM boundary | ✅ Implemented |
| Deterministic decisions | ✅ Implemented |
| End-to-end workflow | ✅ Implemented |
| Evidence/measurement | ✅ Implemented |

---

*Generated: 2026-09-06*
*Phase: 8 — Evidence (Final)*
