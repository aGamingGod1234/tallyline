const state = { result: null, busy: false };

const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#039;", '"': "&quot;"
  }[character]));
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 3200);
}

function setRunStatus(kind, text) {
  const mark = $(".status-mark");
  mark.className = `status-mark ${kind}`;
  $("#runStatusText").textContent = text;
}

function renderLedger(claims) {
  const body = $("#ledgerBody");
  body.innerHTML = claims.map((claim) => `
    <tr class="claim-row" data-claim="${escapeHtml(claim.id)}" aria-expanded="false">
      <td>${escapeHtml(claim.label)}</td>
      <td>${escapeHtml(claim.value)}</td>
      <td><span class="status-pill status-${escapeHtml(claim.status)}">${escapeHtml(claim.status.replace("-", " "))}</span></td>
      <td>${escapeHtml(claim.source)}</td>
      <td><button class="claim-toggle" type="button" aria-label="Inspect ${escapeHtml(claim.label)}" aria-expanded="false">+</button></td>
    </tr>
    <tr class="claim-detail" data-detail="${escapeHtml(claim.id)}" hidden><td colspan="5"><strong>Why this status:</strong> ${escapeHtml(claim.detail)} <span> / </span><strong>Pass:</strong> ${escapeHtml(claim.confidence)}</td></tr>
  `).join("");
  body.querySelectorAll(".claim-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      const row = button.closest(".claim-row");
      const detail = body.querySelector(`[data-detail="${row.dataset.claim}"]`);
      const expanded = row.getAttribute("aria-expanded") === "true";
      row.setAttribute("aria-expanded", String(!expanded));
      button.setAttribute("aria-expanded", String(!expanded));
      button.textContent = expanded ? "+" : "−";
      detail.hidden = expanded;
    });
  });
}

function decisionResolution(id) {
  if (id === "budget-variance") return "Carry the balance forward to the fall heat-safety round.";
  if (id === "story-consent") return "Keep the non-consented note private; use only the consented story.";
  return "I confirm the activity log covers the full award period.";
}

function renderDecisions(decisions) {
  const open = decisions.filter((decision) => !decision.resolved).length;
  $("#queueCount").textContent = open;
  $("#decisionList").innerHTML = decisions.map((decision) => {
    const resolution = decision.resolution ? `<p class="decision-resolved">✓ ${escapeHtml(decision.resolution)}</p>` : `<button class="decision-action" type="button" data-approve="${escapeHtml(decision.id)}">${escapeHtml(decision.id === "story-consent" ? "Keep note private" : decision.id === "budget-variance" ? "Carry balance forward" : "Confirm coverage")} ↗</button>`;
    return `<article class="decision-item"><div class="decision-top"><span class="decision-label">${escapeHtml(decision.label)}</span><span class="decision-state">${decision.resolved ? "RESOLVED" : "NEEDS YOU"}</span></div><p class="decision-question">${escapeHtml(decision.question)}</p><p class="decision-why">${escapeHtml(decision.why)}</p><p class="decision-evidence">${escapeHtml(decision.evidence)}</p>${resolution}</article>`;
  }).join("");
  $("#decisionList").querySelectorAll("[data-approve]").forEach((button) => {
    button.addEventListener("click", () => approveDecision(button.dataset.approve, button));
  });
}

function renderReport(result) {
  const open = result.decisions.filter((decision) => !decision.resolved).length;
  const statusLine = open ? `${open} decision${open === 1 ? "" : "s"} still open` : "Ready for human review";
  const bullets = result.claims.map((claim) => `<li><strong>${escapeHtml(claim.label)}:</strong> ${escapeHtml(claim.value)} <span class="report-status">[${escapeHtml(claim.status)}]</span></li>`).join("");
  $("#reportSheet").innerHTML = `<div class="report-meta"><span>GN-26-014<strong>Closeout draft</strong></span><span>STATUS<strong>${escapeHtml(statusLine)}</strong></span></div><h4>Evidence-backed results</h4><ul>${bullets}</ul><p class="report-note">This draft excludes unsupported or non-consented narrative. Sources remain indexed in the exported packet.</p>`;
}

function renderAgentReadout(result) {
  const panel = $("#agentReadout");
  const note = String(result.agent_note || "").trim();
  if (result.agent_mode !== "live" || !note) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  $("#agentNote").innerHTML = escapeHtml(note).replace(/\n/g, "<br />");
}

function renderResult(result) {
  state.result = result;
  const summary = result.summary;
  $("#runId").textContent = result.run_id.toUpperCase();
  $("#providerLabel").textContent = result.provider.toUpperCase();
  $("#ledgerSummary").textContent = `${summary.claims} claims · ${summary.supported} supported · ${summary.needs_review} needs review · ${summary.blocked} blocked`;
  $("#savedState").textContent = result.agent_mode === "live" ? "LIVE / SYNTHETIC" : "LOCAL / SYNTHETIC";
  $("#routeFill").style.transform = "scaleX(1)";
  renderLedger(result.claims);
  renderDecisions(result.decisions);
  renderReport(result);
  renderAgentReadout(result);
  setRunStatus("complete", "Trace complete");
  $("#actionNote").textContent = result.agent_mode === "live"
    ? "Live model readout received. Typed tools and the evidence ledger remain authoritative."
    : "Evidence is indexed. Resolve the queue before you export the packet.";
}

async function runCase({ reset = false } = {}) {
  if (state.busy) return;
  state.busy = true;
  const button = $("#runButton");
  button.disabled = true;
  $(".button-label").textContent = "Following evidence…";
  $("#savedState").textContent = "RUNNING / TRACE";
  setRunStatus("running", "Tracing source files");
  $("#routeFill").style.transform = "scaleX(.24)";
  await new Promise((resolve) => window.setTimeout(resolve, reset ? 180 : 620));
  try {
    const response = await fetch(reset ? "/api/reset" : "/api/run", { method: "POST" });
    if (!response.ok) throw new Error("The evidence pass returned an error.");
    renderResult(await response.json());
  } catch (error) {
    setRunStatus("running", "Could not trace");
    $("#actionNote").textContent = error.message;
    showToast(error.message);
  } finally {
    state.busy = false;
    button.disabled = false;
    $(".button-label").textContent = "Run reconciliation";
  }
}

async function approveDecision(decisionId, button) {
  button.disabled = true;
  button.textContent = "Saving…";
  try {
    const response = await fetch("/api/decisions/approve", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision_id: decisionId, resolution: decisionResolution(decisionId) }) });
    if (!response.ok) throw new Error("That decision could not be saved.");
    renderResult(await response.json());
    showToast("Decision added to the packet.");
  } catch (error) {
    button.disabled = false;
    button.textContent = "Try again ↗";
    showToast(error.message);
  }
}

$("#runButton").addEventListener("click", () => runCase());
$("#resetButton").addEventListener("click", () => runCase({ reset: true }));

// The first viewport is useful immediately. A manual query is reserved for
// the recorded live-model walkthrough so the explicit action remains visible
// before the provider call starts.
if (!new URLSearchParams(window.location.search).has("manual")) runCase();
