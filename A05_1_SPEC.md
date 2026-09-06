# A05_1 — Workflow Automation Agent: Accounting / Finance

## 1. Artifact Identity

| Field | Value |
|-------|-------|
| Artifact ID | A.05.1 |
| Title | A Workflow Automation Agent Built Strictly From the Trigger-Decision-Output Template |
| Business Domain | Accounting / Finance |
| Source Workflow | Case 3 — Accounting Firm |

## 2. Business Domain

Accounting / Finance — monthly expense processing and P&L generation for corporate clients of an accounting firm.

## 3. Source Workflow

```
Client sends monthly expense report
        ↓
Excel spreadsheet + receipt images
        ↓
Excel processing
        ↓
Receipt processing
        ↓
Expense / receipt reconciliation
        ↓
Expense categorization
        ↓
Anomaly detection
        ↓
Clean expenses
        ↓
Accounting update
        ↓
Anomalies
        ↓
Human review
        ↓
Approve / Correct / Reject
        ↓
Accounting update
        ↓
P&L generation
        ↓
Client summary
        ↓
Final client output
```

## 4. Business Objective

The accounting team aims to:

- Reconcile monthly expense data from clients
- Verify expense records against receipts
- Identify mismatches and missing receipts
- Categorize expenses into standard accounting categories
- Detect unusual spending patterns
- Investigate exceptions via human review
- Update accounting records
- Generate monthly P&L statements
- Communicate results to the client

The system reduces mechanical processing while preserving human judgment for exceptions.

## 5. Trigger

**Trigger:** Monthly expense package arrives from a fictional client.

**Input:**
- Fictional client identity
- Reporting month
- Expense Excel spreadsheet (synthetic)
- Receipt images or synthetic receipt data

**Output:** A workflow run instance containing the monthly expense package.

## 6. Decisions

| # | Decision | Component | Basis |
|---|----------|-----------|-------|
| D1 | Is the expense data well-formed? | Deterministic Rules | Schema validation |
| D2 | Does the receipt match the expense? | Deterministic Rules | Vendor, amount, date comparison |
| D3 | What category does this expense belong to? | Deterministic Rules + Statistical ML | Rules for clear cases; ML for ambiguous cases |
| D4 | Is this expense anomalous? | Statistical ML + Rules | Threshold-based anomaly scoring with explainable features |
| D5 | Should this anomaly be reviewed by a human? | Deterministic Rules | Threshold routing |
| D6 | Approve / Reject / Correct an expense? | Human | Reviewer judgment with evidence |
| D7 | How to summarize results for the client? | LLM | Natural-language generation from structured data |

**LLM restrictions:** The LLM MUST NOT independently decide expense validity, anomaly status, approval, or rejection.

## 7. Outputs

| Output | Format | Source |
|--------|--------|--------|
| Monthly P&L | Structured table + markdown | Accounting system + P&L generator |
| Reconciliation status | Structured records | Reconciliation processor |
| Anomaly / exception summary | Structured list | Anomaly detector |
| Human review outcomes | Structured audit trail | Human review queue |
| Client-facing summary | Natural language (LLM-generated) | LLM summarizer |
| Audit log | Structured log entries | Audit logger |

## 8. Component Responsibilities

### TRIGGER
- Simulates the monthly expense package arriving from the client
- Produces a workflow run with all input artifacts

### DETERMINISTIC RULES
- Missing receipt detection
- Vendor comparison
- Amount comparison
- Date comparison
- Basic validation
- Deterministic categorization where appropriate

### DETERMINISTIC / STATISTICAL ML
- Expense categorization where statistical classification makes sense
- Anomaly detection
- Unusual spending-pattern detection

**Anomaly detection must remain explainable.**

### LLM
- Structuring receipt information after OCR (future)
- Generating client-facing monthly summary

**The LLM MUST NOT independently decide:**
- Whether an expense is valid
- Whether an expense is anomalous
- Whether an expense should be approved
- Whether an expense should be rejected

### TOOLS / INTERFACES
- Reading files (Excel, receipts)
- Receipt / OCR processing (simulated)
- Accounting-system operations (simulated)
- Report generation
- Simulated client communication

### HUMAN
- Anomalies are routed to human review
- Actions: APPROVE, REJECT, CORRECT
- Decisions persisted with: reviewer, decision, reason, timestamp

## 9. Rules vs ML vs LLM vs Tools vs Human

