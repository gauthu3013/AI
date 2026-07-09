/* TwinCheck frontend — login → upload → dashboard */

const DISCIPLINES = [
  {
    id: "electrical",
    title: "Electrical",
    sub: "Earthing Calculation & Power System Summary",
    sample: "electrical_earthing_and_power.xlsx",
  },
  {
    id: "mechanical",
    title: "Mechanical",
    sub: "Cooling Equipment Data Sheets",
    sample: "mechanical_cooling_datasheets.xlsx",
  },
  {
    id: "process",
    title: "Process",
    sub: "Equipment List (IT racks & mechanical plant)",
    sample: "process_it_equipment_list.xlsx",
  },
];

const state = {
  token: sessionStorage.getItem("twincheck_token"),
  email: sessionStorage.getItem("twincheck_email"),
  uploaded: new Set(),
};

const $ = (sel) => document.querySelector(sel);

/* ---------- status helpers (icon + label, never color alone) ---------- */
const STATUS = {
  good: { icon: "✔", label: "OK" },
  warning: { icon: "▲", label: "Attention" },
  critical: { icon: "✖", label: "Failed" },
  neutral: { icon: "—", label: "No data" },
};

function chip(kind, labelOverride) {
  const s = STATUS[kind] || STATUS.neutral;
  const el = document.createElement("span");
  el.className = `chip ${kind}`;
  el.innerHTML = `<span class="dot" aria-hidden="true">${s.icon}</span>${labelOverride || s.label}`;
  return el;
}

/* ---------- api ---------- */
async function api(path, options = {}) {
  const headers = options.headers || {};
  if (state.token) headers["X-Auth-Token"] = state.token;
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401 && path !== "/api/login") {
    logout();
    throw new Error("Session expired — please sign in again.");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
}

/* ---------- views ---------- */
function show(view) {
  for (const id of ["view-login", "view-upload", "view-dashboard"]) {
    $(`#${id}`).hidden = id !== view;
  }
  $("#userbox").hidden = view === "view-login";
}

function logout() {
  sessionStorage.clear();
  state.token = null;
  state.email = null;
  state.uploaded.clear();
  show("view-login");
}

/* ---------- login ---------- */
$("#login-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  $("#login-error").textContent = "";
  try {
    const body = await api("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: $("#email").value, ps_number: $("#ps").value }),
    });
    state.token = body.token;
    state.email = body.email;
    sessionStorage.setItem("twincheck_token", body.token);
    sessionStorage.setItem("twincheck_email", body.email);
    $("#user-email").textContent = body.email;
    buildUploadCards();
    show("view-upload");
  } catch (err) {
    $("#login-error").textContent = err.message;
  }
});

$("#btn-logout").addEventListener("click", logout);

/* ---------- upload ---------- */
function buildUploadCards() {
  const grid = $("#upload-grid");
  grid.innerHTML = "";
  for (const d of DISCIPLINES) {
    const card = document.createElement("div");
    card.className = "card upload-card";
    card.innerHTML = `
      <h3>${d.title} agent</h3>
      <div class="discipline-sub">${d.sub}</div>
      <label class="drop" id="drop-${d.id}">
        <input type="file" accept=".xlsx" id="file-${d.id}">
        <span id="drop-text-${d.id}">Click to choose the .xlsx deliverable<br>or drop it here</span>
      </label>
      <div class="actions">
        <button class="btn primary" id="btn-${d.id}" disabled>Analyze</button>
        <a class="sample-link" href="/api/samples/${d.sample}" download>Download sample deliverable</a>
      </div>
      <div class="upload-result" id="result-${d.id}"></div>`;
    grid.appendChild(card);

    const input = card.querySelector(`#file-${d.id}`);
    const drop = card.querySelector(`#drop-${d.id}`);
    const btn = card.querySelector(`#btn-${d.id}`);

    input.addEventListener("change", () => {
      if (input.files.length) {
        card.querySelector(`#drop-text-${d.id}`).innerHTML =
          `<span class="filename">${input.files[0].name}</span>`;
        btn.disabled = false;
      }
    });
    for (const evName of ["dragover", "dragleave", "drop"]) {
      drop.addEventListener(evName, (ev) => {
        ev.preventDefault();
        drop.classList.toggle("drag", evName === "dragover");
        if (evName === "drop" && ev.dataTransfer.files.length) {
          input.files = ev.dataTransfer.files;
          input.dispatchEvent(new Event("change"));
        }
      });
    }
    btn.addEventListener("click", () => uploadFile(d.id, input, btn));
  }
}

