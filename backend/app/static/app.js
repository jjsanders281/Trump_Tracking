// === STATE ===

const state = {
  activeTab: "home",
  items: [],
  selectedResultId: null,
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

const verdictBadgeClass = (value) => {
  const normalized = String(value ?? "na").toLowerCase();
  const valid = new Set([
    "true",
    "mixed",
    "misleading",
    "false",
    "unverified",
    "unfulfilled",
    "contradicted",
    "pending",
    "verified",
    "rejected",
    "na",
    "n/a",
  ]);
  if (!valid.has(normalized)) return "badge--na";
  return normalized === "n/a" ? "badge--na" : `badge--${normalized}`;
};

const HIGH_RISK_VERDICTS = new Set(["false", "misleading", "contradicted"]);
const REQUIRED_RATIONALE_SECTIONS = [
  "Evidence:",
  "Why This Is False:",
  "Shut Down False Argument:",
];

function validateHighRiskRationale(verdict, rationale) {
  const normalizedVerdict = String(verdict ?? "").toLowerCase();
  const text = String(rationale ?? "").trim();

  if (!HIGH_RISK_VERDICTS.has(normalizedVerdict)) return null;
  if (text.length < 240) {
    return "For false/misleading/contradicted verdicts, rationale must be detailed (minimum 240 characters).";
  }

  const lower = text.toLowerCase();
  const missing = REQUIRED_RATIONALE_SECTIONS.filter(
    (section) => !lower.includes(section.toLowerCase()),
  );
  if (missing.length) {
    return `Missing rationale section(s): ${missing.join(", ")}`;
  }

  return null;
}

function parseRationaleSections(rationale) {
  const text = String(rationale ?? "").trim();
  if (!text) return [];

  const lines = text.split(/\r?\n/);
  const sections = [];
  let currentTitle = "Rationale";
  let currentBody = [];
  let hasHeading = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (/^[A-Za-z][A-Za-z0-9 "'()\/-]{2,64}:$/.test(trimmed)) {
      const body = currentBody.join("\n").trim();
      if (body) sections.push({ title: currentTitle, body });
      currentTitle = trimmed.slice(0, -1);
      currentBody = [];
      hasHeading = true;
      continue;
    }
    currentBody.push(line);
  }
  const trailingBody = currentBody.join("\n").trim();
  if (trailingBody) {
    sections.push({ title: currentTitle, body: trailingBody });
  } else if (hasHeading) {
    sections.push({ title: currentTitle, body: "No details provided." });
  }

  return sections.length ? sections : [{ title: "Rationale", body: text }];
}

function rationaleSectionClass(title) {
  const normalized = String(title ?? "").toLowerCase();
  if (normalized.includes("shut down") || normalized.includes("counter")) {
    return "rationale-section rationale-section--shutdown";
  }
  if (normalized.includes("evidence")) {
    return "rationale-section rationale-section--evidence";
  }
  return "rationale-section";
}

function renderRationale(rationale) {
  const sections = parseRationaleSections(rationale);
  if (!sections.length) return '<p class="muted">Not assessed yet</p>';

  return `<div class="rationale-stack">
    ${sections
      .map(
        (section) => `<section class="${rationaleSectionClass(section.title)}">
          <h4>${escapeHtml(section.title)}</h4>
          <div class="rationale-text">${escapeHtml(section.body)}</div>
        </section>`,
      )
      .join("")}
  </div>`;
}

// === TAB MANAGEMENT ===

function switchTab(tabName) {
  state.activeTab = tabName;

  for (const btn of document.querySelectorAll(".tab-bar__item")) {
    const isActive = btn.dataset.tab === tabName;
    btn.classList.toggle("tab-bar__item--active", isActive);
    btn.setAttribute("aria-selected", String(isActive));
    btn.tabIndex = isActive ? 0 : -1;
  }

  const tabIds = {
    home: "tabHome",
    search: "tabSearch",
    dashboard: "tabDashboard",
    intake: "tabIntake",
    review: "tabReview",
  };
  for (const [key, id] of Object.entries(tabIds)) {
    const isActive = key === tabName;
    byId(id).classList.toggle("tab-content--active", isActive);
    byId(id).setAttribute("aria-hidden", String(!isActive));
  }

  if (tabName === "dashboard") loadDashboard();
  if (tabName === "review") loadReviewQueue();
  if (tabName === "home") loadHomeHighlights();
}

byId("tabBar").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab-bar__item");
  if (btn) switchTab(btn.dataset.tab);
});

byId("tabBar").addEventListener("keydown", (e) => {
  const current = e.target.closest(".tab-bar__item");
  if (!current) return;
  const tabs = Array.from(document.querySelectorAll(".tab-bar__item"));
  const index = tabs.indexOf(current);
  if (index === -1) return;

  let nextIndex = null;
  if (e.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
  if (e.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
  if (nextIndex === null) return;

  e.preventDefault();
  const next = tabs[nextIndex];
  next.focus();
  switchTab(next.dataset.tab);
});

const homeQuickSearchForm = byId("homeQuickSearchForm");
if (homeQuickSearchForm) {
  homeQuickSearchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = byId("homeQuickSearchInput")?.value?.trim() ?? "";
    if (query) byId("q").value = query;
    switchTab("search");
    runSearch();
  });
}

