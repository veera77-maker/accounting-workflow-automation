# Scenario C — Anomaly Detection

**Run ID:** RUN-442AB459
**Client:** TV-001
**Month:** 2026-08
**Status:** completed
**Generated:** 2026-09-06T15:13:03.087983

## Stage Results

- **Expense Records:** 13
- **Receipt Records:** 13
- **Reconciliation Results:** 13
- **Categorization Results:** 13
- **Anomaly Results:** 13
- **Human Review Items:** 4
- **Human Review Decisions:** 0
- **Ledger Entries:** 9

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
## Anomaly Details

### Expense EXP-0006

- **Verdict:** review
- **Reasons:** duplicate_or_similar_expense
- **Explanation:** Expense matches 1 other expense(s) with same vendor ('Chipotle Mexican Grill'), same amount ($24.50), and same date (2026-08-12). Matching expense IDs: EXP-0014

### Expense EXP-0012

- **Verdict:** review
- **Reasons:** high_value_for_category, high_value_for_category
- **Explanation:** Expense amount $2850.00 exceeds 3.0x the category mean of $645.95 for 'Meals & Entertainment' (threshold: $1937.85) | Reconciliation amount mismatch: expense $2850.00 vs receipt $2650.00 (difference: $200.00). Amount mismatch: expense $2850.00 vs receipt $2650.00 (difference: $200.00)

### Expense EXP-0013

- **Verdict:** review
- **Reasons:** new_or_infrequent_vendor
- **Explanation:** Reconciliation vendor mismatch: expense vendor 'Amazon Business' vs receipt vendor 'Office Depot'. Vendor mismatch: expense 'Amazon Business' vs receipt 'Office Depot'

### Expense EXP-0014

- **Verdict:** review
- **Reasons:** duplicate_or_similar_expense
- **Explanation:** Expense matches 1 other expense(s) with same vendor ('Chipotle Mexican Grill'), same amount ($24.50), and same date (2026-08-12). Matching expense IDs: EXP-0006
