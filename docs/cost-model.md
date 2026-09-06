# Cost Model — A.05.1 Workflow Automation Agent

This document provides a cost model for the A.05.1 workflow. All figures are clearly marked as actual measurements or estimates.

---

## Actual Measurements

### Workflow Execution Cost (Compute)

| Stage | Mean Latency (ms) | Cost Basis |
|-------|-------------------|------------|
| Expense Processing | 3.564 | Local CPU |
| Receipt Processing | 0.297 | Local CPU |
| Parallel Stage (combined) | 6.095 | Local CPU |
| Reconciliation | 0.158 | Local CPU |
| Categorization | 0.169 | Local CPU |
| Anomaly Detection | 0.175 | Local CPU |
| Ledger Posting | 0.114 | Local CPU |
| P&L Generation | 0.062 | Local CPU |
| Client Summary | 0.182 | Local CPU |
| **Total** | **10.822** | **Local CPU** |

**Measurement Method:** 10 runs using `time.perf_counter()`, averaged.

**Note:** These measurements use `FakeLLMClient` (no external API calls). Real LLM latency would be significantly higher.

---

## LLM Cost

### Actual Prototype Cost

| Aspect | Value |
|--------|-------|
| LLM Provider | FakeLLMClient (no real API) |
| Actual LLM Cost | $0.00 |
| Token Count | Not measured (no real API) |
| API Calls | 1 per workflow run |

Production LLM cost was not measured because the prototype uses FakeLLMClient and makes no external API calls. Production cost would depend on provider, model, input/output token volume, and current pricing.

---

## Total Cost Summary

### Prototype (Current)

| Component | Cost |
|-----------|------|
| Compute | Local CPU (negligible) |
| LLM | $0.00 (FakeLLMClient) |
| Storage | Local filesystem (negligible) |
| **Total** | **~$0.00 per run** |

---

## What Was NOT Measured

| Item | Reason |
|------|--------|
| Real LLM API cost | No external provider was called |
| Real LLM latency | FakeLLMClient used for determinism |
| Cloud compute cost | Prototype runs locally |
| Storage cost | In-memory + local filesystem |

---

*Generated: 2026-09-06*
*Phase: 8 — Evidence*