for (const btn of document.querySelectorAll("[data-home-nav]")) {
  btn.addEventListener("click", (event) => {
    event.preventDefault();
    const target = btn.dataset.homeNav;
    if (!target) return;
    switchTab(target);
    if (target === "search") runSearch();
  });
}

// === SEARCH (existing logic, unchanged) ===

function setTextIfPresent(id, value) {
  const el = byId(id);
  if (!el) return;
  el.textContent = value;
}

function clipText(value, max = 160) {
  const text = String(value ?? "").trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max)}...`;
}

async function loadSummary() {
  const res = await fetch("/api/dashboard/summary");
  const data = await res.json();
  const lieTracker = data.lie_tracker || {};

  setTextIfPresent("totalClaims", data.total_claims);
  setTextIfPresent("verifiedClaims", data.verified_claims);
  setTextIfPresent("contradictionLinks", data.contradiction_links);
  setTextIfPresent("homeTotalClaims", data.total_claims);
  setTextIfPresent("homeVerifiedClaims", data.verified_claims);
  setTextIfPresent("homeContradictionLinks", data.contradiction_links);
  setTextIfPresent("homeLiesThisWeek", lieTracker.this_week ?? "-");
  setTextIfPresent("homeLiesThisMonth", lieTracker.this_month ?? "-");
  setTextIfPresent("homeLiesThisYear", lieTracker.this_year ?? "-");
  setTextIfPresent("homeLiesThisTerm", lieTracker.this_term ?? "-");
  setTextIfPresent("homeLiesSinceCampaignLaunch", lieTracker.since_campaign_launch ?? "-");

  const termStart = lieTracker.term_start_date ?? "2025-01-20";
  const campaignLaunch = lieTracker.campaign_launch_date ?? "2015-06-16";
  setTextIfPresent(
    "homeLieTrackerDates",
    `This term since ${termStart} · Campaign launch since ${campaignLaunch} (UTC dates).`,
  );
}

async function loadHomeHighlights() {
  const newsList = byId("homeNewsList");
  const didYouKnowList = byId("homeDidYouKnowList");
  const featuredTitle = byId("homeFeaturedTitle");
  const featuredSummary = byId("homeFeaturedSummary");
  const featuredMeta = byId("homeFeaturedMeta");
  const onThisDayDate = byId("homeOnThisDayDate");
  const onThisDayList = byId("homeOnThisDayList");
  if (
    !newsList || !didYouKnowList || !featuredTitle || !featuredSummary || !featuredMeta
    || !onThisDayDate || !onThisDayList
  ) return;

  try {
    const res = await fetch("/api/claims/search?verified_only=true&limit=30");
    if (!res.ok) return;
    const payload = await res.json();
    const items = payload.items || [];
    if (!items.length) return;

    const featured = items[0];
    const latest = items.slice(1, 5);
    const facts = [...items]
      .sort((a, b) => (b.statement?.impact_score ?? 0) - (a.statement?.impact_score ?? 0))
      .slice(0, 4);

    const now = new Date();
    const month = now.getUTCMonth();
    const day = now.getUTCDate();
    const monthLabel = now.toLocaleDateString("en-US", { month: "long", day: "numeric", timeZone: "UTC" });
    const onThisDayItems = items
      .filter((item) => {
        const d = new Date(item.statement.occurred_at);
        return d.getUTCMonth() === month && d.getUTCDate() === day;
      })
      .slice(0, 3);
    const onThisDayFallback = items.slice(0, 3);
    const onThisDay = onThisDayItems.length ? onThisDayItems : onThisDayFallback;

    const rationaleText = featured.latest_assessment?.rationale ?? "";
    const rationaleExcerpt = rationaleText.split("\n").find((line) => line.trim().startsWith("- "))
      || clipText(rationaleText.replace(/\s+/g, " "), 220);

    featuredTitle.textContent = featured.claim_text;
    featuredSummary.textContent = rationaleExcerpt.replace(/^- /, "");
    featuredMeta.textContent = `${fmtDate(featured.statement.occurred_at)} · ${featured.topic} · ${featured.latest_assessment?.verdict ?? "unverified"}`;
    onThisDayDate.textContent = monthLabel;

    if (latest.length) {
      newsList.innerHTML = latest
        .map(
          (item) =>
            `<li><strong>${escapeHtml(fmtDate(item.statement.occurred_at))}:</strong> ${escapeHtml(item.claim_text.slice(0, 140))}${item.claim_text.length > 140 ? "..." : ""}</li>`,
        )
        .join("");
    }

    if (facts.length) {
      didYouKnowList.innerHTML = facts
        .map((item) => {
          const verdict = item.latest_assessment?.verdict ?? "unverified";
          return `<li><strong>${escapeHtml(item.topic)}:</strong> ${escapeHtml(item.claim_text.slice(0, 120))}${item.claim_text.length > 120 ? "..." : ""} <span class="badge ${verdictBadgeClass(verdict)}">${escapeHtml(verdict)}</span></li>`;
        })
        .join("");
    }

    onThisDayList.innerHTML = onThisDay
      .map((item) => `<li><strong>${escapeHtml(fmtDate(item.statement.occurred_at))}:</strong> ${escapeHtml(clipText(item.statement.quote, 150))}</li>`)
      .join("");
  } catch (_error) {
    // Preserve static placeholders if home highlight request fails.
  }
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
  if (!payload.items.some((item) => item.id === state.selectedResultId)) {
    state.selectedResultId = payload.items.length ? payload.items[0].id : null;
  }

  byId("resultCount").textContent = `${payload.total} result(s)`;

  const tbody = byId("resultsBody");
  tbody.innerHTML = "";

  if (!payload.items.length) {
    state.selectedResultId = null;
    tbody.innerHTML =
      '<tr><td colspan="5" class="muted">No results matched this query.</td></tr>';
    byId("detailPanel").innerHTML =
      '<h2>Claim Detail</h2><p class="muted">No claim selected.</p>';
    return;
  }

  for (const item of payload.items) {
    const tr = document.createElement("tr");
    tr.className = "results-row";
    tr.dataset.claimId = item.id;
    tr.tabIndex = 0;
    const isSelected = item.id === state.selectedResultId;
    tr.classList.toggle("results-row--selected", isSelected);
    tr.setAttribute("aria-selected", String(isSelected));
    const verdictClass = verdictBadgeClass(item.latest_assessment?.verdict ?? "na");
    tr.innerHTML = `
      <td>${escapeHtml(fmtDate(item.statement.occurred_at))}</td>
      <td>${escapeHtml(item.topic)}</td>
      <td><span class="badge ${verdictClass}">${escapeHtml(item.latest_assessment?.verdict ?? "n/a")}</span></td>
      <td>${escapeHtml(item.statement.impact_score)}</td>
      <td>${escapeHtml(item.statement.quote.slice(0, 160))}${item.statement.quote.length > 160 ? "..." : ""}</td>
    `;
    tr.addEventListener("click", () => {
      state.selectedResultId = item.id;
      updateSelectedResultRow();
      renderDetail(item);
    });
    tr.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        state.selectedResultId = item.id;
        updateSelectedResultRow();
        renderDetail(item);
      }
    });
    tbody.appendChild(tr);
  }

  const selected = payload.items.find((item) => item.id === state.selectedResultId) ?? payload.items[0];
  renderDetail(selected);
}

function updateSelectedResultRow() {
  for (const row of document.querySelectorAll("#resultsBody tr[data-claim-id]")) {
    const rowId = parseInt(row.dataset.claimId, 10);
    const isSelected = rowId === state.selectedResultId;
    row.classList.toggle("results-row--selected", isSelected);
    row.setAttribute("aria-selected", String(isSelected));
  }
}

function renderDetail(item) {
  const panel = byId("detailPanel");
  const latest = item.latest_assessment;
  const sources = item.sources
    .map(
      (source) =>
        `<li><a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.publisher)}</a> (Tier ${escapeHtml(source.source_tier)})${source.is_primary ? " - primary" : ""}${source.notes ? `<div class="source-note">${escapeHtml(source.notes)}</div>` : ""}</li>`,
    )
    .join("");

  const tags = item.tags.length
    ? item.tags.map((tag) => `<span class="badge">${escapeHtml(tag.name)}</span>`).join(" ")
    : '<span class="muted">None</span>';

  const publishStatus = latest?.publish_status ?? "pending";
  const isFinalized = publishStatus === "verified" || publishStatus === "rejected";
  const verdictClass = verdictBadgeClass(latest?.verdict ?? "na");
  const publishStatusClass = verdictBadgeClass(publishStatus);

  panel.innerHTML = `
    <h2>Claim Detail</h2>
    <div class="detail-block">
      <p><strong>Date:</strong> ${escapeHtml(fmtDate(item.statement.occurred_at))}</p>
      <p><strong>Venue:</strong> ${escapeHtml(item.statement.venue ?? "Unknown")}</p>
      <p><strong>Quote:</strong> ${escapeHtml(item.statement.quote)}</p>
      <p><strong>Claim:</strong> ${escapeHtml(item.claim_text)}</p>
    </div>
    <div class="detail-block">
      <p><strong>Verdict:</strong> <span class="badge ${verdictClass}">${escapeHtml(latest?.verdict ?? "none")}</span></p>
      <p><strong>Publish status:</strong> <span class="badge ${publishStatusClass}">${escapeHtml(publishStatus)}</span></p>
      <p><strong>Rationale:</strong></p>
      ${renderRationale(latest?.rationale ?? "")}
    </div>
    <div class="detail-block">
      <p><strong>Tags:</strong> ${tags}</p>
      <p><strong>Primary source:</strong> <a href="${escapeHtml(item.statement.primary_source_url)}" target="_blank" rel="noopener noreferrer">link</a></p>
      <p><strong>Corroborating sources:</strong></p>
      <ul>${sources || '<li class="muted">No additional sources.</li>'}</ul>
    </div>
    <div class="detail-actions">
      <button class="btn-edit" data-action="edit" data-claim-id="${item.id}">Edit</button>
      ${isFinalized ? `<button class="btn-reopen" data-action="reopen" data-claim-id="${item.id}">Reopen</button>` : ""}
      <button class="btn-danger" data-action="delete" data-claim-id="${item.id}">Delete</button>
    </div>
    <div id="detailFormArea"></div>
  `;
}

function renderEditForm(item) {
  const s = item.statement;
  const tagsStr = item.tags.map((t) => t.name).join(", ");
  const occurredLocal = s.occurred_at ? new Date(s.occurred_at).toISOString().slice(0, 16) : "";

  const sourcesHtml = item.sources
    .map(
      (src, i) => `<div class="source-row" data-source-idx="${i}">
      <div class="controls">
        <label>Publisher * <input class="editSrcPublisher" type="text" value="${escapeHtml(src.publisher)}" /></label>
        <label>URL * <input class="editSrcUrl" type="url" value="${escapeHtml(src.url)}" /></label>
        <label>Tier
          <select class="editSrcTier">
            <option value="1" ${src.source_tier === 1 ? "selected" : ""}>1 (Primary/Wire)</option>
            <option value="2" ${src.source_tier === 2 ? "selected" : ""}>2 (Major Outlet)</option>
            <option value="3" ${src.source_tier === 3 ? "selected" : ""}>3 (Partisan/Context)</option>
          </select>
        </label>
        <label class="checkbox"><input class="editSrcIsPrimary" type="checkbox" ${src.is_primary ? "checked" : ""} /> Primary</label>
        <button type="button" class="btn-remove-source">Remove</button>
      </div>
    </div>`,
    )
    .join("");

  return `<div class="edit-form">
    <form id="editClaimForm" data-claim-id="${item.id}">
      <fieldset>
        <legend>Statement</legend>
        <div class="controls">
          <label>Date/Time <input id="editOccurredAt" type="datetime-local" value="${occurredLocal}" /></label>
          <label>Speaker <input id="editSpeaker" type="text" value="${escapeHtml(s.speaker)}" /></label>
          <label>Venue <input id="editVenue" type="text" value="${escapeHtml(s.venue ?? "")}" /></label>
          <label>Impact
            <select id="editImpactScore">
              ${[1, 2, 3, 4, 5].map((n) => `<option value="${n}" ${s.impact_score === n ? "selected" : ""}>${n}</option>`).join("")}
            </select>
          </label>
        </div>
        <label>Quote <textarea id="editQuote" rows="3">${escapeHtml(s.quote)}</textarea></label>
        <label>Context <textarea id="editContext" rows="2">${escapeHtml(s.context ?? "")}</textarea></label>
        <label>Primary Source URL <input id="editPrimarySourceUrl" type="url" value="${escapeHtml(s.primary_source_url)}" /></label>
        <label>Media URL <input id="editMediaUrl" type="url" value="${escapeHtml(s.media_url ?? "")}" /></label>
        <label>Region <input id="editRegion" type="text" value="${escapeHtml(s.region)}" /></label>
      </fieldset>
      <fieldset>
        <legend>Claim</legend>
        <label>Claim Text <textarea id="editClaimText" rows="2">${escapeHtml(item.claim_text)}</textarea></label>
        <div class="controls">
          <label>Topic <input id="editTopic" type="text" value="${escapeHtml(item.topic)}" /></label>
          <label>Kind
            <select id="editClaimKind">
              ${["statement", "promise", "denial", "attack", "policy"].map((k) => `<option value="${k}" ${item.claim_kind === k ? "selected" : ""}>${k}</option>`).join("")}
            </select>
          </label>
          <label>Tags (comma-separated) <input id="editTags" type="text" value="${escapeHtml(tagsStr)}" /></label>
        </div>
      </fieldset>
      <fieldset>
        <legend>Sources</legend>
        <div id="editSources">${sourcesHtml}</div>
        <button type="button" id="editAddSourceBtn" class="btn-secondary">+ Add Source</button>
      </fieldset>
      <fieldset>
        <legend>Change Tracking</legend>
        <div class="controls">
          <label>Changed By * <input id="editChangedBy" type="text" required minlength="2" placeholder="Your name or agent ID" /></label>
          <label>Note <input id="editNote" type="text" placeholder="What changed and why..." /></label>
        </div>
      </fieldset>
      <div class="form-actions">
        <button type="submit">Save Changes</button>
        <button type="button" class="btn-cancel" id="editCancelBtn">Cancel</button>
      </div>
      <div id="editStatus" class="form-status"></div>
    </form>
  </div>`;
}

function collectEditSources() {
  const rows = document.querySelectorAll("#editSources .source-row");
  const sources = [];
  for (const row of rows) {
    const publisher = row.querySelector(".editSrcPublisher").value.trim();
    const url = row.querySelector(".editSrcUrl").value.trim();
    if (!publisher || !url) continue;
    sources.push({
      publisher,
      url,
      source_tier: parseInt(row.querySelector(".editSrcTier").value, 10),
      is_primary: row.querySelector(".editSrcIsPrimary").checked,
    });
  }
  return sources;
}

function addEditSourceRow() {
  const container = byId("editSources");
  const row = document.createElement("div");
  row.className = "source-row";
  row.innerHTML = `<div class="controls">
    <label>Publisher * <input class="editSrcPublisher" type="text" /></label>
    <label>URL * <input class="editSrcUrl" type="url" /></label>
    <label>Tier
      <select class="editSrcTier">
        <option value="1">1 (Primary/Wire)</option>
        <option value="2" selected>2 (Major Outlet)</option>
        <option value="3">3 (Partisan/Context)</option>
      </select>
    </label>
    <label class="checkbox"><input class="editSrcIsPrimary" type="checkbox" /> Primary</label>
    <button type="button" class="btn-remove-source">Remove</button>
  </div>`;
  container.appendChild(row);
}

async function saveClaimEdits(event) {
  event.preventDefault();
  const form = event.target;
  const claimId = form.dataset.claimId;
  const statusEl = byId("editStatus");
  statusEl.textContent = "Saving...";
  statusEl.className = "form-status";

  const changedBy = byId("editChangedBy").value.trim();
  const note = byId("editNote").value.trim() || null;

  if (changedBy.length < 2) {
    statusEl.textContent = "Error: Changed By is required (min 2 chars)";
    statusEl.className = "form-status form-status--error";
    return;
  }

  const tags = byId("editTags")
    .value.split(",")
    .map((t) => t.trim())
    .filter(Boolean);

  const patchBody = {
    claim: {
      claim_text: byId("editClaimText").value.trim() || null,
      topic: byId("editTopic").value.trim() || null,
      claim_kind: byId("editClaimKind").value || null,
      tags: tags.length ? tags : null,
    },
    statement: {
      occurred_at: byId("editOccurredAt").value
        ? new Date(byId("editOccurredAt").value).toISOString()
        : null,
      speaker: byId("editSpeaker").value.trim() || null,
      venue: byId("editVenue").value.trim() || null,
      quote: byId("editQuote").value.trim() || null,
      context: byId("editContext").value.trim() || null,
      primary_source_url: byId("editPrimarySourceUrl").value.trim() || null,
      media_url: byId("editMediaUrl").value.trim() || null,
      region: byId("editRegion").value.trim() || null,
      impact_score: parseInt(byId("editImpactScore").value, 10),
    },
    changed_by: changedBy,
    note,
  };

  try {
    // Save claim+statement fields
    const patchRes = await fetch(`/api/claims/${claimId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patchBody),
    });
    if (!patchRes.ok) {
      const err = await patchRes.json();
      throw new Error(err.detail || `PATCH failed: ${patchRes.status}`);
    }

    // Save sources
    const sourcesBody = {
      sources: collectEditSources(),
      changed_by: changedBy,
      note: note ? `Sources: ${note}` : "Sources updated",
    };
    const srcRes = await fetch(`/api/claims/${claimId}/sources`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sourcesBody),
    });
    if (!srcRes.ok) {
      const err = await srcRes.json();
      throw new Error(err.detail || `PUT sources failed: ${srcRes.status}`);
    }

    const updatedClaim = await srcRes.json();

    statusEl.textContent = "Saved successfully!";
    statusEl.className = "form-status form-status--success";

    // Refresh detail view and search results
    setTimeout(() => {
      renderDetail(updatedClaim);
      // Also update the item in state.items so the table row stays consistent
      const idx = state.items.findIndex((it) => it.id === updatedClaim.id);
      if (idx !== -1) state.items[idx] = updatedClaim;
    }, 600);
  } catch (err) {
    statusEl.textContent = `Error: ${escapeHtml(err.message)}`;
    statusEl.className = "form-status form-status--error";
  }
}

