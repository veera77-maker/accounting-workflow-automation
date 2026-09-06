# Architecture — A.05.1 Workflow Automation Agent

## 1. System Purpose

A.05.1 implements a workflow automation agent for the Case 3 Accounting Firm monthly expense reconciliation workflow. The system processes client expense packages through reconciliation, categorization, anomaly detection, human review, accounting, P&L generation, and client summary generation.

---

## 2. Primary System Architecture

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

**Key architectural points:**
- Expense Processing and Receipt Processing operate on independent inputs. This prototype executes them concurrently using `ThreadPoolExecutor`. Reconciliation waits for both results.
- All financial decisions use deterministic rules.
- Human review handles exceptions only.
- LLM is used only for natural-language summarization.
- Ledger and P&L use deterministic arithmetic.

---

## 3. Business Workflow

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

## 4. Trigger–Decision–Output Decomposition

```
TRIGGER
  ↓
Monthly client expense package
  ↓
PROCESSING
  ├── Expense processing
  └── Receipt processing
          ↓
DECISIONS
  ├── Reconciliation
  ├── Categorization
  ├── Anomaly detection
  └── Routing
       ├── NORMAL → Ledger
       └── REVIEW → Human decision
                         ├── APPROVE → Ledger
                         ├── CORRECT → Ledger
                         └── REJECT → No ledger posting

Ledger
  ↓
P&L
  ↓
Client Summary
  ↓
OUTPUT
```

**Component assignment for decisions:**
- Processing: Tools + Rules (deterministic parsing)
- Reconciliation through Routing: Rules (deterministic logic)
- Human decision: Human (judgment required)
- Client Summary: LLM (natural-language generation only)

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

## 5. Component Assignment

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

---

## 6. Execution Dependency Graph

```
                     TRIGGER
                        │
                ┌───────┴───────┐
                │               │
                ▼               ▼
             EXPENSE         RECEIPT
                │               │
                └───────┬───────┘
                      \ /
               WAIT FOR BOTH
                        │
                    RECONCILE
                        │
                   CATEGORIZE
                        │
                 ANOMALY DETECT
                        │
                   NORMAL / REVIEW
                        │
                      LEDGER
                        │
                       P&L
                        │
                  LLM SUMMARY
```

**Dependency rules:**
- EXPENSE and RECEIPT are independent and execute concurrently via `ThreadPoolExecutor`.
- RECONCILE waits for both to complete.
- NORMAL path posts directly to LEDGER.
- REVIEW path routes to HUMAN, then posts or rejects.

---

## 7. Parallel Branch Explanation

Expense Processing and Receipt Processing operate on independent inputs. This prototype executes them concurrently using `ThreadPoolExecutor`. Reconciliation waits for both results.

**Independent Stages:**
- Expense Processing: Reads Excel file, produces ExpenseRecord list
- Receipt Processing: Reads JSON file, produces ReceiptRecord list

**Why Parallel:** These stages read different inputs and produce different outputs. They have no data dependencies on each other.

**Implementation:** `concurrent.futures.ThreadPoolExecutor` with `max_workers=2`

**Dependency:** Reconciliation depends on BOTH results, so it waits for both to complete.

---

## 8. Human-in-the-loop Boundary

```
AUTOMATED (no human)                HUMAN REVIEW REQUIRED
─────────────────────               ─────────────────────
• Expense parsing                   • Approve expense
• Receipt processing                • Reject expense
• Reconciliation                    • Correct expense values
• Categorization
• Anomaly detection
• Ledger posting
• P&L generation
• Client summary (LLM)
```

Anomaly detection routes REVIEW verdicts to human review. All other stages execute without human involvement.

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

```
Validated PLReport
       ↓
Structured data
       ↓
Grounded prompt
       ↓
LLM
       ↓
Natural-language client summary
       ↓
Grounding validation
       ├── PASS → ClientSummaryResult
       └── FAIL → Explicit validation error
```

**LLM IS USED FOR:**
- Natural-language client summary generation.

**LLM IS NOT USED FOR:**
- Expense categorization
- Receipt reconciliation
- Anomaly detection
- Financial calculations
- Ledger posting
- Human-review decisions
- P&L generation

**Rationale:** LLM is the cheapest trustworthy component for natural-language generation. All financial decisions use deterministic rules.

---

## 10. Failure Handling

| Failure | Handling |
|---------|----------|
| Missing expense file | `WorkflowError` raised, status=FAILED |
| Missing receipt file | `WorkflowError` raised, status=FAILED |
| Processing errors | Collected in result, not silently discarded |
| LLM failure | `ClientSummaryError` raised |
| LLM hallucination | Validation fails, explicit error |

---

## 11. Observability/Evidence

**Tracked per workflow run:**
- Run ID, client ID, month
- Stage results (expense/receipt/reconciliation/categorization/anomaly records)
- Human review items and decisions
- Ledger entries
- P&L report
- Client summary
- Validation status
- Errors

---

## 12. Known Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| In-memory ledger | No persistence | Acceptable for prototype |
| FakeLLMClient | No real LLM testing | Acceptable for prototype |
| No retry logic | No resilience framework | Intentionally outside current prototype implementation scope |
| No audit logging | No persistent audit trail | Intentionally outside current prototype implementation scope |

---

*Generated: 2026-09-06*
*Phase: 8 — Evidence*
