// === STATE ===

const state = {
  activeTab: "search",
  items: [],
  dashboardData: null,
  reviewStage: "fact_check",
  reviewItems: [],
  reviewTotal: 0,
  reviewOffset: 0,
  expandedCardId: null,
};

// === UTILITIES ===

const byId = (id) => document.getElementById(id);

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const fmtDate = (value) => {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toISOString().slice(0, 10);
};

// === TAB MANAGEMENT ===

function switchTab(tabName) {
  state.activeTab = tabName;

  for (const btn of document.querySelectorAll(".tab-bar__item")) {
    btn.classList.toggle("tab-bar__item--active", btn.dataset.tab === tabName);
  }

  const tabIds = {
    search: "tabSearch",
    dashboard: "tabDashboard",
    intake: "tabIntake",
    review: "tabReview",
  };
  for (const [key, id] of Object.entries(tabIds)) {
    byId(id).classList.toggle("tab-content--active", key === tabName);
  }

  if (tabName === "dashboard") loadDashboard();
  if (tabName === "review") loadReviewQueue();
}

byId("tabBar").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab-bar__item");
  if (btn) switchTab(btn.dataset.tab);
});

// === SEARCH (existing logic, unchanged) ===

async function loadSummary() {
  const res = await fetch("/api/dashboard/summary");
  const data = await res.json();

  byId("totalClaims").textContent = data.total_claims;
  byId("verifiedClaims").textContent = data.verified_claims;
  byId("contradictionLinks").textContent = data.contradiction_links;
}

function buildQuery() {
  const params = new URLSearchParams();

  const fields = ["q", "topic", "verdict", "start_date", "end_date", "min_impact"];
  for (const field of fields) {
    const value = byId(field).value?.trim();
    if (value) params.set(field, value);
  }

  params.set("verified_only", String(byId("verified_only").checked));
  params.set("limit", "50");
  return params;
}

function renderResults(payload) {
  state.items = payload.items;

  byId("resultCount").textContent = `${payload.total} result(s)`;

  const tbody = byId("resultsBody");
  tbody.innerHTML = "";

  if (!payload.items.length) {
    tbody.innerHTML =
      '<tr><td colspan="5" class="muted">No results matched this query.</td></tr>';
    byId("detailPanel").innerHTML =
      '<h2>Claim Detail</h2><p class="muted">No claim selected.</p>';
    return;
  }

  for (const item of payload.items) {
    const tr = document.createElement("tr");
    tr.dataset.claimId = item.id;
    tr.innerHTML = `
      <td>${escapeHtml(fmtDate(item.statement.occurred_at))}</td>
      <td>${escapeHtml(item.topic)}</td>
      <td><span class="badge">${escapeHtml(item.latest_assessment?.verdict ?? "n/a")}</span></td>
      <td>${escapeHtml(item.statement.impact_score)}</td>
      <td>${escapeHtml(item.statement.quote.slice(0, 160))}${item.statement.quote.length > 160 ? "..." : ""}</td>
    `;
    tr.addEventListener("click", () => renderDetail(item));
    tbody.appendChild(tr);
  }

  renderDetail(payload.items[0]);
}

function renderDetail(item) {
  const panel = byId("detailPanel");
  const latest = item.latest_assessment;
  const sources = item.sources
    .map(
      (source) =>
        `<li><a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.publisher)}</a> (Tier ${escapeHtml(source.source_tier)})${source.is_primary ? " - primary" : ""}</li>`,
    )
    .join("");

  const tags = item.tags.length
    ? item.tags.map((tag) => `<span class="badge">${escapeHtml(tag.name)}</span>`).join(" ")
    : '<span class="muted">None</span>';

  panel.innerHTML = `
    <h2>Claim Detail</h2>
    <div class="detail-block">
      <p><strong>Date:</strong> ${escapeHtml(fmtDate(item.statement.occurred_at))}</p>
      <p><strong>Venue:</strong> ${escapeHtml(item.statement.venue ?? "Unknown")}</p>
      <p><strong>Quote:</strong> ${escapeHtml(item.statement.quote)}</p>
      <p><strong>Claim:</strong> ${escapeHtml(item.claim_text)}</p>
    </div>
    <div class="detail-block">
      <p><strong>Verdict:</strong> ${escapeHtml(latest?.verdict ?? "none")}</p>
      <p><strong>Publish status:</strong> ${escapeHtml(latest?.publish_status ?? "pending")}</p>
      <p><strong>Rationale:</strong> ${escapeHtml(latest?.rationale ?? "Not assessed yet")}</p>
    </div>
    <div class="detail-block">
      <p><strong>Tags:</strong> ${tags}</p>
      <p><strong>Primary source:</strong> <a href="${escapeHtml(item.statement.primary_source_url)}" target="_blank" rel="noopener noreferrer">link</a></p>
      <p><strong>Corroborating sources:</strong></p>
      <ul>${sources || '<li class="muted">No additional sources.</li>'}</ul>
    </div>
  `;
}

