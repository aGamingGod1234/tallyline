import json

import pytest
from fastapi.testclient import TestClient

from app import agent as agent_module
from app import main
from app.agent import provider_label
from app.main import app


def test_provider_label_distinguishes_offline_and_live_paths(monkeypatch):
    monkeypatch.delenv("TALLYLINE_AGENT_MODE", raising=False)
    monkeypatch.delenv("TALLYLINE_MODEL_PROVIDER", raising=False)
    assert provider_label() == "Strands • offline evidence pass"

    monkeypatch.setenv("TALLYLINE_AGENT_MODE", "live")
    monkeypatch.setenv("TALLYLINE_MODEL_PROVIDER", "gemini")
    assert provider_label() == "Strands • live gemini"


def test_live_route_fails_closed_without_provider_credentials(monkeypatch):
    monkeypatch.setenv("TALLYLINE_AGENT_MODE", "live")
    monkeypatch.setenv("TALLYLINE_MODEL_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    response = TestClient(app).post("/api/run")

    assert response.status_code == 503
    assert "Gemini live mode needs" in response.json()["detail"]


def test_real_strands_tools_use_isolated_human_approval_snapshots():
    assert agent_module.STRANDS_AVAILABLE
    note = "Return the unspent balance to the funder."
    approvals = {"budget-variance": note}
    reconcile, draft = agent_module._evidence_tools(approvals)
    approvals.clear()

    ledger = json.loads(reconcile("GN-26-014"))
    assert ledger["decisions"][0]["resolution"] == note
    assert ledger["claims"][3]["status"] == "resolved"
    assert ledger["claims"][4]["status"] == "blocked"
    assert note in draft("GN-26-014")
    assert "**Open human decisions:** 2" in draft("GN-26-014")

    fresh_reconcile, fresh_draft = agent_module._evidence_tools()
    assert not json.loads(fresh_reconcile("GN-26-014"))["decisions"][0]["resolved"]
    assert note not in fresh_draft("GN-26-014")
    assert json.loads(reconcile("unknown"))["error"] == "unknown case"
    assert draft("unknown") == "Unknown case; no draft produced."
    for bounded_tool in (reconcile, draft):
        assert set(bounded_tool.tool_spec["inputSchema"]["json"]["properties"]) == {"case_id"}
    with pytest.raises(TypeError):
        draft("GN-26-014", approved_decisions="Invented approval")


def test_agent_construction_binds_approvals_without_a_provider_call(monkeypatch):
    captured = {}

    def fake_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(agent_module, "Agent", fake_agent)
    monkeypatch.setattr(agent_module, "_configured_model", lambda: None)
    agent_module.build_strands_agent({"period-check": "Coverage confirmed."})

    reconcile, draft = captured["tools"]
    assert json.loads(reconcile("GN-26-014"))["decisions"][2]["resolved"]
    assert "Coverage confirmed." in draft("GN-26-014")


def test_live_invocation_rejects_empty_model_readout(monkeypatch):
    monkeypatch.setattr(agent_module, "build_strands_agent", lambda approvals: lambda prompt: " \n")

    with pytest.raises(RuntimeError, match="empty readout"):
        agent_module.invoke_live_agent("GN-26-014")


def test_gemini_defaults_and_model_override_without_a_provider_call(monkeypatch):
    from strands.models import gemini

    monkeypatch.setenv("TALLYLINE_MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    monkeypatch.delenv("TALLYLINE_MODEL_ID", raising=False)
    monkeypatch.setattr(gemini, "GeminiModel", lambda **kwargs: kwargs)

    configured = agent_module._configured_model()
    assert configured["model_id"] == "gemini-3.8-flash"
    assert configured["params"]["temperature"] == 1.0

    monkeypatch.setenv("TALLYLINE_MODEL_ID", "gemini-2.5-flash")
    assert agent_module._configured_model()["model_id"] == "gemini-2.5-flash"


def test_live_route_uses_same_snapshot_as_ledger_when_state_changes(monkeypatch):
    monkeypatch.setenv("TALLYLINE_AGENT_MODE", "live")
    monkeypatch.setenv("TALLYLINE_MODEL_PROVIDER", "gemini")
    monkeypatch.setattr(main, "_approved", {"budget-variance": "Return the balance."})

    def fake_live_call(case_id, approvals):
        main._approved.clear()
        assert case_id == "GN-26-014"
        assert approvals == {"budget-variance": "Return the balance."}
        return "The balance has a recorded human resolution."

    monkeypatch.setattr(main, "invoke_live_agent", fake_live_call)
    response = TestClient(app).post("/api/run")

    assert response.status_code == 200
    result = response.json()
    assert result["agent_mode"] == "live"
    assert result["provider"] == "Strands • live gemini"
    assert result["decisions"][0]["resolution"] == "Return the balance."
    assert result["agent_note"] == "The balance has a recorded human resolution."