async function reopenClaim(claimId) {
  const area = byId("detailFormArea");
  area.innerHTML = `<div class="edit-form">
    <form id="reopenForm" data-claim-id="${claimId}">
      <fieldset>
        <legend>Reopen Claim</legend>
        <div class="controls">
          <label>Changed By * <input id="reopenChangedBy" type="text" required minlength="2" placeholder="Your name or agent ID" /></label>
          <label>Reason * <input id="reopenReason" type="text" required minlength="5" placeholder="Why is this being reopened?" /></label>
        </div>
      </fieldset>
      <div class="form-actions">
        <button type="submit" class="btn-reopen" style="background:#2a7d3f;color:white;">Reopen</button>
        <button type="button" class="btn-cancel" onclick="byId('detailFormArea').innerHTML=''">Cancel</button>
      </div>
      <div id="reopenStatus" class="form-status"></div>
    </form>
  </div>`;
}

async function submitReopen(event) {
  event.preventDefault();
  const form = event.target;
  const claimId = form.dataset.claimId;
  const statusEl = byId("reopenStatus");
  statusEl.textContent = "Reopening...";
  statusEl.className = "form-status";

  try {
    const res = await fetch(`/api/workflow/reopen/${claimId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        changed_by: byId("reopenChangedBy").value.trim(),
        reason: byId("reopenReason").value.trim(),
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `Reopen failed: ${res.status}`);
    }
    const updatedClaim = await res.json();
    statusEl.textContent = "Claim reopened for re-review.";
    statusEl.className = "form-status form-status--success";
    setTimeout(() => {
      renderDetail(updatedClaim);
      const idx = state.items.findIndex((it) => it.id === updatedClaim.id);
      if (idx !== -1) state.items[idx] = updatedClaim;
    }, 600);
  } catch (err) {
    statusEl.textContent = `Error: ${escapeHtml(err.message)}`;
    statusEl.className = "form-status form-status--error";
  }
}

async function deleteClaim(claimId) {
  const area = byId("detailFormArea");
  area.innerHTML = `<div class="confirm-dialog">
    <p>Are you sure you want to permanently delete this claim?</p>
    <p style="font-weight:normal;font-size:0.84rem;color:var(--muted);">This will remove the claim, its statement, all sources, assessments, and revision history. This cannot be undone.</p>
    <div class="form-actions">
      <button class="btn-danger" id="confirmDeleteBtn" data-claim-id="${claimId}" style="background:#b33;color:white;">Yes, Delete</button>
      <button class="btn-cancel" onclick="byId('detailFormArea').innerHTML=''">Cancel</button>
    </div>
    <div id="deleteStatus" class="form-status"></div>
  </div>`;
}

async function confirmDelete(claimId) {
  const statusEl = byId("deleteStatus");
  statusEl.textContent = "Deleting...";
  statusEl.className = "form-status";

  try {
    const res = await fetch(`/api/claims/${claimId}`, { method: "DELETE" });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `Delete failed: ${res.status}`);
    }
    statusEl.textContent = "Claim deleted.";
    statusEl.className = "form-status form-status--success";

    // Remove from local state and refresh
    state.items = state.items.filter((it) => it.id !== claimId);
    setTimeout(() => {
      byId("detailPanel").innerHTML =
        '<h2>Claim Detail</h2><p class="muted">Claim deleted. Run a new search to refresh.</p>';
      runSearch();
    }, 600);
  } catch (err) {
    statusEl.textContent = `Error: ${escapeHtml(err.message)}`;
    statusEl.className = "form-status form-status--error";
  }
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

// Detail panel action buttons (edit, reopen, delete)
byId("detailPanel").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  const action = btn.dataset.action;
  const claimId = parseInt(btn.dataset.claimId, 10);
  const item = state.items.find((it) => it.id === claimId);

  if (action === "edit" && item) {
    const area = byId("detailFormArea");
    area.innerHTML = renderEditForm(item);

    // Wire up edit form events
    byId("editClaimForm").addEventListener("submit", saveClaimEdits);
    byId("editCancelBtn").addEventListener("click", () => {
      area.innerHTML = "";
    });
    byId("editAddSourceBtn").addEventListener("click", addEditSourceRow);
    byId("editSources").addEventListener("click", (ev) => {
      if (ev.target.closest(".btn-remove-source")) {
        ev.target.closest(".source-row").remove();
      }
    });
  } else if (action === "reopen") {
    reopenClaim(claimId);
  } else if (action === "delete") {
    deleteClaim(claimId);
  }
});

// Delegated listeners for reopen form submit and delete confirm
byId("detailPanel").addEventListener("submit", (e) => {
  const form = e.target.closest("#reopenForm");
  if (form) submitReopen(e);
});
byId("detailPanel").addEventListener("click", (e) => {
  const btn = e.target.closest("#confirmDeleteBtn");
  if (btn) confirmDelete(parseInt(btn.dataset.claimId, 10));
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

  renderBarChart("verdictBars", dashboard.verdict_breakdown, "verdict");
  renderBarChart("topicBars", dashboard.topic_breakdown, "topic");
}

function renderBarChart(containerId, dataObj, clickField) {
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
      const dataAttr = clickField ? ` data-filter-field="${escapeHtml(clickField)}" data-filter-value="${escapeHtml(label)}"` : "";
      return `<div class="bar-row bar-row--clickable" tabindex="0" role="button"${dataAttr}>
      <span class="bar-row__label">${escapeHtml(label)}</span>
      <div class="bar-row__track">
        <div class="bar-row__fill" style="width:${pct}%"></div>
      </div>
      <span class="bar-row__value">${escapeHtml(count)}</span>
    </div>`;
    })
    .join("");
}

// Dashboard workflow queue clicks → navigate to Review tab
byId("dashWorkflowMetrics").addEventListener("click", (e) => {
  const card = e.target.closest("[data-goto-queue]");
  if (!card) return;
  navigateToQueue(card.dataset.gotoQueue);
});
byId("dashWorkflowMetrics").addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const card = e.target.closest("[data-goto-queue]");
  if (!card) return;
  e.preventDefault();
  navigateToQueue(card.dataset.gotoQueue);
});

// Dashboard bar chart clicks → navigate to Search tab with filter
for (const containerId of ["verdictBars", "topicBars"]) {
  byId(containerId).addEventListener("click", (e) => {
    const row = e.target.closest("[data-filter-field]");
    if (!row) return;
    navigateToSearchWithFilter(row.dataset.filterField, row.dataset.filterValue);
  });
  byId(containerId).addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const row = e.target.closest("[data-filter-field]");
    if (!row) return;
    e.preventDefault();
    navigateToSearchWithFilter(row.dataset.filterField, row.dataset.filterValue);
  });
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
  byId("reviewBadgeVerified").textContent = wf.verified;
  byId("reviewBadgeRejected").textContent = wf.rejected;

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
        ${state.reviewStage === "fact_check" ? renderFactCheckForm(item.id) : state.reviewStage === "editorial" ? renderEditorialForm(item.id, assessment) : renderFinalizedDetail(item.id, assessment)}
      </div>
    </div>`;
    })
    .join("");
}

