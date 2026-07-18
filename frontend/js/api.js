// api.js — thin fetch wrappers around the Portfolio Manager REST API.
// One function per backend endpoint. All functions return parsed JSON on
// success and throw an ApiError on any non-2xx response or network failure,
// so callers (app.js) can branch on `err.code` / `err.isNetworkError`.

// Use whatever host the page itself was loaded from (localhost, 127.0.0.1,
// a LAN IP, etc.) rather than hardcoding "localhost" — avoids a same-machine
// origin mismatch if the frontend is ever served from a different host name.
const apiHost = window.location.hostname || "localhost";
export const API_BASE = `http://${apiHost}:8000/api`;

/**
 * Error thrown by every wrapper below. Mirrors the API's shared error
 * envelope: { error: { code, message, details? } }.
 */
export class ApiError extends Error {
  constructor(message, { code = "UNKNOWN_ERROR", status = 0, details = null, isNetworkError = false } = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
    this.isNetworkError = isNetworkError;
  }
}

/**
 * Core fetch wrapper.
 * - Parses JSON responses (including error envelopes).
 * - Treats 204 No Content as a successful `null` result.
 * - Converts network-level failures (backend not running, DNS, CORS-blocked
 *   preflight, etc.) into an ApiError with isNetworkError: true so the UI can
 *   show a distinct "can't reach backend" banner instead of a generic error.
 */
async function request(path, { method = "GET", body } = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (networkErr) {
    throw new ApiError(
      "Could not reach the Portfolio Manager backend. Is the API server running?",
      { code: "NETWORK_ERROR", isNetworkError: true }
    );
  }

  if (response.status === 204) {
    return null;
  }

  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (parseErr) {
      if (!response.ok) {
        throw new ApiError(`Unexpected response from server (status ${response.status}).`, {
          status: response.status,
        });
      }
      throw new ApiError("Server returned a response that could not be parsed as JSON.", {
        status: response.status,
      });
    }
  }

  if (!response.ok) {
    const err = payload && payload.error ? payload.error : {};
    throw new ApiError(err.message || `Request failed with status ${response.status}.`, {
      code: err.code || "UNKNOWN_ERROR",
      status: response.status,
      details: err.details || null,
    });
  }

  return payload;
}

function qs(params) {
  const usp = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") usp.set(k, v);
  });
  const s = usp.toString();
  return s ? `?${s}` : "";
}

// ---- /api/holdings ---------------------------------------------------

export function getHoldings() {
  return request("/holdings");
}

export function getHolding(id) {
  return request(`/holdings/${id}`);
}

export function createHolding(payload) {
  return request("/holdings", { method: "POST", body: payload });
}

export function lookupTicker(symbol) {
  return request(`/holdings/lookup/${encodeURIComponent(symbol)}`);
}

export function updateHolding(id, payload) {
  return request(`/holdings/${id}`, { method: "PATCH", body: payload });
}

export function deleteHolding(id) {
  return request(`/holdings/${id}`, { method: "DELETE" });
}

export function refreshHoldingPrice(id) {
  return request(`/holdings/${id}/refresh-price`, { method: "POST", body: {} });
}

export function refreshAllPrices() {
  return request("/holdings/refresh-prices", { method: "POST", body: {} });
}

// ---- /api/portfolio ----------------------------------------------------

export function getPortfolioSummary() {
  return request("/portfolio/summary");
}

export function getPortfolioPerformance({ from, to, limit } = {}) {
  return request(`/portfolio/performance${qs({ from, to, limit })}`);
}
