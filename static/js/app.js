const els = {
  dropzone: document.getElementById("dropzone"),
  fileInput: document.getElementById("fileInput"),
  browseBtn: document.getElementById("browseBtn"),
  sampleBtn: document.getElementById("sampleBtn"),
  fileMeta: document.getElementById("fileMeta"),
  errorBox: document.getElementById("errorBox"),
  warnBox: document.getElementById("warnBox"),
  results: document.getElementById("results"),
  kpiGrid: document.getElementById("kpiGrid"),
  campaignTable: document.getElementById("campaignTable"),
  channelPanel: document.getElementById("channelPanel"),
  detected: document.getElementById("detected"),
  loading: document.getElementById("loading"),
};

let campaignChart = null;
let channelChart = null;

const NUMBER = new Intl.NumberFormat("en-US");
const MONEY = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

function fmtInt(v) {
  return v == null ? "—" : NUMBER.format(Math.round(v));
}
function fmtMoney(v) {
  return v == null ? "—" : MONEY.format(v);
}
function fmtPct(v) {
  return v == null ? "—" : `${v.toFixed(2)}%`;
}
function fmtX(v) {
  return v == null ? "—" : `${v.toFixed(2)}×`;
}

function show(el) { el.hidden = false; }
function hide(el) { el.hidden = true; }

function setError(msg) {
  if (!msg) { hide(els.errorBox); return; }
  els.errorBox.textContent = msg;
  show(els.errorBox);
}

async function uploadFile(file) {
  setError(null);
  els.fileMeta.textContent = `${file.name} · ${(file.size / 1024).toFixed(1)} KB`;
  show(els.loading);

  const form = new FormData();
  form.append("file", file);

  try {
    const res = await fetch("/api/analyze", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) {
      setError(data.error || "Something went wrong analyzing the file.");
      hide(els.results);
      return;
    }
    render(data);
  } catch (err) {
    setError(`Network error: ${err.message}`);
  } finally {
    hide(els.loading);
  }
}

function kpiCard(label, value, sub) {
  return `<div class="kpi">
    <div class="kpi__label">${label}</div>
    <div class="kpi__value">${value}</div>
    <div class="kpi__sub">${sub || ""}</div>
  </div>`;
}