function renderQueueCardDetail(item) {
  const sources = item.sources
    .map(
      (s) =>
        `<li><a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.publisher)}</a> (Tier ${escapeHtml(s.source_tier)})${s.is_primary ? " - primary" : ""}${s.notes ? `<div class="source-note">${escapeHtml(s.notes)}</div>` : ""}</li>`,
    )
    .join("");

  const publishStatus = item.latest_assessment?.publish_status ?? "pending";
  const isFinalized = publishStatus === "verified" || publishStatus === "rejected";

  return `<div class="detail-block">
    <p><strong>Quote:</strong> ${escapeHtml(item.statement.quote)}</p>
    <p><strong>Venue:</strong> ${escapeHtml(item.statement.venue ?? "Unknown")}</p>
    <p><strong>Claim Text:</strong> ${escapeHtml(item.claim_text)}</p>
    <p><strong>Kind:</strong> ${escapeHtml(item.claim_kind)}</p>
    <p><strong>Primary Source:</strong> <a href="${escapeHtml(item.statement.primary_source_url)}" target="_blank" rel="noopener noreferrer">link</a></p>
    ${sources ? `<p><strong>Sources:</strong></p><ul>${sources}</ul>` : ""}
    ${item.tags.length ? `<p><strong>Tags:</strong> ${item.tags.map((t) => `<span class="badge">${escapeHtml(t.name)}</span>`).join(" ")}</p>` : ""}
    <div class="detail-actions">
      ${isFinalized ? `<button class="btn-reopen" data-review-action="reopen" data-claim-id="${item.id}">Reopen</button>` : ""}
      <button class="btn-danger" data-review-action="delete" data-claim-id="${item.id}">Delete</button>
    </div>
    <div class="review-action-area" data-claim-id="${item.id}"></div>
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
    <label>Rationale *
      <textarea class="fcRationale" rows="8" required minlength="40"
        placeholder="Evidence:
- Source + specific finding

Why This Is False:
- Point-by-point mismatch between claim and record

Shut Down False Argument:
- Direct rebuttal of common counterarguments using cited facts"></textarea>
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
  const verdictClass = verdictBadgeClass(verdict);
  return `<div class="detail-block">
    <p><strong>Fact-Check Verdict:</strong> <span class="badge ${verdictClass}">${escapeHtml(verdict)}</span></p>
    <p><strong>Rationale:</strong></p>
    ${renderRationale(rationale)}
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

function renderFinalizedDetail(claimId, assessment) {
  const verdict = assessment?.verdict ?? "n/a";
  const rationale = assessment?.rationale ?? "No rationale available";
  const reviewer = assessment?.reviewer_primary ?? "Unknown";
  const publishStatus = assessment?.publish_status ?? "n/a";
  const verdictClass = verdictBadgeClass(verdict);
  const statusClass = verdictBadgeClass(publishStatus);
  return `<div class="detail-block">
    <p><strong>Verdict:</strong> <span class="badge ${verdictClass}">${escapeHtml(verdict)}</span></p>
    <p><strong>Status:</strong> <span class="badge ${statusClass}">${escapeHtml(publishStatus)}</span></p>
    <p><strong>Rationale:</strong></p>
    ${renderRationale(rationale)}
    <p><strong>Reviewer:</strong> ${escapeHtml(reviewer)}</p>
  </div>`;
}

// === CROSS-TAB NAVIGATION ===

function navigateToQueue(stage) {
  // Switch to the review tab and select the given sub-tab stage
  state.reviewStage = stage;
  state.reviewOffset = 0;
  state.expandedCardId = null;

  // Update sub-tab visual state
  for (const b of document.querySelectorAll("#reviewSubTabs .sub-tab-bar__item")) {
    b.classList.toggle("sub-tab-bar__item--active", b.dataset.stage === stage);
  }

  switchTab("review");
}

function navigateToSearchWithFilter(filterField, filterValue) {
  // Reset all search filters first
  byId("q").value = "";
  byId("topic").value = "";
  byId("verdict").value = "";
  byId("start_date").value = "";
  byId("end_date").value = "";
  byId("min_impact").value = "";
  byId("verified_only").checked = false;

  // Set the requested filter
  const el = byId(filterField);
  if (el) el.value = filterValue;

  switchTab("search");
  runSearch();
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

// Review queue reopen/delete actions
byId("reviewQueue").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-review-action]");
  if (!btn) return;
  const action = btn.dataset.reviewAction;
  const claimId = parseInt(btn.dataset.claimId, 10);
  const area = btn.closest(".detail-block").querySelector(`.review-action-area[data-claim-id="${claimId}"]`);
  if (!area) return;

  if (action === "reopen") {
    area.innerHTML = `<div class="edit-form" style="margin-top:0.6rem;">
      <form class="review-reopen-form" data-claim-id="${claimId}">
        <div class="controls">
          <label>Changed By * <input class="rrChangedBy" type="text" required minlength="2" placeholder="Your name or agent ID" /></label>
          <label>Reason * <input class="rrReason" type="text" required minlength="5" placeholder="Why reopen?" /></label>
        </div>
        <div class="form-actions">
          <button type="submit" class="btn-reopen" style="background:#2a7d3f;color:white;">Reopen</button>
          <button type="button" class="btn-cancel" onclick="this.closest('.review-action-area').innerHTML=''">Cancel</button>
        </div>
        <div class="action-status form-status"></div>
      </form>
    </div>`;
  } else if (action === "delete") {
    area.innerHTML = `<div class="confirm-dialog">
      <p>Permanently delete this claim?</p>
      <div class="form-actions">
        <button class="btn-danger review-confirm-delete" data-claim-id="${claimId}" style="background:#b33;color:white;">Yes, Delete</button>
        <button class="btn-cancel" onclick="this.closest('.review-action-area').innerHTML=''">Cancel</button>
      </div>
      <div class="action-status form-status"></div>
    </div>`;
  }
});

