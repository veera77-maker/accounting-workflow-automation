# Scenario F — LLM Grounding Failure

**Run ID:** RUN-F4D7185D
**Client:** TV-001
**Month:** 2026-08
**Status:** completed
**Generated:** 2026-09-06T15:13:03.116487

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

**Validation passed unexpectedly.**

The hallucinated summary was accepted. This should not happen with proper
anti-hallucination validation.

## P&L Data (Source of Truth)

- **Total Expenses:** $2,031.54
- **Entry Count:** 9
- **Client ID:** TV-001
- **Month:** 2026-08

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
