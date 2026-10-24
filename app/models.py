from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


Status = Literal["supported", "needs-review", "blocked", "resolved"]


class DecisionApproval(BaseModel):
    decision_id: Literal["budget-variance", "story-consent", "period-check"]
    resolution: str = Field(min_length=1, max_length=500)

    @field_validator("resolution")
    @classmethod
    def require_resolution(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A resolution note is required.")
        return value


class Claim(BaseModel):
    id: str
    requirement_id: str
    label: str
    value: str
    status: Status
    source: str
    detail: str
    confidence: str
    approved: bool = False


class Decision(BaseModel):
    id: str
    label: str
    question: str
    why: str
    evidence: str
    resolved: bool = False
    resolution: str | None = None


class CaseSummary(BaseModel):
    award_id: str
    title: str
    funder: str
    period: str
    amount: int
    requirements: int
    claims: int
    supported: int
    needs_review: int
    blocked: int


class RunResult(BaseModel):
    run_id: str
    provider: str
    agent: str
    agent_mode: Literal["local", "live"] = "local"
    agent_note: str | None = None
    state: Literal["ready", "running", "complete"]
    summary: CaseSummary
    claims: list[Claim]
    decisions: list[Decision]
    report_markdown: str
    evidence_index: list[dict[str, str]]
    warnings: list[str]