| Responsibility | Assignment | Rationale |
|----------------|------------|-----------|
| Schema validation | Rules | Deterministic, clearly specified |
| Missing receipt check | Rules | Binary, deterministic |
| Vendor comparison | Rules | Exact/fuzzy string matching |
| Amount comparison | Rules | Numeric comparison with tolerance |
| Date comparison | Rules | Date arithmetic |
| Expense categorization (clear cases) | Rules | deterministic mapping |
| Expense categorization (ambiguous) | Statistical ML | Pattern-based classification |
| Anomaly detection | Statistical ML + Rules | Explainable threshold-based scoring |
| Receipt OCR (future) | Tools | External capability |
| Client summary | LLM | Natural-language generation |
| Approval / rejection | Human | Judgment required |
| Accounting updates | Tools | Simulated system operations |
| P&L generation | Rules | Aggregation from accounting records |

## 10. Local Simulation Boundary

The application runs locally using synthetic data only.

**DO NOT connect to:**
- Real bank accounts
- Real payment systems
- Real customer financial data
- Real accounting systems
- Real email delivery
- Real client information

**Fictional entities:**
- Accounting firm: "Sterling & Associates CPAs"
- Corporate clients: "TechVista Inc.", "GreenLeaf Manufacturing", "Pinnacle Consulting"
- Employees, vendors, expenses, receipts, historical data, accounting records — all synthetic

The accounting system is simulated locally.

## 11. Functional Requirements

### A. Monthly Expense Trigger
- **Input:** Fictional client, reporting month, expense file, receipt files
- **Output:** Workflow run containing the monthly expense package

### B. Expense / Excel Processor
- Extract structured records including:
  - expense_id
  - employee
  - date
  - description
  - vendor
  - amount
  - category
  - receipt_reference

### C. Receipt Processor
- Extract: vendor, amount, date, line items (where available)
- Keep receipt processing separate from reconciliation
- Initial implementation uses synthetic receipt data
- Design allows OCR substitution later

### D. Expense Categorizer
- Categories (Case 3):
  - Travel
  - Meals & Entertainment
  - Software
  - Office Supplies
  - Professional Services
  - Utilities
  - Marketing
  - Miscellaneous
- Use rules for clear cases; ML for ambiguous cases
- Do not use LLM merely because it is convenient

### E. Reconciliation
- Match expense records against receipts
- Check: vendor, amount, date
- Support statuses:
  - EXACT_MATCH
  - AMOUNT_MISMATCH
  - VENDOR_MISMATCH
  - DATE_MISMATCH
  - MISSING_RECEIPT
- Every exception contains: reason, evidence

### F. Anomaly Detection
- Detect:
  - Unusually high expense for a category
  - Duplicate / similar expense
  - Unusual spending pattern
  - New / infrequent vendor
  - Significant historical spending change
- Output: NORMAL or REVIEW with reason, evidence/features, configurable threshold

### G. Human Review
- Every REVIEW item enters a human-review queue
- Reviewer can: approve, reject, correct
- Decision and reason are persisted

### H. Simulated Accounting System
- Maintain local accounting records
- Clean expenses posted automatically
- Human-reviewed expenses posted after human decision
- Maintain audit trail

### I. P&L Generation
- Generate monthly P&L from accounting records
- Include: total expenses, totals by category, monthly summary
- Do not calculate final P&L directly from raw input

### J. Client Summary
- LLM used only for natural-language summarization
- Provide LLM with structured and validated results
- LLM must not invent financial facts

### K. Final Output
- Monthly P&L
- Reconciliation status
- Anomaly / exception summary
- Human review outcomes
- Client-facing summary

## 12. Auditability

Every workflow run must be inspectable. Log:

1. Trigger
2. Input
3. Component executed
4. Component input
5. Component output
6. Decision
7. Reason / evidence
8. Human intervention
9. Accounting update
10. Final output

A reviewer must be able to reconstruct the complete workflow from the audit log.

## 13. Failure Handling

Explicitly handle:
- Malformed expense data
- Missing receipt
- Unreadable receipt
- Reconciliation failure
- Anomaly detector failure
- Accounting update failure
- LLM failure

**Rules:**
- Never silently discard data
- Preserve original inputs
- Provide explicit failure states
- Use human / manual fallback where appropriate

## 14. Synthetic Test Cases

| # | Test Case | Path |
|---|-----------|------|
| 1 | Normal expense + matching receipt | Happy path |
| 2 | Amount mismatch | Reconciliation exception |
| 3 | Missing receipt | Reconciliation exception |
| 4 | Vendor mismatch | Reconciliation exception |
| 5 | Date mismatch | Reconciliation exception |
| 6 | Unusually high-value meal | Anomaly detection |
| 7 | Duplicate expense | Anomaly detection |
| 8 | New vendor | Anomaly detection |
| 9 | Significant category-spending change | Anomaly detection |
| 10 | Legitimate anomaly approved by human | Human review — approve |
| 11 | Suspicious anomaly rejected by human | Human review — reject |
| 12 | Expense corrected by human | Human review — correct |

## 15. Testing

Create:
- Unit tests
- Reconciliation tests
- Categorization tests
- Anomaly detection tests
- Human review tests
- Accounting record tests
- P&L tests
- End-to-end tests

