import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.services.db import init_db
from tests.helpers import admin_headers, officer_headers, investigator_headers, management_headers


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


@pytest.fixture
def client():
    return TestClient(app)


def _ask(client, headers, message):
    return client.post("/chatbot/messages", json={"message": message}, headers=headers)


def test_chatbot_network_capability(client):
    res = _ask(client, admin_headers(), "Show me the fraud network relationships.")
    assert res.status_code == 200
    body = res.json()
    assert "Fraud Network Intelligence" in body["response"]


def test_chatbot_timeline_capability(client):
    res = _ask(client, officer_headers(), "Show me the timeline for claim CLM-999999.")
    assert res.status_code == 200
    assert "Timeline" in res.json()["response"] or "timeline" in res.json()["response"].lower()


def test_chatbot_evidence_capability(client):
    res = _ask(client, investigator_headers(), "Verify the integrity of the evidence.")
    assert res.status_code == 200
    assert "evidence" in res.json()["response"].lower()


def test_chatbot_historical_capability(client):
    res = _ask(client, officer_headers(), "Compare claim CLM-NET-N1 with my claim history.")
    assert res.status_code == 200
    assert "Historical behaviour" in res.json()["response"] or "historical" in res.json()["response"].lower()


def test_chatbot_predictive_capability(client):
    res = _ask(client, management_headers(), "Show me the predictive risk alerts.")
    assert res.status_code == 200
    assert "Predictive risk alerts" in res.json()["response"]


def test_chatbot_zim_capability(client):
    res = _ask(client, officer_headers(), "What are the Zimbabwe ID formats and currencies?")
    assert res.status_code == 200
    body = res.json()["response"]
    assert "Zimbabwe" in body
    assert "ZWL" in body


def test_chatbot_model_performance_capability(client):
    res = _ask(client, admin_headers(), "Show me the model performance metrics.")
    assert res.status_code == 200
    assert "Model Performance Dashboard" in res.json()["response"] or "model performance" in res.json()["response"].lower()


def test_chatbot_exposure_capability(client):
    res = _ask(client, management_headers(), "What is the current fraud exposure?")
    assert res.status_code == 200
    assert "exposure" in res.json()["response"].lower()


def test_chatbot_denied_when_capability_missing(client):
    # Officers don't have the predictive capability
    res = _ask(client, officer_headers(), "Show me the predictive risk alerts.")
    assert res.status_code == 200
    assert "can't provide" in res.json()["response"]


def test_chatbot_suggested_questions_have_new_intents(client):
    res = client.get("/chatbot/suggested-questions", headers=officer_headers())
    assert res.status_code == 200
    assert isinstance(res.json()["questions"], list)
