// app.js — DOM rendering + event wiring for the Portfolio Manager dashboard.
// All backend access goes through js/api.js; this file owns state + render.

import {
  ApiError,
  getHoldings,
  createHolding,
  updateHolding,
  deleteHolding,
  refreshHoldingPrice,
  refreshAllPrices,
  lookupTicker,
  getPortfolioSummary,
  getPortfolioPerformance,
} from "./api.js";

// ---------------------------------------------------------------------
// State
// ---------------------------------------------------------------------

const state = {
  holdings: [],
  summary: null,
  performancePoints: null,
  editingId: null,
  rowErrors: {}, // holdingId -> message (transient, per-row refresh failures)
  activeRange: "ALL",
  perfGeometry: null, // set by renderPerformanceChart, used by the hover handler
};

// ---------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------

const $ = (sel) => document.querySelector(sel);

const el = {
  connectionBanner: $("#connection-banner"),
  connectionBannerText: $("#connection-banner-text"),
  connectionRetryBtn: $("#connection-retry-btn"),
  toastRegion: $("#toast-region"),
  asOf: $("#as-of"),
  refreshPricesBtn: $("#refresh-prices-btn"),

  heroTotalValue: $("#hero-total-value"),
  heroReturnBadge: $("#hero-return-badge"),
  heroCostBasis: $("#hero-cost-basis"),
  heroPlValue: $("#hero-pl-value"),

  rangeFilter: $("#range-filter"),
  performanceCanvas: $("#performance-canvas"),
  perfEmpty: $("#perf-empty"),
  perfTooltip: $("#perf-tooltip"),

  form: $("#holding-form"),
  formTitle: $("#form-title"),
  formError: $("#form-error"),
  formSubmitBtn: $("#form-submit-btn"),
  formCancelBtn: $("#form-cancel-btn"),
  fId: $("#f-id"),
  fSymbol: $("#f-symbol"),
  fSymbolHint: $("#f-symbol-hint"),
  fName: $("#f-name"),
  fQuantity: $("#f-quantity"),
  fCostBasis: $("#f-cost-basis"),
  fCurrentPrice: $("#f-current-price"),
  fPurchaseDate: $("#f-purchase-date"),

  holdingsCount: $("#holdings-count"),
  holdingsEmpty: $("#holdings-empty"),
  holdingsTable: $("#holdings-table"),
  holdingsTbody: $("#holdings-tbody"),
};

// ---------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------

const moneyFmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const moneyFmtCompact = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

function formatMoney(v) {
  const n = Number(v);
  return moneyFmt.format(Number.isFinite(n) ? n : 0);
}
function formatMoneyCompact(v) {
  const n = Number(v);
  return moneyFmtCompact.format(Number.isFinite(n) ? n : 0);
}
function formatSignedPercent(v) {
  const n = Number.isFinite(Number(v)) ? Number(v) : 0;
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
}
function formatQuantity(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return "0";
  return n.toLocaleString("en-US", { maximumFractionDigits: 8 });
}
function formatDateTime(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}
function formatShortDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
function getCSSVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// ---------------------------------------------------------------------
// Toasts
// ---------------------------------------------------------------------

function showToast({ title, items = [], isError = false, timeout = 7000 }) {
  const toast = document.createElement("div");
  toast.className = `toast${isError ? " toast-error" : ""}`;
  const titleEl = document.createElement("p");
  titleEl.className = "toast-title";
  titleEl.textContent = title;
  toast.appendChild(titleEl);
  if (items.length) {
    const list = document.createElement("ul");
    list.className = "toast-list";
    items.slice(0, 6).forEach((text) => {
      const li = document.createElement("li");
      li.textContent = text;
      list.appendChild(li);
    });
    toast.appendChild(list);
  }
  const closeBtn = document.createElement("button");
  closeBtn.className = "toast-close";
  closeBtn.type = "button";
  closeBtn.setAttribute("aria-label", "Dismiss");
  closeBtn.textContent = "×";
  closeBtn.addEventListener("click", () => toast.remove());
  toast.appendChild(closeBtn);

  el.toastRegion.appendChild(toast);
  if (timeout) setTimeout(() => toast.remove(), timeout);
}

// ---------------------------------------------------------------------
// Connection banner
// ---------------------------------------------------------------------

