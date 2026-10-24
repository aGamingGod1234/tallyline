import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TALLYLINE_AGENT_MODE", "local")
    with TestClient(app) as client:
        client.post("/api/reset")
        yield client
        client.post("/api/reset")


def test_approve_export_and_reset_through_api(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.post("/api/run").json()["claims"][0]["value"] == "128 households"
    note = "Return the unspent balance to the funder."

    response = client.post("/api/decisions/approve", json={
        "decision_id": "budget-variance", "resolution": note,
    })

    assert response.status_code == 200
    assert response.json()["decisions"][0]["resolution"] == note
    assert not response.json()["decisions"][1]["resolved"]
    exported = client.get("/api/export")
    assert exported.headers["content-type"].startswith("text/markdown")
    assert "tallyline-closeout.md" in exported.headers["content-disposition"]
    assert note in exported.text
    assert "**Open human decisions:** 2" in exported.text

    assert client.post("/api/reset").status_code == 200
    assert note not in client.get("/api/export").text
    assert all(not decision["resolved"] for decision in client.get("/api/case").json()["decisions"])


@pytest.mark.parametrize("decision_id,resolution", [
    ("unknown-decision", "A note"),
    ("budget-variance", "   \n\t"),
    ("budget-variance", ""),
    ("budget-variance", "x" * 501),
])
def test_invalid_approval_does_not_change_the_case(client, decision_id, resolution):
    before = client.get("/api/case").json()

    response = client.post("/api/decisions/approve", json={
        "decision_id": decision_id, "resolution": resolution,
    })

    assert response.status_code == 422
    assert client.get("/api/case").json() == before


def test_application_import_and_assets_work_outside_repository(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    code = """
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    assert 'Tallyline' in client.get('/').text
    for path in ['/static/app.js', '/static/styles.css', '/api/case']:
        assert client.get(path).status_code == 200, path
"""
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(repo)},
        check=True,
        capture_output=True,
        text=True,
    )
