"""Pytest fixtures.

The environment is pointed at a temporary SQLite file *before* the application
modules are imported, so tests never touch a development database and never
call a live API.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_TMP_DIR = tempfile.mkdtemp(prefix="b2b_lead_engine_tests_")
os.environ["DATABASE_URL"] = "sqlite:///" + (pathlib.Path(_TMP_DIR) / "test.db").as_posix()
os.environ["DRY_RUN"] = "true"
os.environ["FRONTEND_ORIGIN"] = "http://127.0.0.1:5173"
# Ensure fixture mode: no live API keys - set to empty strings so they won't be loaded from .env
os.environ["TAVILY_API_KEY"] = ""
os.environ["EXA_API_KEY"] = ""
os.environ["GNEWS_API_KEY"] = ""
os.environ["BRAVE_API_KEY"] = ""
os.environ["OPENCORPORATES_API_KEY"] = ""
os.environ["GROQ_API_KEY"] = ""

from app import models  # noqa: E402
from app.db import Base, engine, init_db  # noqa: E402

init_db()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_tables():
    """Start every test from empty tables."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def campaign(client) -> dict:
    """A campaign with explicit, testable target settings."""
    response = client.post(
        "/api/campaigns",
        json={
            "name": "US B2B software — M1 test campaign",
            "settings": {
                "countries": ["United States"],
                "sectors": ["software", "it services", "data"],
                "employee_min": 20,
                "employee_max": 200,
                "target_titles": ["Founder", "CEO"],
                "exclusions": [],
                "require_domain": True,
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def make_company_payload(**overrides) -> dict:
    payload = {
        "canonical_name": "Acme Analytics Co",
        "website_domain": "https://acme-analytics.example.com/about",
        "country": "United States",
        "sector": "software",
        "employee_min": 25,
        "employee_max": 60,
    }
    payload.update(overrides)
    return payload
