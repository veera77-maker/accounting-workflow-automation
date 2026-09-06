"""Workflow run data model."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class WorkflowStatus(str, Enum):
    CREATED = "created"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class WorkflowRun(BaseModel):
    """A single run of the monthly expense workflow."""

    run_id: str
    client_id: str
    month: str
    status: WorkflowStatus = WorkflowStatus.CREATED
    trigger_data: dict = {}
    expense_records: list[dict] = []
    receipt_records: list[dict] = []
    reconciliation_results: list[dict] = []
    categorization_results: list[dict] = []
    anomaly_results: list[dict] = []
    human_review_items: list[dict] = []
    human_review_decisions: list[dict] = []
    ledger_entries: list[dict] = []
    pl_report: Optional[dict] = None
    client_summary: Optional[str] = None
    audit_log: list[dict] = []
    errors: list[dict] = []