function showConnectionBanner(message) {
  el.connectionBannerText.textContent = message;
  el.connectionBanner.hidden = false;
}
function hideConnectionBanner() {
  el.connectionBanner.hidden = true;
}

// ---------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------

async function loadAll() {
  try {
    const [holdings, summary] = await Promise.all([getHoldings(), getPortfolioSummary()]);
    state.holdings = holdings;
    state.summary = summary;
    hideConnectionBanner();
    await loadPerformance();
    renderAll();
  } catch (err) {
    handleLoadError(err);
  }
}

async function loadPerformance() {
  try {
    const params = rangeToParams(state.activeRange);
    const result = await getPortfolioPerformance(params);
    state.performancePoints = result.points;
  } catch (err) {
    // Performance is secondary — don't block the rest of the dashboard.
    state.performancePoints = [];
    if (err instanceof ApiError && err.isNetworkError) {
      handleLoadError(err);
    }
  }
}

function handleLoadError(err) {
  if (err instanceof ApiError && err.isNetworkError) {
    showConnectionBanner(
      "Cannot reach the Portfolio Manager backend at http://localhost:8000. Make sure the API server is running, then retry."
    );
  } else {
    showConnectionBanner(err.message || "Something went wrong loading the dashboard.");
  }
}

function rangeToParams(range) {
  if (range === "ALL") return { limit: 2000 };
  const days = { "1M": 30, "3M": 90, "6M": 182, "1Y": 365 }[range] || 90;
  const from = new Date();
  from.setDate(from.getDate() - days);
  return { from: from.toISOString().slice(0, 10), limit: 2000 };
}

// ---------------------------------------------------------------------
// Render orchestration
// ---------------------------------------------------------------------

function renderAll() {
  renderHero();
  renderPerformanceChart();
  renderHoldingsTable();
}

function renderHero() {
  const s = state.summary;
  if (!s) return;
  el.asOf.textContent = `Prices as of ${formatDateTime(s.as_of) || "—"}`;
  el.heroTotalValue.textContent = formatMoney(s.total_market_value);
  el.heroCostBasis.textContent = formatMoney(s.total_cost_basis);
  setDeltaBadge(el.heroReturnBadge, s.total_return_percent, formatSignedPercent(s.total_return_percent));
  setDeltaBadge(el.heroPlValue, s.total_unrealized_pl, formatMoney(s.total_unrealized_pl));
}

function setDeltaBadge(node, rawValue, text) {
  const n = Number(rawValue) || 0;
  node.classList.remove("is-up", "is-down", "is-flat");
  let arrow = "–"; // en dash for flat
  if (n > 0) {
    node.classList.add("is-up");
    arrow = "▲";
  } else if (n < 0) {
    node.classList.add("is-down");
    arrow = "▼";
  } else {
    node.classList.add("is-flat");
  }
  node.textContent = `${arrow} ${text}`;
}

// ---------------------------------------------------------------------
// Canvas helper
// ---------------------------------------------------------------------