async function runSearch() {
  const params = buildQuery();
  const res = await fetch(`/api/claims/search?${params.toString()}`);
  const data = await res.json();
  renderResults(data);
}

byId("searchBtn").addEventListener("click", runSearch);
byId("q").addEventListener("keydown", (event) => {
  if (event.key === "Enter") runSearch();
});

// === DASHBOARD ===

async function loadDashboard() {
  const [dashRes, wfRes] = await Promise.all([
    fetch("/api/dashboard/summary"),
    fetch("/api/workflow/summary"),
  ]);
  const dashboard = await dashRes.json();
  const workflow = await wfRes.json();
  state.dashboardData = { dashboard, workflow };

  byId("queueFactCheck").textContent = workflow.fact_check;
  byId("queueEditorial").textContent = workflow.editorial;
  byId("queueVerified").textContent = workflow.verified;
  byId("queueRejected").textContent = workflow.rejected;

  byId("dashTotalClaims").textContent = dashboard.total_claims;
  byId("dashVerifiedClaims").textContent = dashboard.verified_claims;
  byId("dashContradictionLinks").textContent = dashboard.contradiction_links;

  renderBarChart("verdictBars", dashboard.verdict_breakdown);
  renderBarChart("topicBars", dashboard.topic_breakdown);
}

function renderBarChart(containerId, dataObj) {
  const container = byId(containerId);
  const entries = Object.entries(dataObj);
  if (!entries.length) {
    container.innerHTML = '<p class="muted">No data yet.</p>';
    return;
  }
  const maxVal = Math.max(...entries.map(([, v]) => v), 1);
  container.innerHTML = entries
    .map(([label, count]) => {
      const pct = Math.round((count / maxVal) * 100);
      return `<div class="bar-row">
      <span class="bar-row__label">${escapeHtml(label)}</span>
      <div class="bar-row__track">
        <div class="bar-row__fill" style="width:${pct}%"></div>
      </div>
      <span class="bar-row__value">${escapeHtml(count)}</span>
    </div>`;
    })
    .join("");
}

// === INTAKE ===

function addSourceRow() {
  const container = byId("intakeSources");
  const row = document.createElement("div");
  row.className = "source-row";
  row.innerHTML = `<div class="controls">
    <label>Publisher * <input class="srcPublisher" type="text" required /></label>
    <label>URL * <input class="srcUrl" type="url" required /></label>
    <label>Tier
      <select class="srcTier">
        <option value="1">1 (Primary/Wire)</option>
        <option value="2" selected>2 (Major Outlet)</option>
        <option value="3">3 (Partisan/Context)</option>
      </select>
    </label>
    <label class="checkbox"><input class="srcIsPrimary" type="checkbox" /> Primary</label>
    <button type="button" class="btn-remove-source">Remove</button>
  </div>`;
  container.appendChild(row);
  updateRemoveSourceBtns();
}

function updateRemoveSourceBtns() {
  const rows = document.querySelectorAll("#intakeSources .source-row");
  for (const row of rows) {
    const btn = row.querySelector(".btn-remove-source");
    btn.style.display = rows.length > 1 ? "" : "none";
  }
}

function collectSources() {
  const rows = document.querySelectorAll("#intakeSources .source-row");
  const sources = [];
  for (const row of rows) {
    const publisher = row.querySelector(".srcPublisher").value.trim();
    const url = row.querySelector(".srcUrl").value.trim();
    if (!publisher || !url) continue;
    sources.push({
      publisher,
      url,
      source_tier: parseInt(row.querySelector(".srcTier").value, 10),
      is_primary: row.querySelector(".srcIsPrimary").checked,
    });
  }
  return sources;
}

