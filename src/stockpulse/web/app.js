const state = { days: 30, messageCursor: null, messageHasMore: false, failedRunsOnly: false, metrics: [] };
const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
  $("range-select").addEventListener("change", (event) => {
    state.days = event.target.value === "all" ? null : Number(event.target.value);
    loadDashboard();
  });
  $("refresh-button").addEventListener("click", loadDashboard);
  $("message-filters").addEventListener("submit", (event) => {
    event.preventDefault();
    loadMessages(true);
  });
  $("clear-filters").addEventListener("click", () => {
    $("message-filters").reset();
    loadMessages(true);
  });
  $("load-more").addEventListener("click", () => loadMessages(false));
  $("show-failed-runs").addEventListener("click", () => {
    state.failedRunsOnly = !state.failedRunsOnly;
    $("show-failed-runs").textContent = state.failedRunsOnly ? "Show all runs" : "Show failed only";
    loadRuns();
  });
  window.addEventListener("resize", debounce(() => drawTrendChart(state.metrics), 120));
  loadDashboard();
});

async function loadDashboard() {
  setBusy(true);
  clearError();
  const range = dateRange();
  try {
    const [ready, overview, metrics, topics, anomalies] = await Promise.all([
      api("/api/v1/ready", {}, true),
      api("/api/v1/overview"),
      api("/api/v1/metrics/sentiment", range),
      api("/api/v1/topics"),
      api("/api/v1/anomalies", { limit: 1 }),
    ]);
    renderSystem(ready);
    renderOverview(overview);
    state.metrics = metrics.data || [];
    drawTrendChart(state.metrics);
    renderTopics(topics.data || []);
    renderAnomaly((anomalies.data || [])[0] || overview.latest_anomaly);
    populateTopicFilter(topics.data || []);
    await Promise.all([loadMessages(true), loadRuns()]);
  } catch (error) {
    showError(error.message || "Dashboard data could not be loaded.");
    renderSystem(null, true);
  } finally {
    setBusy(false);
  }
}

async function api(path, params = {}, allowUnavailable = false) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") url.searchParams.set(key, value);
  });
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    if (allowUnavailable && response.status === 503) return null;
    throw new Error(payload.error?.message || `Request failed (${response.status})`);
  }
  return response.json();
}

function renderSystem(ready, hardError = false) {
  const dot = $("nav-status-dot");
  dot.className = hardError ? "error" : ready ? "ready" : "error";
  $("nav-status").textContent = hardError ? "API unavailable" : ready ? "System ready" : "Database not ready";
}

function renderOverview(data) {
  const metric = data.latest_metric;
  if (!metric) {
    $("freshness").textContent = "No analyzed history yet";
    return;
  }
  const score = Number(metric.sentiment_score || 0);
  $("sentiment-score").textContent = signed(score);
  $("sentiment-label").textContent = score > .1 ? "Bullish direction" : score < -.1 ? "Bearish direction" : "Balanced direction";
  $("message-volume").textContent = number(metric.analyzed_count);
  $("confidence").textContent = percent(metric.average_confidence);
  $("low-confidence").textContent = `${number(metric.low_confidence_count)} low-confidence`;
  $("bullish-count").textContent = number(metric.bullish_count);
  $("bearish-count").textContent = number(metric.bearish_count);
  const total = Math.max(Number(metric.analyzed_count || 0), 1);
  $("bullish-bar").style.width = `${100 * Number(metric.bullish_count || 0) / total}%`;
  $("neutral-bar").style.width = `${100 * Number(metric.neutral_count || 0) / total}%`;
  $("bearish-bar").style.width = `${100 * Number(metric.bearish_count || 0) / total}%`;
  $("freshness").textContent = `Latest metric · ${formatDate(metric.stat_date)}`;
  const anomaly = data.latest_anomaly;
  $("anomaly-status").textContent = anomaly ? title(anomaly.status) : "Not evaluated";
  $("anomaly-summary").textContent = anomaly?.signals?.length ? anomaly.signals.map(title).join(" · ") : "No active signal";
}

function renderTopics(rows) {
  const container = $("topics-list");
  if (!rows.length) {
    container.innerHTML = '<div class="empty-state">No topic assignments yet.</div>';
    return;
  }
  const top = rows.slice(0, 8);
  const max = Math.max(...top.map((row) => Number(row.message_count || 0)), 1);
  container.innerHTML = top.map((row) => `
    <div class="topic-item">
      <span class="topic-name">${escapeHtml(row.topic)}</span>
      <span class="topic-value">${number(row.message_count)} · ${percent(row.average_score)}</span>
      <div class="topic-track"><i style="width:${Math.max(4, 100 * Number(row.message_count || 0) / max)}%"></i></div>
    </div>`).join("");
}

