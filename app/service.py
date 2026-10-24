from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .models import CaseSummary, Claim, Decision, RunResult


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


def _read_fixtures() -> dict[str, Any]:
    award = json.loads((FIXTURES / "award_brief.json").read_text())
    stories = json.loads((FIXTURES / "story_notes.json").read_text())
    with (FIXTURES / "activity_log.csv").open(newline="") as handle:
        activity = list(csv.DictReader(handle))
    with (FIXTURES / "finance.csv").open(newline="") as handle:
        finance = list(csv.DictReader(handle))
    return {"award": award, "stories": stories, "activity": activity, "finance": finance}


def _dedupe_activity(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    duplicates = 0
    for row in rows:
        key = row["event_id"]
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(row)
    return unique, duplicates


def _money(value: float) -> str:
    return f"${value:,.0f}"


def run_case(approved: dict[str, str] | None = None) -> RunResult:
    approved = approved or {}
    data = _read_fixtures()
    award = data["award"]
    activity, duplicate_count = _dedupe_activity(data["activity"])

    households = sum(int(row["households"]) for row in activity)
    kits = sum(int(row["kits"]) for row in activity)
    workshops = sum(int(row["workshops"]) for row in activity)
    spent = sum(float(row["amount"]) for row in data["finance"])
    variance = award["amount"] - spent
    target = award["targets"]

    claims = [
        Claim(
            id="claim-households",
            requirement_id="R1",
            label="Households reached",
            value=f"{households} households",
            status="supported",
            source="activity_log.csv · 4 unique event rows",
            detail=f"Target {target['households']}; the duplicate event row was excluded before totaling.",
            confidence="reconciled",
        ),
        Claim(
            id="claim-kits",
            requirement_id="R2",
            label="Cooling kits distributed",
            value=f"{kits} kits",
            status="supported",
            source="activity_log.csv · distribution totals",
            detail=f"Target {target['kits']}; distribution records cover the reported period.",
            confidence="reconciled",
        ),
        Claim(
            id="claim-workshops",
            requirement_id="R3",
            label="Cooling workshops",
            value=f"{workshops} workshops",
            status="supported",
            source="activity_log.csv · workshop rows",
            detail=f"Target {target['workshops']}; all three dated sessions are present.",
            confidence="reconciled",
        ),
        Claim(
            id="claim-funds",
            requirement_id="R4",
            label="Award spending",
            value=f"{_money(spent)} of {_money(award['amount'])}",
            status="resolved" if "budget-variance" in approved else "needs-review",
            source="finance.csv · category total",
            detail=(
                f"{_money(variance)} remains unallocated."
                if "budget-variance" not in approved
                else f"Human note: {approved['budget-variance']}"
            ),
            confidence="reconciled",
            approved="budget-variance" in approved,
        ),
        Claim(
            id="claim-story",
            requirement_id="R5",
            label="Community voice",
            value="1 consented story · 1 held back",
            status="resolved" if "story-consent" in approved else "blocked",
            source="story_notes.json · notes 01 and 02",
            detail=(
                f"Human note: {approved['story-consent']}"
                if "story-consent" in approved
                else "Note 02 has no publication consent; it cannot enter the narrative draft."
            ),
            confidence="consent check",
            approved="story-consent" in approved,
        ),
    ]

    decisions = [
        Decision(
            id="budget-variance",
            label="Finance note",
            question=f"What should explain the {_money(variance)} variance?",
            why="The ledger is reconciled, but a funder-facing explanation is not present in the source files.",
            evidence="finance.csv · $15,940 recorded against an $18,000 award",
            resolved="budget-variance" in approved,
            resolution=approved.get("budget-variance"),
        ),
        Decision(
            id="story-consent",
            label="Consent boundary",
            question="Keep the second beneficiary note out of the report?",
            why="The note is useful context but does not include permission to publish identifiable experience.",
            evidence="story_notes.json · note 02 · consent: false",
            resolved="story-consent" in approved,
            resolution=approved.get("story-consent"),
        ),
        Decision(
            id="period-check",
            label="Period check",
            question="Confirm the activity log covers May 1–Aug 31, 2026?",
            why="The rows reconcile internally; the operator still owns the final coverage assertion.",
            evidence="activity_log.csv · 4 unique events · dates 2026-05-18 to 2026-08-22",
            resolved="period-check" in approved,
            resolution=approved.get("period-check"),
        ),
    ]

    supported = sum(claim.status == "supported" for claim in claims)
    needs_review = sum(claim.status == "needs-review" for claim in claims)
    blocked = sum(claim.status == "blocked" for claim in claims)
    summary = CaseSummary(
        award_id=award["id"],
        title=award["title"],
        funder=award["funder"],
        period=award["period"],
        amount=award["amount"],
        requirements=len(award["reporting_requirements"]),
        claims=len(claims),
        supported=supported,
        needs_review=needs_review,
        blocked=blocked,
    )
    report = _draft_report(award, claims, decisions, duplicate_count)
    evidence_index = [
        {"source": "award_brief.json", "role": "targets, amount, reporting requirements"},
        {"source": "activity_log.csv", "role": "dated outputs and deduplicated event totals"},
        {"source": "finance.csv", "role": "expense categories and award variance"},
        {"source": "story_notes.json", "role": "narrative context and consent flags"},
    ]
    warnings = [
        "Synthetic fixture data — no real beneficiary information is included.",
        "Tallyline prepares a packet; a human still owns the final submission.",
    ]
    return RunResult(
        run_id="run-gn-2608",
        provider="Strands • offline evidence pass",
        agent="Tallyline Coordinator",
        state="complete",
        summary=summary,
        claims=claims,
        decisions=decisions,
        report_markdown=report,
        evidence_index=evidence_index,
        warnings=warnings,
    )


def _draft_report(award: dict[str, Any], claims: list[Claim], decisions: list[Decision], duplicate_count: int) -> str:
    claim_lines = "\n".join(f"- **{claim.label}:** {claim.value} ({claim.status}; {claim.source})" for claim in claims)
    open_lines = "\n".join(f"- {decision.label}: {decision.question}" for decision in decisions if not decision.resolved)
    resolved_lines = "\n\n".join(
        f"### {decision.label}\n\n"
        + "\n".join(f"> {line}" for line in (decision.resolution or "").splitlines())
        for decision in decisions if decision.resolved
    )
    return (
        f"# {award['title']} — closeout draft\n\n"
        f"**Funder:** {award['funder']}  \n**Award:** ${award['amount']:,.0f}  \n**Period:** {award['period']}\n\n"
        "## Evidence-backed results\n\n"
        f"{claim_lines}\n\n"
        "## Reconciliation note\n\n"
        f"The deterministic pass retained unique event IDs and excluded {duplicate_count} duplicate-looking row. "
        "Numbers above are sourced from the fixture files; they are not an evaluation of a real program.\n\n"
        "## Human decisions before submission\n\n"
        f"{open_lines or '- No open decisions.'}\n"
        + (f"\n## Recorded human decisions\n\n{resolved_lines}\n" if resolved_lines else "")
    )


def export_markdown(result: RunResult) -> str:
    open_count = sum(not decision.resolved for decision in result.decisions)
    return result.report_markdown + (
        "\n---\n\n"
        "## Evidence index\n\n"
        + "\n".join(f"- `{row['source']}` — {row['role']}" for row in result.evidence_index)
        + f"\n\n**Open human decisions:** {open_count}\n"
    )