function buildIntakePayload() {
  const tags = byId("intakeTags")
    .value.split(",")
    .map((t) => t.trim())
    .filter(Boolean);

  return {
    statement: {
      occurred_at: byId("intakeOccurredAt").value
        ? new Date(byId("intakeOccurredAt").value).toISOString()
        : null,
      speaker: byId("intakeSpeaker").value.trim() || "Donald J. Trump",
      venue: byId("intakeVenue").value.trim() || null,
      quote: byId("intakeQuote").value.trim(),
      context: byId("intakeContext").value.trim() || null,
      primary_source_url: byId("intakePrimarySourceUrl").value.trim(),
      media_url: byId("intakeMediaUrl").value.trim() || null,
      region: byId("intakeRegion").value.trim() || "US",
      impact_score: parseInt(byId("intakeImpactScore").value, 10),
    },
    claim: {
      claim_text: byId("intakeClaimText").value.trim(),
      topic: byId("intakeTopic").value.trim(),
      claim_kind: byId("intakeClaimKind").value,
      tags,
    },
    sources: collectSources(),
    intake_note: byId("intakeNote").value.trim() || null,
  };
}

async function submitIntake(event) {
  event.preventDefault();
  const statusEl = byId("intakeStatus");
  statusEl.textContent = "Submitting...";
  statusEl.className = "form-status";

  try {
    const payload = buildIntakePayload();
    const res = await fetch("/api/workflow/intake", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `Server returned ${res.status}`);
    }

    const claim = await res.json();
    statusEl.textContent = `Intake submitted successfully. Claim ID: ${claim.id}`;
    statusEl.className = "form-status form-status--success";

    // Reset form but preserve defaults
    byId("intakeForm").reset();
    byId("intakeSpeaker").value = "Donald J. Trump";
    byId("intakeRegion").value = "US";
    byId("intakeImpactScore").value = "3";
    byId("intakeClaimKind").value = "statement";

    // Reset sources to one empty row
    byId("intakeSources").innerHTML = "";
    addSourceRow();
  } catch (err) {
    statusEl.textContent = `Error: ${escapeHtml(err.message)}`;
    statusEl.className = "form-status form-status--error";
  }
}

byId("intakeForm").addEventListener("submit", submitIntake);
byId("addSourceBtn").addEventListener("click", addSourceRow);
byId("intakeSources").addEventListener("click", (e) => {
  if (e.target.closest(".btn-remove-source")) {
    e.target.closest(".source-row").remove();
    updateRemoveSourceBtns();
  }
});

// Initialize with one source row
addSourceRow();

// === REVIEW ===

const REVIEW_LIMIT = 25;

async function loadReviewQueue() {
  // Refresh badge counts
  const wfRes = await fetch("/api/workflow/summary");
  const wf = await wfRes.json();
  byId("reviewBadgeFactCheck").textContent = wf.fact_check;
  byId("reviewBadgeEditorial").textContent = wf.editorial;

  const stage = state.reviewStage;
  const res = await fetch(
    `/api/workflow/queues/${stage}?limit=${REVIEW_LIMIT}&offset=${state.reviewOffset}`,
  );
  const data = await res.json();
  state.reviewItems = data.items;
  state.reviewTotal = data.total;
  renderReviewQueue();
  renderReviewPagination();
}

function renderReviewQueue() {
  const container = byId("reviewQueue");
  const items = state.reviewItems;

  if (!items.length) {
    container.innerHTML = '<p class="muted">No items in this queue.</p>';
    return;
  }

  container.innerHTML = items
    .map((item) => {
      const isExpanded = state.expandedCardId === item.id;
      const assessment = item.latest_assessment;
      return `<div class="queue-card ${isExpanded ? "queue-card--expanded" : ""}"
                   data-claim-id="${item.id}">
      <div class="queue-card__header">
        <span class="queue-card__title">${escapeHtml(item.claim_text.slice(0, 120))}${item.claim_text.length > 120 ? "..." : ""}</span>
        <span class="queue-card__meta">
          <span class="badge">${escapeHtml(item.topic)}</span>
          <span>${escapeHtml(fmtDate(item.statement.occurred_at))}</span>
          <span>Impact ${escapeHtml(item.statement.impact_score)}</span>
        </span>
      </div>
      <div class="queue-card__body">
        ${renderQueueCardDetail(item)}
        ${state.reviewStage === "fact_check" ? renderFactCheckForm(item.id) : renderEditorialForm(item.id, assessment)}
      </div>
    </div>`;
    })
    .join("");
}