function renderAnomaly(item) {
  const badge = $("anomaly-badge");
  if (!item) {
    badge.className = "badge muted";
    badge.textContent = "Not evaluated";
    $("anomaly-explanation").textContent = "No anomaly evaluation is stored for the current analysis version.";
    $("anomaly-details").innerHTML = "";
    return;
  }
  badge.className = `badge ${item.status === "anomaly" ? "anomaly" : ""}`;
  badge.textContent = title(item.status);
  $("anomaly-explanation").textContent = item.explanation;
  $("anomaly-details").innerHTML = [
    ["History", `${number(item.history_days)} days`],
    ["Volume ratio", item.volume_ratio == null ? "—" : `${Number(item.volume_ratio).toFixed(2)}×`],
    ["Sentiment shift", item.sentiment_shift == null ? "—" : signed(item.sentiment_shift)],
    ["Topic shift", item.shifted_topic || "—"],
  ].map(([term, value]) => `<div><dt>${term}</dt><dd>${escapeHtml(value)}</dd></div>`).join("");
}

async function loadMessages(reset) {
  if (reset) state.messageCursor = null;
  const range = dateRange();
  const params = {
    ...range,
    limit: 20,
    cursor: reset ? null : state.messageCursor,
    query: $("message-query").value.trim(),
    ai_sentiment: $("message-sentiment").value,
    topic: $("message-topic").value,
  };
  try {
    const payload = await api("/api/v1/messages", params);
    const rows = payload.data || [];
    renderMessages(rows, !reset);
    state.messageCursor = payload.meta.next_cursor;
    state.messageHasMore = payload.meta.has_more;
    $("load-more").hidden = !state.messageHasMore;
    $("messages-state").textContent = rows.length ? `${rows.length} message${rows.length === 1 ? "" : "s"} on this page` : "No messages match these filters";
    $("message-count-label").textContent = state.messageHasMore ? "More results available" : "End of results";
  } catch (error) {
    $("messages-state").textContent = error.message;
    if (reset) renderMessages([], false);
  }
}

function renderMessages(rows, append) {
  const body = $("messages-body");
  if (!append) body.innerHTML = "";
  if (!rows.length && !append) {
    body.innerHTML = '<tr><td colspan="6"><div class="empty-state">No messages to display.</div></td></tr>';
    return;
  }
  body.insertAdjacentHTML("beforeend", rows.map((row) => {
    const confidence = row.ai_confidence == null ? "—" : percent(row.ai_confidence);
    const topics = (row.topics || []).map((topic) => `<span class="tag">${escapeHtml(topic.topic)}</span>`).join("") || '<span class="tag">Unassigned</span>';
    const url = safeUrl(row.url);
    return `<tr>
      <td class="message-cell"><strong>${escapeHtml(row.body)}</strong><small>@${escapeHtml(row.username || "unknown")}</small></td>
      <td><span class="signal ${String(row.ai_sentiment || "neutral").toLowerCase()}">${escapeHtml(row.ai_sentiment || "Pending")}</span><br><small>${confidence}</small></td>
      <td>${escapeHtml(row.stocktwits_sentiment || "Unlabeled")}</td>
      <td>${topics}</td><td>${formatDateTime(row.created_at)}</td>
      <td>${url ? `<a class="source-link" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Open ↗</a>` : "—"}</td>
    </tr>`;
  }).join(""));
}

async function loadRuns() {
  try {
    const payload = await api("/api/v1/runs", { limit: 20, status: state.failedRunsOnly ? "failed" : null });
    renderRuns(payload.data || []);
  } catch (error) {
    $("runs-body").innerHTML = `<tr><td colspan="6">${escapeHtml(error.message)}</td></tr>`;
  }
}

function renderRuns(rows) {
  const body = $("runs-body");
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="6"><div class="empty-state">No runs match this view.</div></td></tr>';
    return;
  }
  body.innerHTML = rows.map((row) => `<tr>
    <td>${formatDateTime(row.started_at)}</td><td>${escapeHtml(title(row.action))}</td>
    <td><span class="badge ${escapeHtml(row.status)}">${escapeHtml(title(row.status))}</span></td>
    <td>${number(row.message_count)}</td><td>${number(row.inserted_count)} / ${number(row.duplicate_count)}</td>
    <td>${duration(row.started_at, row.finished_at)}</td>
  </tr>`).join("");
}