async function uploadFile(discipline, input, btn) {
  const result = $(`#result-${discipline}`);
  result.textContent = "Analyzing…";
  btn.disabled = true;
  try {
    const form = new FormData();
    form.append("file", input.files[0]);
    const body = await api(`/api/upload/${discipline}`, { method: "POST", body: form });
    state.uploaded.add(discipline);
    result.innerHTML = "";
    const kind = body.errors ? "critical" : body.warnings ? "warning" : "good";
    const label = body.errors
      ? `${body.errors} error${body.errors > 1 ? "s" : ""}${body.warnings ? `, ${body.warnings} warning${body.warnings > 1 ? "s" : ""}` : ""}`
      : body.warnings
        ? `${body.warnings} warning${body.warnings > 1 ? "s" : ""}`
        : "No issues found";
    result.appendChild(chip(kind, label));
    result.append(` Agent analyzed ${body.filename}.`);
    $("#btn-dashboard").disabled = false;
    $("#upload-status-line").textContent = state.uploaded.size === 3
      ? "All three deliverables analyzed — the twin can validate end-to-end."
      : `${state.uploaded.size}/3 deliverables analyzed. Cross-discipline checks need all three.`;
  } catch (err) {
    result.textContent = err.message;
  } finally {
    btn.disabled = false;
  }
}

$("#btn-dashboard").addEventListener("click", () => loadDashboard());
$("#btn-back").addEventListener("click", () => show("view-upload"));
$("#btn-refresh").addEventListener("click", () => loadDashboard());

/* ---------- dashboard ---------- */
async function loadDashboard() {
  show("view-dashboard");
  try {
    const data = await api("/api/dashboard");
    renderTiles(data);
    renderPower(data.twin.power_chain);
    renderCooling(data.twin.cooling_chain);
    renderSummary(data.summary);
    renderFindings(data.findings);
  } catch (err) {
    alert(err.message);
  }
}

function renderTiles(data) {
  const errors = data.findings.filter((f) => f.severity === "error").length;
  const warnings = data.findings.filter((f) => f.severity === "warning").length;
  const uploaded = Object.values(data.disciplines).filter((d) => d.uploaded).length;
  const verdict = errors ? "critical" : warnings ? "warning" : uploaded ? "good" : "neutral";
  const verdictText = errors ? "Failed" : warnings ? "Review" : uploaded ? "Passed" : "No data";

  const tiles = [
    { label: "Design verdict", value: verdictText, chipKind: verdict, chipLabel: errors ? `${errors} blocking issue${errors > 1 ? "s" : ""}` : warnings ? "warnings only" : "all checks green" },
    { label: "Errors", value: errors, chipKind: errors ? "critical" : "good", chipLabel: errors ? "must fix" : "none" },
    { label: "Warnings", value: warnings, chipKind: warnings ? "warning" : "good", chipLabel: warnings ? "review" : "none" },
    { label: "Deliverables analyzed", value: `${uploaded}/3`, chipKind: uploaded === 3 ? "good" : "warning", chipLabel: uploaded === 3 ? "twin complete" : "twin partial" },
  ];
  const wrap = $("#tiles");
  wrap.innerHTML = "";
  for (const t of tiles) {
    const el = document.createElement("div");
    el.className = "tile";
    el.innerHTML = `<div class="tile-label">${t.label}</div><div class="tile-value">${t.value}</div>`;
    const note = document.createElement("div");
    note.className = "tile-note";
    note.appendChild(chip(t.chipKind, t.chipLabel));
    el.appendChild(note);
    wrap.appendChild(el);
  }
}