function render(data) {
  setError(null);

  // KPI cards.
  const t = data.totals || {};
  const k = data.kpis || {};
  const cards = [];
  if (t.impressions != null) cards.push(kpiCard("Impressions", fmtInt(t.impressions), "total shown"));
  if (t.clicks != null) cards.push(kpiCard("Clicks", fmtInt(t.clicks), k.ctr != null ? `${fmtPct(k.ctr)} CTR` : ""));
  if (t.spend != null) cards.push(kpiCard("Spend", fmtMoney(t.spend), k.cpc != null ? `${fmtMoney(k.cpc)} CPC` : ""));
  if (t.conversions != null) cards.push(kpiCard("Conversions", fmtInt(t.conversions), k.conversion_rate != null ? `${fmtPct(k.conversion_rate)} CVR` : ""));
  if (k.cpa != null) cards.push(kpiCard("CPA", fmtMoney(k.cpa), "cost per acquisition"));
  if (t.revenue != null) cards.push(kpiCard("Revenue", fmtMoney(t.revenue), k.roas != null ? `${fmtX(k.roas)} ROAS` : ""));
  if (k.cpm != null) cards.push(kpiCard("CPM", fmtMoney(k.cpm), "cost per 1k impr."));
  els.kpiGrid.innerHTML = cards.join("") || `<div class="kpi"><div class="kpi__value">${fmtInt(data.row_count)}</div><div class="kpi__sub">rows analyzed</div></div>`;

  // Campaign breakdown.
  const campaigns = (data.breakdowns && data.breakdowns.campaign) || [];
  renderCampaignTable(campaigns, data.detected_columns);
  renderCampaignChart(campaigns);

  // Channel breakdown.
  const channels = (data.breakdowns && data.breakdowns.channel) || [];
  if (channels.length) {
    show(els.channelPanel);
    renderChannelChart(channels);
  } else {
    hide(els.channelPanel);
  }

  // Detected columns.
  els.detected.innerHTML = Object.entries(data.detected_columns || {})
    .map(([canonical, actual]) => `<span class="chip"><b>${canonical}</b> ← ${actual}</span>`)
    .join("") || `<span class="chip">No standard columns detected</span>`;

  // Warnings.
  if (data.warnings && data.warnings.length) {
    els.warnBox.innerHTML = data.warnings.map((w) => `• ${w}`).join("<br/>");
    show(els.warnBox);
  } else {
    hide(els.warnBox);
  }

  show(els.results);
  els.results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderCampaignTable(rows, detected) {
  if (!rows.length) {
    els.campaignTable.innerHTML = "<tbody><tr><td>No campaign column detected.</td></tr></tbody>";
    return;
  }
  const has = (m) => detected && Object.prototype.hasOwnProperty.call(detected, m);
  const head = ["Campaign", "Rows"];
  if (has("impressions")) head.push("Impr.");
  if (has("clicks")) head.push("Clicks");
  head.push("CTR");
  if (has("spend")) head.push("Spend");
  if (has("conversions")) head.push("Conv.");
  head.push("CPA");
  if (has("revenue")) head.push("Revenue", "ROAS");

  const thead = `<thead><tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr></thead>`;
  const body = rows.map((r) => {
    const cells = [`<td>${r.name}</td>`, `<td>${fmtInt(r.rows)}</td>`];
    if (has("impressions")) cells.push(`<td>${fmtInt(r.impressions)}</td>`);
    if (has("clicks")) cells.push(`<td>${fmtInt(r.clicks)}</td>`);
    cells.push(`<td>${fmtPct(r.ctr)}</td>`);
    if (has("spend")) cells.push(`<td>${fmtMoney(r.spend)}</td>`);
    if (has("conversions")) cells.push(`<td>${fmtInt(r.conversions)}</td>`);
    cells.push(`<td>${fmtMoney(r.cpa)}</td>`);
    if (has("revenue")) cells.push(`<td>${fmtMoney(r.revenue)}</td>`, `<td>${fmtX(r.roas)}</td>`);
    return `<tr>${cells.join("")}</tr>`;
  }).join("");

  els.campaignTable.innerHTML = `${thead}<tbody>${body}</tbody>`;
}

function baseChartOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: "#cbd5f5" } },
    },
    scales: {
      x: { ticks: { color: "#94a3c8" }, grid: { color: "rgba(148,163,200,0.1)" } },
      y: { ticks: { color: "#94a3c8" }, grid: { color: "rgba(148,163,200,0.1)" } },
    },
  };
}

function renderCampaignChart(rows) {
  const ctx = document.getElementById("campaignChart");
  if (campaignChart) campaignChart.destroy();
  const top = rows.slice(0, 8);
  const metric = top.some((r) => r.spend != null) ? "spend" : "impressions";
  campaignChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: top.map((r) => r.name),
      datasets: [{
        label: metric === "spend" ? "Spend ($)" : "Impressions",
        data: top.map((r) => r[metric] ?? 0),
        backgroundColor: "rgba(109,139,255,0.7)",
        borderRadius: 6,
      }],
    },
    options: baseChartOptions(),
  });
}

function renderChannelChart(rows) {
  const ctx = document.getElementById("channelChart");
  if (channelChart) channelChart.destroy();
  const metric = rows.some((r) => r.spend != null) ? "spend" : "impressions";
  const palette = ["#6d8bff", "#22d3ee", "#34d399", "#fbbf24", "#fb7185", "#a78bfa", "#f472b6"];
  channelChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: rows.map((r) => r.name),
      datasets: [{
        data: rows.map((r) => r[metric] ?? 0),
        backgroundColor: rows.map((_, i) => palette[i % palette.length]),
        borderColor: "#0b1020",
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "right", labels: { color: "#cbd5f5" } } },
    },
  });
}

// --- Event wiring ---------------------------------------------------------
els.browseBtn.addEventListener("click", () => els.fileInput.click());
els.fileInput.addEventListener("change", (e) => {
  if (e.target.files.length) uploadFile(e.target.files[0]);
});

els.sampleBtn.addEventListener("click", async () => {
  setError(null);
  show(els.loading);
  try {
    const res = await fetch("/static/sample/marketing_sample.csv");
    const blob = await res.blob();
    const file = new File([blob], "marketing_sample.csv", { type: "text/csv" });
    await uploadFile(file);
  } catch (err) {
    setError(`Could not load sample data: ${err.message}`);
    hide(els.loading);
  }
});

["dragenter", "dragover"].forEach((evt) =>
  els.dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    els.dropzone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach((evt) =>
  els.dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    els.dropzone.classList.remove("dragover");
  })
);
els.dropzone.addEventListener("drop", (e) => {
  if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
});
