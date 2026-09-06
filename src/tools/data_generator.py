"""Synthetic data generator for testing.

Creates Excel expense spreadsheets and JSON receipt files
that simulate monthly client submissions.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook


DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "synthetic"


def _load_json(filename: str) -> list[dict]:
    with open(DATA_DIR / filename) as f:
        return json.load(f)


EXPENSE_ROWS_TV001_AUG2026: list[dict] = [
    {"employee": "Alice Johnson", "date": "2026-08-03", "description": "Flight to NYC for client meeting",
     "vendor": "Delta Airlines", "amount": 487.00, "category": "Travel", "receipt_ref": "RCP-001"},
    {"employee": "Alice Johnson", "date": "2026-08-03", "description": "Hotel stay - NYC 2 nights",
     "vendor": "Hilton Hotels", "amount": 420.00, "category": "Travel", "receipt_ref": "RCP-002"},
    {"employee": "Alice Johnson", "date": "2026-08-03", "description": "Uber to/from airport",
     "vendor": "Uber Technologies", "amount": 67.50, "category": "Travel", "receipt_ref": "RCP-003"},
    {"employee": "Bob Williams", "date": "2026-08-07", "description": "Client dinner - Pinnacle pitch",
     "vendor": "The Capital Grille", "amount": 312.00, "category": "Meals & Entertainment", "receipt_ref": "RCP-004"},
    {"employee": "Bob Williams", "date": "2026-08-12", "description": "Team lunch",
     "vendor": "Chipotle Mexican Grill", "amount": 24.50, "category": "Meals & Entertainment", "receipt_ref": "RCP-005"},
    {"employee": "Alice Johnson", "date": "2026-08-14", "description": "Office coffee run",
     "vendor": "Starbucks", "amount": 18.75, "category": "Meals & Entertainment", "receipt_ref": "RCP-006"},
    {"employee": "Bob Williams", "date": "2026-08-18", "description": "Microsoft 365 annual license",
     "vendor": "Microsoft Corporation", "amount": 299.99, "category": "Software", "receipt_ref": "RCP-007"},
    {"employee": "Alice Johnson", "date": "2026-08-20", "description": "Printer paper and toner",
     "vendor": "Staples", "amount": 87.30, "category": "Office Supplies", "receipt_ref": "RCP-008"},
    {"employee": "Bob Williams", "date": "2026-08-22", "description": "Salesforce CRM monthly",
     "vendor": "Salesforce", "amount": 150.00, "category": "Software", "receipt_ref": "RCP-009"},
    {"employee": "Alice Johnson", "date": "2026-08-25", "description": "Internet service - August",
     "vendor": "Comcast Business", "amount": 189.00, "category": "Utilities", "receipt_ref": "RCP-010"},
    # Anomaly: unusually high meal expense
    {"employee": "Bob Williams", "date": "2026-08-27", "description": "Executive client entertainment event",
     "vendor": "The Capital Grille", "amount": 2850.00, "category": "Meals & Entertainment", "receipt_ref": "RCP-011"},
    # Vendor mismatch: expense says Amazon Business, receipt is Office Depot
    {"employee": "Alice Johnson", "date": "2026-08-28", "description": "Office supplies - emergency order",
     "vendor": "Amazon Business", "amount": 145.60, "category": "Office Supplies", "receipt_ref": "RCP-013"},
    # Duplicate expense (same amount, same vendor, same day as another)
    {"employee": "Bob Williams", "date": "2026-08-12", "description": "Team lunch - second order",
     "vendor": "Chipotle Mexican Grill", "amount": 24.50, "category": "Meals & Entertainment", "receipt_ref": "RCP-012"},
]

RECEIPT_DATA_TV001_AUG2026: list[dict] = [
    {"receipt_id": "RCP-001", "vendor": "Delta Airlines", "amount": 487.00, "date": "2026-08-03",
     "line_items": [{"description": "Flight JFK-LAX round trip", "amount": 487.00, "quantity": 1}]},
    {"receipt_id": "RCP-002", "vendor": "Hilton Hotels", "amount": 420.00, "date": "2026-08-03",
     "line_items": [{"description": "Standard room - 2 nights", "amount": 210.00, "quantity": 2}]},
    {"receipt_id": "RCP-003", "vendor": "Uber Technologies", "amount": 67.50, "date": "2026-08-03",
     "line_items": [{"description": "Airport transfer", "amount": 67.50, "quantity": 1}]},
    {"receipt_id": "RCP-004", "vendor": "The Capital Grille", "amount": 312.00, "date": "2026-08-07",
     "line_items": [
         {"description": "Ribeye steak", "amount": 89.00, "quantity": 2},
         {"description": "Wine bottle", "amount": 65.00, "quantity": 1},
         {"description": "Side dishes", "amount": 34.00, "quantity": 2},
         {"description": "Tax and tip", "amount": 40.00, "quantity": 1},
     ]},
    {"receipt_id": "RCP-005", "vendor": "Chipotle Mexican Grill", "amount": 24.50, "date": "2026-08-12",
     "line_items": [{"description": "Burrito bowls x3", "amount": 24.50, "quantity": 3}]},
    {"receipt_id": "RCP-006", "vendor": "Starbucks", "amount": 18.75, "date": "2026-08-14",
     "line_items": [{"description": "Coffee and pastries", "amount": 18.75, "quantity": 1}]},
    {"receipt_id": "RCP-007", "vendor": "Microsoft Corporation", "amount": 299.99, "date": "2026-08-18",
     "line_items": [{"description": "Microsoft 365 Business - annual", "amount": 299.99, "quantity": 1}]},
    {"receipt_id": "RCP-008", "vendor": "Staples", "amount": 87.30, "date": "2026-08-20",
     "line_items": [
         {"description": "Copy paper ream", "amount": 42.30, "quantity": 1},
         {"description": "Toner cartridge", "amount": 45.00, "quantity": 1},
     ]},
    {"receipt_id": "RCP-009", "vendor": "Salesforce", "amount": 150.00, "date": "2026-08-22",
     "line_items": [{"description": "Salesforce CRM - monthly subscription", "amount": 150.00, "quantity": 1}]},
    {"receipt_id": "RCP-010", "vendor": "Comcast Business", "amount": 189.00, "date": "2026-08-25",
     "line_items": [{"description": "Business internet - August", "amount": 189.00, "quantity": 1}]},
    # Amount mismatch: receipt shows 2650.00 but expense says 2850.00
    {"receipt_id": "RCP-011", "vendor": "The Capital Grille", "amount": 2650.00, "date": "2026-08-27",
     "line_items": [
         {"description": "Private dining room", "amount": 500.00, "quantity": 1},
         {"description": "Multi-course dinner x8", "amount": 180.00, "quantity": 8},
         {"description": "Wine selection", "amount": 350.00, "quantity": 1},
         {"description": "Tax and gratuity", "amount": 250.00, "quantity": 1},
     ]},
    # Receipt for the duplicate expense
    {"receipt_id": "RCP-012", "vendor": "Chipotle Mexican Grill", "amount": 24.50, "date": "2026-08-12",
     "line_items": [{"description": "Burrito bowls x3", "amount": 24.50, "quantity": 3}]},
    # Vendor mismatch: receipt is Office Depot but expense says Amazon Business
    {"receipt_id": "RCP-013", "vendor": "Office Depot", "amount": 145.60, "date": "2026-08-28",
     "line_items": [
         {"description": "Printer paper", "amount": 65.60, "quantity": 1},
         {"description": "Toner cartridge", "amount": 80.00, "quantity": 1},
     ]},
]


def generate_expense_excel(client_id: str, month: str, output_path: Path) -> Path:
    """Create an Excel file simulating a client's monthly expense submission."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Expenses"

    headers = ["Employee", "Date", "Description", "Vendor", "Amount", "Category", "Receipt Ref"]
    ws.append(headers)

    rows = [r for r in EXPENSE_ROWS_TV001_AUG2026]
    for row in rows:
        ws.append([
            row["employee"],
            row["date"],
            row["description"],
            row["vendor"],
            row["amount"],
            row["category"],
            row.get("receipt_ref", ""),
        ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(output_path))
    return output_path


def generate_receipt_json(client_id: str, month: str, output_path: Path) -> Path:
    """Create a JSON file with receipt data for the given client/month."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(RECEIPT_DATA_TV001_AUG2026, f, indent=2)
    return output_path
