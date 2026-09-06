# A.05.1 — Workflow Automation Agent

**Accounting / Finance — Case 3: Accounting Firm**

A workflow automation agent for monthly expense processing and P&L generation, built strictly from the Trigger-Decision-Output template.

---

## Why This Workflow

The Case 3 Accounting Firm workflow was chosen because it involves:

- Multiple input sources (Excel spreadsheets + receipt data)
- Sequential dependencies across stages
- Branching logic (normal vs. review routing)
- Human-in-the-loop for exceptions
- State management (ledger accumulation)
- Structured output generation (P&L + client summary)

The expense and receipt stages operate on independent inputs, making concurrent execution a useful implementation choice in this prototype. This demonstrates the full Trigger-Decision-Output pattern with thoughtful component assignment.

---

## Business Workflow

```
Client sends monthly expense report
        ↓
Excel spreadsheet + receipt data
        ↓
Expense processing + Receipt processing (parallel)
        ↓
Reconciliation
        ↓
Categorization
        ↓
Anomaly detection
        ↓
Clean expenses → Ledger
Anomalies → Human review
        ↓
Human decisions → Ledger
        ↓
P&L generation
        ↓
Client summary (LLM)
        ↓
Final client output
```

---

## Architecture Overview

```
┌──────────────────────────────────────┐
│         MONTHLY TRIGGER              │
│ Client expense package arrives       │
└──────────────────┬───────────────────┘
                   │
          ┌────────┴────────┐
          │                 │
          ▼                 ▼
┌──────────────────┐  ┌──────────────────┐
│ Expense Processing│  │ Receipt Processing│
│ Excel parsing     │  │ JSON parsing      │
└────────┬─────────┘  └─────────┬─────────┘
         │                      │
         └──────────┬───────────┘
                    ▼
          ┌─────────────────────┐
          │   RECONCILIATION    │
          │ Vendor / amount /   │
          │ date comparison     │
          └──────────┬─────────┘
                     ▼
          ┌─────────────────────┐
          │   CATEGORIZATION    │
          │ Vendor lookup +     │
          │ keywords            │
          └──────────┬─────────┘
                     ▼
          ┌─────────────────────┐
          │ ANOMALY DETECTION   │
          │ Threshold-based     │
          │ scoring             │
          └──────────┬─────────┘
                     │
              ┌──────┴──────┐
              │             │
           NORMAL         REVIEW
              │             │
              │        HUMAN REVIEW
              │        APPROVE/CORRECT
              │             │
              └──────┬──────┘
                     ▼
              ┌────────────┐
              │   LEDGER   │
              └─────┬──────┘
                    ▼
              ┌────────────┐
              │ P&L REPORT │
              └─────┬──────┘
                    ▼
              ┌────────────┐
              │ LLM CLIENT │
              │   SUMMARY  │
              └─────┬──────┘
                    ▼
              ┌────────────┐
              │  CLIENT    │
              │  OUTPUT    │
              └────────────┘

For REJECT:
Human Review → REJECT → No Ledger Posting
```

Expense Processing and Receipt Processing operate on independent inputs. This prototype executes them concurrently using `ThreadPoolExecutor`. Reconciliation waits for both results.

---

## Trigger → Decision → Output

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

## Component Assignment

| Decision | Component | Rationale |
|----------|-----------|-----------|
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

The detailed reasoning behind these component assignments is maintained in [docs/routing-decisions.md](docs/routing-decisions.md).

---

## Human-in-the-Loop Boundary

**Human review is involved for:**
- Approving/rejecting/correcting anomalous expenses
- Any expense with `AnomalyVerdict.REVIEW`

**Human review is NOT involved for:**
- Normal expenses (posted directly to ledger)
- Financial calculations
- P&L generation
- Client summary generation

---

## Narrow LLM Boundary

**LLM is used for:**
- Natural-language client summary generation only

**LLM is NOT used for:**
- Expense categorization
- Receipt reconciliation
- Anomaly detection
- Financial calculations
- Ledger posting
- Human-review decisions
- P&L generation

The LLM is intentionally limited to natural-language client-summary generation because the underlying financial facts are already computed and validated by deterministic components. The LLM receives structured data from a validated P&L report. Anti-hallucination validation checks that the summary contains the source facts. If validation fails, `ClientSummaryError` is raised. The prototype uses `FakeLLMClient` for determinism.

---

## Failure-Driven Engineering

During development, five observed failures and three design issues were documented. The observed failures came from actual execution or testing; the design issues were decisions reconsidered during implementation. Full details are in [docs/failure-log.md](docs/failure-log.md).

| ID | Type | Issue | Root Cause | Resolution |
|----|------|-------|------------|------------|
| F-001 | Observed | Import path error | `src` not in Python path for direct script execution | Added project root to `sys.path` |
| F-002 | Observed | No vendor mismatch data | Data generator too clean | Modified generator to include mismatches |
| F-003 | Design | ML categorization considered | All vendors unambiguous | Moved to deterministic rules |
| F-004 | Observed | Threshold sensitivity | Small dataset (13 expenses) | Added `min_category_count` threshold |
| F-005 | Observed | Queue duplicates | No duplicate check | Added `_reviewed_ids` set |
| F-006 | Design | P&L from raw input | Initial design | Moved to ledger entries only |
| F-007 | Observed | Incomplete LLM validation | Only checked total | Expanded to check client, month, entries |
| F-008 | Design | Missing error propagation | Initial design | Added `WorkflowError` handling |