function renderQueueCardDetail(item) {
  const sources = item.sources
    .map(
      (s) =>
        `<li><a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.publisher)}</a> (Tier ${escapeHtml(s.source_tier)})${s.is_primary ? " - primary" : ""}</li>`,
    )
    .join("");
  return `<div class="detail-block">
    <p><strong>Quote:</strong> ${escapeHtml(item.statement.quote)}</p>
    <p><strong>Venue:</strong> ${escapeHtml(item.statement.venue ?? "Unknown")}</p>
    <p><strong>Primary Source:</strong> <a href="${escapeHtml(item.statement.primary_source_url)}" target="_blank" rel="noopener noreferrer">link</a></p>
    ${sources ? `<p><strong>Sources:</strong></p><ul>${sources}</ul>` : ""}
    ${item.tags.length ? `<p><strong>Tags:</strong> ${item.tags.map((t) => `<span class="badge">${escapeHtml(t.name)}</span>`).join(" ")}</p>` : ""}
  </div>`;
}

function renderFactCheckForm(claimId) {
  return `<form class="action-form" data-action="fact-check" data-claim-id="${claimId}">
    <h3>Submit Fact-Check</h3>
    <div class="controls">
      <label>Verdict *
        <select class="fcVerdict" required>
          <option value="">Select...</option>
          <option value="true">True</option>
          <option value="mixed">Mixed</option>
          <option value="misleading">Misleading</option>
          <option value="false">False</option>
          <option value="unverified">Unverified</option>
          <option value="unfulfilled">Unfulfilled</option>
          <option value="contradicted">Contradicted</option>
        </select>
      </label>
      <label>Reviewer Name *
        <input class="fcReviewer" type="text" required minlength="2" placeholder="Your name" />
      </label>
      <label>Source Tier Used
        <select class="fcSourceTier">
          <option value="1" selected>1</option>
          <option value="2">2</option>
          <option value="3">3</option>
        </select>
      </label>
    </div>
    <label>Rationale * (min 10 chars)
      <textarea class="fcRationale" rows="3" required minlength="10"
        placeholder="Explain the verdict with evidence references..."></textarea>
    </label>
    <label>Note
      <textarea class="fcNote" rows="2" placeholder="Optional note..."></textarea>
    </label>
    <label>Contradiction Claim IDs (comma-separated)
      <input class="fcContradictionIds" type="text" placeholder="e.g. 5, 12" />
    </label>
    <div class="form-actions">
      <button type="submit">Submit Fact-Check</button>
    </div>
    <div class="action-status form-status"></div>
  </form>`;
}

function renderEditorialForm(claimId, assessment) {
  const verdict = assessment?.verdict ?? "n/a";
  const rationale = assessment?.rationale ?? "No rationale available";
  const reviewer = assessment?.reviewer_primary ?? "Unknown";
  return `<div class="detail-block">
    <p><strong>Fact-Check Verdict:</strong> <span class="badge">${escapeHtml(verdict)}</span></p>
    <p><strong>Rationale:</strong> ${escapeHtml(rationale)}</p>
    <p><strong>Fact-Checker:</strong> ${escapeHtml(reviewer)}</p>
  </div>
  <form class="action-form" data-action="editorial" data-claim-id="${claimId}">
    <h3>Editorial Decision</h3>
    <div class="controls">
      <label>Decision *
        <select class="edDecision" required>
          <option value="">Select...</option>
          <option value="verified">Verify (Publish)</option>
          <option value="rejected">Reject</option>
        </select>
      </label>
      <label>Reviewer Name *
        <input class="edReviewer" type="text" required minlength="2" placeholder="Your name" />
      </label>
    </div>
    <label>Note
      <textarea class="edNote" rows="2" placeholder="Optional editorial note..."></textarea>
    </label>
    <div class="form-actions">
      <button type="submit">Submit Decision</button>
    </div>
    <div class="action-status form-status"></div>
  </form>`;
}

