# Architecture Documentation

This directory contains architecture documentation for the A.05.1 Workflow Automation Agent.

## Component Overview

```
┌─────────────────────────────────────────────────────┐
│                    TRIGGER                          │
│         (Monthly Expense Package Arrival)           │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              EXPENSE PROCESSOR                      │
│         (Excel / Spreadsheet Parsing)               │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              RECEIPT PROCESSOR                       │
│         (Receipt Data Extraction)                   │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              RECONCILER                             │
│         (Expense ↔ Receipt Matching)                │
└──────────┬────────────────────┬─────────────────────┘
           │                    │
     ┌─────▼─────┐        ┌────▼─────┐
     │  MATCHED  │        │ EXCEPTION│
     └─────┬─────┘        └────┬─────┘
           │                    │
           ▼                    ▼
┌──────────────────┐  ┌──────────────────┐
│  CATEGORIZER     │  │  HUMAN REVIEW    │
│  (Rules + ML)    │  │  (Approve/Reject)│
└────────┬─────────┘  └────────┬─────────┘
         │                     │
         ▼                     ▼
┌─────────────────────────────────────────────────────┐
│              ANOMALY DETECTOR                       │
│         (Statistical + Rules)                       │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│           SIMULATED ACCOUNTING SYSTEM               │
│         (Ledger Entries)                            │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              P&L GENERATOR                          │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│         LLM CLIENT SUMMARY (NLG Only)              │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              FINAL OUTPUT                           │
│    (P&L + Reconciliation + Anomalies + Summary)     │
└─────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | Type |
|-----------|---------------|------|
| Trigger | Simulate monthly expense package arrival | Tool |
| Expense Processor | Parse Excel, extract structured records | Tool |
| Receipt Processor | Extract receipt data (synthetic/OCR) | Tool |
| Reconciler | Match expenses against receipts | Rules |
| Categorizer | Assign expense categories | Rules + ML |
| Anomaly Detector | Identify unusual expenses | Rules + ML |
| Human Review | Approve/reject/correct anomalies | Human |
| Accounting System | Maintain ledger entries | Tool |
| P&L Generator | Aggregate monthly P&L | Rules |
| Client Summary | Generate natural-language summary | LLM |
| Audit Logger | Record all workflow events | Tool |

## Data Flow

1. Trigger creates a `WorkflowRun` with input data
2. Expense Processor extracts `ExpenseRecord` list
3. Receipt Processor extracts `ReceiptRecord` list
4. Reconciler produces `ReconciliationResult` for each expense
5. Categorizer assigns categories to matched expenses
6. Anomaly Detector flags unusual expenses
7. Flagged items enter Human Review queue
8. Approved/reviewed expenses post to Ledger
9. P&L Generator creates monthly `PLReport`
10. LLM generates client-facing summary
11. Final output compiled from all components