// The performance canvas is sized by CSS (`width: 100%; height: 240px`), so
// setCSSSize defaults to false to avoid an inline style permanently
// overriding that responsive rule.
function setupHiDPICanvas(canvas, cssWidth, cssHeight, setCSSSize = false) {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(cssWidth * dpr);
  canvas.height = Math.round(cssHeight * dpr);
  if (setCSSSize) {
    canvas.style.width = `${cssWidth}px`;
    canvas.style.height = `${cssHeight}px`;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return ctx;
}

// ---------------------------------------------------------------------
// Performance line chart
// ---------------------------------------------------------------------

function renderPerformanceChart() {
  const points = state.performancePoints || [];
  const canvas = el.performanceCanvas;
  const rect = canvas.getBoundingClientRect();
  const cssWidth = Math.max(rect.width || canvas.parentElement.clientWidth, 280);
  const cssHeight = 240;

  if (points.length === 0) {
    el.perfEmpty.hidden = false;
    const ctx = setupHiDPICanvas(canvas, cssWidth, cssHeight, false);
    ctx.clearRect(0, 0, cssWidth, cssHeight);
    state.perfGeometry = null;
    return;
  }
  el.perfEmpty.hidden = true;

  const ctx = setupHiDPICanvas(canvas, cssWidth, cssHeight, false);
  ctx.clearRect(0, 0, cssWidth, cssHeight);

  const padding = { top: 18, right: 12, bottom: 26, left: 58 };
  const plotW = cssWidth - padding.left - padding.right;
  const plotH = cssHeight - padding.top - padding.bottom;

  const values = points.map((p) => Number(p.total_value));
  let minV = Math.min(...values);
  let maxV = Math.max(...values);
  if (minV === maxV) {
    minV -= Math.max(1, Math.abs(minV) * 0.05);
    maxV += Math.max(1, Math.abs(maxV) * 0.05);
  }
  const rangePad = (maxV - minV) * 0.12;
  const wasNonNegative = Math.min(...values) >= 0;
  minV -= rangePad;
  maxV += rangePad;
  if (wasNonNegative && minV < 0) minV = 0;

  const xForIndex = (i) =>
    padding.left + (points.length === 1 ? plotW / 2 : (i / (points.length - 1)) * plotW);
  const yForValue = (v) => padding.top + plotH - ((v - minV) / (maxV - minV)) * plotH;

  // gridlines + y ticks
  ctx.strokeStyle = getCSSVar("--gridline");
  ctx.lineWidth = 1;
  ctx.font = "11px system-ui, -apple-system, sans-serif";
  ctx.fillStyle = getCSSVar("--text-muted");
  const tickCount = 4;
  for (let t = 0; t <= tickCount; t++) {
    const v = minV + ((maxV - minV) * t) / tickCount;
    const y = yForValue(v);
    ctx.beginPath();
    ctx.moveTo(padding.left, Math.round(y) + 0.5);
    ctx.lineTo(cssWidth - padding.right, Math.round(y) + 0.5);
    ctx.stroke();
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.fillText(formatMoneyCompact(v), padding.left - 8, y);
  }

  // area fill
  ctx.beginPath();
  points.forEach((p, i) => {
    const x = xForIndex(i);
    const y = yForValue(Number(p.total_value));
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.lineTo(xForIndex(points.length - 1), padding.top + plotH);
  ctx.lineTo(xForIndex(0), padding.top + plotH);
  ctx.closePath();
  ctx.fillStyle = getCSSVar("--series-line-fill");
  ctx.fill();

  // line
  ctx.beginPath();
  points.forEach((p, i) => {
    const x = xForIndex(i);
    const y = yForValue(Number(p.total_value));
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = getCSSVar("--series-line");
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.stroke();

  // end marker (surface ring + fill dot)
  const lastIdx = points.length - 1;
  const lastX = xForIndex(lastIdx);
  const lastY = yForValue(Number(points[lastIdx].total_value));
  ctx.beginPath();
  ctx.arc(lastX, lastY, 5, 0, Math.PI * 2);
  ctx.fillStyle = getCSSVar("--surface-1");
  ctx.fill();
  ctx.beginPath();
  ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
  ctx.fillStyle = getCSSVar("--series-line");
  ctx.fill();

  // end value label (direct label on the series endpoint)
  ctx.fillStyle = getCSSVar("--text-primary");
  ctx.font = "600 12px system-ui, -apple-system, sans-serif";
  ctx.textAlign = "right";
  ctx.textBaseline = "bottom";
  ctx.fillText(formatMoney(points[lastIdx].total_value), cssWidth - padding.right, lastY - 8);

  // x-axis endpoint date labels
  ctx.fillStyle = getCSSVar("--text-muted");
  ctx.font = "11px system-ui, -apple-system, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  ctx.fillText(formatShortDate(points[0].timestamp), padding.left, cssHeight - padding.bottom + 8);
  ctx.textAlign = "right";
  ctx.fillText(formatShortDate(points[lastIdx].timestamp), cssWidth - padding.right, cssHeight - padding.bottom + 8);

  state.perfGeometry = { points, xForIndex, yForValue, padding, plotW, plotH, cssWidth, cssHeight };
}

function drawCrosshair(idx) {
  const geo = state.perfGeometry;
  if (!geo) return;
  renderPerformanceChart(); // repaint base chart, then overlay
  const ctx = el.performanceCanvas.getContext("2d");
  const p = geo.points[idx];
  const x = geo.xForIndex(idx);
  const y = geo.yForValue(Number(p.total_value));

  ctx.save();
  ctx.strokeStyle = getCSSVar("--baseline");
  ctx.lineWidth = 1;
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  ctx.moveTo(x, geo.padding.top);
  ctx.lineTo(x, geo.padding.top + geo.plotH);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.beginPath();
  ctx.arc(x, y, 5, 0, Math.PI * 2);
  ctx.fillStyle = getCSSVar("--surface-1");
  ctx.fill();
  ctx.beginPath();
  ctx.arc(x, y, 4, 0, Math.PI * 2);
  ctx.fillStyle = getCSSVar("--series-line");
  ctx.fill();
  ctx.restore();

  el.perfTooltip.hidden = false;
  el.perfTooltip.style.left = `${x}px`;
  el.perfTooltip.style.top = `${y}px`;
  el.perfTooltip.innerHTML = `<strong>${formatMoney(p.total_value)}</strong><br>${formatShortDate(p.timestamp)}`;
}

function hideCrosshair() {
  el.perfTooltip.hidden = true;
  if (state.perfGeometry) renderPerformanceChart();
}

function wirePerformanceHover() {
  el.performanceCanvas.addEventListener("mousemove", (e) => {
    const geo = state.perfGeometry;
    if (!geo || geo.points.length === 0) return;
    const rect = el.performanceCanvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const n = geo.points.length;
    const ratio = n === 1 ? 0 : (mouseX - geo.padding.left) / geo.plotW;
    const idx = Math.min(n - 1, Math.max(0, Math.round(ratio * (n - 1))));
    drawCrosshair(idx);
  });
  el.performanceCanvas.addEventListener("mouseleave", hideCrosshair);
}

// ---------------------------------------------------------------------
// Holdings table
// ---------------------------------------------------------------------

function renderHoldingsTable() {
  const holdings = state.holdings || [];
  el.holdingsCount.textContent = holdings.length ? `${holdings.length} holding${holdings.length === 1 ? "" : "s"}` : "";

  if (holdings.length === 0) {
    el.holdingsEmpty.hidden = false;
    el.holdingsTable.hidden = true;
    return;
  }
  el.holdingsEmpty.hidden = true;
  el.holdingsTable.hidden = false;

  el.holdingsTbody.innerHTML = "";
  holdings.forEach((h) => {
    const tr = document.createElement("tr");
    const plPositive = h.unrealized_pl > 0;
    const plNegative = h.unrealized_pl < 0;
    const plClass = plPositive ? "is-up" : plNegative ? "is-down" : "is-flat";

    const updatedLabel = h.last_price_updated_at ? formatDateTime(h.last_price_updated_at) : "Not refreshed";

    tr.innerHTML = `
      <td>
        <div class="holding-name-cell">
          <span class="holding-symbol">${escapeHtml(h.symbol)}</span>
          <span class="holding-name-sub">${escapeHtml(h.name)}</span>
        </div>
      </td>
      <td class="num">${formatQuantity(h.quantity)}</td>
      <td class="num">${formatMoney(h.cost_basis_per_unit)}</td>
      <td class="num">${formatMoney(h.current_price)}</td>
      <td class="num">${formatMoney(h.market_value)}</td>
      <td class="num">
        <div class="pl-cell">
          <span class="delta-badge ${plClass}">${formatMoney(h.unrealized_pl)}</span>
          <span class="pl-pct muted">${formatSignedPercent(h.unrealized_pl_percent)}</span>
        </div>
      </td>
      <td class="muted">${updatedLabel}</td>
      <td class="actions-col">
        <div class="row-actions">
          <button type="button" class="icon-btn refresh-row-btn" title="Refresh live price" aria-label="Refresh live price for ${escapeHtml(h.symbol)}">⟳</button>
          <button type="button" class="icon-btn edit-row-btn" title="Edit holding" aria-label="Edit ${escapeHtml(h.name)}">✎</button>
          <button type="button" class="icon-btn danger delete-row-btn" title="Delete holding" aria-label="Delete ${escapeHtml(h.name)}">✕</button>
        </div>
        ${state.rowErrors[h.id] ? `<div class="row-error">${escapeHtml(state.rowErrors[h.id])}</div>` : ""}
      </td>
    `;

    const refreshBtn = tr.querySelector(".refresh-row-btn");
    if (refreshBtn) refreshBtn.addEventListener("click", () => handleRefreshOne(h.id, refreshBtn));
    tr.querySelector(".edit-row-btn").addEventListener("click", () => beginEdit(h));
    tr.querySelector(".delete-row-btn").addEventListener("click", () => handleDelete(h));

    el.holdingsTbody.appendChild(tr);
  });
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------------------------------------------------------------------
// Row actions: single refresh / delete
// ---------------------------------------------------------------------

async function handleRefreshOne(id, btnEl) {
  btnEl.disabled = true;
  btnEl.classList.add("is-loading");
  delete state.rowErrors[id];
  try {
    await refreshHoldingPrice(id);
    await loadAll();
  } catch (err) {
    state.rowErrors[id] = err.message || "Refresh failed.";
    renderHoldingsTable();
    setTimeout(() => {
      delete state.rowErrors[id];
      renderHoldingsTable();
    }, 8000);
  }
}

async function handleDelete(holding) {
  const label = holding.symbol || holding.name;
  const confirmed = window.confirm(`Delete "${label}"? This cannot be undone.`);
  if (!confirmed) return;
  try {
    await deleteHolding(holding.id);
    if (state.editingId === holding.id) resetForm();
    showToast({ title: `Deleted ${label}.` });
    await loadAll();
  } catch (err) {
    showToast({ title: `Could not delete ${label}.`, items: [err.message], isError: true });
  }
}

// ---------------------------------------------------------------------
// Bulk refresh
// ---------------------------------------------------------------------

async function handleRefreshAll() {
  const btn = el.refreshPricesBtn;
  btn.disabled = true;
  btn.classList.add("is-loading");
  const label = btn.querySelector(".btn-label");
  const originalLabel = label.textContent;
  label.textContent = "Refreshing…";

  try {
    const result = await refreshAllPrices();
    if (result.total_eligible === 0) {
      showToast({ title: "No holdings to refresh." });
    } else {
      const failed = result.results.filter((r) => r.status === "ERROR");
      if (failed.length === 0) {
        showToast({ title: `Refreshed ${result.succeeded} of ${result.total_eligible} holdings.` });
      } else {
        showToast({
          title: `Refreshed ${result.succeeded} of ${result.total_eligible}; ${failed.length} failed.`,
          items: failed.map((f) => `${f.symbol}: ${f.error.message}`),
          isError: true,
          timeout: 10000,
        });
      }
    }
    await loadAll();
  } catch (err) {
    if (err instanceof ApiError && err.isNetworkError) {
      handleLoadError(err);
    } else if (err instanceof ApiError && err.status === 502) {
      showToast({ title: "Yahoo Finance is unreachable right now.", items: [err.message], isError: true });
    } else {
      showToast({ title: "Price refresh failed.", items: [err.message], isError: true });
    }
  } finally {
    btn.disabled = false;
    btn.classList.remove("is-loading");
    label.textContent = originalLabel;
  }
}

// ---------------------------------------------------------------------
// Add / edit form
// ---------------------------------------------------------------------

function clearFormErrors() {
  el.formError.hidden = true;
  el.formError.textContent = "";
  document.querySelectorAll(".field-error").forEach((n) => (n.textContent = ""));
}

function applyValidationErrors(err) {
  if (err.details && err.details.length) {
    let anyMatched = false;
    err.details.forEach((d) => {
      const target = document.querySelector(`[data-error-for="${d.field}"]`);
      if (target) {
        target.textContent = d.message;
        anyMatched = true;
      }
    });
    if (!anyMatched) {
      el.formError.textContent = err.message;
      el.formError.hidden = false;
    }
  } else {
    el.formError.textContent = err.message;
    el.formError.hidden = false;
  }
}

function resetForm() {
  el.form.reset();
  state.editingId = null;
  el.fId.value = "";
  el.formTitle.textContent = "Add Holding";
  el.formSubmitBtn.textContent = "Add Holding";
  el.formCancelBtn.hidden = true;
  clearFormErrors();
  setSymbolHint("");
}

function beginEdit(holding) {
  state.editingId = holding.id;
  el.fId.value = holding.id;

  el.fSymbol.value = holding.symbol || "";
  el.fName.value = holding.name || "";
  el.fQuantity.value = holding.quantity;
  el.fCostBasis.value = holding.cost_basis_per_unit;
  el.fCurrentPrice.value = holding.current_price;
  el.fPurchaseDate.value = holding.purchase_date || "";

  el.formTitle.textContent = `Edit ${holding.symbol || holding.name}`;
  el.formSubmitBtn.textContent = "Save Changes";
  el.formCancelBtn.hidden = false;
  clearFormErrors();
  setSymbolHint("");
  el.form.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------------------------------------------------------------------
// Symbol -> company name / price auto-fill
// ---------------------------------------------------------------------

function setSymbolHint(text, isError = false) {
  el.fSymbolHint.textContent = text;
  el.fSymbolHint.classList.toggle("is-error", isError);
}

async function handleSymbolLookup() {
  const symbol = el.fSymbol.value.trim().toUpperCase();
  el.fSymbol.value = symbol;
  if (!symbol) {
    setSymbolHint("");
    return;
  }

  setSymbolHint("Looking up…");
  try {
    const result = await lookupTicker(symbol);
    // The user may have already changed the symbol while this was in
    // flight — only apply a result that still matches what's in the field.
    if (el.fSymbol.value.trim().toUpperCase() !== symbol) return;
    el.fName.value = result.name;
    if (el.fCurrentPrice.value === "") el.fCurrentPrice.value = result.price;
    setSymbolHint(`Found: ${result.name}`);
  } catch (err) {
    if (el.fSymbol.value.trim().toUpperCase() !== symbol) return;
    setSymbolHint("Couldn't find that ticker — you can still enter the company name yourself.", true);
  }
}

function buildPayload() {
  const payload = {
    symbol: el.fSymbol.value.trim().toUpperCase(),
    name: el.fName.value.trim(),
    quantity: el.fQuantity.value === "" ? undefined : Number(el.fQuantity.value),
  };
  if (el.fCostBasis.value !== "") payload.cost_basis_per_unit = Number(el.fCostBasis.value);
  if (el.fCurrentPrice.value !== "") payload.current_price = Number(el.fCurrentPrice.value);
  if (el.fPurchaseDate.value !== "") payload.purchase_date = el.fPurchaseDate.value;
  return payload;
}

async function handleFormSubmit(e) {
  e.preventDefault();
  clearFormErrors();
  const payload = buildPayload();
  el.formSubmitBtn.disabled = true;

  try {
    if (state.editingId) {
      await updateHolding(state.editingId, payload);
      showToast({ title: "Holding updated." });
    } else {
      const existing = state.holdings.find((h) => h.symbol === payload.symbol);
      await createHolding(payload);
      showToast({
        title: existing
          ? `Added ${formatQuantity(payload.quantity)} more shares to your existing ${payload.symbol} position.`
          : "Holding added.",
      });
    }
    resetForm();
    await loadAll();
  } catch (err) {
    if (err instanceof ApiError && err.isNetworkError) {
      handleLoadError(err);
    } else if (err instanceof ApiError && err.code === "VALIDATION_ERROR") {
      applyValidationErrors(err);
    } else if (err instanceof ApiError) {
      el.formError.textContent = err.message;
      el.formError.hidden = false;
    } else {
      el.formError.textContent = "Unexpected error saving this holding.";
      el.formError.hidden = false;
    }
  } finally {
    el.formSubmitBtn.disabled = false;
  }
}

// ---------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------

function wireEvents() {
  el.connectionRetryBtn.addEventListener("click", loadAll);
  el.refreshPricesBtn.addEventListener("click", handleRefreshAll);
  el.form.addEventListener("submit", handleFormSubmit);
  el.formCancelBtn.addEventListener("click", resetForm);
  el.fSymbol.addEventListener("blur", handleSymbolLookup);

  el.rangeFilter.addEventListener("click", async (e) => {
    const btn = e.target.closest(".range-btn");
    if (!btn) return;
    state.activeRange = btn.dataset.range;
    el.rangeFilter.querySelectorAll(".range-btn").forEach((b) => b.classList.toggle("is-active", b === btn));
    await loadPerformance();
    renderPerformanceChart();
  });

  wirePerformanceHover();

  window.addEventListener("resize", debounce(() => renderPerformanceChart(), 150));

  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      renderPerformanceChart();
    });
  }
}

function debounce(fn, wait) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}

// ---------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------

function init() {
  wireEvents();
  loadAll();
}

init();
