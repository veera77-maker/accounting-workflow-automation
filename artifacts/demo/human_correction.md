# Scenario D — Human Correction

**Run ID:** RUN-C25A16B6
**Client:** TV-001
**Month:** 2026-08
**Status:** completed
**Generated:** 2026-09-06T15:13:03.097126

## Stage Results

- **Expense Records:** 13
- **Receipt Records:** 13
- **Reconciliation Results:** 13
- **Categorization Results:** 13
- **Anomaly Results:** 13
- **Human Review Items:** 4
- **Human Review Decisions:** 1
- **Ledger Entries:** 10

## Anomaly Verdicts

- **NORMAL:** 9
- **REVIEW:** 4

## Reconciliation Statuses

- **amount_mismatch:** 1
- **exact_match:** 11
- **vendor_mismatch:** 1

## Ledger Entries

| Entry ID | Expense ID | Category | Amount | Source | Status |
|----------|------------|----------|--------|--------|--------|
| LED-000001 | EXP-0002 | Travel | $487.00 | auto | posted |
| LED-000002 | EXP-0003 | Travel | $420.00 | auto | posted |
| LED-000003 | EXP-0004 | Travel | $67.50 | auto | posted |
| LED-000004 | EXP-0005 | Meals & Entertainment | $312.00 | auto | posted |
| LED-000005 | EXP-0007 | Meals & Entertainment | $18.75 | auto | posted |
| LED-000006 | EXP-0008 | Software | $299.99 | auto | posted |
| LED-000007 | EXP-0009 | Office Supplies | $87.30 | auto | posted |
| LED-000008 | EXP-0010 | Software | $150.00 | auto | posted |
| LED-000009 | EXP-0011 | Utilities | $189.00 | auto | posted |
| LED-000010 | EXP-0006 | Meals & Entertainment | $150.00 | human_review | human_reviewed |

## P&L Report

- **Total Expenses:** $2,181.54
- **Entry Count:** 10

| Category | Total | Count |
|----------|-------|-------|
| Meals & Entertainment | $480.75 | 3 |
| Office Supplies | $87.30 | 1 |
| Software | $449.99 | 2 |
| Travel | $974.50 | 3 |
| Utilities | $189.00 | 1 |

## Client Summary

```
Monthly Expense Summary for TV-001
Reporting Period: August 2026

Total Expenses: $2,181.54
Total Accounting Entries: 10

Expense Breakdown by Category:
- Meals & Entertainment: $480.75 (3 entries)
- Office Supplies: $87.30 (1 entries)
- Software: $449.99 (2 entries)
- Travel: $974.50 (3 entries)
- Utilities: $189.00 (1 entries)
```

## Correction Details

- **Review ID:** REV-D6DB70DE
- **Expense ID:** EXP-0006
- **Reviewer:** demo-reviewer
- **Decision:** correct
- **Reason:** Amount was reported incorrectly; actual amount is $150.00
- **Corrected Amount:** $150.00

The corrected expense was posted to the ledger with source="human_review" and status=HUMAN_REVIEWED.