**End-to-end test covers:**
```
Trigger
→ Expense Processing
→ Receipt Processing
→ Reconciliation
→ Categorization
→ Anomaly Detection
→ Human Review (where required)
→ Accounting Records
→ P&L
→ Client Summary
→ Final Output
```

## 16. Repository Architecture

Separate these concerns:
- Workflow orchestration
- Business logic
- Deterministic rules
- ML (categorization, anomaly detection)
- LLM (client summary only)
- Tools (file I/O, simulated accounting)
- Human review
- Data models
- Persistence
- Tests
- Synthetic data

No single giant agent file. Clear interfaces and structured schemas.
Workflow must be reproducible and independently testable.

## 17. Repository Structure

```
project-root/
|
├── README.md
├── A05_1_SPEC.md
├── pyproject.toml
├── requirements.txt
|
├── src/
│   ├── __init__.py
│   ├── workflow/
│   │   ├── __init__.py
│   │   └── orchestrator.py
│   ├── triggers/
│   │   ├── __init__.py
│   │   └── monthly_trigger.py
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── expense_processor.py
│   │   ├── receipt_processor.py
│   │   ├── reconciler.py
│   │   └── categorizer.py
│   ├── decisions/
│   │   ├── __init__.py
│   │   └── anomaly_detector.py
│   ├── human_review/
│   │   ├── __init__.py
│   │   └── review_queue.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── file_reader.py
│   │   └── accounting_system.py
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client_summary.py
│   ├── accounting/
│   │   ├── __init__.py
│   │   ├── ledger.py
│   │   └── pl_generator.py
│   ├── audit/
│   │   ├── __init__.py
│   │   └── audit_logger.py
│   └── models/
│       ├── __init__.py
│       ├── expense.py
│       ├── receipt.py
│       ├── reconciliation.py
│       ├── anomaly.py
│       ├── human_review.py
│       ├── accounting.py
│       └── workflow.py
|
├── data/
│   ├── synthetic/
│   │   ├── clients.json
│   │   ├── employees.json
│   │   ├── vendors.json
│   │   ├── expenses/
│   │   ├── receipts/
│   │   └── historical/
│   └── outputs/
|
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_expense_processor.py
│   ├── test_receipt_processor.py
│   ├── test_reconciler.py
│   ├── test_categorizer.py
│   ├── test_anomaly_detector.py
│   ├── test_human_review.py
│   ├── test_accounting.py
│   ├── test_pl_generator.py
│   └── test_end_to_end.py
|
└── docs/
    └── architecture/
```

## 18. Implementation Phases

### PHASE 1 (CURRENT)
- Repository inspection
- Project structure
- Schemas
- Synthetic data foundation
- Create / update A05_1_SPEC.md
- **STOP after completion**

### PHASE 2
- Monthly trigger
- Expense processor
- Receipt processor
- **STOP after completion**

### PHASE 3
- Reconciliation
- Categorization
- **STOP after completion**

### PHASE 4
- Anomaly detector
- Human-review queue
- **STOP after completion**

### PHASE 5
- Simulated accounting system
- P&L generation
- **STOP after completion**

### PHASE 6
- LLM client-summary generation
- **STOP after completion**

### PHASE 7
- Complete workflow orchestration
- **STOP after completion**

### PHASE 8
- Audit log
- Failure handling
- Full testing
- Measured results
- Demo
- **STOP after completion**

## 19. Evidence and Measurement Rules

This is a portfolio artifact.

- Do NOT claim performance that has not been measured
- Do not invent accuracy, automation percentage, cost savings, latency improvements, or business impact
- Any performance claim must come from an actual executed experiment

**Clearly distinguish:**
- SOURCE REQUIREMENT (from this spec)
- OUR IMPLEMENTATION DECISION (design choices)
- MEASURED RESULT (from experiments)
- ASSUMPTION (unverified beliefs)
- LIMITATION (known constraints)

## 20. Non-Goals

Do not build:
- Generic chatbot
- Generic autonomous agent
- Production accounting SaaS
- Real banking integration
- Real payment integration
- Real email delivery
- Unnecessary microservices
- Kubernetes
- Unnecessary cloud infrastructure
- LLM-based decision-making for every step

## 21. Important Implementation Rule

Before making an implementation decision, check:

> "Does this support the Case 3 business workflow and A.05.1 Trigger-Decision-Output principle?"

- If YES → proceed when appropriate
- If NO → do not introduce it merely because it is technically interesting

Prefer the simplest implementation that clearly demonstrates the workflow and component boundaries.

## 22. Current Project Status

| Item | Status |
|------|--------|
| Phase | 1 — Foundation |
| A05_1_SPEC.md | Created |
| Project structure | Created |
| Data schemas | Defined |
| Synthetic data | Defined |
| Tests | Pending |