function meter({ title, loadKw, capacityKw, note }) {
  const el = document.createElement("div");
  el.className = "meter";
  if (!capacityKw) {
    el.innerHTML = `<div class="meter-head"><span class="meter-title">${title}</span></div>
      <div class="meter-empty">No capacity data in the uploaded deliverables.</div>`;
    return el;
  }
  const ratio = loadKw / capacityKw;
  const kind = ratio > 1 ? "critical" : ratio > 0.9 ? "warning" : "good";
  const label = ratio > 1 ? "Over capacity" : ratio > 0.9 ? "Near limit" : "OK";
  const pct = Math.min(ratio, 1) * 100;

  el.innerHTML = `
    <div class="meter-head">
      <span class="meter-title">${title}</span>
      <span class="meter-values">${fmt(loadKw)} / ${fmt(capacityKw)} kW · ${(ratio * 100).toFixed(0)}%</span>
    </div>
    <div class="track" title="${title}: load ${fmt(loadKw)} kW of ${fmt(capacityKw)} kW capacity">
      <div class="fill ${kind}" style="width:${pct}%"></div>
    </div>
    <div class="meter-foot"><span class="meter-note">${note || ""}</span></div>`;
  el.querySelector(".meter-foot").appendChild(chip(kind, label));
  return el;
}

function fmt(n) {
  return Number(n).toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function renderPower(chain) {
  const wrap = $("#power-meters");
  wrap.innerHTML = "";
  if (!chain) {
    wrap.innerHTML = `<div class="meter-empty">Upload the electrical deliverable to model the power chain.</div>`;
    return;
  }
  wrap.appendChild(meter({
    title: "Utility feed",
    loadKw: chain.facility_load_kw, capacityKw: chain.utility_kw,
    note: "Facility load (IT + 30% auxiliaries) vs utility capacity",
  }));
  wrap.appendChild(meter({
    title: `Transformers (${(chain.transformers || []).map((t) => t.tag).join(", ") || "—"})`,
    loadKw: chain.facility_load_kw, capacityKw: chain.transformer_kw,
    note: "Facility load vs usable transformer capacity",
  }));
  wrap.appendChild(meter({
    title: `UPS (${(chain.ups || []).map((u) => u.tag).join(", ") || "—"})`,
    loadKw: chain.it_load_kw, capacityKw: chain.ups_kw,
    note: "Critical IT load vs installed UPS capacity",
  }));
}

function renderCooling(chain) {
  const wrap = $("#cooling-meters");
  wrap.innerHTML = "";
  if (!chain) {
    wrap.innerHTML = `<div class="meter-empty">Upload the mechanical deliverable to model the cooling chain.</div>`;
    return;
  }
  const tags = (chain.chillers || []).map((c) => c.tag).join(", ") || "—";
  wrap.appendChild(meter({
    title: `Installed cooling (${tags})`,
    loadKw: chain.heat_load_kw, capacityKw: chain.cooling_capacity_kw,
    note: "IT heat load vs total chiller capacity",
  }));
  wrap.appendChild(meter({
    title: "N+1 scenario (largest chiller lost)",
    loadKw: chain.heat_load_kw, capacityKw: chain.n_plus_1_capacity_kw,
    note: "Heat load vs remaining capacity after one failure",
  }));
}

function renderSummary(summary) {
  const card = $("#summary-card");
  if (!summary) { card.hidden = true; return; }
  card.hidden = false;
  $("#summary-source").textContent = summary.source === "claude" ? "Claude AI" : "rule-based";
  $("#summary-text").textContent = summary.text;
}

function renderFindings(findings) {
  const tbody = $("#findings-table tbody");
  tbody.innerHTML = "";
  $("#findings-count").textContent = `${findings.length} total`;
  if (!findings.length) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="5">No findings — all checks passed.</td></tr>`;
    return;
  }
  for (const f of findings) {
    const tr = document.createElement("tr");
    const sevKind = f.severity === "error" ? "critical" : f.severity === "warning" ? "warning" : "neutral";
    const sevTd = document.createElement("td");
    sevTd.appendChild(chip(sevKind, f.severity));
    tr.appendChild(sevTd);
    tr.insertAdjacentHTML("beforeend", `
      <td>${f.discipline}</td>
      <td class="finding-title">${escapeHtml(f.title)}</td>
      <td class="finding-detail">${escapeHtml(f.detail)}</td>
      <td class="loc">${escapeHtml(f.location)}</td>`);
    tbody.appendChild(tr);
  }
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

/* ---------- boot ---------- */
if (state.token) {
  $("#user-email").textContent = state.email || "";
  buildUploadCards();
  show("view-upload");
} else {
  show("view-login");
}
