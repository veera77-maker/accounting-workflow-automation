"""Shared test fixtures for A.05.1 tests."""

import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "synthetic"


@pytest.fixture
def clients():
    """Load synthetic client data."""
    with open(DATA_DIR / "clients.json") as f:
        return json.load(f)


@pytest.fixture
def employees():
    """Load synthetic employee data."""
    with open(DATA_DIR / "employees.json") as f:
        return json.load(f)


@pytest.fixture
def vendors():
    """Load synthetic vendor data."""
    with open(DATA_DIR / "vendors.json") as f:
        return json.load(f)