// Review queue reopen form submit
byId("reviewQueue").addEventListener("submit", async (e) => {
  const form = e.target.closest(".review-reopen-form");
  if (form) {
    e.preventDefault();
    const claimId = form.dataset.claimId;
    const statusEl = form.querySelector(".action-status");
    statusEl.textContent = "Reopening...";
    statusEl.className = "action-status form-status";

    try {
      const res = await fetch(`/api/workflow/reopen/${claimId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          changed_by: form.querySelector(".rrChangedBy").value.trim(),
          reason: form.querySelector(".rrReason").value.trim(),
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `Reopen failed: ${res.status}`);
      }
      statusEl.textContent = "Reopened. Reloading queue...";
      statusEl.className = "action-status form-status form-status--success";
      setTimeout(() => {
        state.expandedCardId = null;
        loadReviewQueue();
      }, 600);
    } catch (err) {
      statusEl.textContent = `Error: ${escapeHtml(err.message)}`;
      statusEl.className = "action-status form-status form-status--error";
    }
    return;
  }
});

// Review queue delete confirm
byId("reviewQueue").addEventListener("click", async (e) => {
  const btn = e.target.closest(".review-confirm-delete");
  if (!btn) return;
  const claimId = btn.dataset.claimId;
  const statusEl = btn.closest(".confirm-dialog").querySelector(".action-status");
  statusEl.textContent = "Deleting...";
  statusEl.className = "action-status form-status";

  try {
    const res = await fetch(`/api/claims/${claimId}`, { method: "DELETE" });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `Delete failed: ${res.status}`);
    }
    statusEl.textContent = "Deleted. Reloading queue...";
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

// Action form submissions (fact-check and editorial)
byId("reviewQueue").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target.closest(".action-form");
  if (!form) return;
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }

  const action = form.dataset.action;
  const claimId = form.dataset.claimId;
  const statusEl = form.querySelector(".action-status");
  statusEl.textContent = "Submitting...";
  statusEl.className = "action-status form-status";

  try {
    let url, body;

    if (action === "fact-check") {
      const contradictionRaw = form.querySelector(".fcContradictionIds").value;
      const verdict = form.querySelector(".fcVerdict").value;
      const rationale = form.querySelector(".fcRationale").value.trim();
      const rationaleError = validateHighRiskRationale(verdict, rationale);
      if (rationaleError) {
        statusEl.textContent = `Error: ${rationaleError}`;
        statusEl.className = "action-status form-status form-status--error";
        return;
      }

      const contradictionIds = contradictionRaw
        .split(",")
        .map((s) => parseInt(s.trim(), 10))
        .filter((n) => !isNaN(n));

      url = `/api/workflow/fact-check/${claimId}`;
      body = {
        verdict,
        rationale,
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

switchTab(state.activeTab);
await loadSummary();
await runSearch();
