const state = {
  items: [],
};

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
    : "<span class=\"muted\">None</span>";

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
      <ul>${sources || "<li class=\"muted\">No additional sources.</li>"}</ul>
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

await loadSummary();
await runSearch();
