/* Monsoon Twin frontend — scenario controls + live digital twin dashboard */

const POLL_MS = 2000;

const ELECTRICAL_FAULTS = [
  ["flood", "Flood / water ingress"],
  ["earth_fault", "Earth-fault alarm"],
  ["breaker_trip", "Trip breaker"],
  ["ups_fail", "UPS/DG unavailable"],
  ["ir_decline", "IR declining"],
  ["clear", "Clear faults"],
];
const PROCESS_FAULTS = [
  ["trip_duty_pump", "Trip duty pump"],
  ["block_pump", "Block pump (low flow)"],
  ["high_level", "Force high level"],
  ["clear", "Clear faults"],
];

const state = { assets: null, paused: false };

const $ = (sel) => document.querySelector(sel);

const STATUS = {
  good: { icon: "✔", label: "OK" },
  warning: { icon: "▲", label: "Attention" },
  critical: { icon: "✖", label: "Failed" },
  neutral: { icon: "—", label: "N/A" },
};
const RISK_TO_CHIP = { low: "good", medium: "warning", high: "critical" };

function chipInner(kind, label) {
  const s = STATUS[kind] || STATUS.neutral;
  return `<span class="dot" aria-hidden="true">${s.icon}</span>${label ?? s.label}`;
}
function chip(kind, label) {
  return `<span class="chip ${kind}">${chipInner(kind, label)}</span>`;
}
function setChip(el, kind, label) {
  el.className = `chip ${kind}`;
  el.innerHTML = chipInner(kind, label);
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function api(path, options = {}) {
  const res = await fetch(path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
}
async function postJson(path, body) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/* ---------- controls ---------- */
function setActiveSeg(groupId, attr, value) {
  document.querySelectorAll(`#${groupId} .seg`).forEach((btn) => {
    btn.classList.toggle("active", btn.dataset[attr] === String(value));
  });
}

$("#rainfall-group").addEventListener("click", async (ev) => {
  const btn = ev.target.closest("button[data-rainfall]");
  if (!btn) return;
  await postJson("/api/control/rainfall", { level: btn.dataset.rainfall });
  setActiveSeg("rainfall-group", "rainfall", btn.dataset.rainfall);
});

$("#speed-group").addEventListener("click", async (ev) => {
  const btn = ev.target.closest("button[data-speed]");
  if (!btn) return;
  const speed = Number(btn.dataset.speed);
  await postJson("/api/control/speed", { speed });
  setActiveSeg("speed-group", "speed", speed);
});

$("#btn-pause").addEventListener("click", async () => {
  state.paused = !state.paused;
  await postJson("/api/control/pause", { paused: state.paused });
  $("#btn-pause").textContent = state.paused ? "▶ Resume" : "⏸ Pause";
});

$("#btn-reset").addEventListener("click", async () => {
  await api("/api/control/reset", { method: "POST" });
  state.paused = false;
  $("#btn-pause").textContent = "⏸ Pause";
  setActiveSeg("rainfall-group", "rainfall", "calm");
  setActiveSeg("speed-group", "speed", 10);
  await refresh();
});

function buildFaultControls(assets) {
  const wrap = $("#fault-group");
  const assetSelect = document.createElement("select");
  assetSelect.className = "ctl";
  assetSelect.id = "fault-asset";
  const electricalGroup = document.createElement("optgroup");
  electricalGroup.label = "Electrical";
  const processGroup = document.createElement("optgroup");
  processGroup.label = "Process";
  for (const a of assets.electrical) {
    electricalGroup.innerHTML += `<option value="${a.id}">${a.label}</option>`;
  }
  for (const a of assets.process) {
    processGroup.innerHTML += `<option value="${a.id}">${a.label}</option>`;
  }
  assetSelect.append(electricalGroup, processGroup);

  const faultSelect = document.createElement("select");
  faultSelect.className = "ctl";
  faultSelect.id = "fault-type";

  const injectBtn = document.createElement("button");
  injectBtn.className = "btn primary";
  injectBtn.textContent = "Inject";

  const clearBtn = document.createElement("button");
  clearBtn.className = "btn ghost";
  clearBtn.textContent = "Clear all faults";

  function populateFaultTypes() {
    const isElectrical = assets.electrical.some((a) => a.id === assetSelect.value);
    const options = isElectrical ? ELECTRICAL_FAULTS : PROCESS_FAULTS;
    faultSelect.innerHTML = options.map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
  }
  assetSelect.addEventListener("change", populateFaultTypes);
  populateFaultTypes();

  injectBtn.addEventListener("click", async () => {
    await postJson("/api/control/fault", { asset_id: assetSelect.value, fault_type: faultSelect.value });
    await refresh();
  });
  clearBtn.addEventListener("click", async () => {
    const all = [...assets.electrical, ...assets.process];
    await Promise.all(all.map((a) => postJson("/api/control/fault", { asset_id: a.id, fault_type: "clear" })));
    await refresh();
  });

  wrap.append(assetSelect, faultSelect, injectBtn, clearBtn);
}

/* ---------- rendering ---------- */
function fmtClock(simMinutes) {
  const total = Math.round(simMinutes);
  const day = Math.floor(total / 1440);
  const hh = String(Math.floor((total % 1440) / 60)).padStart(2, "0");
  const mm = String(total % 60).padStart(2, "0");
  return `Day ${day}, ${hh}:${mm}`;
}

function param(label, valueHtml, flagged) {
  return `<div><div class="muted">${label}</div><div class="param-val${flagged ? " flagged" : ""}">${valueHtml}</div></div>`;
}

function electricalCard(asset, riskLevel) {
  const chipKind = RISK_TO_CHIP[riskLevel] || "neutral";
  return `
    <div class="asset-card">
      <div class="asset-head">
        <span class="asset-title">${escapeHtml(asset.label)}</span>
        ${chip(chipKind, (riskLevel || "n/a").toUpperCase())}
      </div>
      <div class="asset-params">
        ${param("Water level", `${asset.water_level_m.toFixed(2)} m`, asset.water_level_m > 0.5)}
        ${param("Humidity", `${asset.humidity_pct.toFixed(0)}%`, asset.humidity_pct > 85)}
        ${param("Water ingress", asset.water_ingress ? "ALERT" : "Normal", asset.water_ingress)}
        ${param("Motor current", `${asset.motor_current_pct.toFixed(0)}%`, asset.motor_current_pct > 115)}
        ${param("Breaker", asset.breaker_status, asset.breaker_status === "tripped")}
        ${param("Leakage current", `${asset.leakage_current_ma.toFixed(0)} mA`, asset.earth_fault_alarm)}
        ${param("UPS/DG", asset.ups_dg_available ? "Available" : "Unavailable", !asset.ups_dg_available)}
        ${param("IR value", `${asset.ir_mohm.toFixed(0)} MΩ${asset.ir_trend_declining ? " ↓" : ""}`, asset.ir_mohm < 100)}
      </div>
    </div>`;
}

function processCard(asset, riskLevel) {
  const chipKind = RISK_TO_CHIP[riskLevel] || "neutral";
  const pct = Math.max(0, Math.min(100, asset.level_pct));
  const barKind = pct > 85 ? "critical" : pct > 60 ? "warning" : "";
  const rate = asset.rate_of_rise_pct_min;
  return `
    <div class="asset-card">
      <div class="asset-head">
        <span class="asset-title">${escapeHtml(asset.label)}</span>
        ${chip(chipKind, (riskLevel || "n/a").toUpperCase())}
      </div>
      <div class="asset-params">
        <div>
          <div class="muted">Level</div>
          <div class="param-val${pct > 85 ? " flagged" : ""}">${asset.level_pct.toFixed(0)}%</div>
          <div class="bar"><div class="bar-fill ${barKind}" style="width:${pct}%"></div></div>
        </div>
        ${param("Rate of rise", `${rate >= 0 ? "+" : ""}${rate.toFixed(2)}%/min`, rate > 1.0)}
        ${param("Duty pump", asset.duty_pump_status, asset.duty_pump_status === "trip")}
        ${param("Standby pump", asset.standby_pump_status, false)}
        ${param("Discharge pressure", `${asset.pump_discharge_bar.toFixed(1)} bar`, asset.duty_pump_status !== "off" && asset.pump_discharge_bar < 2.0)}
        ${param("Flow", `${asset.pump_flow_m3h.toFixed(0)} m³/h`, asset.duty_pump_status !== "off" && asset.pump_flow_m3h < 40)}
        ${param("Critical equipment", asset.critical_equipment_available ? "Available" : "Unavailable", !asset.critical_equipment_available)}
      </div>
    </div>`;
}

function renderTwinPanels(snapshot, riskByAsset) {
  $("#electrical-grid").innerHTML = Object.values(snapshot.electrical)
    .map((a) => electricalCard(a, riskByAsset[a.id]?.risk_level)).join("");
  $("#process-grid").innerHTML = Object.values(snapshot.process)
    .map((a) => processCard(a, riskByAsset[a.id]?.risk_level)).join("");
}

function renderRiskTable(rows) {
  const tbody = document.querySelector("#risk-table tbody");
  if (!rows.length) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="5">No data yet.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((r) => `
    <tr>
      <td>${chip(RISK_TO_CHIP[r.risk_level], r.risk_level.toUpperCase())}</td>
      <td class="risk-label">${escapeHtml(r.label)}</td>
      <td class="risk-problem">${escapeHtml(r.predicted_problem)}</td>
      <td class="risk-eta">${escapeHtml(r.eta_label)}</td>
      <td class="risk-action">${escapeHtml(r.recommended_action)}</td>
    </tr>`).join("");
}

function renderBriefing(risksBody) {
  $("#briefing-source").textContent = risksBody.briefing.source === "claude" ? "Claude AI" : "rule-based";
  $("#briefing-text").textContent = risksBody.briefing.text;
  setChip($("#overall-chip"), RISK_TO_CHIP[risksBody.overall_level],
    `Plant risk: ${risksBody.overall_level.toUpperCase()}`);
}

/* ---------- refresh loop ---------- */
async function refresh() {
  const [stateBody, risksBody] = await Promise.all([api("/api/state"), api("/api/risks")]);

  $("#sim-clock").textContent = fmtClock(stateBody.sim_minutes);
  $("#rainfall-mm").textContent = `${stateBody.rainfall_mm_hr} mm/hr`;
  setActiveSeg("rainfall-group", "rainfall", stateBody.rainfall_level);
  setActiveSeg("speed-group", "speed", stateBody.sim_control.speed);
  state.paused = stateBody.sim_control.paused;
  $("#btn-pause").textContent = state.paused ? "▶ Resume" : "⏸ Pause";

  const riskByAsset = Object.fromEntries(risksBody.rows.map((r) => [r.asset_id, r]));
  renderTwinPanels(stateBody, riskByAsset);
  renderRiskTable(risksBody.rows);
  renderBriefing(risksBody);
}

async function boot() {
  const stateBody = await api("/api/state");
  state.assets = {
    electrical: Object.values(stateBody.electrical).map((a) => ({ id: a.id, label: a.label })),
    process: Object.values(stateBody.process).map((a) => ({ id: a.id, label: a.label })),
  };
  buildFaultControls(state.assets);
  setActiveSeg("speed-group", "speed", 10);
  await refresh();
  setInterval(() => refresh().catch((err) => console.error(err)), POLL_MS);
}

boot().catch((err) => {
  console.error(err);
  $("#briefing-text").textContent = `Failed to load: ${err.message}`;
});