// Card expand/collapse
byId("reviewQueue").addEventListener("click", (e) => {
  const header = e.target.closest(".queue-card__header");
  if (!header) return;
  const card = header.closest(".queue-card");
  const claimId = parseInt(card.dataset.claimId, 10);
  state.expandedCardId = state.expandedCardId === claimId ? null : claimId;
  renderReviewQueue();
});

// Action form submissions (fact-check and editorial)
byId("reviewQueue").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target.closest(".action-form");
  if (!form) return;

  const action = form.dataset.action;
  const claimId = form.dataset.claimId;
  const statusEl = form.querySelector(".action-status");
  statusEl.textContent = "Submitting...";
  statusEl.className = "action-status form-status";

  try {
    let url, body;

    if (action === "fact-check") {
      const contradictionRaw = form.querySelector(".fcContradictionIds").value;
      const contradictionIds = contradictionRaw
        .split(",")
        .map((s) => parseInt(s.trim(), 10))
        .filter((n) => !isNaN(n));

      url = `/api/workflow/fact-check/${claimId}`;
      body = {
        verdict: form.querySelector(".fcVerdict").value,
        rationale: form.querySelector(".fcRationale").value.trim(),
        reviewer_primary: form.querySelector(".fcReviewer").value.trim(),
        source_tier_used: parseInt(form.querySelector(".fcSourceTier").value, 10),
        sources: [],
        contradiction_claim_ids: contradictionIds,
        note: form.querySelector(".fcNote").value.trim() || null,
      };
    } else if (action === "editorial") {
      url = `/api/workflow/editorial/${claimId}`;
      body = {
        publish_status: form.querySelector(".edDecision").value,
        reviewer_secondary: form.querySelector(".edReviewer").value.trim(),
        note: form.querySelector(".edNote").value.trim() || null,
      };
    }

    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `Server returned ${res.status}`);
    }

    statusEl.textContent = "Submitted successfully. Reloading queue...";
    statusEl.className = "action-status form-status form-status--success";

    setTimeout(() => {
      state.expandedCardId = null;
      loadReviewQueue();
    }, 600);
  } catch (err) {
    statusEl.textContent = `Error: ${escapeHtml(err.message)}`;
    statusEl.className = "action-status form-status form-status--error";
  }
});

// Sub-tab switching (fact_check / editorial)
byId("reviewSubTabs").addEventListener("click", (e) => {
  const btn = e.target.closest(".sub-tab-bar__item");
  if (!btn) return;
  for (const b of document.querySelectorAll(".sub-tab-bar__item")) {
    b.classList.toggle("sub-tab-bar__item--active", b === btn);
  }
  state.reviewStage = btn.dataset.stage;
  state.reviewOffset = 0;
  state.expandedCardId = null;
  loadReviewQueue();
});

// Pagination
function renderReviewPagination() {
  const container = byId("reviewPagination");
  const totalPages = Math.ceil(state.reviewTotal / REVIEW_LIMIT);
  const currentPage = Math.floor(state.reviewOffset / REVIEW_LIMIT) + 1;

  if (totalPages <= 1) {
    container.innerHTML = `<span class="pagination__info">${state.reviewTotal} item(s)</span>`;
    return;
  }

  container.innerHTML = `
    <button ${currentPage <= 1 ? "disabled" : ""} data-page="prev">Prev</button>
    <span class="pagination__info">Page ${currentPage} of ${totalPages} (${state.reviewTotal} items)</span>
    <button ${currentPage >= totalPages ? "disabled" : ""} data-page="next">Next</button>
  `;
}

byId("reviewPagination").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-page]");
  if (!btn || btn.disabled) return;
  if (btn.dataset.page === "prev") state.reviewOffset -= REVIEW_LIMIT;
  if (btn.dataset.page === "next") state.reviewOffset += REVIEW_LIMIT;
  state.expandedCardId = null;
  loadReviewQueue();
});

// === INITIALIZATION ===

await loadSummary();
await runSearch();