---

## Measured Prototype Results

**Latency (10 runs, `time.perf_counter()`):**

These are local prototype measurements, not production performance benchmarks.

| Stage | Mean (ms) |
|-------|-----------|
| Total | 10.822 |
| Expense Processing | 3.564 |
| Receipt Processing | 0.297 |
| Parallel Stage (combined) | 6.095 |
| Reconciliation | 0.158 |
| Categorization | 0.169 |
| Anomaly Detection | 0.175 |
| Ledger Posting | 0.114 |
| P&L Generation | 0.062 |
| Client Summary | 0.182 |

**Cost (prototype only):**

| Component | Cost |
|-----------|------|
| Compute | Local CPU; no production infrastructure cost measured |
| External LLM API | $0.00 — no external LLM API calls were made (`FakeLLMClient` used) |
| Storage | Local filesystem |

Production LLM cost was not measured. The prototype uses `FakeLLMClient` and makes no external API calls. Production cost would depend on provider, model, input/output token volume, and current pricing.

---

## Demo Scenarios

Six deterministic scenarios are available:

| Scenario | Description |
|----------|-------------|
| A | Normal expense (happy path) |
| B | Reconciliation mismatch |
| C | Anomaly detection (HIGH_VALUE, DUPLICATE, NEW_VENDOR) |
| D | Human correction |
| E | Human rejection |
| F | LLM grounding failure |

Output files are generated under `artifacts/demo/`.

---

## Testing

```
298 passed in 2.62s
```

- Phases 1-6: 253 tests
- Phase 7 (orchestrator): 45 tests

```bash
pytest tests/ -v
```

---

## Known Limitations

| Limitation | Impact | Status |
|------------|--------|--------|
| In-memory ledger | No persistence | Acceptable for prototype |
| FakeLLMClient | No real LLM testing | Acceptable for prototype |
| No retry logic | No resilience framework | Intentionally outside current prototype implementation scope |
| No audit logging | No persistent audit trail | Intentionally outside current prototype implementation scope |

---

## Repository Structure

```
├── A05_1_SPEC.md              # Authoritative specification
├── pyproject.toml
├── requirements.txt
├── src/
│   ├── workflow/              # Orchestrator
│   ├── triggers/              # Monthly trigger
│   ├── processors/            # Expense, receipt, reconciliation, categorization
│   ├── decisions/             # Anomaly detection
│   ├── human_review/          # Review queue
│   ├── tools/                 # File I/O, data generation
│   ├── llm/                   # Client summary (LLM only)
│   ├── accounting/            # Ledger, P&L
│   ├── audit/                 # Audit logging (placeholder)
│   └── models/                # Data schemas
├── data/
│   ├── synthetic/             # Fictional clients, vendors, expenses, receipts
│   └── outputs/               # Workflow outputs
├── scripts/
│   └── run_demo.py            # End-to-end demo
├── tests/                     # 298 tests
├── artifacts/
│   └── demo/                  # Demo output files
└── docs/
    ├── architecture.md        # Architecture documentation
    ├── FINAL_EVIDENCE_REPORT.md
    ├── routing-decisions.md
    ├── llm-boundary.md
    ├── failure-log.md
    ├── cost-model.md
    └── parallel-evidence.md
```

---

## How to Run

```bash
pip install -r requirements.txt
pytest tests/ -v
python scripts/run_demo.py
```

---

## Documentation

| Document | Contents |
|----------|----------|
| [A05_1_SPEC.md](A05_1_SPEC.md) | Authoritative specification |
| [docs/architecture.md](docs/architecture.md) | System architecture, diagrams, component assignment |
| [docs/FINAL_EVIDENCE_REPORT.md](docs/FINAL_EVIDENCE_REPORT.md) | End-to-end results, measurements, test results |
| [docs/routing-decisions.md](docs/routing-decisions.md) | Component assignment rationale per stage |
| [docs/llm-boundary.md](docs/llm-boundary.md) | LLM usage and non-usage boundaries |
| [docs/failure-log.md](docs/failure-log.md) | 5 observed failures + 3 design issues with root causes and resolutions |
| [docs/cost-model.md](docs/cost-model.md) | Cost analysis and what was not measured |
| [docs/parallel-evidence.md](docs/parallel-evidence.md) | Parallel execution dependency analysis |

---

## Evidence Classification

| Category | Source | Contents |
|----------|--------|----------|
| **Source requirements** | [`A05_1_SPEC.md`](A05_1_SPEC.md) | Trigger-Decision-Output pattern, decisions D1-D7, LLM restrictions |
| **Implementation decisions** | [`docs/routing-decisions.md`](docs/routing-decisions.md), [`docs/parallel-evidence.md`](docs/parallel-evidence.md) | Component assignment rationale, ThreadPoolExecutor concurrency choice |
| **Measured results** | [`docs/FINAL_EVIDENCE_REPORT.md`](docs/FINAL_EVIDENCE_REPORT.md) | 10.822 ms mean latency (10 runs), 298 tests passing |
| **Limitations** | [`docs/architecture.md`](docs/architecture.md), [`docs/cost-model.md`](docs/cost-model.md) | In-memory ledger, FakeLLMClient, no retry, no audit logging, cost analysis |