function drawTrendChart(rows) {
  const canvas = $("trend-chart");
  const empty = $("chart-empty");
  if (!rows.length) { canvas.hidden = true; empty.hidden = false; return; }
  canvas.hidden = false; empty.hidden = true;
  const rect = canvas.getBoundingClientRect();
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.max(320, rect.width * ratio); canvas.height = Math.max(220, rect.height * ratio);
  const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio);
  const width = canvas.width / ratio, height = canvas.height / ratio;
  const pad = { left: 42, right: 18, top: 18, bottom: 28 };
  const chartW = width - pad.left - pad.right, chartH = height - pad.top - pad.bottom;
  const maxVolume = Math.max(...rows.map((r) => Number(r.analyzed_count || 0)), 1);
  ctx.clearRect(0, 0, width, height); ctx.font = "10px system-ui"; ctx.fillStyle = "#6f837c";
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + chartH * i / 4;
    ctx.strokeStyle = "rgba(220,239,232,.08)"; ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(width - pad.right, y); ctx.stroke();
    ctx.fillText((1 - i * .5).toFixed(1), 7, y + 3);
  }
  const step = chartW / Math.max(rows.length, 1);
  rows.forEach((row, index) => {
    const barH = chartH * .55 * Number(row.analyzed_count || 0) / maxVolume;
    ctx.fillStyle = "rgba(127,151,143,.18)";
    ctx.fillRect(pad.left + index * step + step * .18, pad.top + chartH - barH, Math.max(2, step * .64), barH);
  });
  ctx.strokeStyle = "#65e3ad"; ctx.lineWidth = 2; ctx.beginPath();
  rows.forEach((row, index) => {
    const x = pad.left + step * (index + .5);
    const y = pad.top + (1 - (Number(row.sentiment_score || 0) + 1) / 2) * chartH;
    index ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
  const labels = rows.length > 4 ? [0, Math.floor((rows.length - 1) / 2), rows.length - 1] : rows.map((_, i) => i);
  labels.forEach((index) => { const text = String(rows[index].stat_date).slice(5); const x = pad.left + step * (index + .5); ctx.fillStyle = "#6f837c"; ctx.fillText(text, x - 13, height - 7); });
}

function populateTopicFilter(rows) {
  const select = $("message-topic"), current = select.value;
  select.innerHTML = '<option value="">All topics</option>' + rows.map((row) => `<option>${escapeHtml(row.topic)}</option>`).join("");
  if ([...select.options].some((option) => option.value === current)) select.value = current;
}

function dateRange() {
  if (!state.days) return {};
  const end = new Date(), start = new Date(); start.setUTCDate(end.getUTCDate() - state.days + 1);
  return { start_date: isoDate(start), end_date: isoDate(end) };
}
function isoDate(value) { return value.toISOString().slice(0, 10); }
function formatDate(value) { if (!value) return "—"; return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(new Date(`${String(value).slice(0,10)}T00:00:00Z`)); }
function formatDateTime(value) { if (!value) return "—"; return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC", timeZoneName: "short" }).format(new Date(value)); }
function number(value) { return new Intl.NumberFormat().format(Number(value || 0)); }
function percent(value) { return value == null ? "—" : `${(100 * Number(value)).toFixed(1)}%`; }
function signed(value) { const n = Number(value || 0); return `${n >= 0 ? "+" : ""}${n.toFixed(2)}`; }
function title(value) { return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }
function duration(start, end) { if (!start || !end) return "In progress"; const seconds = Math.max(0, (new Date(end) - new Date(start)) / 1000); return seconds < 60 ? `${Math.round(seconds)}s` : `${Math.round(seconds / 60)}m`; }
function safeUrl(value) { try { const url = new URL(value); return url.protocol === "https:" ? url.href : ""; } catch { return ""; } }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char])); }
function setBusy(value) { $("refresh-button").disabled = value; $("refresh-button").textContent = value ? "Refreshing…" : "Refresh data"; }
function showError(message) { const box = $("global-error"); box.hidden = false; box.textContent = message; }
function clearError() { $("global-error").hidden = true; $("global-error").textContent = ""; }
function debounce(fn, delay) { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); }; }
