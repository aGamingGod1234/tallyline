from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .models import DecisionApproval
from .agent import invoke_live_agent, provider_label
from .service import export_markdown, run_case


app = FastAPI(title="Tallyline", version="0.1.0")
STATIC = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")

_approved: dict[str, str] = {}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "product": "tallyline"}


@app.get("/api/case")
def get_case():
    return run_case(_approved.copy())


@app.post("/api/run")
def run():
    approved = _approved.copy()
    result = run_case(approved)
    if os.getenv("TALLYLINE_AGENT_MODE", "local").lower() != "live":
        return result
    try:
        result.agent_note = invoke_live_agent(result.summary.award_id, approved)
        result.agent_mode = "live"
        result.provider = provider_label()
        return result
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Live Strands run unavailable: {error}") from error


@app.post("/api/decisions/approve")
def approve(decision: DecisionApproval):
    _approved[decision.decision_id] = decision.resolution
    return run_case(_approved.copy())


@app.post("/api/reset")
def reset():
    _approved.clear()
    return run_case()


@app.get("/api/export", response_class=PlainTextResponse)
def export():
    return PlainTextResponse(
        export_markdown(run_case(_approved.copy())),
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=tallyline-closeout.md"},
    )
