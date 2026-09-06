# Scenario B — Reconciliation Mismatch

**Run ID:** RUN-E5FA791B
**Client:** TV-001
**Month:** 2026-08
**Status:** completed
**Generated:** 2026-09-06T15:13:03.079398

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
## Reconciliation Mismatch Details

### Expense EXP-0012

- **Status:** amount_mismatch
- **Reason:** Amount mismatch: expense $2850.00 vs receipt $2650.00 (difference: $200.00)
- **Evidence:** {
  "vendor_match": true,
  "vendor_method": "exact",
  "amount_match": false,
  "date_match": true,
  "expense_vendor": "The Capital Grille",
  "receipt_vendor": "The Capital Grille",
  "expense_amount": 2850.0,
  "receipt_amount": 2650.0,
  "expense_date": "2026-08-27",
  "receipt_date": "2026-08-27"
}

### Expense EXP-0013

- **Status:** vendor_mismatch
- **Reason:** Vendor mismatch: expense 'Amazon Business' vs receipt 'Office Depot'
- **Evidence:** {
  "vendor_match": false,
  "vendor_method": "similarity(0.22)",
  "amount_match": true,
  "date_match": true,
  "expense_vendor": "Amazon Business",
  "receipt_vendor": "Office Depot",
  "expense_amount": 145.6,
  "receipt_amount": 145.6,
  "expense_date": "2026-08-28",
  "receipt_date": "2026-08-28"
}
