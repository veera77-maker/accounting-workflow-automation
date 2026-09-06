"""Monthly expense trigger — simulates client submitting expense package.

Trigger
    ↓
Decisions
    ↓
Actions
    ↓
Output

This component is the TRIGGER in the A.05.1 template.
It creates a WorkflowRun and populates it with the input artifacts
that a real client would send: expense spreadsheet + receipt data.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from models.workflow import WorkflowRun, WorkflowStatus
from tools.data_generator import generate_expense_excel, generate_receipt_json


DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "synthetic"


def _load_clients() -> list[dict]:
    with open(DATA_DIR / "clients.json") as f:
        return json.load(f)


def trigger_monthly_expense(
    client_id: str,
    month: str,
    output_dir: Path | None = None,
) -> WorkflowRun:
    """Simulate a client sending their monthly expense package.

    Args:
        client_id: Fictional client identifier (e.g. "TV-001").
        month: Reporting month in YYYY-MM format (e.g. "2026-08").
        output_dir: Where to write generated files. Defaults to data/outputs/.

    Returns:
        WorkflowRun populated with trigger data and file paths.
    """
    clients = _load_clients()
    client = next((c for c in clients if c["client_id"] == client_id), None)
    if client is None:
        raise ValueError(f"Unknown client_id: {client_id}")

    if output_dir is None:
        output_dir = DATA_DIR.parent / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
    excel_path = output_dir / f"{client_id}_{month}_expenses.xlsx"
    receipt_path = output_dir / f"{client_id}_{month}_receipts.json"

    generate_expense_excel(client_id, month, excel_path)
    generate_receipt_json(client_id, month, receipt_path)

    run = WorkflowRun(
        run_id=run_id,
        client_id=client_id,
        month=month,
        status=WorkflowStatus.CREATED,
        trigger_data={
            "client_name": client["name"],
            "contact": client["contact"],
            "industry": client["industry"],
            "expense_file": str(excel_path),
            "receipt_file": str(receipt_path),
        },
    )

    return run
